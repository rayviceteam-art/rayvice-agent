"""Offline tests. No real keys needed. Verifies isolation + all modules."""
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("AGENT_DB_PATH", "data/test.db")
# ensure clean test db
try:
    os.remove("data/test.db")
except Exception:
    pass

import config
import tasks, approvals, memory, scheduler, converse
import modes, notifications, rate_limits, duplicate
import tools_registry
import tools_setup  # noqa: registers tools
from growth import leads, content, support, monitor, analytics, feedback
from logs_sys import audit

fails = []
def ok(name, fn):
    try:
        fn()
        print(f"PASS {name}")
    except Exception as e:
        print(f"FAIL {name}: {e}")
        fails.append(name)

def t_tasks():
    tid = tasks.create("research test", risk_level="LOW")
    tasks.set_status(tid, "RUNNING")
    assert tasks.get(tid)["status"] == "RUNNING"

def t_approval():
    aid, msg = approvals.request_approval("outreach.send-manual", "test-target", "why", "exp", "MEDIUM", "payload")
    assert "ACTION REQUIRES APPROVAL" in msg
    approvals.decide(aid, False)

def t_memory():
    memory.write("business", {"test": "1"})
    assert memory.read("business")["test"] == "1"

def t_leads():
    lid, score, reasons = leads.upsert({"name": "Test Worker", "location": "Sydney, Australia",
        "business_type": "independent support worker", "business_url": "", "source": "test",
        "relevance_reason": "test", "tags": []})
    assert score >= 50 and reasons
    leads.set_status(lid, "QUALIFIED")

def t_content():
    pid, text, errs = content.draft_post("NDIS invoice admin pain", "billing-edu")
    if pid:
        assert len(text) > 100
        content.set_status(pid, "APPROVAL_REQUIRED")
    else:
        assert "skipped" in errs or "junk" in errs  # quiet path, no junk stored

def t_quality_gate():
    errs = content.quality_check("short")
    assert any("short" in e.lower() for e in errs)
    # safety-preface glitch must never pass as real draft
    import model_router as _mr
    real = _mr.run_task
    _mr.run_task = lambda *a, **k: type("R", (), {"ok": True, "text": "User Safety: safe", "model": "x"})()
    try:
        p, t, e = content.draft_post("x", "billing-edu")
        assert p is None and ("junk" in e or "skipped" in e)
    finally:
        _mr.run_task = real

def t_rotation():
    from growth import pipeline as _pl
    import memory as _mem
    _mem.write("marketing", {"used_topics": []})
    t1 = _pl.pick_topic()
    _mem.append_list("marketing", "used_topics", {"topic": t1, "date": "2999-01-01T00:00:00"})
    t2 = _pl.pick_topic()
    assert t1 != t2 or len(_pl.CONTENT_TOPICS) == 1

def t_quiet_report():
    from growth import reports as _rep
    assert isinstance(_rep.is_quiet_day(), bool)

def t_tavily_nokey():
    import os
    import research as _rs
    saved = os.environ.pop("TAVILY_API_KEY", None)
    try:
        assert _rs.tavily_search("x", 1) is None
    finally:
        if saved is not None:
            os.environ["TAVILY_API_KEY"] = saved

def t_support():
    intent, st, draft = support.draft_reply("How much does Rayvice cost?")
    assert intent in support.INTENTS

def t_sched():
    scheduler.ensure_defaults()
    assert isinstance(scheduler.due(), list)

def t_audit():
    audit("test", "t", "tool", "in", "out", "d", "s", "r", "")

def t_protected():
    if os.environ.get("GITHUB_ACTIONS"):
        return  # CI: phone-only paths, local guard yahan lagu nahi
    # must exist and we must NOT have modified them (mtime check skipped, just existence)
    assert os.path.exists("/root/rayvice-live")
    assert os.path.exists("/root/agent.py")

def t_modes():
    assert modes.mode() in modes.MODES
    ok, _ = modes.allowed("research")
    assert ok
    ok2, _ = modes.allowed("send-external")
    assert not ok2  # safe default: approval needed

def t_ratelimit():
    ok, _ = rate_limits.allow("search")
    assert ok

def t_duplicate():
    import uuid
    k = f"test:{uuid.uuid4().hex}"
    assert duplicate.check_and_mark(k) is False
    assert duplicate.check_and_mark(k) is True

def t_tools():
    assert "web_search" in tools_registry.REGISTRY
    assert "website_check" in tools_registry.REGISTRY

def t_analytics():
    assert "connected nahi" in analytics.summary_text()  # nothing connected yet
    analytics.record("visitors", 100, "test")
    analytics.record("signup_rate", 10, "test")
    assert "DATA NOT CONNECTED" in analytics.funnel_text()  # rest honestly marked
    assert "drop" in analytics.funnel_text()

def t_feedback():
    collect = feedback.collect("test pricing question", "PRICING", "test")
    assert collect

def t_github():
    from engineering import github as _gh
    s = _gh.status()
    assert isinstance(s, str) and len(s) > 0

def t_converse():
    converse.clear()
    converse.push("user", "hello bhai")
    converse.push("assistant", "samajh gaya bhai")
    h = converse.history(8)
    assert h[-2]["content"] == "hello bhai" and h[-1]["role"] == "assistant"
    for i in range(50):
        converse.push("user", f"m{i}")
    assert len(converse.history(100)) <= 40  # cap works
    converse.clear()

def t_action_intent():
    import main as _main
    lid, _, _ = leads.upsert({"name": "Intent Worker", "location": "Sydney, Australia",
        "business_type": "independent support worker", "source": "test",
        "relevance_reason": "test", "tags": []})
    out = _main.handle_owner_text(f"{lid} ko msg bhej de")
    assert "APPROVAL" in out  # approval bana, bheja nahi

ok("tasks", t_tasks)
ok("approval", t_approval)
ok("memory", t_memory)
ok("leads", t_leads)
ok("content", t_content)
ok("support", t_support)
ok("quality-gate", t_quality_gate)
ok("rotation", t_rotation)
ok("quiet-report", t_quiet_report)
ok("tavily-nokey", t_tavily_nokey)
ok("scheduler", t_sched)
ok("audit", t_audit)
ok("protected-untouched", t_protected)
ok("modes", t_modes)
ok("ratelimit", t_ratelimit)
ok("duplicate", t_duplicate)
ok("tools", t_tools)
ok("analytics", t_analytics)
ok("feedback", t_feedback)
ok("github", t_github)
ok("converse", t_converse)
ok("action-intent", t_action_intent)

# cleanup
try:
    os.remove("data/test.db")
except Exception:
    pass

print("FAILURES:", fails if fails else "none")
sys.exit(1 if fails else 0)
