"""Platform registry. Only official APIs; status always honest."""
from social.platforms.base import PlatformAdapter, PublishResult, draft_text, http_json, classify_http  # noqa
from social.platforms.meta import FacebookAdapter, InstagramAdapter
from social.platforms.reddit import RedditAdapter
from social.platforms.linkedin import LinkedInAdapter
from social.platforms.x import XAdapter

REGISTRY = {
    "instagram": InstagramAdapter,
    "facebook": FacebookAdapter,
    "linkedin": LinkedInAdapter,
    "reddit": RedditAdapter,
    "x": XAdapter,
}


def get_adapter(name):
    cls = REGISTRY.get((name or "").lower())
    return cls() if cls else None


def capabilities():
    """Capability matrix — docs/platform-capabilities.md isi se update hota hai."""
    out = []
    for name, cls in REGISTRY.items():
        cap = dict(cls.CAPABILITY)
        a = cls()
        cap["configured"] = a.configured()
        cap["available"] = bool(cap["configured"]) if cap.get("free") else False
        out.append(cap)
    return out


def enabled_platforms(config_platforms):
    """Intent + credentials dono ho tabhi enabled (X kabhi nahi)."""
    out = []
    for p in config_platforms or []:
        if p == "x":
            continue
        a = get_adapter(p)
        if a and a.configured():
            out.append(p)
    return out
