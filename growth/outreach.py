"""Outreach: genuine, no spam. Default = draft + approval queue. No auto-send."""
import model_router
import approvals
from growth import leads

RATE_NOTE = "Conservative: max 10-15 manual outreach/day across channels. No mass DM."

def draft_outreach(lead):
    prompt = [
        {"role": "system", "content": "Write genuine short business outreach. No fake personalization, no human impersonation, no spam. Australian English."},
        {"role": "user", "content": f"Lead: {lead}. Write 3-line personalized opener + 1 value line about Rayvice billing help + soft CTA. If pain unknown, ask one question."},
    ]
    res = model_router.run_task("draft", prompt)
    text = res.text if res.ok else f"Hi {lead.get('name','there')}, noticed your NDIS support work in {lead.get('location','Australia')}. Many sole traders mention invoice admin pain — open to a 2-min look at Rayvice trial? (Example draft, AI offline)"
    return text

def queue_outreach(lead_id):
    # duplicate guard: same lead ka pending approval hai to dobara nahi
    import sqlite3
    import config as _cfg
    c = sqlite3.connect(_cfg.AGENT_DB_PATH)
    r = c.execute("SELECT id FROM approvals WHERE status='PENDING' AND action='outreach.send-manual' AND target LIKE ?",
                  (f"%{lead_id}%",)).fetchone()
    c.close()
    if r:
        return r[0], f"Is lead ke liye approval pehle se pending hai bhai ({r[0]}), `queue` me dekh lo. Duplicate nahi banaya."
    # fetch lead
    import sqlite3, config
    c = sqlite3.connect(config.AGENT_DB_PATH)
    c.row_factory = sqlite3.Row
    r = c.execute("SELECT * FROM leads WHERE lead_id=?", (lead_id,)).fetchone()
    c.close()
    if not r:
        return None, "Lead not found"
    lead = dict(r)
    if lead["qualification_status"] == "DO_NOT_CONTACT":
        return None, "Blocked: DO_NOT_CONTACT"
    draft = draft_outreach(lead)
    aid, msg = approvals.request_approval(
        action="outreach.send-manual",
        target=f"{lead.get('name')} <{lead.get('public_profile_url')}>",
        why=f"Score {lead.get('lead_score')}: {lead.get('score_reasons')}. {RATE_NOTE}",
        expected=f"Draft:\n{draft}\n\nOwner sends MANUALLY. No auto-send.",
        risk="MEDIUM",
        payload=draft)
    leads.set_status(lead_id, "APPROVAL_REQUIRED")
    return aid, msg + "\n\n" + draft

OBJECTIONS = {}

def record_objection(text, outcome=""):
    OBJECTIONS[text] = OBJECTIONS.get(text, {"count": 0, "outcome": outcome})
    OBJECTIONS[text]["count"] += 1
    OBJECTIONS[text]["outcome"] = outcome or OBJECTIONS[text]["outcome"]
    return OBJECTIONS[text]
