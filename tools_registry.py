"""Tool registry with timeout/retry/backoff/circuit-breaker."""
import time
from collections import defaultdict

_breaker = defaultdict(lambda: {"fails": 0, "open_until": 0})

class Tool:
    def __init__(self, name, fn, timeout=30):
        self.name = name
        self.fn = fn
        self.timeout = timeout

REGISTRY = {}

def register(name, timeout=30):
    def deco(fn):
        REGISTRY[name] = Tool(name, fn, timeout)
        return fn
    return deco

TOOL_RATE_MAP = {"web_search": "search", "fetch_url": "search", "website_check": "monitor",
                 "content_draft": "openrouter", "lead_hunt": "search"}

def run(name, retries=2, **kwargs):
    if name not in REGISTRY:
        return {"ok": False, "error": f"Unknown tool {name}"}
    import rate_limits
    ok, why = rate_limits.allow(TOOL_RATE_MAP.get(name, "default"))
    if not ok:
        return {"ok": False, "error": why}
    b = _breaker[name]
    if time.time() < b["open_until"]:
        return {"ok": False, "error": f"Circuit open for {name}, try later"}
    last = None
    for i in range(retries + 1):
        try:
            out = REGISTRY[name].fn(**kwargs)
            b["fails"] = 0
            return {"ok": True, "data": out}
        except Exception as e:
            last = str(e)[:500]
            b["fails"] += 1
            if b["fails"] >= 5:
                b["open_until"] = time.time() + 300
            time.sleep(min(2 ** i, 8))
    return {"ok": False, "error": last}
