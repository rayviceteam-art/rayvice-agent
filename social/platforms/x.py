"""X (Twitter) adapter: BLOCKED_API_ACCESS.

Feb 2026 se X ka free API tier khatam (pay-per-use $0.015/post, card required).
Policy: no card -> no X publishing. Ye adapter sirf honest status dikhata hai;
koi unofficial scraping/browser automation nahi hogi.
"""
from social.platforms.base import PlatformAdapter, PublishResult


class XAdapter(PlatformAdapter):
    name = "x"
    CAPABILITY = {
        "platform": "x",
        "method": "X API v2 POST /2/tweets — pay-per-use only (official)",
        "account_type": "any (with paid API credits)",
        "scopes": ["tweet.write", "users.read"],
        "available": False,
        "free": False,
        "limits": "Free tier discontinued Feb 2026; ~$0.015/post pay-per-use",
        "blocker": "BLOCKED_API_ACCESS — no free tier in 2026; needs paid credits (card)",
        "last_verified": "2026-10-17",
        "test_result": "NOT AVAILABLE ON FREE TIER",
    }

    def configured(self):
        return False

    def verify(self):
        return False, "BLOCKED_API_ACCESS: X free API tier discontinued (Feb 2026). Pay-per-use needs a card."

    def publish(self, draft, media=None, dry_run=True):
        if dry_run:
            return super().publish(draft, media, dry_run=True)
        return PublishResult(False, error="BLOCKED_API_ACCESS: X publishing disabled (no free API tier)",
                             retryable=False)
