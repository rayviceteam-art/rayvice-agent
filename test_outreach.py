"""Offline tests for the outreach package. No network, no SMTP, no AI.

Run: python3 test_outreach.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["SOCIAL_DB_PATH"] = "data/test_outreach.db"
os.environ.setdefault("AGENT_DB_PATH", "data/test_agent.db")
os.environ["OUTREACH_DRYRUN"] = "true"
os.environ["GROQ_API_KEYS"] = "k1,k2,k3"
for f in ("data/test_outreach.db", "data/test_outreach.db-wal", "data/test_outreach.db-shm"):
    try:
        os.remove(f)
    except Exception:
        pass

from social import db  # noqa: E402
from outreach import compose, pipeline, sources, store  # noqa: E402

fails = []


def ok(name, fn):
    try:
        fn()
        print(f"PASS {name}")
    except Exception as e:
        print(f"FAIL {name}: {e}")
        fails.append(name)


def t_schema():
    db.ensure_schema()
    c = db.connect()
    names = {r["name"] for r in c.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'outreach_%'").fetchall()}
    c.close()
    assert {"outreach_leads", "outreach_messages", "outreach_suppression",
            "outreach_replies", "outreach_runs"} <= names, names


def t_extract_emails():
    html = ('<a href="mailto:Info@Example.com.au">Email us</a> '
            '<p>Call office@brightcare.com.au or no-reply@x.com</p> '
            '<img src="logo@2x.png">')
    got = sources.extract_emails(html)
    assert "info@example.com.au" in got, got
    assert "office@brightcare.com.au" in got, got
    assert all("no-reply" not in e for e in got), got


def t_best_email_prefers_business():
    emails = ["jane@gmail.com", "info@brightcare.com.au", "accounts@brightcare.com.au"]
    assert sources.best_email(emails, "brightcare.com.au") in ("info@brightcare.com.au",
                                                               "accounts@brightcare.com.au")


def t_best_email_rejects_personal_other_domain():
    assert sources.best_email(["john.smith@randombuilderco.com"], "brightcare.com.au") == ""
    # free-mail business inbox on the provider's own page is allowed
    assert sources.best_email(["brightcare@gmail.com"], "brightcare.com.au") == "brightcare@gmail.com"


def t_blocklist():
    assert sources.is_blocked("https://www.facebook.com/whatever")
    assert sources.is_blocked("https://www.ndiscommission.gov.au/x")
    assert sources.is_blocked("https://aruma.com.au")
    assert not sources.is_blocked("https://brightcaresupport.com.au")


def t_clean_name():
    assert pipeline._clean_name("NDIS Provider | Bright Care Support", "brightcare.com.au") == "Bright Care Support"
    assert pipeline._clean_name("", "brightcare.com.au") == "Brightcare"
    assert pipeline._clean_name("Home", "happyhands.com.au") == "Happyhands"
    assert pipeline._clean_name("IAC: Registered NDIS Provider in Melbourne", "iac.com.au") == "IAC"
    assert pipeline._clean_name("Contact", "brightcare.com.au") == "Brightcare"


def t_compose_validation():
    good = ('Hi there, we help small NDIS providers turn shifts into clean invoices. '
            'Try Rayvice free at rayvice.com. Kind regards, Rayvice. '
            'If this is not relevant reply "stop" and I will not email again. ' * 3)
    assert compose.validate("Quick question about invoicing", good) == []
    assert compose.validate("Re: your account", good)  # fake Re:
    assert compose.validate("Hello", "guarantee compliance short")  # banned + no opt-out + short
    assert compose.validate("Hello", ("guarantee " + good))  # banned phrase


def t_suppression():
    store.add_suppression("Blocked@Example.com.au", "test")
    assert store.is_suppressed("blocked@example.com.au")
    assert store.is_suppressed("BLOCKED@example.com.au")
    assert not store.is_suppressed("fresh@example.com.au")


def t_message_idempotent():
    lid = store.upsert_lead({"name": "X", "domain": "x.com.au", "email": "a@x.com.au"})
    m1 = store.log_message(lid, "a@x.com.au", "subject", "body")
    m2 = store.log_message(lid, "a@x.com.au", "subject", "body")
    assert m1 and not m2, (m1, m2)
    assert store.message_exists("a@x.com.au")


def t_send_dryrun_no_network():
    res = pipeline.send_daily(dry=True)
    assert res["sent"] == 0 and res["dry"] is True


def t_format_preview():
    text = pipeline.format_preview([{"name": "Test Co", "email": "t@test.com.au",
                                     "subject": "Hi", "body": "Body here"}])
    assert "t@test.com.au" in text and "Hi" in text


def t_icp_real_provider():
    text = ("We are a registered NDIS provider offering disability support services and "
            "support workers for participants across Sydney. Our community access and "
            "supported independent living supports help you reach your goals.")
    r = sources.icp_evaluate(text, "brightcare.com.au")
    assert r["ok"] and r["score"] >= 4, r


def t_icp_rejects_directory():
    text = ("Find an NDIS provider near you. Compare providers, browse providers and read "
            "reviews in our NDIS provider directory.")
    assert not sources.icp_evaluate(text, "x.com.au")["ok"]


def t_icp_rejects_irrelevant():
    assert not sources.icp_evaluate("Best coffee in Melbourne, open 7am daily.", "cafe.com.au")["ok"]
    assert not sources.icp_evaluate("We are a law firm offering legal advice and conveyancing.", "law.com.au")["ok"]


def t_icp_footer_noise_allowed():
    text = ("We provide NDIS disability support services and support workers for participants. "
            "Our community participation and support coordination supports help you reach goals. "
            "Rayville Support is a registered NDIS provider. Read about the NDIS Commission. "
            "Careers: send your resume to our team. * 2")
    r = sources.icp_evaluate(text, "rayville.com.au")
    assert r["ok"], r


def t_icp_soft_negative_penalty():
    text = ("NDIS disability support services and support workers for participants, "
            "community access and supported independent living. Our team includes a lawyer "
            "for legal advice.")
    r = sources.icp_evaluate(text, "x.com.au")
    assert "soft_negatives" in r and r["soft_negatives"], r
    assert r["ok"], r  # real provider with footer legal link still passes


def t_icp_solo_worker_accept():
    text = ("I'm an NDIS support worker based in Geelong. I provide community access and "
            "in-home support for NDIS participants, with self-managed and plan-managed "
            "clients welcome. Contact me to chat about your goals.")
    r = sources.icp_evaluate(text, "sarahsupport.com.au")
    assert r["ok"], r


def t_icp_rejects_single_ndis_mention():
    # ek hi "NDIS" mention kaafi nahi — ye cleaning business target nahi hai
    text = ("Professional cleaning services in Sydney. We also offer NDIS cleaning for "
            "participants. Book online today. House cleaning, office cleaning and end of "
            "lease cleaning.")
    r = sources.icp_evaluate(text, "sparkleclean.com.au")
    assert not r["ok"], r


def t_icp_rejects_plan_manager():
    text = ("We are an NDIS plan manager. Our plan management services process invoices "
            "from your providers and support workers. As your plan manager we handle "
            "plan management fees and payments for participants.")
    assert not sources.icp_evaluate(text, "planpay.com.au")["ok"]


def t_icp_rejects_registration_consultant():
    text = ("NDIS provider registration services. We help you become a registered NDIS "
            "provider with audit-ready policies, registration support and compliance "
            "templates. Book a free consult with our team.")
    assert not sources.icp_evaluate(text, "ndisreghelp.com.au")["ok"]


def t_aussie_gate():
    assert sources._aussie_ok("brightcare.com.au")
    assert sources._aussie_ok("support.org.au")
    assert not sources._aussie_ok("support.com")
    assert not sources._aussie_ok("randomagency.io")


def t_retry_no_compose():
    store.upsert_lead({"name": "RC", "domain": "retry.com.au", "email": "a@retry.com.au"})
    c = db.connect()
    lid = c.execute("SELECT id FROM outreach_leads WHERE domain='retry.com.au'").fetchone()["id"]
    c.close()
    store.set_lead_status(lid, "NO_COMPOSE", {"error": "AI down"})
    ds = store.domain_status()
    assert ds["retry.com.au"] == (lid, "NO_COMPOSE"), ds.get("retry.com.au")
    # pipeline skip logic: NO_COMPOSE retryable, baaki nahi
    retryable = [d for d, (_, st) in ds.items() if st == "NO_COMPOSE"]
    assert "retry.com.au" in retryable
    rows = store.leads_by_status("NO_COMPOSE", limit=10)
    assert any(r["domain"] == "retry.com.au" for r in rows)


def t_provider_groq_registered():
    from ai_provider import get_provider
    p = get_provider("groq")
    assert p.name == "groq"
    assert p.keys == ["k1", "k2", "k3"], p.keys


def t_followup_columns():
    db.ensure_schema()
    c = db.connect()
    cols = {r["name"] for r in c.execute("PRAGMA table_info(outreach_messages)")}
    c.close()
    assert {"followup", "parent_id"} <= cols, cols


def t_followup_idempotent():
    lid = store.upsert_lead({"name": "G", "domain": "g.com.au", "email": "c@g.com.au"})
    m1 = store.log_message(lid, "c@g.com.au", "subj", "body")
    assert m1
    f1 = store.log_message(lid, "c@g.com.au", "re: subj", "body2", followup=1, parent_id=m1)
    assert f1, "followup insert should succeed"
    assert store.followup_exists("c@g.com.au")
    f2 = store.log_message(lid, "c@g.com.au", "re: subj", "body3", followup=1, parent_id=m1)
    assert not f2, "second followup must be blocked"


def t_followup_validate():
    good = ('Hi there, just following up on my note about invoicing for your shifts. '
            'No worries at all if it is not a fit. Rayvice has a free 9-day trial at rayvice.com. '
            'Kind regards, Sartaj. If not relevant just reply "stop".')
    assert compose.validate_followup("Re: invoicing", good) == []
    assert compose.validate_followup("Re: x", "too short")


def t_followup_candidates():
    lid = store.upsert_lead({"name": "F Co", "domain": "f.com.au", "email": "b@f.com.au"})
    mid = store.log_message(lid, "b@f.com.au", "Subj", "Body")
    c = db.connect()
    c.execute("UPDATE outreach_messages SET status='SENT', sent_at='2020-01-01T00:00:00Z' WHERE id=?", (mid,))
    c.execute("UPDATE outreach_leads SET status='SENT' WHERE id=?", (lid,))
    c.commit()
    c.close()
    assert any(r["message_id"] == mid for r in store.followup_candidates(4, limit=50))
    store.set_lead_status(lid, "REPLIED")
    assert not any(r["message_id"] == mid for r in store.followup_candidates(4, limit=50))


def t_sent_local_cap():
    from datetime import timedelta
    from social import calendar
    db.ensure_schema()
    lid = store.upsert_lead({"name": "Cap Co", "domain": "capco.com.au", "email": "cap@capco.com.au"})
    mid = store.log_message(lid, "cap@capco.com.au", "s", "b", status="QUEUED")
    store.mark_message(mid, "SENT")
    today = calendar.today_local()
    assert store.sent_local(today) >= 1, "aaj bheja count nahi hua"
    assert store.sent_local(today - timedelta(days=1)) == 0, "kal ka count galat"


def t_query_rotation():
    from datetime import date
    a = sources._queries_for(["NSW"], day=date(2026, 3, 1))
    b = sources._queries_for(["NSW"], day=date(2026, 3, 2))
    assert a and all(isinstance(x, tuple) and len(x) == 2 for x in a)
    assert {st for _, st in a} == {"NSW"}
    assert any("NSW" in q or q.split()[2] in sources.CITIES["NSW"] for q, _ in a)
    assert a != b, "roz queries same hain (naye leads nahi milenge)"


def t_rank_best():
    ce = [("c", {"email": "y@b.au", "icp": {"ok": True, "score": 3}}),
          ("a", {"email": "x@a.au", "icp": {"ok": True, "score": 9}}),
          ("b", {"email": "", "icp": {"ok": True, "score": 9}}),
          ("d", {"email": "z@c.au", "icp": {"ok": False, "score": 1}})]
    ce.sort(key=pipeline._rank_key, reverse=True)
    assert [c for c, _ in ce] == ["a", "c", "b", "d"], [c for c, _ in ce]


def t_scan_ignores_newsletter():
    from outreach import mailer
    before = store.suppressed_set()
    s = {"scanned": 0, "replies": 0, "unsub": 0, "bounces": 0}
    news = ("Hi, your weekly digest is here. Check out these top reads for your team. "
            "You are receiving this because you signed up. Click here to unsubscribe. "
            "Manage your preferences in your account settings at any time. " * 2)
    mailer._handle("noreply@medium.com", "Weekly digest", news, s)
    assert "noreply@medium.com" not in store.suppressed_set() - before, "newsletter ko unsubscribe maana"
    mailer._handle("random@someone.com", "Re: hi", "please unsubscribe me, thanks", s)
    assert "random@someone.com" in store.suppressed_set(), "chhota clear opt-out ignore ho gaya"


ok("schema", t_schema)
ok("scan-ignores-newsletter", t_scan_ignores_newsletter)
ok("sent-local-cap", t_sent_local_cap)
ok("query-rotation", t_query_rotation)
ok("rank-best", t_rank_best)
ok("extract-emails", t_extract_emails)
ok("best-email-business", t_best_email_prefers_business)
ok("best-email-reject-personal", t_best_email_rejects_personal_other_domain)
ok("blocklist", t_blocklist)
ok("clean-name", t_clean_name)
ok("compose-validation", t_compose_validation)
ok("suppression", t_suppression)
ok("message-idempotent", t_message_idempotent)
ok("send-dryrun", t_send_dryrun_no_network)
ok("format-preview", t_format_preview)
ok("icp-real-provider", t_icp_real_provider)
ok("icp-reject-directory", t_icp_rejects_directory)
ok("icp-reject-irrelevant", t_icp_rejects_irrelevant)
ok("aussie-gate", t_aussie_gate)
ok("icp-footer-noise", t_icp_footer_noise_allowed)
ok("icp-soft-negative", t_icp_soft_negative_penalty)
ok("icp-solo-worker", t_icp_solo_worker_accept)
ok("icp-reject-single-mention", t_icp_rejects_single_ndis_mention)
ok("icp-reject-plan-manager", t_icp_rejects_plan_manager)
ok("icp-reject-registration", t_icp_rejects_registration_consultant)
ok("retry-no-compose", t_retry_no_compose)
ok("provider-groq", t_provider_groq_registered)
ok("followup-columns", t_followup_columns)
ok("followup-idempotent", t_followup_idempotent)
ok("followup-validate", t_followup_validate)
ok("followup-candidates", t_followup_candidates)

for f in ("data/test_outreach.db", "data/test_outreach.db-wal", "data/test_outreach.db-shm"):
    try:
        os.remove(f)
    except Exception:
        pass

print("FAILURES:", fails if fails else "none")
sys.exit(1 if fails else 0)
