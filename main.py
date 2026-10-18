"""Rayvice Agent Core: USER -> Agent -> Planner -> Memory -> Tool -> Verify -> Approval -> Audit."""
import sys
import config
import tasks
import approvals
import scheduler
from logs_sys import info, audit
import telegram_bot

def execute_job(job):
    name = job["name"]
    try:
        if name == "website.check":
            from growth.pipeline import website_check_and_alert
            res = website_check_and_alert()
            return f"website check: {res}"
        if name == "morning.research":
            from growth.pipeline import morning_research
            sig = morning_research()
            return f"research: {len(sig)} signals"
        if name == "daily.content":
            from growth.pipeline import daily_content
            pid, aid, msg, text = daily_content()
            if not pid:
                return f"draft skipped (no junk sent): {text}"[:300]
            telegram_bot.send(f"📝 Aaj ka post draft [{pid}] ready hai bhai, approval {aid}:\n{text[:2500]}\n\nPadh le, APPROVE {aid} bhej, fir khud manually post kar dena.")
            return f"draft {pid} approval {aid}"
        if name == "lead.hunt":
            from growth import hunt as _hunt
            items = _hunt.hunt_leads()
            if not items:
                return "hunt: 0 opportunities, nothing sent (quiet rule)"
            telegram_bot.send(_hunt.digest_text(items)[:3900])
            return f"hunt: {len(items)} opportunities"
        if name == "evening.report":
            from growth import reports
            if reports.is_quiet_day():
                return "evening report skipped: quiet day, nothing to report"
            telegram_bot.send(reports.build())
            return "evening report sent"
        if name in ("weekly.report", "monthly.summary"):
            from growth import reports
            rep = reports.build()
            telegram_bot.send(rep)
            return "report sent"
    except Exception as e:
        return f"job {name} failed (non-fatal): {e}"
    return f"job {name} done"

def _biz_context():
    try:
        import json as _js
        with open("knowledge/rayvice.json", encoding="utf-8") as f:
            b = _js.load(f)
        return (f"{b.get('company')}: {b.get('positioning')} Price ~{b.get('pricing_aud_per_month')} AUD/mo. "
                f"Trial: {b.get('trial')}. Site: {b.get('site')}. {b.get('caution', '')}")
    except Exception:
        return "Rayvice: NDIS sole-trader billing software, Australia."

