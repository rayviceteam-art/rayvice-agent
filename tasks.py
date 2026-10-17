"""Task manager. Persistent sqlite, survives restart."""
import json
import sqlite3
import uuid
import os
from datetime import datetime

import config

STATUSES = ["PENDING", "PLANNING", "RUNNING", "WAITING_APPROVAL", "COMPLETED", "FAILED", "CANCELLED"]
RISKS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

def _db():
    os.makedirs(os.path.dirname(config.AGENT_DB_PATH) or ".", exist_ok=True)
    c = sqlite3.connect(config.AGENT_DB_PATH)
    c.execute("""CREATE TABLE IF NOT EXISTS tasks(
      task_id TEXT PRIMARY KEY, task_type TEXT, priority INTEGER,
      created_at TEXT, status TEXT, owner TEXT, required_tools TEXT,
      risk_level TEXT, approval_required INTEGER, result TEXT, error TEXT, retry_count INTEGER)""")
    return c

def create(task_type, priority=2, owner="agent", required_tools="", risk_level="LOW", approval_required=False):
    assert risk_level in RISKS
    tid = "t_" + uuid.uuid4().hex[:10]
    c = _db()
    c.execute("INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
              (tid, task_type, priority, datetime.utcnow().isoformat() + "Z",
               "PENDING", owner, required_tools, risk_level,
               1 if approval_required else 0, "", "", 0))
    c.commit()
    c.close()
    return tid

def set_status(tid, status, result="", error=""):
    assert status in STATUSES
    c = _db()
    if result or error:
        c.execute("UPDATE tasks SET status=?, result=?, error=? WHERE task_id=?", (status, result[:4000], error[:2000], tid))
    else:
        c.execute("UPDATE tasks SET status=? WHERE task_id=?", (status, tid))
    c.commit()
    c.close()

def bump_retry(tid):
    c = _db()
    c.execute("UPDATE tasks SET retry_count=retry_count+1 WHERE task_id=?", (tid,))
    c.commit()
    c.close()

def get(tid):
    c = _db()
    c.row_factory = sqlite3.Row
    r = c.execute("SELECT * FROM tasks WHERE task_id=?", (tid,)).fetchone()
    c.close()
    return dict(r) if r else None

def pending(limit=20):
    c = _db()
    c.row_factory = sqlite3.Row
    rows = c.execute("SELECT * FROM tasks WHERE status IN ('PENDING','PLANNING','RUNNING') ORDER BY priority DESC LIMIT ?", (limit,)).fetchall()
    c.close()
    return [dict(r) for r in rows]
