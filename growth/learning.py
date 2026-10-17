"""Learning loop + persistent objection DB. Business outcomes > vanity metrics."""
import json
import os

LEARN_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "knowledge", "memory", "learning.json")
OBJ_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "knowledge", "memory", "objections.json")

def _load(p, default):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def _save(p, d):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2)
    os.replace(tmp, p)

def record_outcome(kind, detail, result):
    d = _load(LEARN_PATH, {"events": []})
    d["events"].append({"kind": kind, "detail": str(detail)[:300], "result": str(result)[:300]})
    d["events"] = d["events"][-300:]
    _save(LEARN_PATH, d)

def record_objection(text, outcome=""):
    d = _load(OBJ_PATH, {})
    e = d.get(text, {"count": 0, "outcome": ""})
    e["count"] += 1
    if outcome:
        e["outcome"] = outcome
    d[text] = e
    _save(OBJ_PATH, d)
    return e

def top_objections(limit=10):
    d = _load(OBJ_PATH, {})
    return sorted(d.items(), key=lambda x: -x[1]["count"])[:limit]

def content_ideas_from_learnings():
    d = _load(LEARN_PATH, {"events": []})
    ideas = []
    for e in d.get("events", [])[-30:]:
        if "question" in e.get("detail", "").lower() or e.get("kind") == "support":
            ideas.append(f"FAQ from repeated question: {e['detail'][:100]}")
    return ideas[:10]
