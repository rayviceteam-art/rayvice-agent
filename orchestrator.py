"""RayviceOrchestrator: coordinates all agents. Thin coordinator, agents do the work."""
import modes
from logs_sys import audit

def what_should_i_do_today():
    """Owner asks 'What should I do today?' -> top opportunities + attention list."""
    from growth import reports, leads
    import approvals
    from growth import monitor
    rep = reports.build()
    q = approvals.queue()
    due = leads.followups_due()
    lines = [rep, "\n🎯 Aaj ka focus bhai:"]
    if q:
        lines.append(f"• Pehle approvals nipatao ({len(q)} pending) — `queue` bhej")
    else:
        lines.append("• Approval queue clear hai ✅")
    if due:
        lines.append(f"• {len(due)} follow-up baki hai — `followups` bhej")
    lines.append("• Content: 09:30 wala draft aayega, manually post karna")
    lines.append("• Hunt: 10:00 wali report dekhna")
    return "\n".join(lines)

def run_daily_operations():
    """Owner says 'Run today's operations' -> safe workflow now, rest on schedule."""
    ok, reason = modes.allowed("recurring-approved")
    if not ok:
        return reason
    from growth.pipeline import run_daily
    out = run_daily(notify=True)
    audit("orchestrator", "daily-ops", "pipeline", "", str(out)[:300], "DONE", "", "", "")
    return f"Ho gaya bhai ✅ Aaj ka operation chala diya: {out}. Baaki schedule pe hota rahega."
