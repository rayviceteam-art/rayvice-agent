# DEPLOYMENT STATUS — Rayvice Social Automation

Updated: 2026-10-17 · Owner: Rayvice · Budget: ₹0 (no card)

## Current state: `DEPLOYED=NO · DRY_RUN=YES · PUBLISHING=NONE`

| Layer | Component | Status |
|---|---|---|
| App | `social/` pipeline + CLI | ✅ COMPLETE + TESTED (dry-run pass, 2026-10-17) |
| Tests | `test_social.py` 22/22, `test_all.py` 22/22 | ✅ PASS |
| Scheduler | GitHub Actions hourly cron | ⏳ workflow file ready — repo push + secrets pending |
| DB | `data/social.db` (social state) | ✅ local; GH Actions me persist karne ke liye commit-back step workflow me hai |
| Media | `media/` + raw.githubusercontent URLs | ✅ local Pillow card verified; public URL verify `MEDIA_PUBLIC_BASE` set hone par |
| Telegram | notifications + commands | ✅ notify path live-verified (audit me `telegram` entry dekho); ⚠️ `TELEGRAM_ALLOWED_USER_ID` set karna pending (auth tighten) |
| Platforms | Meta / Reddit / LinkedIn | 🔒 BLOCKED — credentials (owner, Phase 5) |
| Platforms | X | ❌ NOT AVAILABLE ON FREE TIER (no workaround) |

## Environment matrix

| Option | Card? | Free? | Verdict |
|---|---|---|---|
| GitHub Actions (public repo) | Nahi | ✅ unlimited min | **CHOSEN** — cron tick + tests + backup |
| Oracle Cloud Always Free | **Haan** (required) | — | Rejected (budget policy) |
| Fly / Railway / Koyeb | Haan | — | Rejected |
| Render free | Nahi | 750h/mo, sleeps 15min, ephemeral FS | Backend already hai; social state ke liye unsuitable |
| Phone (PRoot) | Nahi | ✅ | Dev only — `main.py` optional; phone off = agent off |

## How it runs in production (post Phase 4)

1. GitHub Actions `social-tick.yml` har ghante `scripts/run_social.py --tick` chalata hai.
2. App Sydney-hour gate check karta hai (09:00/12:30/17:30 AEST) — off-hours = instant quiet exit.
3. Run ke baad workflow `data/social.db` + `media/` ko repo me commit-back karta hai (state persistence).
4. Failures: Telegram alert + `data/social.db` me error log + exponential backoff retry (max 5, phir dead-letter).
5. Owner commands: Telegram `social status|run|week|errors|retry` ya `pause`/`resume`.

## Backup & restore

- **Backup:** `data/social.db` + `media/` repo me commit-back = git history hi backup hai (rollback possible).
- **Extra snapshot:** `social.db.bak` copy `data/backups/` me (workflow step, 7-day rotation).
- **Restore:** `git checkout <commit> -- data/social.db media/` ya `.bak` file copy — `ensure_schema()` idempotent hai.
- Sensitive `data/agent.db` (leads/chat) **kabhi repo me nahi** — uska backup owner-specific.

## Logs (kahan dekhna hai)

| Cheez | Kahan |
|---|---|
| Run history | `social_runs` table (`social status` / DB query) |
| Errors | `social_errors` table + `logs/agent.log` (Telegram `social errors`) |
| Publish records | `social_publications` (status OK/DRY_RUN/FAILED...) |
| Audit trail | `data/agent.db` → `audit` table (redacted) |

## Quota / rate-limit counters

- `social_quota` table: per-platform per-day publish counts (Meta 25/24h guard, Reddit subreddit limits).
- AI: existing daily free counter (`FREE_DAILY_LIMIT`) + backoff; paid blocked (`ALLOW_PAID_AI=false`).

## Blockers (owner action)

1. **GitHub PAT** (`repo` + `workflow`) → repo push + Actions enable. **Phase 4 unlock.**
2. `TELEGRAM_ALLOWED_USER_ID` (owner ki Telegram numeric ID) → command authorization tighten.
3. Platform apps (Phase 5): Reddit (~10 min), Meta (~15 min), LinkedIn (~15 min). X: skip.
4. Frontend repo (`Rayvice-frontend`) ke git config me **leaked PAT** — revoke + remote URL clean (execution mere haath me jab owner karne bole).

## Rollback

- Code: `git revert` / `git checkout <prev>` — kuch bhi irreversible nahi.
- Publishing: `social pause` + Actions workflow disable (`gh workflow disable` ya UI).
- Hard stop: workflow file delete — pipeline band, data safe.
