# SECURITY — Rayvice Agent

- Secrets sirf `.env` (perm 600). Code/git/log/memory/knowledge me kabhi nahi.
- `SECRET_KEYS` redaction: audit + logs me token dikhega nahi.
- `.env` git me nahi jayega (`.gitignore`).
- Least privilege: GitHub token ho to bhi default read-only; write = approval.
- No ToS bypass: scraping/CAPTCHA/login/rate-limit bypass mana hai.
- No private-data access, no impersonation, no fake identity.
- Production: Rayvice API server SAME; deploy/prod-DB/infra/finance = approval mandatory.
- Audit: `audit` table me har action (timestamp, agent, task, tool, decision, approval, result, error).
- Incident mile (outage/security/data-loss risk) → CRITICAL notify turant.
