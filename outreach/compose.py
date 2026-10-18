"""AI cold-email generation — short, personal, compliant (AU Spam Act 2003)."""
import json
import re

import config
import model_router

PROMPT_VERSION = "outreach-v1"

BANNED = ("guarantee", "100%", "risk-free", "risk free", "act now", "limited time",
          "final notice", "urgent", "no risk", "free money", "double your", "make $$$",
          "click here", "buy now", "limited offer", "winner", "congratulations you")


def _biz():
    try:
        with open("knowledge/rayvice.json", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"positioning": "Rayvice: NDIS invoicing and admin software for Australian support providers."}


def build_messages(lead):
    biz = _biz()
    sender = config.OUTREACH_FROM_NAME or "Rayvice"
    system = (
        "You write short, genuine one-to-one cold emails on behalf of an Australian small business owner "
        f"({sender} from Rayvice). Product: {biz.get('positioning', 'NDIS invoicing/admin software')}. "
        "Pricing ~AUD 24-44/mo, 9-day free trial, no card. Audience: owners of small NDIS support providers "
        "in Australia who manage a team of support workers. "
        "STRICT RULES: Australian English. Plain text only. 70-110 words. No markdown, no HTML, no emojis. "
        "Personal and specific to the recipient business name/area. Value-first: name ONE real admin pain "
        "(e.g. turning a week of support shifts into clean invoices, tracking day/evening/weekend rate splits, "
        "keeping records organised) and how Rayvice helps. ONE soft call to action: try the free trial at rayvice.com. "
        "Never invent statistics, testimonials, customer numbers or NDIS endorsement. Never guarantee compliance. "
        "Do not state NDIS price caps as fixed facts. No fear-based language, no fake urgency, no legal/tax advice. "
        "NEVER invent or guess a recipient's name — if no contact name is given, open with 'Hi there,' or the "
        "business name. Do not claim to automate 'compliance' or guarantee correctness; say it helps keep records "
        "organised and billing clean. "
        "No fake 'Re:' subject and do not pretend prior contact. "
        'Reply with ONLY JSON: {"subject":"...","body":"..."}. '
        "The body MUST end with exactly this signature block on its own lines, then the opt-out line:\n"
        f"Kind regards,\n{sender}\nrayvice.com\n"
        "If this isn't relevant, just reply \"stop\" and I won't email again."
    )
    user = (f"Recipient business: {lead.get('name') or 'this provider'}. "
            f"Located in {lead.get('suburb') or lead.get('state') or 'Australia'}. "
            f"Website: {lead.get('domain', '')}. "
            f"Context: {(lead.get('snippet') or '')[:200]}")
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
    if not subject or len(subject) > 90:
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
