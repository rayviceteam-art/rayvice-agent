# SETUP — Rayvice Agent (budget 0, no domain)

1. `cp .env.example .env`
2. Bharo: `OPENROUTER_API_KEY` (openrouter.ai → Keys), `TELEGRAM_BOT_TOKEN` (@BotFather), `TELEGRAM_CHAT_ID` (@userinfobot). Secret chat me mat bhejo.
3. Optional: `TAVILY_API_KEY` (tavily.com free), `GITHUB_REPO` (+ token for private).
4. `pip install -r requirements.txt` (core stdlib pe bhi chalta hai — Termux friendly).
5. `python3 health_check.py` → OpenRouter + Telegram OK hona chahiye.
6. `python3 test_all.py` → sab PASS.
7. `setsid nohup python3 main.py > logs/service.log 2>&1 < /dev/null &` → 24x7 polling.
8. Telegram me `help` bhejo.

**Termux:** same folder `~/rayvice-agent/` me copy karo, `termux-wake-lock` + battery optimization OFF + `tmux`.
**Keys rotate:** `.env` me badlo, service restart karo. Kabhi git me mat dalo (`.gitignore` me `.env` hai).
