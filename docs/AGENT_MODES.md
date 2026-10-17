# AGENT_MODES — 4 mode + emergency stop

- **OBSERVE:** research/analyze/monitor/report only. Kuch external change nahi.
- **ASSIST:** + draft/code/test/organize. External = approval.
- **SUPERVISED_AUTO (default):** + pre-approved recurring workflows. Sensitive/prod/finance = approval.
- **FULL_AUTO:** sirf explicit owner config ke baad. Tab bhi audit + limits + stop + DO_NOT_CONTACT + platform rules lagenge.

**Emergency stop:** `pause` → AUTOMATION_ENABLED=false → external actions stop (research/report chal sakte hai). Kuch delete nahi hota. `resume` → wapas.
**Badlo:** `mode ASSIST` jese bhejo. `.env` me AGENT_MODE bhi set kar sakte ho.
