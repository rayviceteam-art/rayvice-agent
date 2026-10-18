"""Daily group content kit — text-only NDIS posts + comment drafts for FB groups & IG captions.

Meta Group API is closed (2019 se band), isliye agent khud groups me post/comment NAHI karta.
Ye module roz fresh, quality content tayyar karta hai jo owner khud groups me paste karta hai.
Group posts/comments me ZERO promo (brand = profile); soft CTA sirf IG captions me.

- 6 pillars x day-of-year rotation -> 5 posts/day, har din badalte hue
- Dedup: last 30 kits ke texts se overlap check (Jaccard)
- QUIET RULE: LLM fail -> hand-written template kit (kit kabhi khali nahi jaata)
"""
import json
import re

import model_router
from social import calendar, db, validators

PROMPT_VERSION = "kit-v1"

PILLARS = [
    ("practical_tip",
     "one specific, practical NDIS admin tip for support workers (record-keeping, travel km, evidence, invoice timing)"),
    ("myth_vs_fact",
     "bust a common myth about NDIS invoicing or claiming, gently and factually"),
    ("checklist",
     "a short 3-4 point checklist support workers can use this week"),
    ("question",
     "a genuine engagement question for support workers (biggest admin frustration etc.) — invite replies"),
    ("common_mistake",
     "a common mistake sole traders make with NDIS admin and how to avoid it"),
    ("worker_wellbeing",
     "something supportive for support workers themselves (burnout, boundaries, time mindset) — zero business promotion"),
]

COMMENT_THEMES = [
    "a new sole trader asking how to start invoicing participants for the first time",
    "someone confused about claiming travel kilometres for community access shifts",
    "a worker unsure how evening/weekend rate splits should appear on an invoice",
    "a question about what to write in progress notes so claims are not queried",
    "a plan manager has not paid an invoice and the worker asks what to do next",
    "a worker asking when to check the latest NDIS pricing arrangements",
]

FALLBACK_POSTS = {
    "practical_tip":
        "A small habit that saves hours: keep a notes app open during every shift and jot the essentials "
        "before you leave — time in and out, travel kilometres, what you did, goals progressed, anything "
        "out of the ordinary. By invoice day your progress notes and invoice practically write themselves. "
        "It takes about 60 seconds per shift and saves a whole evening at month-end.",
    "myth_vs_fact":
        "Myth: \"I should wait until the end of the month to invoice — that's how everyone does it.\" "
        "Fact: there's no rule saying NDIS invoices must be monthly. For many sole traders, invoicing "
        "weekly or per plan manager cycle means faster cash flow and less month-end chaos. (Example) If a "
        "plan manager pays on a fortnightly cycle, weekly invoices often land in the next cycle instead of "
        "waiting behind a pile of month-end paperwork.",
    "checklist":
        "Quick end-of-week checklist for support workers: 1) every shift has a start and end time recorded, "
        "2) travel kilometres noted for community access, 3) progress notes done same day where possible, "
        "4) any unusual shift (public holiday, evening, weekend) flagged so the right rate is used at "
        "invoice time. Ten minutes now saves an hour later.",
    "question":
        "Honest question for the support workers here: what is the single most frustrating part of your "
        "admin? For most people it's either progress notes or chasing invoicing at month-end. Curious what "
        "it looks like in your week — the answer usually shows you exactly what to fix first.",
    "common_mistake":
        "One of the most common invoicing mistakes: dating the invoice the day the shift happened, then "
        "sending it three weeks later. It confuses plan managers and can push payment into the next cycle. "
        "Keep it simple — shift dates live in your records, the invoice date is the day you actually send it.",
    "worker_wellbeing":
        "A gentle reminder: \"no\" is a complete sentence. If a shift change leaves you without a real "
        "break, it's okay to say that doesn't work for you. Sustainable support work means protecting your "
        "own energy too — participants get the best version of you when you're not running on empty.",
}

