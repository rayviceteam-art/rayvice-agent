"""Platform-specific content generation. Structured JSON in, validated draft out.

QUIET RULE (existing agent philosophy): AI fail/junk = kuch store/publish nahi.
Har platform ka apna native tone; same content unchanged cross-post NAHI hota.
"""
import json
import re
import uuid
from datetime import datetime, timezone

import config
import model_router
from social import db, validators

PROMPT_VERSION = "v1"

_RULES = {
    "instagram": ("Write an Instagram caption. First line = strong practical hook (max 12 words). "
                  "Body 90-150 words, short paragraphs, 1-2 relevant emojis max. End with a clear CTA "
                  "for the 9-day free trial of Rayvice (rayvice.com). 8-10 specific hashtags."),
    "facebook": ("Write a Facebook Page post. Conversational, helpful first line hook, 90-150 words, "
                 "practical value for Australian NDIS sole traders. Clear CTA to try Rayvice free "
                 "(9-day trial, no card). 2-4 hashtags max."),
    "linkedin": ("Write a professional LinkedIn post. Credible, specific, no hype. Hook line, then "
                 "120-200 words of practical insight for independent NDIS support workers. Clear but "
                 "modest CTA (Rayvice free trial). 3-5 hashtags."),
    "reddit": ("Write a Reddit self-post for an Australian NDIS/support-worker community. "
               "Educational, discussion-oriented, ZERO sales tone, no hashtags. Title <= 120 chars. "
               "Body 120-200 words sharing practical advice; Rayvice mention only if natural and "
               "honest, otherwise omit."),
}


def _schema_hint(platform):
    if platform == "reddit":
        return ('{"title": "...", "hook": "...", "body": "...", "cta": "...", "hashtags": [], '
                '"image_prompt": "..."}')
    return ('{"hook": "...", "body": "...", "cta": "...", "hashtags": ["..."], "image_prompt": "..."}')


def build_messages(platform, plan):
    biz_path = "knowledge/rayvice.json"
    try:
        with open(biz_path, encoding="utf-8") as f:
            biz = json.load(f)
    except Exception:
        biz = {"positioning": "Rayvice: NDIS invoicing/admin software for Australian sole traders."}
    system = (
        "You write social content for Rayvice, software for independent Australian NDIS support workers. "
        f"Product: {biz.get('positioning', '')}. Pricing ~AUD 24-44/mo, 9-day free trial no card. "
        "STRICT RULES: Australian English spelling. Never invent statistics, testimonials, customer numbers, "
        "revenue, partnerships, certifications, or NDIS endorsement. Never guarantee compliance or approval. "
        "Price rules/limits may change — do not state current NDIS price caps as fixed facts; speak about "
        "checking official sources. No fear-based marketing, no fake urgency, no legal/tax advice. "
        "Label any hypothetical scenario with '(Example)'. "
        f"Reply with ONLY valid JSON matching: {_schema_hint(platform)} — no markdown, no commentary."
    )
    user = (f"Platform: {platform}. {_RULES.get(platform, '')}\n"
            f"Content theme: {plan.get('theme')}. Topic: {plan.get('topic')}. "
            f"Category: {plan.get('category')}.")
    if plan.get("feature_key"):
        user += (f" Feature benefit to convey: {plan.get('feature_benefit', '')} "
                 "Describe only this generic capability — no invented UI details, numbers or screenshots.")
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _extract_json(text):
    if not text:
        return None
    t = text.strip()
    t = re.sub(r"^```(?:json)?|```$", "", t, flags=re.M).strip()
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


def _idempotency_key(platform, plan):
    return f"draft:{platform}:{plan.get('date')}:{validators.content_hash(plan.get('topic', ''))[:10]}"


def prior_texts_for(platform, limit=30):
    c = db.connect()
    rows = c.execute(
        "SELECT hook, body, cta FROM social_drafts WHERE platform=? ORDER BY ts DESC LIMIT ?",
        (platform, limit)).fetchall()
    c.close()
    return [" ".join([r["hook"] or "", r["body"] or "", r["cta"] or ""]) for r in rows]


def generate_draft(platform, plan, allow_retry=True):
    """Returns dict: {ok, draft_id|error, errors, warnings, draft}. Stores only clean drafts."""
    platform = (platform or "").lower()
    if platform == "x":
        return {"ok": False, "error": "X is BLOCKED_API_ACCESS (no free tier) — generation skipped"}

    key = _idempotency_key(platform, plan)
    c = db.connect()
    row = c.execute("SELECT id, media_id, status FROM social_drafts WHERE idempotency_key=?", (key,)).fetchone()
    c.close()
    if row:
        return {"ok": False, "error": f"draft already exists for today ({row['id']})", "duplicate": True,
                "draft_id": row["id"], "media_id": row["media_id"] or "", "draft_status": row["status"]}

    res = model_router.run_task("draft", build_messages(platform, plan))
    data = _extract_json(res.text) if getattr(res, "ok", False) else None
    if data is None and allow_retry:
        msgs = build_messages(platform, plan) + [
            {"role": "assistant", "content": (getattr(res, "text", "") or "")[:500]},
            {"role": "user", "content": "That was not valid JSON. Reply again with ONLY the JSON object."}]
        res2 = model_router.run_task("draft", msgs)
        data = _extract_json(res2.text) if getattr(res2, "ok", False) else None
    if data is None:
        err = getattr(res, "error", "AI unavailable") or "AI gave junk output"
        return {"ok": False, "error": f"draft skipped (no junk stored): {err}"[:300]}

    body = str(data.get("body") or "").strip()
    if len(body.split()) < 40:
        return {"ok": False, "error": "draft skipped: too short / malformed AI output"}

    check = validators.validate(platform, hook=str(data.get("hook") or ""), body=body,
                                cta=str(data.get("cta") or ""), hashtags=data.get("hashtags") or [],
                                title=str(data.get("title") or ""),
                                prior_texts=prior_texts_for(platform))
    n = check["normalised"]
    if check["errors"]:
        return {"ok": False, "error": "validation failed: " + "; ".join(check["errors"][:4]),
                "errors": check["errors"], "warnings": check["warnings"]}

    did = "s_" + uuid.uuid4().hex[:10]
    full = "\n\n".join(x for x in [n["hook"], n.get("title") or "", n["body"], n["cta"]] if x)
    chash = validators.content_hash(full)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    c = db.connect()
    try:
        c.execute("INSERT INTO social_drafts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (did, ts, plan.get("idea_id") or "", platform, "text+image",
                   n["hook"], n["body"], n["cta"], json.dumps(n["hashtags"]),
                   "", "READY", json.dumps({"warnings": check["warnings"]}),
                   getattr(res, "model", ""), PROMPT_VERSION, key, chash))
        c.commit()
    except Exception as e:
        c.close()
        return {"ok": False, "error": f"DB insert failed: {e}"}
    c.close()
    return {"ok": True, "draft_id": did, "errors": [], "warnings": check["warnings"],
            "draft": {"platform": platform, "hook": n["hook"], "title": n.get("title") or "",
                      "body": n["body"], "cta": n["cta"], "hashtags": n["hashtags"],
                      "image_prompt": str(data.get("image_prompt") or plan.get("topic") or "")}}
