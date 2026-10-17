"""Approval queue. Human must approve HIGH/CRITICAL + external sends."""
import sqlite3
import uuid
import os
from datetime import datetime

import config
from logs_sys import audit

LOW_AUTO = {"research", "organize", "analyze", "draft", "test", "branch", "prepare"}

def _db():
    os.makedirs(os.path.dirname(config.AGENT_DB_PATH) or ".", exist_ok=True)
    c = sqlite3.connect(config.AGENT_DB_PATH)
    c.execute("""CREATE TABLE IF NOT EXISTS approvals(
      id TEXT PRIMARY KEY, ts TEXT, action TEXT, target TEXT, why TEXT,
      expected TEXT, risk TEXT, status TEXT, payload TEXT)""")
    return c

def needs_approval(action, risk):
    if risk in ("HIGH", "CRITICAL"):
        return True
    sensitive = ("send", "publish", "delete", "production", "purchase", "paid", "money",
                 "database", "infra", "outreach", "dm", "message-external")
    return any(s in action.lower() for s in sensitive)

def request_approval(action, target, why, expected, risk="MEDIUM", payload=""):
    aid = "a_" + uuid.uuid4().hex[:8]
    c = _db()
    c.execute("INSERT INTO approvals VALUES(?,?,?,?,?,?,?,?,?)",
              (aid, datetime.utcnow().isoformat() + "Z", action, target[:500],
               why[:1000], expected[:1000], risk, "PENDING", payload[:4000]))
    c.commit()
    c.close()
    audit("agent", action, "approval.request", why, expected, "WAIT_FOR_OWNER", "PENDING", "", "")
    return aid, (f"ACTION REQUIRES APPROVAL [{aid}] — bhai ye dekh le:\n"
                 f"Kya karna hai: {action}\nKiske liye: {target}\nKyu: {why}\n"
                 f"Hoga kya: {expected}\nRisk: {risk}\n"
                 f"Telegram me reply kar: APPROVE {aid} ya REJECT {aid}")

def decide(aid, ok):
    c = _db()
    c.execute("UPDATE approvals SET status=? WHERE id=?", ("APPROVED" if ok else "REJECTED", aid))
    c.commit()
    c.close()
    audit("owner", aid, "approval.decide", aid, "APPROVED" if ok else "REJECTED",
          "OWNER_DECISION", "APPROVED" if ok else "REJECTED", "", "")
    return ok

def queue():
    c = _db()
    c.row_factory = sqlite3.Row
    rows = c.execute("SELECT * FROM approvals WHERE status='PENDING' ORDER BY ts").fetchall()
    c.close()
    return [dict(r) for r in rows]
