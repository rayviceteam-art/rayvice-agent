"""Content validation: brand rules, compliance bans, limits, AU English, duplicates.

Hard rules (errors) = publish block. Soft rules (warnings) = owner ko dikhao.
Koi bhi claim jo verify nahi hua (NDIS endorsement, testimonials, revenue) BLOCK.
"""
import hashlib
import re

PLATFORM_LIMITS = {
    "instagram": {"body": 2200, "hashtags_max": 30, "hashtags_recommended": 10, "caption_required": True},
    "facebook": {"body": 63206, "hashtags_max": 10, "hashtags_recommended": 3},
    "linkedin": {"body": 3000, "hashtags_max": 10, "hashtags_recommended": 5},
    "x": {"body": 280, "hashtags_max": 5, "hashtags_recommended": 2},
    "reddit": {"body": 40000, "title": 300, "hashtags_max": 0, "hashtags_recommended": 0},
}

# Har banned pattern = (compiled regex, human reason)
_BANNED = [
    (r"\bndis[\s-]*(endorsed|certified|official|approved by)\b", "NDIS endorsement claim (unverified)"),
    (r"\bofficially endorsed\b", "Endorsement claim (unverified)"),
    (r"\bguaranteed\s+(ndis\s+)?approval\b", "Guaranteed approval claim"),
    (r"\b100%\s+compliant\b", "Compliance guarantee"),
    (r"\bfull(y)?\s+compliant\s+guarantee\b", "Compliance guarantee"),
    (r"\b(testimonial|customer says|5[\s-]?star review|our customers love)\b", "Invented testimonial"),
    (r"\b(made|earned|saved)\s+\$[\d,]+", "Revenue figure (unverified)"),
    (r"\bwe('ve)? helped\s+\d+", "Customer-number claim (unverified)"),
    (r"\b\d{1,3}(,\d{3})+\s+(customers|users|workers|businesses)\b", "Customer-number claim (unverified)"),
    (r"\bact now or\b", "Misleading urgency"),
    (r"\byou('ll| will) (lose|be audited|face penalties)\b", "Fear-based claim"),
    (r"\b(legally|tax|financial)\s+guaranteed\b", "Legal/tax guarantee"),
    (r"\bwe (provide|give) (legal|tax|financial) advice\b", "Advice claim"),
    (r"\b#1\b|\bnumber one\b|\bbest in australia\b", "Unsupported superlative"),
    (r"\brisk[- ]free\b", "Unsupported risk claim"),
]

# Sensitive info patterns — errors, never publish PII.
_SENSITIVE = [
    (r"\b0[45]\d{2}[\s-]?\d{3}[\s-]?\d{3}\b", "Australian mobile number"),
    (r"\b\+61[\s-]?[45]\d{2}[\s-]?\d{3}[\s-]?\d{3}\b", "Australian phone number"),
    (r"\b(ndis|participant)\s*(number|no\.?|#)\s*[:\s]?\s*\d{6,}", "NDIS/participant number"),
    (r"\bmedicare\s*(number|no\.?|#)\s*[:\s]?\s*\d{6,}", "Medicare number"),
    (r"\bdob\s*[:\s]\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", "Date of birth"),
]

_EMAIL_OK = re.compile(r"[\w.+-]+@rayvice\.com", re.I)
_EMAIL_ANY = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")

# US -> AU spelling normalisation (word-boundary, case-preserving).
_AU_SPELLINGS = {
    "organize": "organise", "organizes": "organises", "organized": "organised",
    "organizing": "organising", "organization": "organisation", "organizations": "organisations",
    "color": "colour", "colors": "colours", "colored": "coloured",
    "center": "centre", "centers": "centres",
    "analyze": "analyse", "analyzes": "analyses", "analyzed": "analysed", "analyzing": "analysing",
    "customize": "customise", "customizes": "customises", "customized": "customised", "customizing": "customising",
    "customization": "customisation", "customizations": "customisations",
    "apologize": "apologise", "apologized": "apologised",
    "labor": "labour", "favor": "favour", "favors": "favours", "favorite": "favourite", "favorites": "favourites",
    "behavior": "behaviour", "behaviors": "behaviours",
    "catalog": "catalogue", "catalogs": "catalogues",
    "traveled": "travelled", "traveling": "travelling", "canceled": "cancelled", "canceling": "cancelling",
    "modeling": "modelling", "fulfill": "fulfil", "enrollment": "enrolment",
    "aluminum": "aluminium", "license": "licence", "licenses": "licences",
    "recognize": "recognise", "recognized": "recognised", "minimize": "minimise", "maximize": "maximise",
    "prioritize": "prioritise", "prioritized": "prioritised", "summarize": "summarise",
}