def chat_reply(text):
    """Free-form baat-cheet meri tarah: samajh ke Hinglish jawab. Action dikhe to approval."""
    import re as _re
    # 1) Action intent with concrete id? seedha approval banao, bakwaas nahi.
    lid = _re.search(r"l_[a-f0-9]{8}", text)
    pid = _re.search(r"p_[a-f0-9]{8}", text)
    low = text.lower()
    action_verb = any(w in low for w in ("bhej", "post", "publish", "send", "deploy", "outreach", "approve"))
    if lid and action_verb:
        from growth import outreach as _out
        aid, msg = _out.queue_outreach(lid.group(0))
        return (msg + "\n\nYaad rahe bhai: msg tu khud bhejega, agent nahi bhejega.")[:3900]
    if pid and any(w in low for w in ("post", "publish", "bhej")):
        aid, msg = approvals.request_approval("content.publish-manual", pid.group(0),
                                              "Owner ne publish ko bola", "Owner manually post karega.",
                                              "MEDIUM", text[:1000])
        return (msg + "\nDraft ready hai, APPROVE karke khud post kar dena bhai.")[:3900]
    if "deploy" in low and ("kar" in low or "karde" in low or "do" in low):
        aid, msg = approvals.request_approval("deploy.production", "rayvice-backend",
                                              "Owner ne deploy ko bola", "Tests + plan ke baad hi deploy.",
                                              "CRITICAL", text[:1000])
        return (msg + "\nProd deploy bina approval ke kabhi nahi hoga bhai.")[:3900]
    # 2) Warna AI se samajh ke jawab (meri tarah)
    import converse as _conv
    import model_router as _router
    try:
        import scheduler as _sched
        _tt = _sched.timetable()
    except Exception:
        _tt = "08:00 research, 09:30 post draft, 10:00 lead hunt, har 6h website check, 20:00 report"
    system = (
        f"Tu Rayvice ka personal AI operator hai, owner se Roman Hinglish me baat karta hai "
        f"(jaise 'samajh gaya bhai', simple shabd, chhoti lines). Context: {_biz_context()} "
        f"Tera roz ka time-table (khud automatic chalta hai): {_tt} "
        f"Tere Telegram commands: health, status, report, queue, tasks, draft <topic>, hunt, leads, "
        f"outreach <lead_id>, followups, check site, deploy, bugs, analytics, feedback, schedule, pause, resume, mode. "
        f"Rules: customer post/msg English me hote hai (Aussie audience), owner se Hinglish. "
        f"Jo nahi pata use UNKNOWN bol, invent mat kar (price/feature/testimonial/revenue). "
        f"2-5 line me jawab de, lamba lecture mat de. "
        f"Agar user bhejne/post/delete/deploy karne ko bole to khud mat kar — puch kaunsa wala, "
        f"approval banaunga; yaad dila: queue/outreach/draft commands. "
        f"Secrets (API keys/tokens) kabhi mat maang, kabhi mat dikha."
    )
    msgs = [{"role": "system", "content": system}] + _conv.history(8) + [{"role": "user", "content": text}]
    tid = tasks.create("chat: " + text[:60], risk_level="LOW")
    tasks.set_status(tid, "RUNNING")
    res = None
    err = ""
    try:
        res = _router.run_task("chat", msgs, timeout=45)
    except Exception as e:
        err = str(e)[:200]
    if res is not None and res.ok and res.text.strip():
        txt = res.text.strip()
        # Validation: free-router kabhi safety-preface jaisa kachra de deta hai — ek retry
        if len(txt) < 15 or txt.lower().startswith("user safety"):
            try:
                res2 = _router.run_task("chat", msgs + [{"role": "user", "content": "Seedha jawab do bhai, short me."}], timeout=45)
                if res2 is not None and res2.ok and len(res2.text.strip()) >= 15 and not res2.text.strip().lower().startswith("user safety"):
                    txt = res2.text.strip()
                    res = res2
                else:
                    raise ValueError("retry bhi kharab")
            except Exception:
                tasks.set_status(tid, "COMPLETED", result="fallback: bad-model-reply")
                return (f"Samajh gaya bhai, par model ne gol-mol jawab diya. Fir se puch le, ya command bhej: "
                        f"report | hunt | draft | schedule | health")
        _conv.push("user", text)
        _conv.push("assistant", txt[:2000])
        tasks.set_status(tid, "COMPLETED", result=txt[:500])
        audit("agent", tid, "chat", text[:300], txt[:300], "REPLY", "", "", "")
        return txt[:3500]
    why = (res.error if res is not None else err)[:200]
    tasks.set_status(tid, "COMPLETED", result="fallback: " + why)
    audit("agent", tid, "chat", text[:300], "fallback", "FALLBACK", "", "", why)
    return (f"Samajh gaya bhai, par AI dimag abhi jawab nahi de paya ({why}). "
            f"Thodi der me fir puch lena, ya seedha command bhej: report | hunt | draft | schedule | health")

