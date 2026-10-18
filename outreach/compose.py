"""AI cold-email generation — short, personal, compliant (AU Spam Act 2003)."""
import hashlib
import json
import re

import config
import model_router

PROMPT_VERSION = "outreach-v2"

BANNED = ("guarantee", "100%", "risk-free", "risk free", "act now", "limited time",
          "final notice", "urgent", "no risk", "free money", "double your", "make $$$",
          "click here", "buy now", "limited offer", "winner", "congratulations you")

TEMPLATED_OPENERS = ("i hope this email finds you well", "i hope this finds you well",
                     "i wanted to reach out", "i just wanted to reach out",
                     "i came across your", "to whom it may concern", "dear sir", "dear madam",
                     "hope you are doing well", "hope you're well")

# Different value angles so batch me har email fresh lage (roz same template nahi).
ANGLES = [
    "turning a week of support shifts into clean invoices without re-typing anything",
    "getting day/evening/weekend rate splits right on every invoice",
    "not leaving all the billing to a painful month-end pile-up",
    "keeping shift notes and records organised and easy to find later",
    "tracking travel kilometres for community access shifts accurately",
    "following up plan-managed invoices without losing track of what's been paid",
    "batching many shifts into fewer, clearer invoices",
]


def _angle(lead):
    key = (lead.get("domain") or lead.get("email") or lead.get("name") or "x").lower()
    return ANGLES[int(hashlib.md5(key.encode()).hexdigest(), 16) % len(ANGLES)]


def _biz():
    try:
        with open("knowledge/rayvice.json", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"positioning": "Rayvice: NDIS invoicing and admin software for Australian support providers."}


def build_messages(lead):
    biz = _biz()
    sender = config.OUTREACH_FROM_NAME or "Rayvice"
    angle = _angle(lead)
    system = (
        "You are writing a short, genuine one-to-one email as a real person at an Australian small business "
        f"(signing as '{sender}' from Rayvice). This is a friendly B2B note, NOT a newsletter and NOT an ad. "
        f"Product: {biz.get('positioning', 'NDIS invoicing/admin software for support providers')}. "
        "Pricing is about AUD 24-44/month with a 9-day free trial, no card. "
        "Audience: owners of small Australian NDIS support providers who manage a team of support workers. "
        "The email must feel personally written to THAT business. "
        "Use ONLY the business name, area and the context line provided. Do NOT invent or infer anything "
        "about their team size, growth, locations, clients, staff names or internal operations. If a detail "
        "isn't given, keep it general. "
        "Greeting rule: use the business name only if it reads naturally (separate words); if the name looks "
        "like one run-together word or a domain, greet with 'Hi there'. "
        "STRUCTURE: (1) one specific, human opening line that references their business name or area — no "
        "generic greetings; (2) name ONE real admin pain and briefly how Rayvice eases it; (3) one low-pressure "
        "call to action: invite them to try the free trial at rayvice.com (do NOT propose phone calls, meetings "
        "or ask them to reply 'demo'); (4) sign-off. "
        f"Focus on this ONE pain for this email: {angle}. Do not list other features. "
        "HARD RULES: Australian English spelling. Plain text only, no markdown, no HTML, no emojis. 55-90 words. "
        "Vary sentence structure naturally — do not sound templated. "
        "Do NOT use these openers: 'I hope this email finds you well', 'I wanted to reach out', "
        "'I came across your website', 'Dear Sir/Madam'. "
        "Never invent statistics, testimonials, customer numbers, names, or NDIS endorsement. Never guarantee "
        "compliance. Do not state NDIS price caps as fixed facts. No fear-based language, no fake urgency, "
        "no legal/tax advice. NEVER invent or guess a recipient's first name — if unknown, open with the "
        "business name or 'Hi there'. Do not claim to automate 'compliance' or guarantee correctness. "
        "No fake 'Re:' subject and do not pretend prior contact. "
        'Reply with ONLY JSON: {"subject":"...","body":"..."}. '
        "Subject must be 3-6 words, specific and calm (no ALL CAPS, no '!'). "
        "The body MUST end with exactly this signature, then the opt-out line on its own line:\n"
        f"Kind regards,\n{sender}\nrayvice.com\n"
        "If this isn't relevant, just reply \"stop\" and I won't email again."
    )
    user = (f"Recipient business: {lead.get('name') or 'this provider'}. "
            f"Located in {lead.get('suburb') or lead.get('state') or 'Australia'}. "
            f"Website: {lead.get('domain', '')}. "
            f"Context from their site: {(lead.get('snippet') or '')[:200]}")
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _extract_json(text):
    if not text:
        return None
    t = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        return json.loads(t)
    except Exception:
        pass
    m = re.search(r"\{.*\}", t, re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return None
    return None


def validate(subject, body):
    errs = []
    b = body or ""
    low = b.lower()
    if len(b.split()) < 45:
        errs.append("body too short")
    if len(b) > 1700:
        errs.append("body too long")
    if "rayvice" not in low:
        errs.append("no product mention")
    if "stop" not in low and "unsubscribe" not in low:
        errs.append("no opt-out line")
    if "<html" in low or "<p>" in low or "<div" in low:
        errs.append("html not allowed")
    for bad in BANNED:
        if bad in low:
            errs.append(f"banned phrase: {bad}")
    for op in TEMPLATED_OPENERS:
        if op in low[:120]:
            errs.append(f"templated opener: {op}")
    if not subject or len(subject) > 60:
        errs.append("subject missing/too long")
    if subject and subject.strip().lower().startswith("re:"):
        errs.append("fake Re: subject")
    return errs


def compose_email(lead):
    res = model_router.run_task("outreach", build_messages(lead))
    data = _extract_json(getattr(res, "text", "")) if getattr(res, "ok", False) else None
    if data is None:
        # one retry asking for JSON only
        msgs = build_messages(lead) + [
            {"role": "assistant", "content": (getattr(res, "text", "") or "")[:400]},
            {"role": "user", "content": "That was not valid JSON. Reply again with ONLY the JSON object."}]
        res2 = model_router.run_task("outreach", msgs)
        data = _extract_json(getattr(res2, "text", "")) if getattr(res2, "ok", False) else None
    if data is None:
        return {"ok": False, "error": "AI unavailable/junk output"}
    subject = str(data.get("subject") or "").strip()
    body = str(data.get("body") or "").strip()
    errs = validate(subject, body)
    if errs:
        return {"ok": False, "error": "validation: " + "; ".join(errs[:4]), "errors": errs}
    return {"ok": True, "subject": subject, "body": body, "model": getattr(res, "model", "")}
