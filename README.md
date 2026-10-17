# Rayvice Agent — autonomous business operator (isolated)

Isolated workspace. Does NOT touch:
- `/root/rayvice-live/` (Rayvice SaaS — API server SAME rahega)
- `/root/agent.py`, `groq-rotator.mjs`, `gemini-rotator.mjs`
- Phone/Termux DeepSeek harness (separate device)

Docs: `docs/` me ARCHITECTURE, SETUP, SECURITY, TOOLS, AUTOMATION, MEMORY, AGENT_MODES, APPROVALS, TROUBLESHOOTING.
Knowledge: `knowledge/*.md` (business/product/pricing/ICP/faq/sales/objections/content/technical/integrations/policies).

## Quick start (Termux or VPS, budget 0, no domain)
1. `cp .env.example .env` and fill `OPENROUTER_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
2. `pip install -r requirements.txt` (only `Pillow`; core works on stdlib too)
3. `python3 health_check.py`
4. `python3 test_all.py && python3 test_social.py`
5. `python3 main.py` (Telegram polling, no webhook needed)
6. In Telegram: `health`, `report`, `queue`, `APPROVE <id>`, `REJECT <id>`, `social status`

Termux: `termux-wake-lock`, battery optimization OFF, run inside `tmux`.

## Social automation (new — master prompt implementation)
Daily content pipeline: research → AI drafts → media → validation → 5 platforms → Telegram report.
- CLI: `python3 scripts/run_social.py --tick|--status|--errors|--week|--verify|--capabilities`
- Scheduler: GitHub Actions hourly cron (`.github/workflows/social-tick.yml`), Sydney-hour gate in-app
- Safety: `SOCIAL_DRYRUN=true` default; X = NOT AVAILABLE ON FREE TIER; retry/backoff/dead-letter built-in
- Docs: `IMPLEMENTATION_PLAN.md`, `DEPLOYMENT_STATUS.md`, `docs/platform-capabilities.md`, `docs/ARCHITECTURE.md`

## What was built (prompt base)
- AIProvider abstraction (OpenRouter), FREE_AI_MODE, daily counter, backoff, fallback, never spends when ALLOW_PAID_AI=false
- Model router (research/draft/code routes, configurable)
- Memory (business/marketing/sales/product/technical, no secrets)
- Tasks (PENDING..CANCELLED, LOW..CRITICAL), approvals (ACTION REQUIRES APPROVAL), audit (redacted), scheduler (persistent), tools registry (retry/circuit-breaker)
- GrowthAgent: lead DB SQLite + transparent score, content engine draft-only, outreach approval queue (manual send), support drafts + escalate, website monitor, daily report
- Manual post only for X/LinkedIn/Reddit (budget 0, anti-ban)

## Env required
OPENROUTER_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID. Optional: FREE_MODELS, FREE_DAILY_LIMIT.
