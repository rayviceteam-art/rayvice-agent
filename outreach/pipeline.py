"""Outreach orchestration: discover -> enrich -> compose -> queue -> send -> scan."""
import html as _html
import re
from concurrent.futures import ThreadPoolExecutor

import config
from social import db
from outreach import compose, mailer, sources, store

_GENERIC_NAME = ("ndis provider", "ndis service", "ndis agency", "ndis registered",
                 "registered ndis", "disability service", "disability support",
                 "home", "welcome", "homepage", "home page", "contact us", "contact",
                 "best ndis", "ndis support", "support services", "our services", "services")
_GENERIC_DESC = ("ndis", "disability", "aged care", "allied health", "support service",
                 "home care", "community service", "care service", "provider")


def _is_generic_name(s):
    low = (s or "").lower().strip()
    if not low:
        return True
    if any(g in low for g in _GENERIC_DESC):
        return True
    if any(g == low or low.startswith(g) for g in _GENERIC_NAME):
        return True
    return len(s) > 40 or len(s.split()) > 4 or "," in s or "&" in s


def _clean_name(name, domain):
    n = _html.unescape(name or "").strip()
    n = re.sub(r"\s+", " ", n)
    for sep in ("|", "–", "—", " - ", ":", "·"):
        if sep in n:
            parts = [p.strip() for p in n.split(sep) if p.strip()]
            nong = [p for p in parts if not _is_generic_name(p)]
            n = (min(nong, key=len) if nong else parts[-1]).strip()
            break
    # "Personalised Aged Care, NDIS & Allied Health Services" -> pehla part agar tail descriptors ho
    if "," in n:
        head = n.split(",")[0].strip()
        tail = n[len(head):].lower()
        if len(head) >= 3 and any(k in tail for k in ("ndis", "service", "support", "care", "health")):
            n = head
    if _is_generic_name(n):
        return domain.split(".")[0].replace("-", " ").title() or "there"
    return n[:40]


def _rank_key(ce):
    """Candidate ko 'best' order me sort karo: ICP-ok, email hai, phir score."""
    ev = (ce[1] if len(ce) > 1 else {}) or {}
    icp = ev.get("icp") or {}
    return (1 if icp.get("ok") else 0, 1 if ev.get("email") else 0, icp.get("score", 0))


def build_daily(count=None, states=None, max_eval=None):
    """N naye leads + personalised emails QUEUE karo. Nothing sent here.

    Sirf wahi leads jinki site ICP gate pass kare (real NDIS support worker/provider).
    max_eval: kitni candidate sites evaluate karni hain — count ke hisaab se auto
    (30 leads chahiye to ~90 sites evaluate hoti hain).
    """
    count = count or config.OUTREACH_DAILY_CAP
    states = states or config.OUTREACH_STATES
    if max_eval is None:
        max_eval = min(120, max(40, count * 3))
    db.ensure_schema()
    prev = store.domain_status()
    supp = store.suppressed_set()
    made, no_email = [], 0
    rejected = 0
    # Pehle purane NO_COMPOSE leads retry karo (email already known hai, bina re-search).
    for r in store.leads_by_status("NO_COMPOSE", limit=count):
        if len(made) >= count:
            break
        lead = dict(r)
        if not lead.get("email"):
            continue
        lead["name"] = _clean_name(lead.get("name"), lead["domain"])  # purane generic names saaf karo
        comp = compose.compose_email(lead)
        if not comp.get("ok"):
            continue
        mid = store.log_message(lead["id"], lead["email"], comp["subject"], comp["body"], status="QUEUED")
        if mid:
            store.set_lead_status(lead["id"], "NEW")
            made.append({**lead, "lead_id": lead["id"], "message_id": mid,
                         "subject": comp["subject"], "body": comp["body"]})
    todo = [c for c in sources.find_candidates(states)
            if not prev.get(c["domain"]) or prev[c["domain"]][1] == "NO_COMPOSE"][:max_eval]
    evals = []
    if todo:
        with ThreadPoolExecutor(max_workers=6) as ex:
            evals = list(ex.map(lambda c: (c, sources.evaluate_site(c["domain"])), todo))
        evals.sort(key=_rank_key, reverse=True)  # best qualified leads pehle
    for c, ev in evals:
        if len(made) >= count:
            break
        name = _clean_name(ev["title"] or c.get("name") or "", c["domain"])
        lead = {**c, "email": ev["email"], "email_source": ev["source_url"], "name": name,
                "snippet": ev["text"] or c.get("snippet"), "notes": {"icp": ev["icp"]}}
        existing = prev.get(c["domain"])
        if not ev["icp"]["ok"]:
            lid = existing[0] if existing else store.upsert_lead(lead)
            store.set_lead_status(lid, "NOT_RELEVANT", {"icp": ev["icp"]})
            rejected += 1
            continue
        email = ev["email"]
        if not email:
            no_email += 1
            continue
        if email in supp or store.message_exists(email):
            continue
        lid = existing[0] if existing else store.upsert_lead(lead)
        comp = compose.compose_email(lead)
        if not comp.get("ok"):
            store.set_lead_status(lid, "NO_COMPOSE", {"error": comp.get("error"), "icp": ev["icp"]})
            continue
        mid = store.log_message(lid, email, comp["subject"], comp["body"], status="QUEUED")
        if mid:
            made.append({**lead, "lead_id": lid, "message_id": mid, "icp": ev["icp"],
                         "subject": comp["subject"], "body": comp["body"]})
    return {"ok": True, "generated": len(made), "items": made, "no_email": no_email, "rejected": rejected}