_WORD = re.compile(r"[a-z0-9]+")


def _auto_case(src, dst):
    if src.isupper():
        return dst.upper()
    if src[:1].isupper():
        return dst.capitalize()
    return dst


def normalise_au_english(text):
    """US spellings ko AU spelling me badlo (safe word-level, case preserve)."""
    if not text:
        return text
    for us, au in _AU_SPELLINGS.items():
        text = re.sub(rf"\b{us}\b", lambda m: _auto_case(m.group(0), au), text, flags=re.I)
    return text


def content_hash(*parts):
    joined = "\n".join(p or "" for p in parts).strip().lower()
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def shingles(text, n=4):
    words = _WORD.findall((text or "").lower())
    if len(words) < n:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i:i + n]) for i in range(len(words) - n + 1)}


def similarity(a, b, n=4):
    sa, sb = shingles(a, n), shingles(b, n)
    if not sa or not sb:
        return 0.0
    inter = len(sa & sb)
    return inter / float(len(sa | sb))


def find_near_duplicate(text, prior_texts, threshold=0.7):
    """Returns the prior text that is too similar, ya None."""
    for p in prior_texts or []:
        if similarity(text, p) >= threshold:
            return p
    return None


def validate(platform, hook="", body="", cta="", hashtags=None, title="", prior_texts=None):
    """Returns {"errors": [...], "warnings": [...], "normalised": {...}}."""
    platform = (platform or "").lower()
    limits = PLATFORM_LIMITS.get(platform)
    errors, warnings = [], []
    if not limits:
        return {"errors": [f"Unknown platform: {platform}"], "warnings": [],
                "normalised": {"hook": hook, "body": body, "cta": cta, "title": title,
                               "hashtags": hashtags or []}}

    body = normalise_au_english(body or "")
    hook = normalise_au_english(hook or "")
    cta = normalise_au_english(cta or "")
    title = normalise_au_english(title or "")
    hashtags = [h.strip().lstrip("#") for h in (hashtags or []) if h and h.strip()]

    full_text = " ".join([hook, title, body, cta]).strip()
    if len(full_text) < 40:
        errors.append("Content too short to be useful (min ~40 chars)")

    for rx, reason in _BANNED:
        m = re.search(rx, full_text, re.I)
        if m:
            errors.append(f"Blocked claim: {reason} (\"{m.group(0)[:60]}\")")

    for rx, reason in _SENSITIVE:
        if re.search(rx, full_text, re.I):
            errors.append(f"Sensitive info: {reason}")

    for m in _EMAIL_ANY.finditer(full_text):
        if not _EMAIL_OK.fullmatch(m.group(0)):
            errors.append(f"Sensitive info: non-Rayvice email ({m.group(0)[:60]})")

    body_total = (hook + "\n\n" + body + "\n\n" + cta).strip()
    if len(body_total) > limits["body"]:
        errors.append(f"{platform} caption/body limit exceeded ({len(body_total)}/{limits['body']})")
    if platform == "reddit":
        if not title.strip():
            errors.append("Reddit post needs a title")
        elif len(title) > limits["title"]:
            errors.append(f"Reddit title too long ({len(title)}/{limits['title']})")
        if hashtags:
            warnings.append("Reddit me hashtags nahi daalte — hata do")
    if len(hashtags) > limits["hashtags_max"]:
        errors.append(f"Too many hashtags ({len(hashtags)}/{limits['hashtags_max']})")
    elif len(hashtags) > limits["hashtags_recommended"]:
        warnings.append(f"Hashtags zyada hai ({len(hashtags)}), recommended {limits['hashtags_recommended']}")

    if prior_texts:
        dup = find_near_duplicate(full_text, prior_texts)
        if dup:
            errors.append("Near-duplicate of a previous post (75%+ similar)")

    return {"errors": errors, "warnings": warnings,
            "normalised": {"hook": hook, "body": body, "cta": cta, "title": title,
                           "hashtags": hashtags}}
