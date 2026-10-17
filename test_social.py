"""Offline tests for the social automation package. No real keys, no network.

Run: python3 test_social.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["SOCIAL_DB_PATH"] = "data/test_social.db"
os.environ.setdefault("AGENT_DB_PATH", "data/test_agent.db")
os.environ["SOCIAL_PLATFORMS"] = "facebook,instagram"
for f in ("data/test_social.db", "data/test_social.db-wal", "data/test_social.db-shm"):
    try:
        os.remove(f)
    except Exception:
        pass

import config  # noqa: E402
from social import calendar, db, generator, media, publish_queue, validators  # noqa: E402
from social.platforms import get_adapter, capabilities  # noqa: E402
from social.platforms.base import classify_http, PublishResult  # noqa: E402

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
    n = c.execute("SELECT COUNT(*) n FROM sqlite_master WHERE type='table' AND name LIKE 'social_%'").fetchone()["n"]
    c.close()
    assert n >= 10, f"expected >=10 social tables, got {n}"


def t_validators_limits():
    r = validators.validate("x", body="short")
    assert r["errors"], "short content should error"
    long_body = "word " * 800
    r2 = validators.validate("linkedin", body=long_body)
    assert any("limit" in e for e in r2["errors"]), r2["errors"]


def t_validators_banned():
    r = validators.validate("linkedin", body="Rayvice is NDIS endorsed and 100% compliant, guaranteed approval!")
    assert any("Blocked claim" in e for e in r["errors"])
    assert any("Compliance guarantee" in e for e in r["errors"])


def t_validators_sensitive():
    r = validators.validate("facebook", body="Call me on 0412 345 678 about your invoice today please thanks")
    assert any("phone" in e.lower() or "mobile" in e.lower() for e in r["errors"])
    r2 = validators.validate("facebook", body="Email participant@example.com for help with invoice admin today")
    assert any("email" in e.lower() for e in r2["errors"])


def t_validators_au_english():
    out = validators.normalise_au_english("Organize your color palette at the center of your organization").lower()
    assert "organise" in out and "colour" in out and "centre" in out and "organisation" in out


def t_validators_duplicate():
    a = "Clean invoices save time every single week for support workers in Australia today"
    b = "Clean invoices save time every single week for support workers in Australia tomorrow!"
    dup = validators.find_near_duplicate(b, [a], threshold=0.6)
    assert dup, "near-duplicate should be detected"


def t_calendar():
    p = calendar.plan_for()
    assert p["topic"] and p["category"]
    assert calendar.plan_for()["topic"] == p["topic"], "same day = same deterministic topic"
    assert len(calendar.week_plan()) == 7
    assert calendar.in_publish_window(hours=[]) is None


def t_media_card():
    path = media.render_branded_card("Test Invoice Checklist", subtitle="Testing 123")
    okv, info = media.validate_image(path)
    assert okv, info
    assert info["width"] == 1080 and info["bytes"] > 1000
    os.remove(path)


def t_media_public_url():
    saved = config.MEDIA_PUBLIC_BASE
    config.MEDIA_PUBLIC_BASE = "https://raw.githubusercontent.com/rayviceteam-art/rayvice-agent/main/media"
    assert media.public_url("x.png").endswith("/x.png")
    config.MEDIA_PUBLIC_BASE = saved


def t_generator_mocked():
    import model_router
    real = model_router.run_task
    model_router.run_task = lambda *a, **k: type("R", (), {
        "ok": True, "model": "mock",
        "text": '{"hook": "Stop typing invoices twice", "body": "' + " ".join(["invoice"] * 60) + '", "cta": "Try the free trial", "hashtags": ["ndis", "bookkeeping"], "image_prompt": "clean desk"}'})()
    try:
        plan = {"date": "2026-01-05", "category": "invoicing-education", "theme": "t", "topic": "invoice admin"}
        r1 = generator.generate_draft("facebook", plan)
        assert r1["ok"], r1
        r2 = generator.generate_draft("facebook", plan)
        assert not r2["ok"] and r2.get("duplicate"), f"idempotency failed: {r2}"
        assert r2.get("draft_id") == r1["draft_id"], "duplicate must return draft_id (orphan recovery)"
    finally:
        model_router.run_task = real


def t_generator_junk():
    import model_router
    real = model_router.run_task
    model_router.run_task = lambda *a, **k: type("R", (), {"ok": True, "model": "m", "text": "User Safety: safe"})()
    try:
        r = generator.generate_draft("linkedin", {"date": "2026-01-06", "category": "faq", "theme": "t", "topic": "x"})
        assert not r["ok"] and "skipped" in r["error"]
    finally:
        model_router.run_task = real


def t_queue_idempotent():
    q1, created1 = publish_queue.enqueue("d_test1", "facebook", scheduled_utc=db.utcnow())
    q2, created2 = publish_queue.enqueue("d_test1", "facebook", scheduled_utc=db.utcnow())
    assert created1 is True and created2 is False, (created1, created2)
    assert q1 == q2


def t_backoff_math():
    d1 = publish_queue.next_attempt_delay(1, base=60)
    d2 = publish_queue.next_attempt_delay(2, base=60)
    d3 = publish_queue.next_attempt_delay(1, retry_after=99999, base=60)
    assert d2 > d1, (d1, d2)
    assert d3 >= 21600, "retry_after dominates but capped behaviour documented"
    capd = publish_queue.next_attempt_delay(20, base=60)
    assert capd <= 21600, "cap 6h"


def t_retry_deadletter():
    qid, _ = publish_queue.enqueue("d_dead", "facebook", scheduled_utc=db.utcnow())
    for i in range(config.SOCIAL_MAX_ATTEMPTS + 1):
        will_retry = publish_queue.retry_or_die(qid, "boom", retryable=True)
        if not will_retry:
            break
    c = db.connect()
    st = c.execute("SELECT status FROM social_queue WHERE id=?", (qid,)).fetchone()["status"]
    c.close()
    assert st == "DEAD_LETTER", st
    qid2, _ = publish_queue.enqueue("d_perm", "facebook", scheduled_utc=db.utcnow())
    publish_queue.retry_or_die(qid2, "auth", retryable=False)
    c = db.connect()
    st2 = c.execute("SELECT status FROM social_queue WHERE id=?", (qid2,)).fetchone()["status"]
    c.close()
    assert st2 == "FAILED_PERMANENT", st2


def t_process_due_dryrun():
    c = db.connect()
    c.execute("INSERT INTO social_drafts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              ("d_pub1", db.utcnow(), "", "facebook", "text+image", "Hook line here",
               "Body text for this post with enough words to be realistic " * 2, "CTA",
               "[]", "", "READY", "{}", "mock", "v1", "draft:facebook:test:d_pub1", "hash1"))
    c.commit()
    c.close()
    publish_queue.enqueue("d_pub1", "facebook", scheduled_utc=db.utcnow())
    res = publish_queue.process_due(dry_run=True, notify=False)
    assert res["dry_run"] >= 1, res
    assert publish_queue.already_published("facebook", "d_pub1") is True
    res2 = publish_queue.process_due(dry_run=True, notify=False)
    assert res2["dry_run"] == 0, "no double publish"


def t_pause_blocks():
    saved = os.environ.get("AUTOMATION_ENABLED")
    os.environ["AUTOMATION_ENABLED"] = "false"
    try:
        res = publish_queue.process_due(dry_run=True, notify=False)
        assert res["skipped"] >= 0 and "paused" in " ".join(res["errors"])
    finally:
        if saved is None:
            os.environ.pop("AUTOMATION_ENABLED", None)
        else:
            os.environ["AUTOMATION_ENABLED"] = saved


def t_lock():
    t1 = publish_queue.acquire_lock("testlock", ttl_seconds=60)
    t2 = publish_queue.acquire_lock("testlock", ttl_seconds=60)
    assert t1 and not t2
    publish_queue.release_lock("testlock", t1)
    t3 = publish_queue.acquire_lock("testlock", ttl_seconds=60)
    assert t3
    publish_queue.release_lock("testlock", t3)


def t_classify_http():
    r, m, ra = classify_http(429, {}, {"Retry-After": "120"})
    assert r and ra == 120
    r2, _, _ = classify_http(401, {}, {})
    assert not r2
    r3, _, _ = classify_http(500, {}, {})
    assert r3


def t_x_blocked():
    x = get_adapter("x")
    res = x.publish({"hook": "hi", "body": "x" * 100, "cta": ""}, media={}, dry_run=False)
    assert not res.ok and "BLOCKED_API_ACCESS" in res.error
    assert x.CAPABILITY["test_result"] == "NOT AVAILABLE ON FREE TIER"


def t_pipeline_mocked():
    import model_router
    from social import pipeline
    real = model_router.run_task
    model_router.run_task = lambda *a, **k: type("R", (), {
        "ok": True, "model": "mock",
        "text": '{"hook": "Weekend rates check", "body": "' + " ".join(["shift"] * 60) +
                '", "cta": "Double-check official sources", "hashtags": ["ndis"], "image_prompt": "calendar"}'})()
    saved_platforms = config.SOCIAL_PLATFORMS
    config.SOCIAL_PLATFORMS = ["facebook"]
    try:
        res = pipeline.daily_tick(dry_run=True, force_window=True, notify=False)
        assert res["ok"], res
        assert res["publish"]["dry_run"] >= 1, res
    finally:
        model_router.run_task = real
        config.SOCIAL_PLATFORMS = saved_platforms


def t_pipeline_orphan_recovery():
    import model_router
    from social import pipeline
    real = model_router.run_task
    model_router.run_task = lambda *a, **k: type("R", (), {
        "ok": True, "model": "mock",
        "text": '{"hook": "Orphan hook", "body": "' + " ".join(["claim"] * 60) +
                '", "cta": "Check the guide", "hashtags": ["ndis"], "image_prompt": "desk"}'})()
    saved_platforms = config.SOCIAL_PLATFORMS
    config.SOCIAL_PLATFORMS = ["linkedin"]
    try:
        c = db.connect()
        c.execute("DELETE FROM social_queue")
        c.execute("DELETE FROM social_drafts WHERE platform='linkedin'")
        c.commit()
        c.close()
        r1 = pipeline.daily_tick(dry_run=True, force_window=True, notify=False)
        assert r1["ok"], r1
        c = db.connect()
        c.execute("DELETE FROM social_queue WHERE platform='linkedin'")
        c.commit()
        c.close()
        r2 = pipeline.daily_tick(dry_run=True, force_window=True, notify=False)
        assert r2["ok"], r2
        assert any("recovered" in str(g) for g in r2["generated"]), f"duplicate draft should recover+enqueue: {r2['generated']}"
    finally:
        model_router.run_task = real
        config.SOCIAL_PLATFORMS = saved_platforms


def t_status_text():
    from social import pipeline
    s = pipeline.status_text()
    assert "Social automation" in s and "Queue" in s
    e = pipeline.errors_text()
    assert isinstance(e, str) and e


def t_drafts_text():
    from social import pipeline
    c = db.connect()
    row = c.execute("SELECT id FROM social_drafts ORDER BY rowid DESC LIMIT 1").fetchone()
    c.close()
    out = pipeline.drafts_text(limit=2)
    assert out and "Recent drafts" in out, out
    if row:
        assert row["id"] in out, "latest draft id draft list me hona chahiye"


def t_parse_command_slash():
    import telegram_bot
    cmd, arg = telegram_bot.parse_command("/approve a_12345678")
    assert cmd == "APPROVE" and arg == "a_12345678"
    cmd2, _ = telegram_bot.parse_command("/status")
    assert cmd2 == "MESSAGE"


ok("schema", t_schema)
ok("validators-limits", t_validators_limits)
ok("validators-banned", t_validators_banned)
ok("validators-sensitive", t_validators_sensitive)
ok("validators-au-english", t_validators_au_english)
ok("validators-duplicate", t_validators_duplicate)
ok("calendar", t_calendar)
ok("media-card", t_media_card)
ok("media-public-url", t_media_public_url)
ok("generator-mocked", t_generator_mocked)
ok("generator-junk", t_generator_junk)
ok("queue-idempotent", t_queue_idempotent)
ok("backoff-math", t_backoff_math)
ok("retry-deadletter", t_retry_deadletter)
ok("process-due-dryrun", t_process_due_dryrun)
ok("pause-blocks", t_pause_blocks)
ok("lock", t_lock)
ok("classify-http", t_classify_http)
ok("x-blocked", t_x_blocked)
ok("pipeline-mocked", t_pipeline_mocked)
ok("pipeline-orphan-recovery", t_pipeline_orphan_recovery)
ok("status-text", t_status_text)
ok("drafts-text", t_drafts_text)
ok("parse-command-slash", t_parse_command_slash)

try:
    os.remove("data/test_social.db")
except Exception:
    pass

print("FAILURES:", fails if fails else "none")
sys.exit(1 if fails else 0)
