"""Content engine: Research -> Writer -> Review -> Scheduler. Draft-only, manual post (budget 0)."""
import json
import os
import sqlite3
import uuid
from datetime import datetime

import config
import model_router

CATEGORIES = ["billing-edu", "rate-split-edu", "admin-pain", "productivity",
              "compliance-awareness", "product-edu", "build-in-public",
              "problem-story", "faq", "feature", "trial-edu"]

def _db():
    os.makedirs(os.path.dirname(config.AGENT_DB_PATH) or ".", exist_ok=True)
    c = sqlite3.connect(config.AGENT_DB_PATH)
    c.execute("""CREATE TABLE IF NOT EXISTS posts(
      id TEXT PRIMARY KEY, ts TEXT, category TEXT, topic TEXT, draft TEXT,
      cta TEXT, status TEXT, history TEXT)""")
    return c

def quality_check(draft):
    errs = []
    low = draft.lower()
    banned = ["guaranteed ndia approval", "100% compliant", "testimonial", "5-star review",
              "made $", "fake", "ndis endorsed", "ndis certified"]
    for b in banned:
        if b in low:
            errs.append(f"Blocked claim: {b}")
    if "http" in low and "rayvice.com" not in low:
        pass
    if len(draft.split()) < 30:
        errs.append("Too short, add useful detail")
    # no plagiarism check offline; flag exact dupes via DB
    c = _db()
    r = c.execute("SELECT id FROM posts WHERE draft=?", (draft,)).fetchone()
    c.close()
    if r:
        errs.append("Duplicate of existing draft")
    return errs

def draft_post(topic, category="billing-edu"):
    """Returns (pid, text, errs) on success, (None, '', error) on failure.
    QUIET RULE: AI fail ya kachra output = NO draft, NO send. Fallback text
    kabhi owner ko nahi jayega (wahi purana spam tha)."""
    assert category in CATEGORIES
    with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), "knowledge", "rayvice.json"), encoding="utf-8") as f:
        biz = json.load(f)
    prompt = [
        {"role": "system", "content": f"You write for Rayvice: {biz['positioning']} Audience: Australian NDIS sole traders. Write in plain Australian English (customers are Aussie, NOT Hinglish). No fake stats/testimonials/endorsements. Useful + clear CTA for 9-day free trial."},
        {"role": "user", "content": f"Category {category}. Topic: {topic}. Write 120-180 word LinkedIn/Reddit-safe draft + CTA. Label examples as Example."},
    ]
    res = model_router.run_task("draft", prompt)
    if not res.ok:
        return None, "", f"AI unavailable, draft skipped (no junk sent): {res.error}"[:300]
    text = res.text.strip()
    # Hard-fail free-model glitches (e.g. safety prefaces) — never store/send.
    if len(text.split()) < 30 or text.lower().startswith("user safety"):
        return None, "", "AI gave junk output, draft skipped (no junk sent)"
    errs = quality_check(text)
    pid = "p_" + uuid.uuid4().hex[:8]
    c = _db()
    c.execute("INSERT INTO posts VALUES(?,?,?,?,?,?,?,?)",
              (pid, datetime.utcnow().isoformat() + "Z", category, topic, text,
               "Try 9-day free trial", "DRAFT", json.dumps(errs)))
    c.commit()
    c.close()
    return pid, text, errs

def set_status(pid, status):
    assert status in ("DRAFT", "APPROVAL_REQUIRED", "APPROVED", "PUBLISHED")
    c = _db()
    c.execute("UPDATE posts SET status=? WHERE id=?", (status, pid))
    c.commit()
    c.close()
