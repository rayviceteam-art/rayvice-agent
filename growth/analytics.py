"""AnalyticsAgent. Never fabricate — unavailable metric = DATA NOT CONNECTED."""
import json
import os
import sqlite3
from datetime import datetime

import config

METRICS = ["visitors", "signup_rate", "trial_starts", "trial_activation",
           "trial_to_paid", "churn", "revenue", "plan_distribution",
           "feature_usage", "support_volume", "lead_conversion", "content_performance"]

def _db():
    os.makedirs(os.path.dirname(config.AGENT_DB_PATH) or ".", exist_ok=True)
    c = sqlite3.connect(config.AGENT_DB_PATH)
    c.execute("CREATE TABLE IF NOT EXISTS metrics(ts TEXT, name TEXT, value TEXT, source TEXT)")
    return c

def record(name, value, source="manual"):
    c = _db()
    c.execute("INSERT INTO metrics VALUES(?,?,?,?)",
              (datetime.utcnow().isoformat() + "Z", name, json.dumps(value), source))
    c.commit()
    c.close()

def latest(name):
    c = _db()
    r = c.execute("SELECT value, ts FROM metrics WHERE name=? ORDER BY ts DESC LIMIT 1", (name,)).fetchone()
    c.close()
    if not r:
        return None
    return {"value": json.loads(r[0]), "ts": r[1]}

def funnel_text():
    """VISITOR -> SIGNUP -> TRIAL -> ACTIVATED -> PAYING -> RETAINED."""
    stages = ["visitors", "signup_rate", "trial_starts", "trial_activation", "trial_to_paid"]
    lines = ["📈 Revenue funnel bhai (jo connected nahi wo clearly likha hai):"]
    prev = None
    for s in stages:
        v = latest(s)
        if v is None:
            lines.append(f"• {s}: DATA NOT CONNECTED (analytics key lagegi tab aayega)")
        else:
            drop = ""
            if prev and isinstance(v["value"], (int, float)) and isinstance(prev, (int, float)) and prev:
                drop = f" (drop {100 - round(100 * v['value'] / prev)}%)"
            lines.append(f"• {s}: {v['value']}{drop}")
            prev = v["value"] if isinstance(v["value"], (int, float)) else prev
    lines.append("Sabse bada drop wahi dikhega jaha data hoga — bina data ke guess nahi marunga.")
    return "\n".join(lines)

def summary_text():
    ok = sum(1 for m in METRICS if latest(m) is not None)
    return (f"Analytics: {ok}/{len(METRICS)} metrics connected hai bhai.\n" + funnel_text()
            if ok else
            "Analytics abhi connected nahi hai bhai — Stripe/Neon/PostHog key lagegi tab aayega. Tab tak leads + content + website wale numbers report me milenge.")
