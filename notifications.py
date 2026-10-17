"""Owner notifications by severity. Channel: Telegram (authorized)."""
import telegram_bot
from logs_sys import audit

PREFIX = {"CRITICAL": "🚨 CRITICAL bhai", "HIGH": "⚠️ HIGH", "MEDIUM": "🔔", "LOW": "ℹ️"}

def notify(severity, text):
    sev = (severity or "MEDIUM").upper()
    if sev not in PREFIX:
        sev = "MEDIUM"
    msg = f"{PREFIX[sev]}: {text}"[:3800]
    audit("agent", "notify", "telegram", sev, text[:300], "NOTIFY", sev, "", "")
    if sev == "LOW":
        import os
        if os.environ.get("NOTIFY_LOW", "false").lower() != "true":
            return {"ok": True, "skipped": "LOW suppressed"}
    return telegram_bot.send(msg)