def handle_owner_text(text):
    cmd, arg = telegram_bot.parse_command(text)
    if cmd == "MESSAGE" and text.startswith("/"):
        text = text[1:]
    if cmd == "APPROVE":
        ok = approvals.decide(arg, True)
        return f"{arg} {'APPROVE ho gaya bhai ✅ Ab tu khud manually bhej/post kar de.' if ok else 'nahi mila. `queue` me id dekh le.'}"
    if cmd == "REJECT":
        approvals.decide(arg, False)
        return f"{arg} reject kar diya. Koi baat nahi, agla draft bana dunga."
    t = text.lower()
    if "report" in t:
        from growth import reports
        return reports.build()
    if "queue" in t or "approval" in t:
        q = approvals.queue()
        if not q:
            return "Approval queue khali hai bhai, sab clear ✅"
        return "Ye pending hai, dekh le:\n" + "\n".join(f"{a['id']} | {a['action']} | {a['target'][:80]} | {a['risk']}" for a in q[:10])
    if "health" in t:
        import health_check
        return health_check.run_text()
    if "follow" in t:
        from growth import leads as _leads
        due = _leads.followups_due()
        if not due:
            return "Koi follow-up baki nahi hai bhai, sab clear ✅"
        return "Ye follow-up baki hai:\n" + "\n".join(f"{l['lead_id']} | {l.get('name')} | {l.get('next_followup')}" for l in due[:15])
    if t.startswith("draft"):
        from growth import content as _content
        topic = text[5:].strip() or "NDIS invoice admin pain (Example)"
        pid, draft, errs = _content.draft_post(topic, "billing-edu")
        if not pid:
            return f"Draft nahi bana bhai ({draft}). Thodi der me fir bolna."[:600]
        _content.set_status(pid, "APPROVAL_REQUIRED")
        aid, msg = approvals.request_approval("content.publish-manual", pid, f"Manual draft, checks {errs}",
                                              "Owner posts MANUALLY.", "MEDIUM", draft[:3000])
        return f"Naya draft ban gaya [{pid}], approval {aid}:\n{draft[:2500]}\n\nPadh le bhai, thik lage to APPROVE {aid} bhej, fir khud manually post kar dena."
    if "check site" in t or "website" in t:
        from growth.pipeline import website_check_and_alert
        return "Website check kar liya bhai:\n" + str(website_check_and_alert())[:1800]
    if t.startswith("hunt"):
        from growth import hunt as _hunt
        items = _hunt.hunt_leads()
        return _hunt.digest_text(items)[:3900]
    if t.startswith("leads"):
        import sqlite3
        c = sqlite3.connect(config.AGENT_DB_PATH)
        c.row_factory = sqlite3.Row
        rows = c.execute("SELECT lead_id, name, lead_score, qualification_status FROM leads ORDER BY lead_score DESC LIMIT 10").fetchall()
        c.close()
        if not rows:
            return "Abhi DB me 0 lead hai. `hunt` bhejo, mai public se dhoond ke details bhejunga."
        return "\n".join(f"{r['lead_id']} | {r['name'][:40]} | score {r['lead_score']} | {r['qualification_status']}" for r in rows)
    if t.startswith("outreach"):
        lid = text.split(None, 1)[1].strip() if len(text.split(None, 1)) > 1 else ""
        if not lid:
            return "Bolo: outreach <lead_id> (pehle `leads` se id lo)"
        from growth import outreach as _out
        aid, msg = _out.queue_outreach(lid)
        return (msg + "\n\nYaad rahe bhai: msg tu khud bhejega, agent nahi bhejega.")[:3900]
    if "schedule" in t or "timetable" in t or "time" in t:
        return f"⏰ Time-table bhai ({config.TIMEZONE}, business {config.BUSINESS_TZ}):\n" + scheduler.timetable()
    if t.startswith("pause") or "rayvice pause" in t:
        import modes as _modes
        return _modes.pause()
    if t.startswith("resume") or "rayvice resume" in t:
        import modes as _modes
        return _modes.resume()
    if t.startswith("mode"):
        import modes as _modes
        arg2 = text.split(None, 1)[1] if len(text.split(None, 1)) > 1 else ""
        if not arg2:
            return f"Abhi mode hai: {_modes.mode()} bhai. Badalne ke liye: mode ASSIST jese bhejo. Options: {', '.join(_modes.MODES)}"
        return _modes.set_mode(arg2)
    if "status" in t or t.startswith("rayvice status"):
        import modes as _modes
        import health_check as _hc
        q = approvals.queue()
        return (f"📟 Status bhai:\nMode: {_modes.mode()} | Automation: {'ON ✅' if _modes.automation_on() else 'PAUSE ⏸️'}\n"
                f"Pending approvals: {len(q)}\n" + scheduler.timetable())
    if "analytic" in t or "funnel" in t:
        from growth import analytics as _an
        return _an.summary_text()[:3900]
    if t.startswith("rayvice tasks") or t == "tasks":
        items = tasks.pending()
        if not items:
            return "Koi pending task nahi hai bhai ✅"
        return "\n".join(f"{x['task_id']} | {x['task_type'][:60]} | {x['status']} | {x['risk_level']}" for x in items[:15])
    if "bug" in t:
        if len(text.split(None, 1)) > 1 and text.split(None, 1)[1].strip().lower() not in ("s", "report"):
            from engineering import bugs as _bugs
            tid, aid, plan = _bugs.investigate(text.split(None, 1)[1].strip())
            return (plan + f"\n\nApproval id: {aid} — APPROVE {aid} bhejega tabhi aage badhunga. Production ko haath nahi lagega.")[:3900]
        from engineering import code_memory as _cm
        return _cm.text()[:3900]
    if "deploy" in t:
        import config as _cfg
        from growth import monitor as _mon
        web = _mon.check_all()
        return (f"🚀 Deploy map bhai (SAME hai, change nahi kiya):\nFrontend: {_cfg.DEPLOY_FRONTEND}\n"
                f"Backend: {_cfg.DEPLOY_BACKEND}\nDB: {_cfg.DEPLOY_DB}\n"
                f"Health: site {'UP ✅' if web['site'].get('ok') else 'DOWN ⚠️'} | backend {'UP ✅' if web['backend'].get('ok') else 'DOWN ⚠️'}\n"
                f"Prod deploy hamesha approval ke baad hi hoga.")
    if "feedback" in t:
        from growth import feedback as _fb
        return _fb.insights_text()[:3900]
    if t.startswith("social") or t in ("social", "post status", "posts"):
        from social import pipeline as _sp
        rest = t.split(None, 1)[1] if len(t.split(None, 1)) > 1 else "status"
        if rest.startswith("error"):
            return _sp.errors_text()[:3900]
        if rest.startswith("week"):
            from social import calendar as _sc
            return "📅 Week plan (Sydney):\n" + "\n".join(
                f"{p['date']} [{p['category']}] {p['topic']}" for p in _sc.week_plan())
        if rest.startswith("run"):
            res = _sp.daily_tick(force_window=True, notify=False)
            return ("Social tick chala bhai:\n" + str(res)[:3400])
        if rest.startswith("retry"):
            n = _sp.retry_dead()
            return f"{n} dead/failed items dobara queue me daal diye. Agle GH Actions tick par try honge."
        if rest.startswith("verify"):
            from social.platforms import capabilities, get_adapter
            lines = ["🔐 Platform verify:"]
            for cap in capabilities():
                a = get_adapter(cap["platform"])
                if a and a.configured():
                    vok, vmsg = a.verify()
                    lines.append(f"• {cap['platform']}: {'OK ✅' if vok else 'FAIL ⚠️'} — {vmsg[:150]}")
                else:
                    lines.append(f"• {cap['platform']}: not configured — {(cap.get('blocker') or '')[:100]}")
            return "\n".join(lines)[:3900]
        if rest.startswith("draft"):
            return _sp.drafts_text()[:3900]
        if rest.startswith("kit"):
            from social import group_kit as _gk
            sub = rest.split(None, 1)[1] if len(rest.split(None, 1)) > 1 else ""
            res = _gk.build_kit(force=("regen" in sub))
            if not res.get("ok"):
                return f"Kit error: {res.get('error')}"[:3900]
            if res.get("already_sent") and "resend" not in sub:
                return "Aaj ka kit bhej diya gaya hai bhai ✅ (naya content: `social kit regen`, dobara bhejna: `social kit resend`)"
            n = _gk.send_kit(res, resend=("resend" in sub))
            return f"🗂 Aaj ka group content kit bhej diya ({n} messages, {res.get('source')}). Groups me paste karo bhai!"[:3900]
        if rest.startswith("capab"):
            from social.platforms import capabilities
            return "\n".join(f"• {c['platform']}: configured={c['configured']} free={c['free']} — {(c.get('blocker') or 'OK')[:90]}"
                             for c in capabilities())[:3900]
        return _sp.status_text()[:3900]
    if t.startswith("roadmap"):
        return "Roadmap proposal ke liye bolo bhai: roadmap <title> | <problem> | <evidence>. Bina approval kuch nahi banega."
    if "what should i do" in t or "aaj kya" in t or t.startswith("rayvice report"):
        import orchestrator as _orc
        return _orc.what_should_i_do_today()[:3900]
    if "run today" in t or "run operations" in t or "aaj ka operation" in t:
        import orchestrator as _orc
        return _orc.run_daily_operations()[:3900]
    if "help" in t:
        return ("Bhai commands ye hai:\n"
                "• health | status | report | queue | tasks\n"
                "• draft <topic> | hunt | leads | outreach <lead_id> | followups\n"
                "• check site | deploy | bugs | analytics | feedback\n"
                "• schedule | pause | resume | mode <name>\n"
                "• social status | social drafts | social run | social week | social errors | social retry | social verify | social kit\n"
                "• APPROVE <id> | REJECT <id>\n"
                "Seedha bol bhi sakta hai: `aaj kya karu` ya `aaj ka operation chala`.\n"
                "Kuch samajh na aaye to aise hi likh ke bhej de, mai samajh lunga.")
    # default: meri tarah baat kar — kuch bhi puche to samajh ke jawab de
    return chat_reply(text)

