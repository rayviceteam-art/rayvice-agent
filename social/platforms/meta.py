"""Meta adapters: Facebook Page (Graph API) + Instagram Professional (Content Publishing API).

FB: page access token + pages_manage_posts.
IG: professional account linked to page + instagram_content_publish. Image URL public hona chahiye.
"""
import config
from social.platforms.base import PlatformAdapter, PublishResult, draft_text, http_json

GRAPH = "https://graph.facebook.com"


def _v():
    return config.META_GRAPH_VERSION


class FacebookAdapter(PlatformAdapter):
    name = "facebook"
    CAPABILITY = {
        "platform": "facebook",
        "method": "Meta Graph API — Page feed/photos (official)",
        "account_type": "Facebook Page (personal profile publishing NOT supported)",
        "scopes": ["pages_show_list", "pages_read_engagement", "pages_manage_posts"],
        "available": None,  # runtime pe configured() se decide hota hai
        "free": True,
        "limits": "Page-level rate limits; free",
        "blocker": "META_ACCESS_TOKEN + META_PAGE_ID chahiye",
        "last_verified": "",
        "test_result": "NOT TESTED",
    }

    def configured(self):
        return bool(config.META_ACCESS_TOKEN and config.META_PAGE_ID)

    def verify(self):
        if not self.configured():
            return False, "META_ACCESS_TOKEN/META_PAGE_ID missing"
        code, parsed, _ = http_json("GET",
            f"{GRAPH}/{_v()}/{config.META_PAGE_ID}?fields=name,id&access_token={config.META_ACCESS_TOKEN}")
        if code == 200 and isinstance(parsed, dict) and parsed.get("id"):
            return True, f"Page OK: {parsed.get('name', '')} ({parsed.get('id')})"
        return False, f"verify failed: HTTP {code} {str(parsed)[:200]}"

    def _publish_live(self, draft, media):
        text = draft_text(draft)
        if media.get("url"):
            code, parsed, hdrs = http_json("POST",
                f"{GRAPH}/{_v()}/{config.META_PAGE_ID}/photos",
                body={"url": media["url"], "caption": text,
                      "access_token": config.META_ACCESS_TOKEN})
            if code == 200 and parsed.get("id"):
                pid = parsed.get("id")
                return PublishResult(True, post_id=pid, raw=parsed)
            from social.platforms.base import classify_http
            retryable, msg, ra = classify_http(code, parsed, hdrs)
            return PublishResult(False, error=f"FB photo post failed: {msg}", retryable=retryable, retry_after=ra, raw=parsed)
        code, parsed, hdrs = http_json("POST",
            f"{GRAPH}/{_v()}/{config.META_PAGE_ID}/feed",
            body={"message": text, "access_token": config.META_ACCESS_TOKEN})
        if code == 200 and parsed.get("id"):
            pid = parsed.get("id")
            return PublishResult(True, post_id=pid,
                                 url=f"https://facebook.com/{pid}", raw=parsed)
        from social.platforms.base import classify_http
        retryable, msg, ra = classify_http(code, parsed, hdrs)
        return PublishResult(False, error=f"FB feed post failed: {msg}", retryable=retryable, retry_after=ra, raw=parsed)


class InstagramAdapter(PlatformAdapter):
    name = "instagram"
    CAPABILITY = {
        "platform": "instagram",
        "method": "Meta Instagram Content Publishing API (official)",
        "account_type": "Instagram Professional (Business/Creator) linked to a Facebook Page",
        "scopes": ["instagram_basic", "instagram_content_publish", "pages_show_list", "pages_read_engagement"],
        "available": None,
        "free": True,
        "limits": "~25 API-published posts / 24h; 1 carousel step; free",
        "blocker": "Professional account + linked Page + INSTAGRAM_ACCOUNT_ID + token",
        "last_verified": "",
        "test_result": "NOT TESTED",
    }

    def configured(self):
        return bool(config.META_ACCESS_TOKEN and config.INSTAGRAM_ACCOUNT_ID)

    def verify(self):
        if not self.configured():
            return False, "META_ACCESS_TOKEN/INSTAGRAM_ACCOUNT_ID missing"
        code, parsed, _ = http_json("GET",
            f"{GRAPH}/{_v()}/{config.INSTAGRAM_ACCOUNT_ID}?fields=username,id&access_token={config.META_ACCESS_TOKEN}")
        if code == 200 and isinstance(parsed, dict) and parsed.get("id"):
            return True, f"IG account OK: @{parsed.get('username', '')}"
        return False, f"verify failed: HTTP {code} {str(parsed)[:200]}"

    def _publish_live(self, draft, media):
        if not media.get("url"):
            return PublishResult(False, error="Instagram needs a public image URL (media missing)", retryable=False)
        caption = draft_text(draft)
        code, parsed, hdrs = http_json("POST",
            f"{GRAPH}/{_v()}/{config.INSTAGRAM_ACCOUNT_ID}/media",
            body={"image_url": media["url"], "caption": caption,
                  "access_token": config.META_ACCESS_TOKEN})
        from social.platforms.base import classify_http
        if code != 200 or not parsed.get("id"):
            retryable, msg, ra = classify_http(code, parsed, hdrs)
            return PublishResult(False, error=f"IG container failed: {msg}", retryable=retryable, retry_after=ra, raw=parsed)
        creation_id = parsed["id"]
        code2, parsed2, hdrs2 = http_json("POST",
            f"{GRAPH}/{_v()}/{config.INSTAGRAM_ACCOUNT_ID}/media_publish",
            body={"creation_id": creation_id, "access_token": config.META_ACCESS_TOKEN})
        if code2 == 200 and parsed2.get("id"):
            pid = parsed2.get("id")
            return PublishResult(True, post_id=pid, raw=parsed2)
        retryable, msg, ra = classify_http(code2, parsed2, hdrs2)
        return PublishResult(False, error=f"IG publish failed: {msg}", retryable=retryable, retry_after=ra, raw=parsed2)
