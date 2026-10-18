"""Outreach orchestration: discover -> enrich -> compose -> queue -> send -> scan."""
import config
from social import db
from outreach import compose, mailer, sources, store

_GENERIC_NAME = ("ndis provider", "ndis service", "ndis agency", "ndis registered",
                 "registered ndis", "disability service", "disability support",
                 "home", "welcome", "homepage", "home page", "contact us", "contact",
                 "best ndis", "ndis support", "support services", "our services", "services")


def _clean_name(name, domain):
    n = (name or "").strip()
    for sep in ("|", ":", "–", "—", " - "):
        if sep in n:
            parts = [p.strip() for p in n.split(sep) if p.strip()]
            nong = [p for p in parts if not any(g in p.lower() for g in _GENERIC_NAME)]
            n = (nong[0] if nong else parts[-1]).strip()
            break
    low = n.lower().strip()
    if not n or any(g == low or low.startswith(g) for g in _GENERIC_NAME):
        return domain.split(".")[0].replace("-", " ").title() or "there"
    return n[:80]


def build_daily(count=None, states=None):
    """N naye leads + personalised emails QUEUE karo. Nothing sent here."""
    count = count or config.OUTREACH_DAILY_CAP
    states = states or config.OUTREACH_STATES
    db.ensure_schema()
    have = store.existing_domains()
    supp = store.suppressed_set()
    made, no_email = [], 0
    for c in sources.find_candidates(states):
        if len(made) >= count:
            break
        if c["domain"] in have:
            continue
        email, src_url, title = sources.discover_from_site(c["domain"])
        if not email:
            no_email += 1
            continue
        if email in supp or store.message_exists(email):
            continue
        lead = {**c, "email": email, "email_source": src_url,
                "name": _clean_name(title or c.get("name") or "", c["domain"])}
        lid = store.upsert_lead(lead)
        comp = compose.compose_email(lead)
        if not comp.get("ok"):
            store.set_lead_status(lid, "NO_COMPOSE", {"error": comp.get("error")})
            continue
        mid = store.log_message(lid, email, comp["subject"], comp["body"], status="QUEUED")
        if mid:
            made.append({**lead, "lead_id": lid, "message_id": mid,
                         "subject": comp["subject"], "body": comp["body"]})
    return {"ok": True, "generated": len(made), "items": made, "no_email": no_email}


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
            f"Leads: {s['leads']} (email mila: {s['with_email']})\n"
            f"Queued: {s['queued']} | Sent: {s['sent']} | Failed: {s['failed']}\n"
            f"Replies: {s['replied']} | Unsub: {s['unsub']} | Suppressed: {s['suppressed']}")
