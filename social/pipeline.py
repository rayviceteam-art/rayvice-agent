"""Daily orchestration: plan -> generate -> media -> enqueue -> publish -> report.

Hourly GH Actions tick isse call karega. Publish window Sydney-local gate hota hai,
retries har tick par chalte hain (rate-limit friendly).
"""
import uuid

import config
from logs_sys import audit
from social import calendar, db, generator, media, publish_queue
from social.platforms import capabilities, get_adapter

PLATFORMS_WITH_MEDIA = {"instagram"}


def _sync_accounts():
    c = db.connect()
    for cap in capabilities():
        c.execute("""INSERT INTO social_accounts(platform,enabled,account_type,account_ref,token_env,scopes,status,last_verified,notes)
                     VALUES(?,?,?,?,?,?,?,?,?)
                     ON CONFLICT(platform) DO UPDATE SET enabled=excluded.enabled, account_type=excluded.account_type,
                     account_ref=excluded.account_ref, scopes=excluded.scopes, status=excluded.status, notes=excluded.notes""",
                  (cap["platform"], 1 if cap.get("configured") else 0, cap.get("account_type", ""),
                   {"instagram": config.INSTAGRAM_ACCOUNT_ID, "facebook": config.META_PAGE_ID,
                    "linkedin": config.LINKEDIN_AUTHOR_URN, "reddit": ",".join(config.SOCIAL_REDDIT_SUBS)}.get(cap["platform"], ""),
                   {"instagram": "META_ACCESS_TOKEN", "facebook": "META_ACCESS_TOKEN",
                    "linkedin": "LINKEDIN_ACCESS_TOKEN", "reddit": "REDDIT_REFRESH_TOKEN"}.get(cap["platform"], ""),
                   ",".join(cap.get("scopes", [])),
                   "READY" if cap.get("configured") else str(cap.get("blocker", ""))[:200],
                   cap.get("last_verified", ""), cap.get("test_result", "")))
    c.commit()
    c.close()


def _store_idea(plan):
    iid = "i_" + uuid.uuid4().hex[:10]
    c = db.connect()
    existing = c.execute("SELECT id FROM social_ideas WHERE topic=? AND substr(ts,1,10)=substr(?,1,10)",
                         (plan["topic"], db.utcnow())).fetchone()
    if existing:
        c.close()
        return existing["id"], False
    c.execute("INSERT INTO social_ideas VALUES(?,?,?,?,?,?,?,?)",
              (iid, db.utcnow(), plan["theme"], plan["topic"], plan["category"],
               "calendar", "ACTIVE", plan["date"]))
    c.commit()
    c.close()
    return iid, True


def daily_tick(dry_run=None, force_window=False, notify=True):
    """Ek tick: generate (window me) + due retries/publishes hamesha."""
    db.ensure_schema()
    if dry_run is None:
        dry_run = config.SOCIAL_DRYRUN
    run_id = "r_" + uuid.uuid4().hex[:10]
    token = publish_queue.acquire_lock("social.daily", ttl_seconds=1500)
    if not token:
        return {"ok": False, "error": "another run is active (lock held)", "run_id": run_id}
    db.record_run(run_id, "social.daily", "RUNNING",
                  f"dry_run={dry_run} force={force_window}")
    summary = {"run_id": run_id, "dry_run": dry_run, "generated": [], "media": [],
               "enqueue": [], "publish": {}, "window": ""}
    try:
        _sync_accounts()
        window = calendar.in_publish_window()
        summary["window"] = window or ""
        if window or force_window:
            plan = calendar.plan_for()
            idea_id, _ = _store_idea(plan)
            plan["idea_id"] = idea_id
            platforms = [p for p in config.SOCIAL_PLATFORMS if p != "x"]
            if "reddit" in platforms and not (config.REDDIT_CLIENT_ID and config.SOCIAL_REDDIT_SUBS):
                platforms.remove("reddit")
            for idx, platform in enumerate(platforms):
                gen = generator.generate_draft(platform, plan)
                if gen.get("ok"):
                    draft_id = gen["draft_id"]
                    summary["generated"].append({platform: draft_id})
                elif gen.get("duplicate") and gen.get("draft_id"):
                    # Orphan recovery: draft bani thi lekin enqueue se pehle run mar gaya
                    draft_id = gen["draft_id"]
                    existing = publish_queue.queued_id(platform, draft_id)
                    if existing:
                        summary["generated"].append({platform: f"{draft_id} (already queued)"})
                        continue
                    summary["generated"].append({platform: draft_id, "recovered": True})
                else:
                    summary["generated"].append({platform: gen.get("error", "skipped")})
                    continue
                if platform in PLATFORMS_WITH_MEDIA and not gen.get("media_id"):
                    img = media.generate_image(gen.get("draft", {}).get("image_prompt", ""),
                                               title=(gen.get("draft", {}).get("hook", "") or plan["topic"])[:90])
                    if img.get("ok"):
                        publish_queue.attach_media(draft_id, img["media_id"], img.get("url", ""))
                        summary["media"].append({platform: img["media_id"], "provider": img["provider"]})
                    else:
                        summary["media"].append({platform: f"failed: {img.get('error')}"})
                sched = db.utcnow()
                if idx > 0:
                    from datetime import datetime, timedelta, timezone
                    sched = (datetime.now(timezone.utc) + timedelta(seconds=idx * 1200)
                             ).strftime("%Y-%m-%dT%H:%M:%SZ")
                qid, created = publish_queue.enqueue(draft_id, platform, scheduled_utc=sched)
                summary["enqueue"].append({platform: qid, "created": created})
        summary["publish"] = publish_queue.process_due(dry_run=dry_run, notify=notify)
        db.record_run(run_id, "social.daily", "COMPLETE", str(summary)[:1800])
        audit("social", run_id, "daily_tick", "", str(summary)[:400], "COMPLETE", "", "", "")
        if notify:
            _notify_summary(summary)
        return {"ok": True, **summary}
    except Exception as e:
        db.log_error(run_id, "", "pipeline", str(e)[:500], retryable=True)
        db.record_run(run_id, "social.daily", "FAILED", str(e)[:800])
        if notify:
            try:
                import telegram_bot
                telegram_bot.send(f"⚠️ Social pipeline error: {str(e)[:300]}")
            except Exception:
                pass
        return {"ok": False, "error": str(e)[:500], "run_id": run_id}
    finally:
        publish_queue.release_lock("social.daily", token)


