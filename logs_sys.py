"""Logging + audit. Never logs secret values."""
import json
import logging
import os
import sqlite3
from datetime import datetime

import config

LOG_PATH = os.path.join(os.path.dirname(__file__), "logs", "agent.log")
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

logging.basicConfig(filename=LOG_PATH, level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
                    format="%(asctime)s %(levelname)s %(message)s")

def info(msg):
    logging.info(msg)
    print(msg)

def warn(msg):
    logging.warning(msg)
    print(f"[WARN] {msg}")

def error(msg):
    logging.error(msg)
    print(f"[ERROR] {msg}")

def _db():
    os.makedirs(os.path.dirname(config.AGENT_DB_PATH) or ".", exist_ok=True)
    c = sqlite3.connect(config.AGENT_DB_PATH)
    c.execute("""CREATE TABLE IF NOT EXISTS audit(
      id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, agent TEXT, task TEXT,
      tool TEXT, input_summary TEXT, output_summary TEXT, decision TEXT,
      approval_status TEXT, result TEXT, error TEXT)""")
    return c

def _scrub(text):
    if not text:
        return ""
    t = str(text)
    for k in config.SECRET_KEYS:
        v = os.environ.get(k, "")
        if v and len(v) > 6 and v in t:
            t = t.replace(v, "***REDACTED***")
    return t[:2000]

def audit(agent, task, tool, input_summary, output_summary, decision="",
          approval_status="", result="", error_msg=""):
    c = _db()
    c.execute("INSERT INTO audit(ts,agent,task,tool,input_summary,output_summary,decision,approval_status,result,error) VALUES(?,?,?,?,?,?,?,?,?,?)",
              (datetime.utcnow().isoformat() + "Z", agent, task, tool,
               _scrub(input_summary), _scrub(output_summary), decision,
               approval_status, _scrub(result), _scrub(error_msg)))
    c.commit()
    c.close()