def poll_loop():
    info("Rayvice agent polling Telegram (no webhook/domain needed)...")
    offset = 0
    import time
    while True:
        try:
            r = telegram_bot.poll_once(offset=offset, timeout=25)
            for u in r.get("result", []):
                offset = u["update_id"] + 1
                msg = u.get("message", {})
                text = msg.get("text", "")
                if not text:
                    continue
                from_id = str((msg.get("from") or {}).get("id") or "")
                if config.TELEGRAM_ALLOWED_USER_ID and from_id != config.TELEGRAM_ALLOWED_USER_ID:
                    audit("telegram", "-", "unauthorized.command", from_id, text[:80], "DENIED", "", "", "")
                    continue
                reply = handle_owner_text(text)
                telegram_bot.send(reply)
            # run due jobs with real actions (pause + duplicate guarded)
            import modes as _modes
            import duplicate as _dup
            from datetime import date as _date
            for job in scheduler.due():
                jname = job["name"]
                if not _modes.automation_on() and jname not in ("morning.research", "evening.report", "website.check", "weekly.report", "monthly.summary"):
                    scheduler.mark_done(jname, job["interval_hours"])
                    audit("scheduler", "-", jname, "", "skipped: paused", "SKIPPED", "", "", "")
                    continue
                daykey = f"job:{jname}:{_date.today().isoformat()}"
                if jname in ("daily.content", "lead.hunt", "evening.report") and _dup.check_and_mark(daykey):
                    scheduler.mark_done(jname, job["interval_hours"])
                    audit("scheduler", "-", jname, "", "skipped: duplicate", "SKIPPED", "", "", "")
                    continue
                tid = tasks.create(jname, risk_level="LOW")
                tasks.set_status(tid, "RUNNING")
                result = execute_job(job)
                tasks.set_status(tid, "COMPLETED", result=result[:2000])
                scheduler.mark_done(jname, job["interval_hours"])
                audit("scheduler", tid, jname, "", result[:500], "SCHEDULED", "", "", "")
        except KeyboardInterrupt:
            break
        except Exception as e:
            info(f"loop error (non-fatal): {e}")
            time.sleep(5)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        print(handle_owner_text(" ".join(sys.argv[2:])))
    else:
        poll_loop()
