"""Lead DB + transparent scoring. SQLite primary (budget 0). Sheet optional mirror later."""
import json
import sqlite3
import uuid
import os
from datetime import datetime

import config

STATUSES = ["NEW", "RESEARCHED", "QUALIFIED", "DRAFT_READY", "APPROVAL_REQUIRED",
            "CONTACTED", "RESPONDED", "CONVERSATION", "TRIAL_INTEREST", "TRIAL_STARTED",
            "PAID", "NOT_INTERESTED", "DO_NOT_CONTACT", "INVALID", "CONVERTED"]

def _db():
    os.makedirs(os.path.dirname(config.AGENT_DB_PATH) or ".", exist_ok=True)
    c = sqlite3.connect(config.AGENT_DB_PATH)
    c.execute("""CREATE TABLE IF NOT EXISTS leads(
      lead_id TEXT PRIMARY KEY, name TEXT, business_name TEXT, role TEXT,
      public_profile_url TEXT, business_url TEXT, location TEXT, business_type TEXT,
      source TEXT, relevance_reason TEXT, qualification_status TEXT, lead_score INTEGER,
      score_reasons TEXT, contact_status TEXT, last_contacted TEXT, last_response TEXT,
      next_followup TEXT, notes TEXT, tags TEXT, created_at TEXT, updated_at TEXT)""")
    return c

def score_lead(info):
    """Transparent scoring. No sensitive inference (no disability/medical/politics/etc)."""
    score, reasons = 0, []
    loc = (info.get("location") or "").lower()
    bt = (info.get("business_type") or "").lower()
    blob = json.dumps(info).lower()
    if "australia" in loc or " aus" in loc or "sydney" in blob or "melbourne" in blob:
        score += 25
        reasons.append("Australian location signal")
    if any(k in bt or k in blob for k in ("sole trader", "sole-trader", "independent", "support worker", "disability support")):
        score += 25
        reasons.append("Independent/sole-trader NDIS fit")
    if "ndis" in blob:
        score += 20
        reasons.append("NDIS related")
    if any(k in blob for k in ("invoice", "billing", "spreadsheet", "admin", "paperwork", "payment problem")):
        score += 15
        reasons.append("Billing/admin pain signal")
    if info.get("source") in ("inbound", "referral", "website"):
        score += 10
        reasons.append("Warm source")
    # negatives
    if any(k in blob for k in ("enterprise", "hospital", "agency chain", "spam", "fake")):
        score -= 30
        reasons.append("Negative: enterprise/spam signal")
    if info.get("location") and "australia" not in loc:
        score -= 20
        reasons.append("Negative: outside Australia")
    return max(0, min(100, score)), reasons

def upsert(info):
    now = datetime.utcnow().isoformat() + "Z"
    lid = info.get("lead_id") or ("l_" + uuid.uuid4().hex[:8])
    score, reasons = score_lead(info)
    c = _db()
    r = c.execute("SELECT lead_id FROM leads WHERE lead_id=?", (lid,)).fetchone()
    status = info.get("qualification_status", "NEW")
    if status not in STATUSES:
        status = "NEW"
    vals = (lid, info.get("name", ""), info.get("business_name", ""), info.get("role", ""),
            info.get("public_profile_url", ""), info.get("business_url", ""),
            info.get("location", ""), info.get("business_type", ""),
            info.get("source", ""), info.get("relevance_reason", ""), status, score,
            json.dumps(reasons), info.get("contact_status", ""), info.get("last_contacted", ""),
            info.get("last_response", ""), info.get("next_followup", ""),
            info.get("notes", ""), ",".join(info.get("tags", [])), now, now)
    if r:
        c.execute("""UPDATE leads SET name=?,business_name=?,role=?,public_profile_url=?,business_url=?,
          location=?,business_type=?,source=?,relevance_reason=?,qualification_status=?,lead_score=?,
          score_reasons=?,contact_status=?,last_contacted=?,last_response=?,next_followup=?,notes=?,tags=?,updated_at=?
          WHERE lead_id=?""", (vals[1], vals[2], vals[3], vals[4], vals[5], vals[6], vals[7], vals[8], vals[9],
                                vals[10], vals[11], vals[12], vals[13], vals[14], vals[15], vals[16], vals[17], vals[18], vals[20], lid))
    else:
        c.execute("INSERT INTO leads VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", vals)
    c.commit()
    c.close()
    return lid, score, reasons

def set_status(lid, status):
    assert status in STATUSES
    c = _db()
    c.execute("UPDATE leads SET qualification_status=?, updated_at=? WHERE lead_id=?",
              (status, datetime.utcnow().isoformat() + "Z", lid))
    c.commit()
    c.close()

def list_by_status(status, limit=50):
    c = _db()
    c.row_factory = sqlite3.Row
    rows = c.execute("SELECT * FROM leads WHERE qualification_status=? ORDER BY lead_score DESC LIMIT ?", (status, limit)).fetchall()
    c.close()
    return [dict(r) for r in rows]

def followups_due():
    c = _db()
    c.row_factory = sqlite3.Row
    now = datetime.utcnow().isoformat() + "Z"
    rows = c.execute("SELECT * FROM leads WHERE next_followup<>'' AND next_followup<=? AND qualification_status NOT IN ('DO_NOT_CONTACT','CONVERTED','NOT_INTERESTED')", (now,)).fetchall()
    c.close()
    return [dict(r) for r in rows]
