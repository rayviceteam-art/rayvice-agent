"""Weekly content calendar for Rayvice. Australia/Sydney aware (DST safe).

Calendar Sunday->Saturday themes; har din ka topic pool se deterministic rotation
(hash of date) — same din dobara same topic nahi jab tak pool exhaust na ho.
"""
from datetime import date, datetime, timedelta, timezone

import config

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None


def tz():
    if ZoneInfo:
        try:
            return ZoneInfo(config.SOCIAL_TZ or "Australia/Sydney")
        except Exception:
            pass
    return timezone(timedelta(hours=10))  # AEST fallback


def now_local():
    return datetime.now(timezone.utc).astimezone(tz())


def today_local():
    return now_local().date()


# weekday(): Monday=0 ... Sunday=6
WEEKLY_THEMES = {
    0: ("invoicing-education", "NDIS invoicing education"),
    1: ("productivity", "Administrative productivity"),
    2: ("rate-calc", "Rate calculations and price-cap awareness"),
    3: ("mistakes", "Common administrative mistakes"),
    4: ("faq", "Frequently asked questions"),
    5: ("checklist", "Practical checklists and templates"),
    6: ("responsible-promo", "Responsible Rayvice promotion / week recap"),
}

# Topic pools — practical, specific, no invented rules/prices. Price rules may
# change: content educates about *checking* official sources, not fixed claims.
TOPIC_POOLS = {
    "invoicing-education": [
        "What to check before sending an NDIS invoice to a plan manager",
        "Invoice line items: why clear support descriptions reduce queries",
        "Plan-managed vs self-managed invoicing: the admin difference",
        "Keeping invoice records audit-ready without the paperwork pile",
        "Batch invoicing: turning a week of shifts into clean invoices",
    ],
    "productivity": [
        "A 15-minute Sunday admin routine for support workers",
        "Turning shift notes into invoices without re-typing everything",
        "Why you should never bill from memory — log it same day",
        "Template your common supports to cut typing time",
        "The folder structure that keeps NDIS paperwork findable",
    ],
    "rate-calc": [
        "Weekend rates: how support workers verify the correct rate",
        "Evening shifts and rate splits: doing the maths right",
        "Public holiday billing: what to double-check before invoicing",
        "Travel billing questions to ask before you invoice",
        "Day vs evening vs weekend: splitting one shift correctly",
    ],
    "mistakes": [
        "The invoice mistake that causes plan manager rejections",
        "Rounding rates by hand: why small errors add up",
        "Forgetting to record the right support category",
        "Mixing up shift times when splitting evening rates",
        "Leaving invoices too late: the monthly admin pile-up",
    ],
    "faq": [
        "FAQ: Do I need special software to invoice as a sole trader?",
        "FAQ: How do I keep records that are easy to find later?",
        "FAQ: What information belongs on an NDIS invoice?",
        "FAQ: How do rate splits affect my invoice line items?",
        "FAQ: What's the fastest safe way to invoice multiple shifts?",
    ],
    "checklist": [
        "Pre-invoice checklist: 6 things to confirm before you send",
        "End-of-shift logging checklist for accurate billing",
        "Month-end admin checklist for independent support workers",
        "New participant onboarding admin checklist",
        "Rate verification checklist before a weekend shift",
    ],
    "responsible-promo": [
        "How Rayvice fits into a simple support-worker admin routine",
        "A quick look at Rayvice's invoice workflow (based on public features)",
        "Why we built Rayvice for independent support workers",
        "Reducing invoice admin: what Rayvice automates and what it doesn't",
        "Trying Rayvice: what to expect in the first week",
    ],
}


def theme_for(day=None):
    """Returns (category, theme_title) for a local date (default: aaj Sydney me)."""
    d = day or today_local()
    return WEEKLY_THEMES[d.weekday()]


def pick_topic(category, day=None):
    """Deterministic rotation: date ka day-number pool me index karta hai."""
    d = day or today_local()
    pool = TOPIC_POOLS.get(category) or ["Rayvice admin tips for NDIS support workers"]
    return pool[d.toordinal() % len(pool)]


def plan_for(day=None):
    """Aaj ka plan: ek idea dict (category, theme, topic, local date)."""
    d = day or today_local()
    category, theme = theme_for(d)
    return {"date": d.isoformat(), "category": category, "theme": theme,
            "topic": pick_topic(category, d)}


def week_plan(start=None):
    """7-din ka plan (default: aaj se)."""
    s = start or today_local()
    return [plan_for(s + timedelta(days=i)) for i in range(7)]


def in_publish_window(now=None, hours=None):
    """Sydney-local publish window check (DST automatically safe).

    Returns the matched 'HH:MM' hour string or None.
    """
    n = now or now_local()
    for h in (hours if hours is not None else config.SOCIAL_PUBLISH_HOURS):
        try:
            hh, mm = map(int, h.split(":"))
        except Exception:
            continue
        if n.hour == hh and n.minute < 30:
            return h
    return None