def build_followups(count=None, days=None):
    """Purane bheje emails (jinka reply nahi aaya) ke liye ek polite follow-up QUEUE karo."""
    count = count or config.OUTREACH_FOLLOWUP_CAP
    days = days if days is not None else config.OUTREACH_FOLLOWUP_DAYS
    db.ensure_schema()
    made = []
    for r in store.followup_candidates(days, limit=count):
        lead = dict(r)
        comp = compose.compose_followup(lead, lead.get("orig_subject"), lead.get("orig_body"))
        if not comp.get("ok"):
            continue
        mid = store.log_message(lead["lead_id"], lead["to_email"], comp["subject"], comp["body"],
                                status="QUEUED", followup=1, parent_id=lead["message_id"])
        if mid:
            made.append({**lead, "email": lead["to_email"], "message_id": mid,
                         "subject": comp["subject"], "body": comp["body"], "followup": 1})
    return {"ok": True, "generated": len(made), "items": made}


def send_daily(count=None, dry=None):
    """QUEUED messages bhejo (dry=True -> sirf list, kuch nahi jaata)."""
    count = count or config.OUTREACH_DAILY_CAP
    dry = config.OUTREACH_DRYRUN if dry is None else dry
    rows = [dict(r) for r in store.queued_messages(count)]
    sent, failed = 0, 0
    for r in rows:
        if dry:
            continue
        res = mailer.send_one(r["to_email"], r["subject"], r["body"])
        if res.get("ok"):
            store.mark_message(r["id"], "SENT")
            store.set_lead_status(r["lead_id"], "SENT")
            sent += 1
        else:
            store.mark_message(r["id"], "FAILED", res.get("error"))
            failed += 1
    return {"ok": True, "would_send": len(rows), "sent": sent, "failed": failed, "dry": dry, "items": rows}


def scan():
    return mailer.scan_inbox()


def format_preview(items, header=""):
    lines = [header or f"📬 Outreach preview — {len(items)} emails (kuch bheja nahi gaya)"]
    for i, it in enumerate(items, 1):
        lines.append("")
        tag = " ↪ follow-up" if it.get("followup") else ""
        lines.append(f"━━ {i}. {it.get('name', '')[:60]}{tag} ━━")
        lines.append(f"To: {it.get('email') or it.get('to_email', '')}")
        icp = it.get("icp") or {}
        if icp.get("strong"):
            lines.append(f"✓ NDIS-relevant ({', '.join(icp['strong'][:5])})")
        lines.append(f"Subject: {it.get('subject', '')}")
        lines.append((it.get("body") or "")[:1200])
    out = "\n".join(lines)
    return out[:3900] if len(out) > 3900 else out


def format_sent(items, sent, dry):
    kind = "DRY-RUN (kuch bheja nahi)" if dry else f"{sent} bheje gaye"
    lines = [f"📤 Outreach: {len(items)} queued — {kind}"]
    for it in items:
        lines.append(f"• {it.get('to_email', '')}  |  {it.get('subject', '')[:60]}")
    return "\n".join(lines)[:3900]


def status_text():
    s = store.stats()
    return ("📊 Outreach stats\n"
            f"Leads: {s['relevant']} relevant (email mila: {s['with_email']}) | skip: {s['not_relevant']}\n"
            f"Queued: {s['queued']} | Sent: {s['sent']} | Failed: {s['failed']}\n"
            f"Replies: {s['replied']} | Unsub: {s['unsub']} | Suppressed: {s['suppressed']}")
