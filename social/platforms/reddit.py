"""Reddit adapter: official OAuth (script app, refresh token). Community rules respected.

Rules: sirf SOCIAL_REDDIT_SUBS me post; no mass-posting, no identical cross-posts;
daily forced nahi — pipeline schedule par decide karta hai.
"""
import base64
import urllib.parse

import config
from social.platforms.base import PlatformAdapter, PublishResult, draft_text, http_json

TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
OAUTH = "https://oauth.reddit.com"


class RedditAdapter(PlatformAdapter):
    name = "reddit"
    CAPABILITY = {
        "platform": "reddit",
        "method": "Reddit API OAuth — /api/submit (official)",
        "account_type": "Reddit account with a registered 'script' app",
        "scopes": ["identity", "submit", "read"],
        "available": None,
        "free": True,
        "limits": "OAuth ~100 QPM; free",
        "blocker": "REDDIT_CLIENT_ID/SECRET/REFRESH_TOKEN + SOCIAL_REDDIT_SUBS chahiye",
        "last_verified": "",
        "test_result": "NOT TESTED",
    }

    def configured(self):
        return bool(config.REDDIT_CLIENT_ID and config.REDDIT_CLIENT_SECRET and
                    config.REDDIT_REFRESH_TOKEN and config.SOCIAL_REDDIT_SUBS)

    def _token(self):
        basic = base64.b64encode(f"{config.REDDIT_CLIENT_ID}:{config.REDDIT_CLIENT_SECRET}".encode()).decode()
        data = urllib.parse.urlencode({"grant_type": "refresh_token",
                                       "refresh_token": config.REDDIT_REFRESH_TOKEN}).encode()
        import urllib.request
        req = urllib.request.Request(TOKEN_URL, data=data, headers={
            "Authorization": f"Basic {basic}",
            "User-Agent": config.REDDIT_USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded"})
        import urllib.error, json as _json
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return _json.loads(r.read().decode()).get("access_token", "")
        except Exception:
            return ""

    def verify(self):
        if not (config.REDDIT_CLIENT_ID and config.REDDIT_CLIENT_SECRET and config.REDDIT_REFRESH_TOKEN):
            return False, "Reddit credentials missing"
        tok = self._token()
        if not tok:
            return False, "token refresh failed (client/secret/refresh token check karo)"
        code, parsed, _ = http_json("GET", f"{OAUTH}/api/v1/me",
                                    headers={"Authorization": f"bearer {tok}",
                                             "User-Agent": config.REDDIT_USER_AGENT})
        if code == 200 and parsed.get("name"):
            return True, f"Reddit OK: u/{parsed.get('name')}"
        return False, f"verify failed: HTTP {code}"

    def _publish_live(self, draft, media):
        sub = (draft.get("subreddit") or (config.SOCIAL_REDDIT_SUBS[0] if config.SOCIAL_REDDIT_SUBS else "")).strip()
        if not sub:
            return PublishResult(False, error="No subreddit configured (SOCIAL_REDDIT_SUBS)", retryable=False)
        if sub not in config.SOCIAL_REDDIT_SUBS:
            return PublishResult(False, error=f"Subreddit r/{sub} not in approved list", retryable=False)
        tok = self._token()
        if not tok:
            return PublishResult(False, error="Reddit token refresh failed", retryable=True, retry_after=600)
        title = (draft.get("title") or draft.get("hook") or "")[:295]
        text = "\n\n".join(x for x in [draft.get("body", "").strip(), draft.get("cta", "").strip()] if x)
        form = urllib.parse.urlencode({"sr": sub, "title": title, "text": text,
                                       "kind": "self", "api_type": "json"}).encode()
        import urllib.request, urllib.error, json as _json
        req = urllib.request.Request(f"{OAUTH}/api/submit", data=form, headers={
            "Authorization": f"bearer {tok}",
            "User-Agent": config.REDDIT_USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                out = _json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            body = {}
            try:
                body = _json.loads(e.read().decode())
            except Exception:
                pass
            retryable = e.code == 429 or e.code >= 500
            return PublishResult(False, error=f"Reddit submit failed: HTTP {e.code} {str(body)[:200]}",
                                 retryable=retryable)
        except Exception as e:
            return PublishResult(False, error=f"Reddit submit error: {e}", retryable=True, retry_after=300)
        errors = (out.get("json") or {}).get("errors") or []
        data = (out.get("json") or {}).get("data") or {}
        if errors:
            return PublishResult(False, error=f"Reddit says: {errors}", retryable=False, raw=out)
        url = data.get("url") or ""
        pid = data.get("id") or data.get("name") or ""
        return PublishResult(True, post_id=pid, url=url, raw={"id": pid, "url": url})
