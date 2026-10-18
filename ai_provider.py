"""AI provider abstraction. Free-mode first, never spend when ALLOW_PAID_AI=false."""
import json
import os
import time
import urllib.request
import urllib.error
from datetime import date

import config

USAGE_PATH = os.path.join(os.path.dirname(__file__), "data", "usage.json")

def _load_usage():
    try:
        with open(USAGE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_usage(d):
    os.makedirs(os.path.dirname(USAGE_PATH), exist_ok=True)
    tmp = USAGE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2)
    os.replace(tmp, USAGE_PATH)

def daily_count():
    u = _load_usage()
    return int(u.get(str(date.today()), {}).get("calls", 0))

def _bump_usage(model, tokens=0):
    u = _load_usage()
    k = str(date.today())
    e = u.get(k, {"calls": 0, "tokens": 0})
    e["calls"] = int(e.get("calls", 0)) + 1
    e["tokens"] = int(e.get("tokens", 0)) + int(tokens or 0)
    e["last_model"] = model
    u[k] = e
    _save_usage(u)

class AIResult:
    def __init__(self, ok, text="", model="", error="", needs_approval=False, approval=None):
        self.ok = ok
        self.text = text
        self.model = model
        self.error = error
        self.needs_approval = needs_approval
        self.approval = approval or {}

class AIProvider:
    name = "base"
    def chat(self, messages, model=None, timeout=60):
        raise NotImplementedError

class OpenRouterProvider(AIProvider):
    name = "openrouter"
    def __init__(self):
        self.base = config.OPENROUTER_BASE_URL
        self.key = config.OPENROUTER_API_KEY

    def _post(self, payload, timeout):
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.base + "/chat/completions", data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.key}",
                "HTTP-Referer": "https://www.rayvice.com",
                "X-Title": "Rayvice-Agent",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))

    def chat(self, messages, model=None, timeout=60):
        models = [model] if model else list(config.FREE_MODELS)
        if not self.key:
            return AIResult(False, error="OPENROUTER_API_KEY missing. Add to .env.")
        if config.AI_MODE == "free" and daily_count() >= config.FREE_DAILY_LIMIT:
            return AIResult(False, error=f"Free daily limit hit ({config.FREE_DAILY_LIMIT}). Pausing non-critical tasks.",
                            needs_approval=True,
                            approval={"action": "increase_limit_or_wait",
                                      "why": "FREE_DAILY_LIMIT reached",
                                      "risk": "LOW"})
        last_err = ""
        for m in models:
            # Never auto-upgrade to paid when forbidden
            is_free = (":free" in m) or (m == "openrouter/free")
            if config.AI_MODE == "free" and not is_free and not config.ALLOW_PAID_AI:
                last_err = f"Blocked paid model {m} (ALLOW_PAID_AI=false)"
                continue
            for attempt in range(3):
                try:
                    out = self._post({"model": m, "messages": messages}, timeout)
                    text = out["choices"][0]["message"]["content"]
                    toks = out.get("usage", {}).get("total_tokens", 0)
                    _bump_usage(m, toks)
                    return AIResult(True, text=text, model=m)
                except urllib.error.HTTPError as e:
                    try:
                        body = e.read().decode("utf-8")[:500]
                    except Exception:
                        body = str(e)
                    last_err = f"{m} HTTP {e.code}: {body}"
                    if e.code in (429, 500, 502, 503, 529):
                        time.sleep((2 ** attempt) + 0.5)
                        continue
                    break
                except Exception as e:
                    last_err = f"{m} error: {e}"
                    time.sleep((2 ** attempt) + 0.5)
        # All free failed -> notify, don't silently pay
        if not config.ALLOW_PAID_AI:
            return AIResult(False, error=f"All free models failed. Last: {last_err}",
                            needs_approval=True,
                            approval={"action": "use_paid_or_wait",
                                      "why": last_err,
                                      "risk": "MEDIUM"})
        return AIResult(False, error=last_err)

class GroqProvider(AIProvider):
    """Groq free tier (OpenAI-compatible), PRIMARY provider.

    - Multi-key rotator: har call agli key se start, 429/401 pe next key.
    - Browser User-Agent (Groq Cloudflare urllib UA ko 403/1010 karta hai).
    - Model fallback: GROQ_MODELS list kram se.
    """
    name = "groq"

    def __init__(self):
        self.base = config.GROQ_BASE_URL
        self.keys = list(config.GROQ_API_KEYS)

    def _next_idx(self, n):
        if n <= 1:
            return 0
        u = _load_usage()
        i = int(u.get("_groq_idx", 0)) % n
        u["_groq_idx"] = (i + 1) % n
        _save_usage(u)
        return i

    def _post(self, model, messages, key, timeout):
        payload = json.dumps({"model": model, "messages": messages}).encode("utf-8")
        req = urllib.request.Request(
            self.base + "/chat/completions", data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
                "User-Agent": "Mozilla/5.0 (compatible; RayviceAgent/1.0)",
            },
            method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))

    def chat(self, messages, model=None, timeout=60):
        if not self.keys:
            return AIResult(False, error="GROQ_API_KEYS missing. Add to .env (free at console.groq.com).")
        models = [model] if model else (config.GROQ_MODELS or ["openai/gpt-oss-120b"])
        start = self._next_idx(len(self.keys))
        last_err = ""
        for m in models:
            for off in range(len(self.keys)):
                idx = (start + off) % len(self.keys)
                key = self.keys[idx]
                try:
                    out = self._post(m, messages, key, timeout)
                    text = out["choices"][0]["message"]["content"] or ""
                    if not text.strip():
                        last_err = f"groq {m} key#{idx + 1}: empty content"
                        continue
                    _bump_usage(m, out.get("usage", {}).get("total_tokens", 0))
                    return AIResult(True, text=text, model=f"groq/{m}")
                except urllib.error.HTTPError as e:
                    try:
                        body = e.read().decode("utf-8")[:200]
                    except Exception:
                        body = str(e)
                    last_err = f"groq {m} key#{idx + 1} HTTP {e.code}: {body}"
                    if e.code in (401, 403, 408, 429, 500, 502, 503, 529):
                        continue  # agli key / warna agla model
                    break  # 400 kinds -> is model pe mat atko
                except Exception as e:
                    last_err = f"groq {m} key#{idx + 1} error: {e}"
                    continue
        return AIResult(False, error=last_err)


def get_provider(name="openrouter"):
    if name == "openrouter":
        return OpenRouterProvider()
    if name == "groq":
        return GroqProvider()
    raise ValueError(f"Unknown provider {name}. Add new class here, don't hard-code elsewhere.")
