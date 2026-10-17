"""Duplicate prevention via idempotency keys (sqlite, survives restart)."""
import os
import sqlite3
from datetime import datetime

import config

def _db():
    os.makedirs(os.path.dirname(config.AGENT_DB_PATH) or ".", exist_ok=True)
    c = sqlite3.connect(config.AGENT_DB_PATH)
    c.execute("CREATE TABLE IF NOT EXISTS idempotency(key TEXT PRIMARY KEY, ts TEXT)")
    return c

def seen(key):
    c = _db()
    r = c.execute("SELECT key FROM idempotency WHERE key=?", (key,)).fetchone()
    c.close()
    return r is not None

def mark(key):
    c = _db()
    c.execute("INSERT OR IGNORE INTO idempotency VALUES(?,?)",
              (key, datetime.utcnow().isoformat() + "Z"))
    c.commit()
    c.close()

def check_and_mark(key):
    """True = already done (skip). False = first time (marked now, proceed)."""
    if seen(key):
        return True
    mark(key)
    return False