FALLBACK_COMMENTS = [
    ("new sole trader invoicing",
     "Welcome to the fold. The basics that keep it smooth: ABN sorted, a simple service agreement, and "
     "invoices that clearly show date, support item, hours and any travel. Keep every invoice to one "
     "page where you can — plan managers love clean, consistent invoices."),
    ("travel kilometres",
     "Travel between participant activities can often be claimed when it's directly related to the "
     "support you deliver. Note start and end odometer or distance each shift, and be consistent — the "
     "current pricing arrangements explain the exact rules for your registration group."),
    ("evening/weekend rate splits",
     "Evening and weekend shifts often attract higher rates, and splits confuse people because time "
     "crosses a boundary. Easiest fix: give each part its own line on the invoice — date, start and "
     "finish, the rate applied — instead of one lumped total."),
    ("progress notes",
     "Best habit: same day, plain language, and cover what you did, goals progressed, outcomes, and any "
     "incidents. Specific beats long. Short accurate notes you actually keep up with are worth more than "
     "essays written two weeks later."),
    ("unpaid invoice",
     "Follow up in writing with the plan manager, quote the invoice number and due date, and ask for "
     "their payment schedule. If it drags, keep a paper trail and escalate politely — most late payments "
     "are admin backlog, not refusal."),
    ("pricing arrangements check",
     "Good moment to check: before you set rates or prepare invoices each quarter, look at the latest "
     "pricing arrangements on the official NDIA site — updates land there first. Five minutes of checking "
     "saves invoice corrections later."),
]

FALLBACK_CAPTIONS = [
    {"text": "Admin shouldn't take longer than the shift itself. From logging hours and travel kilometres "
             "to rate splits and a clean invoice, Rayvice keeps the paperwork sorted so you can focus on "
             "support. 9-day free trial at rayvice.com",
     "hashtags": ["#NDIS", "#SupportWorker", "#NDISProvider", "#DisabilitySupport", "#Invoicing",
                  "#SoleTrader", "#Rayvice"]},
    {"text": "Small habit, big difference: record the details before you leave each shift — times, "
             "kilometres, what you worked on. Invoice day becomes a ten minute job instead of a lost "
             "evening. Try Rayvice free for 9 days, no card needed.",
     "hashtags": ["#NDISBusiness", "#SupportWorkers", "#NDISAdmin", "#NDISAustralia", "#PlanManager",
                  "#Rayvice"]},
]


def pillars_for(day):
    """Day-of-year se 5-pillar rotation — roz badalta hai."""
    d = day
    if isinstance(d, str):
        try:
            from datetime import date as _date
            d = _date.fromisoformat(d[:10])
        except Exception:
            d = None
    if d is None or not hasattr(d, "timetuple"):
        d = calendar.today_local()
    start = d.timetuple().tm_yday % len(PILLARS)
    return [PILLARS[(start + i) % len(PILLARS)] for i in range(5)]


def _words(text):
    return set(re.findall(r"[a-z']{3,}", (text or "").lower()))


def _overlap(a, b):
    wa, wb = _words(a), _words(b)
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / max(1, len(wa | wb))


def prior_texts(limit=30):
    c = db.connect()
    rows = c.execute("SELECT payload FROM social_group_kit ORDER BY date DESC LIMIT ?", (limit,)).fetchall()
    c.close()
    out = []
    for r in rows:
        try:
            p = json.loads(r["payload"])
            out += [x.get("text", "") for x in p.get("posts", [])]
            out += [x.get("reply", "") for x in p.get("comments", [])]
        except Exception:
            continue
    return out


