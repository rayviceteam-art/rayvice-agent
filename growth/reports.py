"""Daily growth report. Concise + actionable. Owner language: Hinglish."""
import sqlite3
import config

def counts():
    c = sqlite3.connect(config.AGENT_DB_PATH)
    def q(sql, args=()):
        try:
            return c.execute(sql, args).fetchone()[0]
        except Exception:
            return 0
    out = {
        "new_leads": q("SELECT COUNT(*) FROM leads WHERE date(created_at)=date('now')"),
        "qual": q("SELECT COUNT(*) FROM leads WHERE qualification_status='QUALIFIED'"),
        "appr": q("SELECT COUNT(*) FROM approvals WHERE status='PENDING'"),
        "drafts": q("SELECT COUNT(*) FROM posts WHERE status IN ('DRAFT','APPROVAL_REQUIRED')"),
    }
    try:
        out["ups"] = c.execute("SELECT COUNT(*) FROM checks WHERE status='UP' AND date(ts)=date('now')").fetchone()[0]
        out["downs"] = c.execute("SELECT COUNT(*) FROM checks WHERE status='DOWN' AND date(ts)=date('now')").fetchone()[0]
    except Exception:
        out["ups"], out["downs"] = 0, 0
    c.close()
    return out

def is_quiet_day():
    """Khaali din = bhejne layak kuch nahi (downs ho to kabhi quiet nahi)."""
    n = counts()
    return not (n["new_leads"] or n["qual"] or n["appr"] or n["drafts"] or n["downs"])

def build():
    n = counts()
    return (f"📊 Rayvice Daily Report bhai:\n"
            f"1. Aaj naye leads: {n['new_leads']}\n2. Total qualified: {n['qual']}\n"
            f"3. Approval pending: {n['appr']} (`queue` bhej ke dekh)\n4. Post drafts: {n['drafts']}\n"
            f"5. Website UP/DOWN aaj: {n['ups']}/{n['downs']}\n"
            f"6. Follow-up ke liye `followups` bhej\n"
            f"7. Agla kaam: `APPROVE <id>` kar, fir khud manually post kar de\n"
            f"Note: X/LinkedIn/Reddit pe post tu khud karega (budget 0, safe wala plan).")
