"""Per-integration rate limits. Never bypass platform limits: STOP, WAIT, RETRY."""
import time
from collections import deque

LIMITS = {
    "telegram": {"per_min": 20, "per_day": 400},
    "openrouter": {"per_min": 15, "per_day": 180},
    "search": {"per_min": 30, "per_day": 1000},
    "github": {"per_min": 20, "per_day": 500},
    "monitor": {"per_min": 10, "per_day": 500},
    "default": {"per_min": 20, "per_day": 500},
}

_hits = {}

def _q(key):
    return _hits.setdefault(key, {"min": deque(), "day": deque()})

def allow(integration):
    lim = LIMITS.get(integration, LIMITS["default"])
    now = time.time()
    q = _q(integration)
    while q["min"] and q["min"][0] < now - 60:
        q["min"].popleft()
    while q["day"] and q["day"][0] < now - 86400:
        q["day"].popleft()
    if len(q["min"]) >= lim["per_min"]:
        return False, f"{integration} per-min limit ({lim['per_min']}) — ruk ja bhai, thodi der baad retry"
    if len(q["day"]) >= lim["per_day"]:
        return False, f"{integration} per-day limit ({lim['per_day']}) — kal try karenge"
    q["min"].append(now)
    q["day"].append(now)
    return True, ""
