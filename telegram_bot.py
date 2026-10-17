"""Telegram polling layer. No domain/webhook needed. Approval buttons via text."""
import json
import urllib.request
import urllib.parse
import time

import config
from logs_sys import audit

def _api(method, params=None, token=None):
    tok = token or config.TELEGRAM_BOT_TOKEN
    if not tok:
        return {"ok": False, "error": "TELEGRAM_BOT_TOKEN missing"}
    url = f"https://api.telegram.org/bot{tok}/{method}"
    data = urllib.parse.urlencode(params or {}).encode()
    req = urllib.request.Request(url, data=data)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"ok": False, "error": str(e)[:300]}

def send(text, chat_id=None):
    cid = chat_id or config.TELEGRAM_CHAT_ID
    if not cid:
        return {"ok": False, "error": "TELEGRAM_CHAT_ID missing"}
    # Telegram cap 4096
    out = []
    for chunk in [text[i:i + 3900] for i in range(0, len(text), 3900)] or [""]:
        r = _api("sendMessage", {"chat_id": cid, "text": chunk})
        out.append(r)
        audit("agent", "telegram.send", "telegram", chunk[:200], str(r)[:300], "SENT", "", "", "")
    return {"ok": True, "data": out}

def poll_once(offset=0, timeout=25):
    return _api("getUpdates", {"offset": offset, "timeout": timeout})

def parse_command(text):
    t = (text or "").strip()
    if t.startswith("/"):  # Telegram style /approve /status etc.
        t = t[1:]
    if t.upper().startswith("APPROVE "):
        return ("APPROVE", t[8:].strip())
    if t.upper().startswith("REJECT "):
        return ("REJECT", t[7:].strip())
    return ("MESSAGE", t)
