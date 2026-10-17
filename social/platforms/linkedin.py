"""LinkedIn adapter: official REST posts (member or organisation author).

Note: some permissions require app review — verify() se sach pata chalega,
assumption nahi. Text-only v1 (image upload flow Phase 5 me agar access mile).
"""
import config
from social.platforms.base import PlatformAdapter, PublishResult, draft_text, http_json

API = "https://api.linkedin.com"


class LinkedInAdapter(PlatformAdapter):
    name = "linkedin"
    CAPABILITY = {
        "platform": "linkedin",
        "method": "LinkedIn REST API /v2/ugcPosts or /rest/posts (official)",
        "account_type": "Member (w_member_social) ya Company Page admin (w_organization_social)",
        "scopes": ["openid", "profile", "w_member_social (or w_organization_social)"],
        "available": None,
        "free": True,
        "limits": "Share API rate limits apply; free",
        "blocker": "App creation + OAuth token + (page ke liye) Community Management approval; LINKEDIN_AUTHOR_URN",
        "last_verified": "",
        "test_result": "NOT TESTED",
    }

    def configured(self):
        return bool(config.LINKEDIN_ACCESS_TOKEN and config.LINKEDIN_AUTHOR_URN)

    def verify(self):
        if not (config.LINKEDIN_ACCESS_TOKEN and config.LINKEDIN_AUTHOR_URN):
            return False, "LINKEDIN_ACCESS_TOKEN/LINKEDIN_AUTHOR_URN missing"
        code, parsed, _ = http_json("GET", f"{API}/v2/userinfo",
                                    headers={"Authorization": f"Bearer {config.LINKEDIN_ACCESS_TOKEN}"})
        if code == 200 and isinstance(parsed, dict) and parsed.get("sub"):
            return True, f"LinkedIn OK: {parsed.get('name', parsed.get('sub'))}"
        return False, f"verify failed: HTTP {code} {str(parsed)[:200]}"

    def _publish_live(self, draft, media):
        text = draft_text(draft)
        payload = {
            "author": config.LINKEDIN_AUTHOR_URN,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }
        code, parsed, hdrs = http_json("POST", f"{API}/v2/ugcPosts",
                                       headers={"Authorization": f"Bearer {config.LINKEDIN_ACCESS_TOKEN}",
                                                "X-Restli-Protocol-Version": "2.0.0"},
                                       body=payload)
        if code in (200, 201) and parsed.get("id"):
            pid = parsed["id"]
            return PublishResult(True, post_id=pid,
                                 url=f"https://www.linkedin.com/feed/update/{pid}/", raw={"id": pid})
        from social.platforms.base import classify_http
        retryable, msg, ra = classify_http(code, parsed, hdrs)
        return PublishResult(False, error=f"LinkedIn post failed: {msg}", retryable=retryable,
                             retry_after=ra, raw=parsed)
