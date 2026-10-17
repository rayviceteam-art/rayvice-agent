# TROUBLESHOOTING — aam dikkat

- **Telegram reply nahi aata:** service chal rahi? `ps -p <pid>` dekho. Token revoke hua? `health_check.py` me Telegram FAIL dikhega. Bot me `/start` bheja?
- **`result":[]` / Chat ID nahi milti:** pehle bot ko `Hi` bhejo, phir getUpdates kholo. Ya @userinfobot use karo.
- **OpenRouter FAIL:** key galat/expired? `FREE_DAILY_LIMIT` khatam? Thodi der ruk ke retry (429 pe auto-backoff hai).
- **Hunt me 0 result:** DuckDuckGo kamzor hai — `TAVILY_API_KEY` dalo.
- **404 backend:** path missing hai, server alive hai — monitor UP ginta hai. 5xx/network fail pe hi DOWN alert.
- **Job do baar chala:** idempotency guard hai; `tasks` me double entry dikhe to `jobs` table ka next_run dekho.
- **Pause ke baad kuch nahi hota:** `resume` bhejo, `status` me Automation ON dekho.
- **Rayvice site kharab dikhe:** agent sirf monitor karta hai, fix = plan + approval. Prod ko haath nahi lagata.
