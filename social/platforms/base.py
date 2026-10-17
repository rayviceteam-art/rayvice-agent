"""Publishing adapter base: official APIs only, honest status reporting.

Never claim a platform connected until a real authenticated verify() passes.
Dry-run mode me koi network call publish ke liye nahi hoti.
"""
import json
import urllib.error
import urllib.request
import uuid


class PublishResult:
    def __init__(self, ok, post_id="", url="", error="", retryable=False,
                 retry_after=0, raw=None, dry_run=False):
        self.ok = ok
        self.post_id = post_id
        self.url = url
        self.error = error
        self.retryable = retryable
        self.retry_after = retry_after or 0
        self.raw = raw or {}
        self.dry_run = dry_run

    def to_dict(self):
        return {"ok": self.ok, "post_id": self.post_id, "url": self.url,
                "error": self.error, "retryable": self.retryable,
                "retry_after": self.retry_after, "dry_run": self.dry_run}


def http_json(method, url, headers=None, body=None, timeout=60):
    """Returns (status_code, parsed_json_or_text_headers). Raises nothing for HTTP errors."""
    data = None
    hdrs = dict(headers or {})
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", errors="replace")
            try:
                return r.getcode(), json.loads(raw), dict(r.headers)
            except Exception:
                return r.getcode(), {"_raw": raw[:2000]}, dict(r.headers)
    except urllib.error.HTTPError as e:
        raw = ""
        try:
            raw = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = {"_raw": raw[:2000]}
        return e.code, parsed, dict(e.headers or {})
    except Exception as e:
        return 0, {"_error": str(e)[:300]}, {}


def classify_http(status, parsed, headers):
    """(retryable, error_text, retry_after) — permanent permission/auth errors retry mat karo."""
    msg = ""
    if isinstance(parsed, dict):
        msg = (parsed.get("error_description") or
               (parsed.get("error") if isinstance(parsed.get("error"), str) else json.dumps(parsed.get("error", ""))[:300])
               or parsed.get("message") or parsed.get("_raw") or parsed.get("_error") or "")
    msg = str(msg)[:400]
    retry_after = 0
    try:
        retry_after = int(headers.get("Retry-After") or 0)
    except Exception:
        retry_after = 0
    if status == 429:
        return True, msg or "rate limited", retry_after or 300
    if status in (500, 502, 503, 504) or status == 0:
        return True, msg or "temporary network/server error", retry_after
    if status in (401, 403):
        return False, msg or "authentication/permission error", 0
    if 400 <= status < 500:
        return False, msg or f"request rejected (HTTP {status})", 0
    return False, msg, 0


class PlatformAdapter:
    name = "base"
    CAPABILITY = {
        "platform": "base", "method": "", "account_type": "", "scopes": [],
        "available": False, "free": True, "limits": "", "blocker": "not implemented",
        "last_verified": "", "test_result": "NOT TESTED",
    }

    def configured(self):
        """Credentials present? (values never logged)"""
        return False

    def verify(self):
        """Cheapest authenticated check. Returns (ok, message). No side effects."""
        return False, "not implemented"

    def publish(self, draft, media=None, dry_run=True):
        if dry_run:
            return PublishResult(True, post_id="dry_" + uuid.uuid4().hex[:10], dry_run=True,
                                 raw={"simulated": True})
        if not self.configured():
            return PublishResult(False, error=f"{self.name}: credentials missing (env config dekh)",
                                 retryable=False)
        return self._publish_live(draft, media or {})

    def _publish_live(self, draft, media):
        return PublishResult(False, error=f"{self.name}: live publish not implemented", retryable=False)


def draft_text(draft):
    """Hook + body + cta + hashtags ko platform text me jodo."""
    parts = []
    if draft.get("hook"):
        parts.append(draft["hook"].strip())
    if draft.get("body"):
        parts.append(draft["body"].strip())
    if draft.get("cta"):
        parts.append(draft["cta"].strip())
    text = "\n\n".join(parts)
    tags = draft.get("hashtags") or []
    if tags:
        text += "\n\n" + " ".join("#" + t.lstrip("#") for t in tags)
    return text.strip()
