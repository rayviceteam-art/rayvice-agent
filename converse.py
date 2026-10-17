"""Short-term conversation memory (owner chat). Capped, sqlite, survives restart."""
import os
import sqlite3
from datetime import datetime

import config

MAX_TURNS = 40  # hard cap, old ones deleted

def _db():
    os.makedirs(os.path.dirname(config.AGENT_DB_PATH) or ".", exist_ok=True)
    c = sqlite3.connect(config.AGENT_DB_PATH)
    c.execute("CREATE TABLE IF NOT EXISTS convo(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, role TEXT, text TEXT)")
    return c

def push(role, text):
    assert role in ("user", "assistant")
    c = _db()
    c.execute("INSERT INTO convo(ts,role,text) VALUES(?,?,?)",
              (datetime.utcnow().isoformat() + "Z", role, (text or "")[:2000]))
    c.execute("DELETE FROM convo WHERE id NOT IN (SELECT id FROM convo ORDER BY id DESC LIMIT ?)", (MAX_TURNS,))
    c.commit()
    c.close()

def history(limit=8):
    c = _db()
    rows = c.execute("SELECT role, text FROM convo ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    c.close()
    return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

def clear():
    c = _db()
    c.execute("DELETE FROM convo")
    c.commit()
    c.close()
