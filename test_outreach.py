"""Offline tests for the outreach package. No network, no SMTP, no AI.

Run: python3 test_outreach.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["SOCIAL_DB_PATH"] = "data/test_outreach.db"
os.environ.setdefault("AGENT_DB_PATH", "data/test_agent.db")
os.environ["OUTREACH_DRYRUN"] = "true"
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


ok("schema", t_schema)
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

for f in ("data/test_outreach.db", "data/test_outreach.db-wal", "data/test_outreach.db-shm"):
    try:
        os.remove(f)
    except Exception:
        pass

print("FAILURES:", fails if fails else "none")
sys.exit(1 if fails else 0)
