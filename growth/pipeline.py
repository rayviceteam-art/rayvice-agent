"""GrowthAgent daily pipeline. Low-risk auto, external send = approval only."""
from logs_sys import audit, info
import tasks
import approvals
import research
import memory as mem
from growth import leads, content, monitor, reports
from growth.learning import record_outcome
import telegram_bot

NDIS_TOPICS = ["NDIS invoicing sole trader", "NDIS support worker admin paperwork",
               "NDIS pricing arrangement 2026", "NDIS billing software Australia"]

CONTENT_TOPICS = [
    "Sunday invoice admin pain (Example)",
    "Evening rate split confusion (Example)",
    "Spreadsheet to trial in 30 sec (Example)",
    "Plan Manager rejection over one wrong line (Example)",
    "Trial limits explained: 9 days, 1 participant (Example)",
    "Support worker Sunday: admin vs care hours (Example)",
]

def pick_topic():
    """14-day no-repeat rotation. QUIET RULE: same topic dobara nahi."""
    import datetime
    used = mem.read("marketing").get("used_topics", [])
    cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=14)).isoformat()
    recent = {u["topic"] for u in used if u.get("date", "") >= cutoff}
    for t in CONTENT_TOPICS:
        if t not in recent:
            return t
    return CONTENT_TOPICS[datetime.datetime.utcnow().day % len(CONTENT_TOPICS)]

def morning_research():
    tid = tasks.create("morning.research", risk_level="LOW")
    tasks.set_status(tid, "RUNNING")
    found = []
    for q in NDIS_TOPICS[:3]:
        for r in research.web_search(q, 4):
            if r.get("text"):
                found.append(r["text"][:200])
    mem.append_list("marketing", "signals", {"n": len(found), "sample": found[:5]})
    tasks.set_status(tid, "COMPLETED", result=f"{len(found)} signals")
    audit("growth", tid, "research", str(NDIS_TOPICS), f"{len(found)} signals", "AUTO", "", "", "")
    record_outcome("research", f"{len(found)} signals", "stored")
    return found

def daily_content():
    tid = tasks.create("daily.content", risk_level="LOW")
    tasks.set_status(tid, "RUNNING")
    topic = pick_topic()
    pid, text, errs = content.draft_post(topic, "billing-edu")
    if not pid:
        # QUIET RULE: AI fail/junk = kuch mat bhej, audit karke chup.
        tasks.set_status(tid, "COMPLETED", result=f"skipped: {text}"[:500])
        audit("growth", tid, "content", topic, "skipped, no junk sent", "SKIPPED", "", "", "")
        return None, None, None, text
    import datetime
    mem.append_list("marketing", "used_topics", {"topic": topic, "date": datetime.datetime.utcnow().isoformat()})
    content.set_status(pid, "APPROVAL_REQUIRED")
    aid, msg = approvals.request_approval("content.publish-manual", pid, f"Daily draft {pid}, checks: {errs}",
                                          "Owner posts MANUALLY to X/LinkedIn/Reddit. No auto-post.",
                                          "MEDIUM", text[:3000])
    tasks.set_status(tid, "COMPLETED", result=pid)
    audit("growth", tid, "content", topic, pid, "WAIT_FOR_OWNER", "PENDING", "", "")
    return pid, aid, msg, text

def website_check_and_alert():
    res = monitor.check_all()
    for name, r in res.items():
        if not r.get("ok"):
            aid, msg = approvals.request_approval("website.investigate", name,
                                                  f"DOWN hai bhai: {r.get('error')}", "Tu haan bolega tabhi investigate/fix karunga.",
                                                  "HIGH", str(r)[:1000])
            telegram_bot.send(f"⚠️ Bhai website DOWN hai: {name}\n{r.get('error')}\n{msg[:1500]}")
    return res

def run_daily(notify=True):
    from growth import hunt as _hunt
    signals = morning_research()
    pid, aid, msg, text = daily_content()
    web = website_check_and_alert()
    due = leads.followups_due()
    rep = reports.build()
    if notify:
        # QUIET RULES: draft bana tabhi bhej; hunt me kuch mila tabhi bhej;
        # report bilkul khaali ho AUR kuch aur nahi bheja to mat bhej.
        sent_anything = False
        if pid:
            telegram_bot.send(f"📝 Aaj ka post draft [{pid}] ready hai bhai, approval {aid}:\n{text[:2500]}\n\nPadh le, thik lage to APPROVE {aid} bhej aur khud manually post kar de.")
            sent_anything = True
        items = _hunt.hunt_leads()
        if items:
            telegram_bot.send(_hunt.digest_text(items)[:3900])
            sent_anything = True
        if due:
            telegram_bot.send(f"Follow-ups due: {len(due)}\n" + "\n".join(
                f"{l['lead_id']} | {l.get('name')} | {l.get('next_followup')}" for l in due[:10]))
            sent_anything = True
        if sent_anything or not reports.is_quiet_day():
            telegram_bot.send(rep)
        else:
            audit("growth", "-", "run_daily", "", "all quiet, nothing sent", "SKIPPED", "", "", "")
    return {"signals": len(signals), "draft": pid, "web": web, "followups": len(due)}
