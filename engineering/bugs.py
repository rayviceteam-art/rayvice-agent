"""Bug investigation: plan + approval. Never edits production directly."""
import tasks
import approvals
from logs_sys import audit

def investigate(symptom, evidence=""):
    tid = tasks.create("bug: " + symptom[:80], risk_level="HIGH", approval_required=True)
    tasks.set_status(tid, "PLANNING")
    plan = (f"BUG PLAN [{tid}] — status WAITING FOR APPROVAL:\n"
            f"Symptom: {symptom}\nEvidence: {evidence or 'collect karna padega (logs, recent changes)'}\n"
            f"Steps: capture → classify → component → recent changes → reproduce → root cause → "
            f"isolated branch me fix → tests → summary.\n"
            f"Risk: MEDIUM/HIGH. Production change bina approval ke NAHI hogi.")
    aid, msg = approvals.request_approval("bugfix.plan", tid, symptom, plan, "HIGH", plan[:3000])
    tasks.set_status(tid, "WAITING_APPROVAL")
    audit("engineering", tid, "bug.investigate", symptom[:300], plan[:300], "WAIT_FOR_OWNER", "PENDING", "", "")
    return tid, aid, msg + "\n\n" + plan
