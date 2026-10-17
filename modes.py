"""Agent modes + emergency stop. OBSERVE < ASSIST < SUPERVISED_AUTO < FULL_AUTO."""
import os
import config

MODES = ["OBSERVE", "ASSIST", "SUPERVISED_AUTO", "FULL_AUTO"]

CAN = {
    "OBSERVE": {"research", "analyze", "monitor", "report"},
    "ASSIST": {"research", "analyze", "monitor", "report", "draft", "code", "test", "organize", "prepare"},
    "SUPERVISED_AUTO": {"research", "analyze", "monitor", "report", "draft", "code", "test", "organize", "prepare",
                        "recurring-approved"},
    "FULL_AUTO": {"research", "analyze", "monitor", "report", "draft", "code", "test", "organize", "prepare",
                  "recurring-approved"},
}

# External sends / prod changes need approval in every mode except explicit FULL_AUTO config,
# and even FULL_AUTO keeps audit + limits + stop controls.
ALWAYS_APPROVE = {"send-external", "publish", "delete", "production", "purchase", "paid", "infra"}

def mode():
    m = (os.environ.get("AGENT_MODE", config.AGENT_MODE) or "SUPERVISED_AUTO").upper()
    return m if m in MODES else "SUPERVISED_AUTO"

def automation_on():
    return (os.environ.get("AUTOMATION_ENABLED", "true" if config.AUTOMATION_ENABLED else "false").lower() == "true")

def allowed(action_kind):
    """Check mode permission. Returns (ok, reason)."""
    if not automation_on() and action_kind not in ("research", "report", "monitor", "analyze"):
        return False, "AUTOMATION_ENABLED=false (pause hai bhai, `resume` bhej ke chalu kar)"
    if action_kind in ALWAYS_APPROVE and mode() != "FULL_AUTO":
        return False, "Approval chahiye (safe mode hai)"
    if action_kind in CAN.get(mode(), set()):
        return True, ""
    return False, f"Mode {mode()} me ye allowed nahi"

def _set_env_file(key, value):
    p = os.path.join(os.path.dirname(__file__), ".env")
    lines, found = [], False
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            lines = f.read().splitlines()
    out = []
    for ln in lines:
        if ln.strip().startswith(key + "="):
            out.append(f"{key}={value}")
            found = True
        else:
            out.append(ln)
    if not found:
        out.append(f"{key}={value}")
    with open(p, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    os.environ[key] = value

def pause():
    _set_env_file("AUTOMATION_ENABLED", "false")
    return "⏸️ Pause kar diya bhai. External action ruk gaye, kuch delete nahi hua. `resume` bhej ke chalu kar lena."

def resume():
    _set_env_file("AUTOMATION_ENABLED", "true")
    return "▶️ Chalu kar diya bhai, schedule wapas time pe chalega."

def set_mode(m):
    m = (m or "").upper()
    if m not in MODES:
        return f"Mode samajh nahi aaya bhai. Ye me se chun: {', '.join(MODES)} (abhi {mode()} hai)"
    _set_env_file("AGENT_MODE", m)
    return f"Mode set ho gaya: {m} ✅"
