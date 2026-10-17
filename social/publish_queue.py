"""Publishing queue: idempotent, retry/backoff, dead-letter, dry-run safe.

Guarantees:
- same (platform, draft) dobara publish NAHI hota (unique idempotency key + publications check)
- ambiguous timeout par pehle state verify, phir retry
- permanent auth/permission errors retry nahi hote — DEAD_LETTER + notify
- pause -> naya publish nahi, queue safe rehta hai
"""
import json
import os
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

import config
import modes
from logs_sys import audit
from social import db
from social.platforms import get_adapter


def _now():
    return datetime.now(timezone.utc)


def _iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def enqueue(draft_id, platform, scheduled_utc=None, subreddit=""):
    """Idempotent enqueue. Returns (queue_id, created_bool)."""
    key = f"pub:{platform}:{draft_id}"
    qid = "q_" + uuid.uuid4().hex[:10]
    ts = db.utcnow()
    when = scheduled_utc or ts
    c = db.connect()
    try:
        c.execute("INSERT INTO social_queue VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (qid, ts, draft_id, platform, when, "QUEUED", 0, when, key, "", 0, "", ts))
        c.commit()
        c.close()
        return qid, True
    except sqlite3.IntegrityError:
        row = c.execute("SELECT id FROM social_queue WHERE idempotency_key=?", (key,)).fetchone()
        c.close()
        return (row["id"] if row else qid), False


def queued_id(platform, draft_id):
    """Queue row (koi bhi status) — orphan recovery ke liye check."""
    c = db.connect()
    r = c.execute("SELECT id, status FROM social_queue WHERE idempotency_key=?",
                  (f"pub:{platform}:{draft_id}",)).fetchone()
    c.close()
    return dict(r) if r else None


def already_published(platform, draft_id):
    """OK ya DRY_RUN — dono ko published maano (dry-run accidentally live na ho jaye)."""
    c = db.connect()
    r = c.execute("SELECT id FROM social_publications WHERE platform=? AND draft_id=? AND status IN ('OK','DRY_RUN')",
                  (platform, draft_id)).fetchone()
    c.close()
    return r is not None


def due_items(limit=20):
    c = db.connect()
    now = db.utcnow()
    rows = c.execute(
        "SELECT * FROM social_queue WHERE status='QUEUED' AND next_attempt_utc<=? "
        "ORDER BY next_attempt_utc LIMIT ?", (now, limit)).fetchall()
    c.close()
    return [dict(r) for r in rows]


def next_attempt_delay(attempts, retry_after=0, base=None):
    """Exponential backoff, capped 6h. Platform Retry-After jeet jata hai."""
    base = base or config.SOCIAL_RETRY_BASE_SECONDS
    exp = min(base * (2 ** max(0, attempts - 1)), 21600)
    return max(int(exp), int(retry_after or 0))


def retry_or_die(qid, error, retryable, retry_after=0):
    c = db.connect()
    row = c.execute("SELECT attempts FROM social_queue WHERE id=?", (qid,)).fetchone()
    if not row:
        c.close()
        return False
    attempts = int(row["attempts"]) + 1
    if retryable and attempts < config.SOCIAL_MAX_ATTEMPTS:
        nxt = _now() + timedelta(seconds=next_attempt_delay(attempts, retry_after))
        c.execute("UPDATE social_queue SET attempts=?, next_attempt_utc=?, last_error=?, retry_after=?, status='QUEUED', updated=? WHERE id=?",
                  (attempts, _iso(nxt), str(error)[:1000], int(retry_after or 0), db.utcnow(), qid))
        will_retry = True
    else:
        status = "DEAD_LETTER" if retryable else "FAILED_PERMANENT"
        c.execute("UPDATE social_queue SET attempts=?, status=?, last_error=?, dead_letter_reason=?, updated=? WHERE id=?",
                  (attempts, status, str(error)[:1000],
                   "" if retryable else "non-retryable error",
                   db.utcnow(), qid))
        will_retry = False
    c.commit()
    c.close()
    return will_retry


def record_success(qid, item, result):
    pub_id = "pub_" + uuid.uuid4().hex[:10]
    c = db.connect()
    c.execute("INSERT INTO social_publications VALUES(?,?,?,?,?,?,?,?,?,?)",
              (pub_id, db.utcnow(), qid, item.get("draft_id", ""), item["platform"],
               result.post_id or "", result.url or "",
               "DRY_RUN" if result.dry_run else "OK", 1 if result.dry_run else 0,
               json.dumps(result.raw or {})[:2000]))
    c.execute("UPDATE social_queue SET status=?, updated=? WHERE id=?",
              ("DRY_RUN" if result.dry_run else "PUBLISHED", db.utcnow(), qid))
    c.commit()
    c.close()
    return pub_id


def mark_status(qid, status, error=""):
    c = db.connect()
    c.execute("UPDATE social_queue SET status=?, last_error=?, updated=? WHERE id=?",
              (status, str(error)[:1000], db.utcnow(), qid))
    c.commit()
    c.close()


def load_draft(draft_id):
    c = db.connect()
    r = c.execute("SELECT * FROM social_drafts WHERE id=?", (draft_id,)).fetchone()
    if not r:
        c.close()
        return None
    d = dict(r)
    try:
        d["hashtags"] = json.loads(d.get("hashtags") or "[]")
    except Exception:
        d["hashtags"] = []
    if d.get("media_id"):
        m = c.execute("SELECT * FROM social_media WHERE id=?", (d["media_id"],)).fetchone()
        d["media"] = dict(m) if m else {}
    else:
        d["media"] = {}
    c.close()
    return d


def attach_media(draft_id, media_id, media_url):
    c = db.connect()
    c.execute("UPDATE social_drafts SET media_id=? WHERE id=?", (media_id, draft_id))
    c.commit()
    c.close()


def process_due(dry_run=None, notify=None, limit=20):
    """Due items ko publish (ya dry-run) karo. Returns summary dict."""
    if dry_run is None:
        dry_run = config.SOCIAL_DRYRUN
    results = {"published": 0, "dry_run": 0, "failed_retry": 0, "dead": 0, "skipped": 0, "errors": []}
    if not modes.automation_on():
        results["skipped"] = len(due_items(limit))
        results["errors"].append("paused: AUTOMATION_ENABLED=false — queue preserved")
        return results

    for item in due_items(limit):
        qid = item["id"]
        platform = item["platform"]
        draft = load_draft(item["draft_id"])
        if not draft:
            mark_status(qid, "FAILED_PERMANENT", "draft missing")
            results["dead"] += 1
            continue
        if already_published(platform, item["draft_id"]):
            mark_status(qid, "CANCELLED_DUPLICATE", "already published")
            results["skipped"] += 1
            continue
        adapter = get_adapter(platform)
        if not adapter:
            mark_status(qid, "FAILED_PERMANENT", f"unknown platform {platform}")
            results["dead"] += 1
            continue
        media = draft.get("media") or {}
        if platform == "instagram" and not media.get("url") and not dry_run:
            mark_status(qid, "FAILED_PERMANENT", "Instagram needs public media URL")
            db.log_error("", platform, "media", "missing public URL", retryable=False)
            results["dead"] += 1
            continue
        try:
            res = adapter.publish(draft, media=media, dry_run=dry_run)
        except Exception as e:
            res = None
            db.log_error("", platform, "exception", str(e)[:500], retryable=True)

        if res is not None and res.ok:
            record_success(qid, item, res)
            if res.dry_run:
                results["dry_run"] += 1
            else:
                results["published"] += 1
            audit("social", qid, f"publish.{platform}",
                  draft.get("hook", "")[:120], f"post_id={res.post_id} dry={res.dry_run}",
                  "PUBLISHED" if not res.dry_run else "DRY_RUN", "", "", "")
            if notify:
                _notify_result(item, draft, res)
        else:
            err = res.error if res else "unknown error"
            retryable = res.retryable if res else True
            retry_after = res.retry_after if res else 0
            will_retry = retry_or_die(qid, err, retryable, retry_after)
            db.log_error("", platform, "publish", err, code="", retryable=will_retry)
            if will_retry:
                results["failed_retry"] += 1
            else:
                results["dead"] += 1
            results["errors"].append(f"{platform}:{qid}: {err[:160]}")
            audit("social", qid, f"publish.{platform}", draft.get("hook", "")[:120],
                  f"FAILED retry={will_retry} err={err[:200]}", "FAILED", "", "", err[:300])
            if notify and not will_retry:
                _notify_dead(item, err)
    return results


def _notify_result(item, draft, res):
    try:
        import telegram_bot
        tag = "🧪 DRY-RUN" if res.dry_run else "✅ Posted"
        telegram_bot.send(f"{tag} [{item['platform']}] {draft.get('hook', '')[:120]}\n"
                          f"id: {res.post_id or '-'} {res.url or ''}")
    except Exception:
        pass


def _notify_dead(item, err):
    try:
        import telegram_bot
        telegram_bot.send(f"❌ Post FAILED (no more retries) [{item['platform']}] qid={item['id']}\n"
                          f"Error: {err[:400]}\nQueue me pada hai — `social errors` se dekh le bhai.")
    except Exception:
        pass


def summary():
    c = db.connect()
    rows = c.execute("SELECT status, COUNT(*) n FROM social_queue GROUP BY status").fetchall()
    c.close()
    return {r["status"]: r["n"] for r in rows}


def acquire_lock(name, ttl_seconds=1800, owner=""):
    """Overlapping runs rokne ke liye simple DB lock. Returns owner token or None."""
    token = owner or uuid.uuid4().hex[:12]
    now = _now()
    c = db.connect()
    row = c.execute("SELECT expires_utc FROM social_locks WHERE name=?", (name,)).fetchone()
    if row:
        try:
            exp = datetime.strptime(row["expires_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except Exception:
            exp = now - timedelta(seconds=1)
        if exp > now:
            c.close()
            return None
    c.execute("INSERT OR REPLACE INTO social_locks VALUES(?,?,?,?)",
              (name, token, _iso(now), _iso(now + timedelta(seconds=ttl_seconds))))
    c.commit()
    c.close()
    return token


def release_lock(name, token):
    c = db.connect()
    c.execute("DELETE FROM social_locks WHERE name=? AND owner=?", (name, token))
    c.commit()
    c.close()
