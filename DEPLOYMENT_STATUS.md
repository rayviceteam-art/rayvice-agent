# DEPLOYMENT STATUS — Rayvice Social Automation

Updated: 2026-10-18 · Owner: Rayvice · Budget: ₹0 (no card)

## Current state: `DEPLOYED=YES · DRY_RUN=NO · PUBLISHING=LIVE (FB+IG)`

> **LIVE ACTIVATED (owner approval, 2026-10-18):** dry-run review complete.
> First live posts: **Mon 19 Oct, 9:00 AM Sydney** — automatic, Sydney windows 9:00/12:30/17:30.
> Rollback: Telegram `pause`, ya `SOCIAL_DRYRUN=true` GH var flip — instant wapas dry-run.

| Layer | Component | Status |
|---|---|---|
| App | `social/` pipeline + CLI | ✅ COMPLETE + TESTED (26 tests pass, 2026-10-18) |
| Repo | github.com/rayviceteam-art/rayvice-agent (public) | ✅ LIVE — push verified, commit-back verified |
| Tests | `test_social.py` 26/26, `test_all.py` 22/22 · CI Tests workflow | ✅ PASS (local + GitHub Actions) |
| Scheduler | GitHub Actions hourly cron + dispatch | ✅ RUNNING — CI tick verified (3 drafts, Pollinations image, dry publish 2, Telegram alert) |
| Secrets | OPENROUTER, TELEGRAM×3, TAVILY + 3 vars | ✅ SET via API (values kabhi repo me nahi) |
| DB | `data/social.db` commit-back | ✅ VERIFIED (chore: social state commit pushed by workflow) |
| Media | Branded card (real logo, Pillow) default; screenshot-frame + Pollinations AI opt-in | ✅ card v2 verified; feature spotlight system live |
| Telegram | notifications + commands | ✅ notify path live-verified (local + CI); TELEGRAM_ALLOWED_USER_ID set |
| Platforms | Meta (FB Page: Rayvice + IG @rayviceofficial) | ✅ **LIVE ENABLED** — first real posts 19 Oct 9:00 Sydney |
| Platforms | Reddit / LinkedIn | 🔒 BLOCKED — credentials (owner, Phase 5); unconfigured platforms auto-skip |
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

## Feature spotlight posts (product features)

- Har **Sunday** ek product feature post — rotation: scheduling → invoicing → dashboard → rate-splits → compliance.
- Real screenshot mile (`assets/screenshots/<key>.png|jpg|jpeg|webp`) to branded frame me use hota hai; warna same content ka branded card (post rukta nahi).
- Screenshots **demo data** ke saath lena — koi real participant name/number nahi (validators PII block karte hain).
- Details: `assets/screenshots/README.md`.

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

1. ~~GitHub PAT~~ ✅ done (repo + workflow scope) — Phase 4 unlock.
2. ~~`TELEGRAM_ALLOWED_USER_ID`~~ ✅ set (2002821626).
3. Platform apps (Phase 5): Reddit (~10 min), Meta (~15 min), LinkedIn (~15 min). X: skip (paid only).
4. Frontend repo (`Rayvice-frontend`) leaked PAT — owner ne abhi defer kiya; **revoke recommended** (jo bhi ho, hamari pipeline us token ko use nahi karti).

## Rollback

- Code: `git revert` / `git checkout <prev>` — kuch bhi irreversible nahi.
- Publishing: `social pause` + Actions workflow disable (`gh workflow disable` ya UI).
- Hard stop: workflow file delete — pipeline band, data safe.

## Group Content Kit (2026-10-18)

- Meta Group API closed hai — groups me auto-join/auto-post/auto-comment **possible nahi** (koshish = Page ban).
- Solution: `social/group_kit.py` — roz subah (Sydney 7-10) Telegram pe kit: 5 text posts (6-pillar rotation, roz badalta) + 5-6 comment replies + 2 IG captions. Owner khud groups me paste karta hai.
- Posts/comments me ZERO promo (brand = owner profile); soft CTA sirf IG captions me.
- Dedup: last 30 kits se Jaccard overlap check; LLM fail -> hand-written template kit (kit kabhi khali nahi).
- Commands: `social kit` (aaj ka bhejo) | `social kit regen` | `social kit resend`. Runner: `scripts/run_group_kit.py --send` (CI tick ke saath chalta hai).
- Posting (social publish) filhaal **paused**: `AUTOMATION_ENABLED=false` + `SOCIAL_DRYRUN=true` (GH var bhi).
