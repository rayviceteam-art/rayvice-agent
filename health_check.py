"""Health check: env, OpenRouter, Telegram, DB. Never prints secrets."""
import os
import sqlite3
import urllib.request
import json
import config

def run_text():
    lines = []
    lines.append(f"AI_MODE={config.AI_MODE} ALLOW_PAID_AI={config.ALLOW_PAID_AI}")
    lines.append(f"OPENROUTER_BASE={config.OPENROUTER_BASE_URL}")
    lines.append("OPENROUTER_API_KEY=" + ("SET" if config.OPENROUTER_API_KEY else "MISSING (add to .env)"))
    lines.append("TELEGRAM_BOT_TOKEN=" + ("SET" if config.TELEGRAM_BOT_TOKEN else "MISSING"))
    lines.append("TELEGRAM_CHAT_ID=" + ("SET" if config.TELEGRAM_CHAT_ID else "MISSING"))
    # DB writable?
    try:
        os.makedirs(os.path.dirname(config.AGENT_DB_PATH) or ".", exist_ok=True)
        c = sqlite3.connect(config.AGENT_DB_PATH)
        c.execute("CREATE TABLE IF NOT EXISTS _hc(id INTEGER PRIMARY KEY)")
        c.execute("INSERT INTO _hc DEFAULT VALUES")
        c.commit()
        c.close()
        lines.append(f"DB OK: {config.AGENT_DB_PATH}")
    except Exception as e:
        lines.append(f"DB FAIL: {e}")
    # OpenRouter reachable? (no spend, just models list)
    if config.OPENROUTER_API_KEY:
        try:
            req = urllib.request.Request(config.OPENROUTER_BASE_URL + "/models",
                                         headers={"Authorization": f"Bearer {config.OPENROUTER_API_KEY}"})
            with urllib.request.urlopen(req, timeout=20) as r:
                d = json.loads(r.read().decode())
                n = len(d.get("data", []))
                lines.append(f"OpenRouter OK: {n} models listed")
        except Exception as e:
            lines.append(f"OpenRouter FAIL (non-fatal): {str(e)[:200]}")
    else:
        lines.append("OpenRouter SKIP: no key")
    # Telegram reachable?
    if config.TELEGRAM_BOT_TOKEN:
        try:
            tok = config.TELEGRAM_BOT_TOKEN
            with urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/getMe", timeout=15) as r:
                me = json.loads(r.read().decode())
                lines.append(f"Telegram OK: @{me.get('result',{}).get('username','?')}")
        except Exception as e:
            lines.append(f"Telegram FAIL: {str(e)[:200]}")
    else:
        lines.append("Telegram SKIP: no token")
    # protected paths untouched?
    for p in ["/root/rayvice-live", "/root/agent.py", "/root/groq-rotator.mjs"]:
        lines.append(f"PROTECTED {p}: {'EXISTS-UNTOUCHED' if os.path.exists(p) else 'not-found'}")
    return "\n".join(lines)

if __name__ == "__main__":
    print(run_text())