def _notify_summary(summary):
    try:
        import telegram_bot
        gen = summary.get("generated") or []
        pub = summary.get("publish") or {}
        if not gen and not any(pub.get(k) for k in ("published", "dry_run", "failed_retry", "dead")):
            return  # quiet tick — spam nahi
        mode_tag = "🧪 DRY-RUN" if summary.get("dry_run") else "🚀 LIVE"
        lines = [f"{mode_tag} Social tick [{summary['run_id']}]"]
        if summary.get("window"):
            lines.append(f"Window: {summary['window']} Sydney")
        for g in gen:
            for p, v in g.items():
                lines.append(f"• {p}: {v}")
        lines.append(f"Queue: published {pub.get('published', 0)} | dry {pub.get('dry_run', 0)} | "
                     f"retry {pub.get('failed_retry', 0)} | dead {pub.get('dead', 0)}")
        telegram_bot.send("\n".join(lines)[:3900])
    except Exception:
        pass


def status_text():
    c = db.connect()
    last = c.execute("SELECT * FROM social_runs ORDER BY started DESC LIMIT 1").fetchone()
    q = c.execute("SELECT status, COUNT(*) n FROM social_queue GROUP BY status").fetchall()
    lastok = c.execute("SELECT ended FROM social_runs WHERE status='COMPLETE' ORDER BY ended DESC LIMIT 1").fetchone()
    c.close()
    qs = {r["status"]: r["n"] for r in q}
    lines = ["📣 Social automation:"]
    lines.append(f"Mode: {'DRY-RUN 🧪' if config.SOCIAL_DRYRUN else 'LIVE 🚀'} | TZ: {config.SOCIAL_TZ}")
    lines.append(f"Last run: {last['status'] if last else '-'} at {last['started'] if last else '-'}")
    lines.append(f"Last success: {lastok['ended'] if lastok else 'never'}")
    lines.append("Queue: " + (", ".join(f"{k}={v}" for k, v in qs.items()) if qs else "khali"))
    for cap in capabilities():
        state = "READY ✅" if cap.get("configured") else (cap.get("blocker") or "NOT SET")[:60]
        lines.append(f"• {cap['platform']}: {state}")
    return "\n".join(lines)


def errors_text(limit=10):
    c = db.connect()
    rows = c.execute("SELECT ts, platform, category, message FROM social_errors ORDER BY id DESC LIMIT ?",
                     (limit,)).fetchall()
    dead = c.execute("SELECT id, platform, last_error FROM social_queue WHERE status IN ('DEAD_LETTER','FAILED_PERMANENT') ORDER BY updated DESC LIMIT 5").fetchall()
    c.close()
    out = []
    if dead:
        out.append("Dead/failed queue items:")
        out += [f"• {r['id']} [{r['platform']}] {str(r['last_error'])[:120]}" for r in dead]
    if rows:
        out.append("Recent errors:")
        out += [f"• {r['ts']} [{r['platform']}] {str(r['message'])[:140]}" for r in rows]
    return "\n".join(out) if out else "Koi social error nahi hai bhai ✅"


def retry_dead(limit=5):
    """Dead-letter items ko manually ek aur chance (owner command)."""
    c = db.connect()
    rows = c.execute("SELECT id FROM social_queue WHERE status IN ('DEAD_LETTER','FAILED_PERMANENT') LIMIT ?",
                     (limit,)).fetchall()
    for r in rows:
        c.execute("UPDATE social_queue SET status='QUEUED', attempts=0, next_attempt_utc=?, dead_letter_reason='' WHERE id=?",
                  (db.utcnow(), r["id"]))
    c.commit()
    c.close()
    return len(rows)
