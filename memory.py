"""Persistent memory. Business/marketing/sales/product/technical. No secrets here."""
import json
import os
from datetime import datetime

MEM_DIR = os.path.join(os.path.dirname(__file__), "knowledge", "memory")
SECTIONS = ["business", "marketing", "sales", "product", "technical"]

def _path(section):
    os.makedirs(MEM_DIR, exist_ok=True)
    return os.path.join(MEM_DIR, f"{section}.json")

def read(section):
    p = _path(section)
    if not os.path.exists(p):
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def write(section, data):
    if section not in SECTIONS:
        raise ValueError(f"Unknown memory section {section}")
    # Hard block secrets in memory
    txt = json.dumps(data).lower()
    for bad in ("sk-or-", "gsk_", "xox", "telegram_bot_token", "api_key"):
        if bad in txt and section != "technical":
            raise ValueError("Refusing to store possible secret in memory. Use .env only.")
    d = read(section)
    d.update(data)
    d["updated_at"] = datetime.utcnow().isoformat() + "Z"
    tmp = _path(section) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2)
    os.replace(tmp, _path(section))
    return d

def append_list(section, key, item, max_len=200):
    d = read(section)
    lst = d.get(key, [])
    lst.append(item)
    d[key] = lst[-max_len:]
    return write(section, d)
