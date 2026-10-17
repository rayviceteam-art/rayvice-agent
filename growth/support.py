"""Customer support: draft answers, escalate risky. Never legal/financial advice."""
import json
import os
import model_router

INTENTS = ["PRODUCT_QUESTION", "PRICING", "TRIAL", "FEATURE", "TECHNICAL",
           "SALES", "OBJECTION", "SUPPORT", "COMPLAINT", "REFUND",
           "PARTNERSHIP", "SPAM", "UNKNOWN"]

ESCALATE = ("legal", "regulatory", "financial advice", "ndis policy uncertain",
            "security incident", "account ownership", "refund exception")

def classify(text):
    t = text.lower()
    if "price" in t or "cost" in t or "$" in t:
        return "PRICING"
    if "trial" in t or "free" in t:
        return "TRIAL"
    if "refund" in t:
        return "REFUND"
    if "bug" in t or "error" in t or "login" in t:
        return "TECHNICAL"
    if "expensive" in t or "spreadsheet" in t:
        return "OBJECTION"
    return "UNKNOWN"

def draft_reply(message):
    intent = classify(message)
    if any(k in message.lower() for k in ESCALATE):
        return intent, "WAIT_FOR_OWNER", "Escalated: needs owner (legal/financial/security). Draft: I'll check that and get back to you."
    with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), "knowledge", "rayvice.json"), encoding="utf-8") as f:
        biz = json.load(f)
    prompt = [
        {"role": "system", "content": f"Support for {biz['company']}: {biz['positioning']} Pricing {biz['pricing_aud_per_month']} AUD/mo, {biz['trial']}. If unknown say I'll check and get back. Never invent."},
        {"role": "user", "content": f"Intent {intent}. Message: {message}. Draft 3-line helpful reply."},
    ]
    res = model_router.run_task("draft", prompt)
    if res.ok:
        return intent, "DRAFT_READY", res.text
    return intent, "DRAFT_READY", "Thanks for asking — I'll check that and get back to you. (AI offline fallback)"
