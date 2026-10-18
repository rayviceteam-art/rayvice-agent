"""Outreach DB helpers (tables live in social.db via social.db DDL)."""
import json
import uuid
from datetime import datetime, timezone

from social import db


def utcnow():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_id(prefix):
    return prefix + uuid.uuid4().hex[:10]


def is_suppressed(email):
    if not email:
        return True
    c = db.connect()
    row = c.execute("SELECT email FROM outreach_suppression WHERE lower(email)=?", (email.lower(),)).fetchone()
    c.close()
    return bool(row)


def add_suppression(email, reason="manual"):
    if not email:
        return
    c = db.connect()
    c.execute("INSERT OR REPLACE INTO outreach_suppression VALUES(?,?,?)", (email.lower(), reason, utcnow()))
    c.commit()
    c.close()


def suppressed_set():
    c = db.connect()
    rows = c.execute("SELECT lower(email) FROM outreach_suppression").fetchall()
    c.close()
    return {r[0] for r in rows}


def lead_by_email(email):
    c = db.connect()
    row = c.execute("SELECT * FROM outreach_leads WHERE lower(email)=?", (email or "",)).fetchone()
    c.close()
    return row


def existing_domains():
    c = db.connect()
    rows = c.execute("SELECT lower(domain) FROM outreach_leads").fetchall()
    c.close()
    return {r[0] for r in rows}


def upsert_lead(lead):
    """lead: dict(name, domain, email, email_source, suburb, state, niche, source). Returns id."""
    lid = lead.get("id") or new_id("l_")
    c = db.connect()
    c.execute(
        "INSERT OR IGNORE INTO outreach_leads VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        (lid, utcnow(), lead.get("name", ""), lead.get("domain", ""), (lead.get("email") or "").lower(),
         lead.get("email_source", ""), lead.get("suburb", ""), lead.get("state", ""), lead.get("niche", ""),
         lead.get("source", ""), "NEW", json.dumps(lead.get("notes") or {})[:2000]))
    c.commit()
    c.close()
    return lid


def set_lead_status(lead_id, status, notes=None):
    c = db.connect()
    if notes is not None:
        c.execute("UPDATE outreach_leads SET status=?, notes=? WHERE id=?", (status, json.dumps(notes)[:2000], lead_id))
    else:
        c.execute("UPDATE outreach_leads SET status=? WHERE id=?", (status, lead_id))
    c.commit()
    c.close()


def log_message(lead_id, to_email, subject, body, status="QUEUED", error="", followup=0, parent_id=""):
    mid = new_id("om_")
    email = (to_email or "").lower()
    key = f"outreach:{email}:f1" if followup else f"outreach:{email}"
    c = db.connect()
    try:
        c.execute(
            "INSERT INTO outreach_messages"
            "(id,ts,lead_id,to_email,subject,body,status,sent_at,error,idempotency_key,followup,parent_id) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (mid, utcnow(), lead_id, email, subject, body, status, "", error[:500], key, 1 if followup else 0, parent_id))
        c.commit()
    except Exception:
        c.close()
        return ""
    c.close()
    return mid


def followup_exists(email):
    c = db.connect()
    row = c.execute("SELECT id FROM outreach_messages WHERE idempotency_key=?",
                    (f"outreach:{(email or '').lower()}:f1",)).fetchone()
    c.close()
    return bool(row)


def followup_candidates(days, limit=10):
    """SENT emails, koi reply/unsub/bounce nahi, follow-up window aa gaya, aur abhi tak follow-up nahi."""
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    c = db.connect()
    rows = c.execute(
        "SELECT m.id AS message_id, m.to_email, m.subject AS orig_subject, m.body AS orig_body, m.sent_at, "
        "l.id AS lead_id, l.name, l.domain, l.suburb, l.state, l.notes "
        "FROM outreach_messages m JOIN outreach_leads l ON l.id=m.lead_id "
        "WHERE m.status='SENT' AND m.followup=0 AND m.sent_at<>'' AND m.sent_at<=? "
        "AND l.status='SENT' "
        "AND NOT EXISTS (SELECT 1 FROM outreach_messages f WHERE f.idempotency_key='outreach:'||m.to_email||':f1') "
        "AND NOT EXISTS (SELECT 1 FROM outreach_suppression s WHERE lower(s.email)=m.to_email) "
        "ORDER BY m.sent_at LIMIT ?", (cutoff, limit)).fetchall()
    c.close()
    return rows


def mark_message(mid, status, error=""):
    c = db.connect()
    sent_at = utcnow() if status == "SENT" else ""
    c.execute("UPDATE outreach_messages SET status=?, sent_at=?, error=? WHERE id=?",
              (status, sent_at, error[:500], mid))
    c.commit()
    c.close()


def message_exists(to_email):
    c = db.connect()
    row = c.execute("SELECT id FROM outreach_messages WHERE idempotency_key=?",
                    (f"outreach:{(to_email or '').lower()}",)).fetchone()
    c.close()
    return bool(row)


def queued_messages(limit=50):
    c = db.connect()
    rows = c.execute("SELECT * FROM outreach_messages WHERE status='QUEUED' ORDER BY ts LIMIT ?", (limit,)).fetchall()
    c.close()
    return rows


def record_reply(lead_email, subject, snippet, kind):
    c = db.connect()
    c.execute("INSERT INTO outreach_replies(ts,lead_email,subject,snippet,kind) VALUES(?,?,?,?,?)",
              (utcnow(), (lead_email or "").lower(), subject[:200], snippet[:1000], kind))
    c.commit()
    c.close()


def log_run(run_id, date, generated, sent, dry_run, detail=""):
    c = db.connect()
    c.execute("INSERT OR REPLACE INTO outreach_runs VALUES(?,?,?,?,?,?)",
              (run_id, date, utcnow(), generated, sent, 1 if dry_run else 0, detail[:2000]))
    c.commit()
    c.close()


def sent_today(date):
    c = db.connect()
    row = c.execute("SELECT COUNT(*) FROM outreach_messages WHERE status='SENT' AND sent_at LIKE ?",
                    (date + "%",)).fetchone()
    c.close()
    return row[0] if row else 0


def stats():
    c = db.connect()
    out = {}
    for label, sql in {
        "leads": "SELECT COUNT(*) FROM outreach_leads",
        "with_email": "SELECT COUNT(*) FROM outreach_leads WHERE email<>''",
        "queued": "SELECT COUNT(*) FROM outreach_messages WHERE status='QUEUED'",
        "sent": "SELECT COUNT(*) FROM outreach_messages WHERE status='SENT'",
        "failed": "SELECT COUNT(*) FROM outreach_messages WHERE status='FAILED'",
        "replied": "SELECT COUNT(*) FROM outreach_replies WHERE kind='reply'",
        "unsub": "SELECT COUNT(*) FROM outreach_replies WHERE kind='unsub'",
        "suppressed": "SELECT COUNT(*) FROM outreach_suppression",
    }.items():
        out[label] = c.execute(sql).fetchone()[0]
    c.close()
    return out