def _build_prompt(exclude_hint=""):
    pil = "\n".join(f"- {k}: {v}" for k, v in PILLARS)
    themes = "\n".join(f"- {t}" for t in COMMENT_THEMES)
    system = (
        "You are a respected Australian NDIS community contributor (not a marketer), writing for Facebook "
        "groups where independent support workers and providers hang out. STRICT RULES: Australian English. "
        "Never invent statistics, testimonials, endorsements, certifications or NDIS approval. Never "
        "guarantee compliance. NEVER state specific NDIS rules, rates, distances, or claim conditions as "
        "fixed facts — instead say it's worth checking the latest official guidance for your situation. "
        "No legal, tax or financial advice. No fear-based language (no 'audit red flags', 'penalties', "
        "'crackdown'), no fake urgency. Label hypothetical situations with '(Example)'. NO promotion, NO "
        "links, NO brand or product names in posts and comments — pure value only (their profile is the "
        "brand). Max 1 emoji per item, plain text. Reply with ONLY valid JSON, no markdown:\n"
        '{"posts":[{"pillar":"...","text":"..."}x5],"comments":[{"topic":"...","reply":"..."}x5],'
        '"ig_captions":[{"text":"...","hashtags":["..."]}x2]}'
    )
    user = (
        f"Write one post for EACH of these 5 pillars (60-110 words each):\n{pil}\n\n"
        f"Write 5 helpful comment replies (2-4 sentences each, kind and specific) for these situations:\n{themes}\n\n"
        "Write 2 Instagram captions (60-100 words, NO hashtags inside the text — hashtags only in the "
        "hashtags array). These MAY softly mention Rayvice free trial (rayvice.com) once, plus 5-8 "
        "hashtags each."
    )
    if exclude_hint:
        user += f"\n\nAvoid reusing these angles/sentences:\n{exclude_hint[:800]}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _extract_json(text):
    if not text:
        return None
    t = re.sub(r"^```(?:json)?|```$", "", (text or "").strip(), flags=re.M).strip()
    try:
        return json.loads(t)
    except Exception:
        pass
    m = re.search(r"\{.*\}", t, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def _validate_item(platform, text, hashtags=None):
    r = validators.validate(platform, body=text or "", hashtags=hashtags or [])
    return not r["errors"], r["errors"]


def _clean_llm_kit(data, pillars):
    """LLM output -> validated kit dict, warna None. Ghatiya/kam items -> fallback items."""
    if not isinstance(data, dict):
        return None, "not a dict"
    posts, comments, caps = [], [], []
    by_pillar = {}
    for p in data.get("posts") or []:
        if isinstance(p, dict) and p.get("text"):
            by_pillar[str(p.get("pillar") or "").strip().lower()] = str(p["text"]).strip()
    for key, _desc in pillars:
        txt = by_pillar.get(key, "")
        n = len(txt.split())
        if not (40 <= n <= 170):
            txt = FALLBACK_POSTS[key]
        good, _errs = _validate_item("facebook", txt)
        posts.append({"pillar": key, "text": txt if good else FALLBACK_POSTS[key]})
    for i, c in enumerate((data.get("comments") or [])[:6]):
        if isinstance(c, dict) and c.get("reply"):
            txt = str(c["reply"]).strip()
        else:
            txt = ""
        n = len(txt.split())
        if not (15 <= n <= 120):
            txt = FALLBACK_COMMENTS[i % len(FALLBACK_COMMENTS)][1]
        good, _errs = _validate_item("facebook", txt)
        topic = str((c or {}).get("topic") or COMMENT_THEMES[i % len(COMMENT_THEMES)]) if isinstance(c, dict) else ""
        comments.append({"topic": topic, "reply": txt if good else FALLBACK_COMMENTS[i % len(FALLBACK_COMMENTS)][1]})
    while len(comments) < 5:
        fb = FALLBACK_COMMENTS[len(comments) % len(FALLBACK_COMMENTS)]
        comments.append({"topic": fb[0], "reply": fb[1]})
    for i, c in enumerate((data.get("ig_captions") or [])[:2]):
        txt = str(c.get("text") or "").strip() if isinstance(c, dict) else ""
        tags = [t.strip() for t in (c.get("hashtags") or []) if t and t.strip()] if isinstance(c, dict) else []
        tags = [t if t.startswith("#") else "#" + t for t in tags]
        inline = re.findall(r"#\w+", txt)
        if inline:
            txt = re.sub(r"\s*#\w+", "", txt).strip()
            for t in inline:
                if t not in tags:
                    tags.append(t)
        seen = set()
        tags = [t for t in tags if not (t.lower() in seen or seen.add(t.lower()))]
        n = len(txt.split())
        if not (40 <= n <= 140) or not (4 <= len(tags) <= 8):
            caps.append(FALLBACK_CAPTIONS[i])
            continue
        good, _errs = _validate_item("instagram", txt, tags[:8])
        caps.append({"text": txt, "hashtags": tags[:8]} if good else FALLBACK_CAPTIONS[i])
    while len(caps) < 2:
        caps.append(FALLBACK_CAPTIONS[len(caps)])
    return {"posts": posts, "comments": comments, "ig_captions": caps}, ""


def _dedup_fix(kit, priors):
    """Agar koi item past 30 kits se zyada milta hai to us pillar ka fallback lagao."""
    changed = []
    for p in kit["posts"]:
        if any(_overlap(p["text"], old) > 0.55 for old in priors):
            fb = FALLBACK_POSTS.get(p["pillar"])
            if fb and _overlap(fb, p["text"]) < 0.9:
                p["text"] = fb
                changed.append(p["pillar"])
    for c in kit["comments"]:
        if any(_overlap(c["reply"], old) > 0.55 for old in priors):
            for topic, reply in FALLBACK_COMMENTS:
                if _overlap(reply, c["reply"]) < 0.9:
                    c["reply"] = reply
                    changed.append("comment")
                    break
    return changed


def generate_kit(day=None, use_llm=True):
    """LLM se kit banao (1 retry), fail -> template fallback. Returns (kit, source)."""
    pillars = pillars_for(day)
    priors = prior_texts()
    last_kit = None
    if use_llm:
        for attempt in range(2):
            msgs = _build_prompt(exclude_hint="" if attempt == 0 else "; ".join(priors[:4]))
            res = model_router.run_task("draft", msgs, timeout=90)
            data = _extract_json(getattr(res, "text", "")) if getattr(res, "ok", False) else None
            kit, err = _clean_llm_kit(data, pillars)
            if kit:
                hits = _dedup_fix(kit, priors)
                if not hits:
                    return kit, "llm"
                last_kit = kit
    if last_kit:
        return last_kit, "llm"
    kit = {
        "posts": [{"pillar": key, "text": FALLBACK_POSTS[key]} for key, _ in pillars],
        "comments": [{"topic": t, "reply": r} for t, r in FALLBACK_COMMENTS[:5]],
        "ig_captions": list(FALLBACK_CAPTIONS),
    }
    return kit, "template"


def build_kit(day=None, force=False, use_llm=True):
    """Aaj ka kit: DB me hai to wahi return, warna generate + store."""
    db.ensure_schema()
    d = str(day or calendar.today_local())
    c = db.connect()
    row = c.execute("SELECT * FROM social_group_kit WHERE date=?", (d,)).fetchone()
    c.close()
    if row and not force:
        try:
            payload = json.loads(row["payload"])
        except Exception:
            payload = None
        if payload:
            return {"ok": True, "date": d, "kit": payload, "source": payload.get("source", ""),
                    "already_sent": bool(row["sent_at"]), "row": dict(row)}
    kit, source = generate_kit(day=d, use_llm=use_llm)
    payload = dict(kit)
    payload["source"] = source
    c = db.connect()
    c.execute("INSERT OR REPLACE INTO social_group_kit VALUES(?,?,?,?,?,?)",
              (d, db.utcnow(), "", "GENERATED", PROMPT_VERSION, json.dumps(payload, ensure_ascii=False)))
    c.commit()
    c.close()
    return {"ok": True, "date": d, "kit": payload, "source": source, "already_sent": False, "row": {}}


def format_messages(res):
    """Kit -> Telegram messages (har ek <= 3900 chars)."""
    kit = res.get("kit") or {}
    posts = kit.get("posts") or []
    comments = kit.get("comments") or []
    caps = kit.get("ig_captions") or []
    tag = "LLM" if kit.get("source") == "llm" else "template"
    msgs, cur = [], [f"🗂 Aaj ka Group Content Kit — {res.get('date', '')} ({tag})"]
    cur.append("5 posts + 5 comment replies + 2 IG captions. Sab English, text-only.")
    cur.append("Groups me paste karo — roz naya content aayega.\n")
    for i, p in enumerate(posts, 1):
        block = f"━━ {i}. [{p.get('pillar', '')}] ━━\n{p.get('text', '')}\n"
        if sum(len(x) for x in cur) + len(block) > 3800:
            msgs.append("\n".join(cur))
            cur = []
        cur.append(block)
    msgs.append("\n".join(cur))
    cur = ["💬 Comment replies (kisi bhi sawal wale post pe paste karo):\n"]
    for i, c in enumerate(comments, 1):
        block = f"── {i}. {c.get('topic', '')} ──\n{c.get('reply', '')}\n"
        if sum(len(x) for x in cur) + len(block) > 3800:
            msgs.append("\n".join(cur))
            cur = []
        cur.append(block)
    msgs.append("\n".join(cur))
    cur = ["📸 Instagram captions (plain card/photo ke saath ya story me):\n"]
    for i, c in enumerate(caps, 1):
        tags = " ".join(c.get("hashtags") or [])
        block = f"── IG {i} ──\n{c.get('text', '')}\n{tags}\n"
        if sum(len(x) for x in cur) + len(block) > 3800:
            msgs.append("\n".join(cur))
            cur = []
        cur.append(block)
    msgs.append("\n".join(cur))
    return [m.strip()[:3900] for m in msgs if m.strip()]


def send_kit(res, resend=False, dry=False):
    """Telegram pe bhejo + DB me SENT mark karo. Returns message count (dry me 0)."""
    if res.get("already_sent") and not resend:
        return 0
    msgs = format_messages(res)
    if dry:
        return 0
    import telegram_bot
    sent = 0
    for m in msgs:
        try:
            telegram_bot.send(m)
            sent += 1
        except Exception:
            break
    if sent == len(msgs):
        c = db.connect()
        c.execute("UPDATE social_group_kit SET sent_at=?, status='SENT' WHERE date=?",
                  (db.utcnow(), res["date"]))
        c.commit()
        c.close()
    return sent
