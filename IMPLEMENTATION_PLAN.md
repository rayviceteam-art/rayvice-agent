# IMPLEMENTATION PLAN — Rayvice Social Automation

Source: `Rayvice_OpenCode_Master_Prompt.md` (full autonomous social media automation project)
Repo: `rayviceteam-art/rayvice-agent` (public) · Owner: Rayvice · Budget: ₹0, no card

## Phase status (statuses: COMPLETE / TESTED / RUNNING / BLOCKED / NOT TESTED / NOT AVAILABLE ON FREE TIER)

| Phase | Kya | Status |
|---|---|---|
| 1 | Environment audit + free hosting eligibility | **COMPLETE** (2026-10-17) |
| 2 | Architecture + local build (social package, DB, adapters, docs) | **COMPLETE** (2026-10-17) |
| 3 | Automated tests + dry-run pipeline | **TESTED** (23/23 social tests, 22/22 core, real dry-run + CI dry-run pass) |
| 4 | GitHub deploy: repo + Actions cron + secrets | **RUNNING** — repo live, secrets set, hourly tick verified end-to-end (2026-10-17) |
| 5 | Platform OAuth connections (Meta/LinkedIn/Reddit apps) | **BLOCKED** — owner app creation pending; X = NOT AVAILABLE ON FREE TIER |
| 6 | Production publishing enable | **NOT STARTED** — requires Phase 5 + owner approval |
| 7 | Scheduler reliability + backup + recovery verify | **PARTIAL** — backup artifact + commit-back verified; long-term soak pending |

## Phase 1 findings (audit)

- Environment: Android → PRoot Ubuntu 26.04 (aarch64). Phone off = process off ⇒ persistent host chahiye.
- **Oracle Cloud Always Free: credit/debit card REQUIRED** (official FAQ) ⇒ budget policy ke against, BLOCKED.
- Fly/Railway/Koyeb: card required ⇒ rejected. Render free: 750h/mo, 15-min idle sleep, ephemeral FS ⇒ media/DB ke liye unsuitable.
- **GitHub Actions chuna:** public repo = unlimited minutes, no card; private = 2000 min/mo (hourly tick ≈ 900–1400 min/mo — tight).
- X API: free tier discontinued Feb 2026 (pay-per-use $0.015/post) ⇒ **NOT AVAILABLE ON FREE TIER**.
- n8n: card-free persistent host nahi ⇒ master prompt ka allowed alternative: scheduled scripts (yehi banaya).
- Existing: `rayvice-agent` (Telegram + OpenRouter + SQLite) ko hi upgrade kiya, koi purani cheez delete nahi.

## Phase 2 — what was built (2026-10-17)

- `social/` package: db, validators, calendar, media, generator, platforms (meta/reddit/linkedin/x), publish_queue, pipeline
- `scripts/run_social.py` CLI (tick/status/errors/week/verify/retry-dead/capabilities)
- `test_social.py` — 22 tests (mocked APIs, no network)
- DB split: `data/social.db` (committable) vs `data/agent.db` (sensitive, gitignored)
- Telegram: `/status /queue /errors /pause /resume` + `social ...` commands + owner user-ID authorization
- Docs: is file, `docs/platform-capabilities.md`, `DEPLOYMENT_STATUS.md`, ARCHITECTURE update

## Phase 4 — GitHub deploy (DONE 2026-10-17)

1. ✅ Owner PAT (repo + workflow scope) — set as local `GITHUB_TOKEN` (.env, gitignored).
2. ✅ Repo create `rayviceteam-art/rayvice-agent` (public) + push.
3. ✅ GH Secrets: OPENROUTER_API_KEY, TELEGRAM_BOT_TOKEN/CHAT_ID/ALLOWED_USER_ID, TAVILY_API_KEY + vars (MEDIA_PUBLIC_BASE, SOCIAL_PLATFORMS, SOCIAL_DRYRUN=true) — API se set, values kabhi repo me nahi.
4. ✅ Workflow `social-tick.yml`: hourly cron + manual dispatch; verified run: 3 drafts (FB/IG/LI), Pollinations image, dry publishes, state commit-back, backup artifact.
5. ✅ CI Tests workflow pass (28+22 tests).

## Phase 5 — platform connections (pending, owner zरूरी)

| Platform | Steps (owner) | Time |
|---|---|---|
| Reddit | reddit.com/prefs/apps → "script" app → client_id+secret; OAuth refresh token flow (guide milega) | ~10 min |
| Meta (FB+IG) | developers.facebook.com → app → Page + Pro IG link → long-lived token | ~15 min |
| LinkedIn | linkedin developer app → member/page permissions → OAuth token | ~15 min |
| X | ❌ skip (paid only) | — |

## Definition of Done mapping

- [x] Project files created · [x] Environment audited · [x] Architecture documented
- [x] Free hosting eligibility checked (documented) · [x] App/workflow implementation completed
- [x] Database + migrations working · [x] Secrets protected (.env gitignored, no secrets in DB/repo; GH Secrets via API)
- [x] AI generation tested (mock + real dry-run, local + CI) · [x] Media pipeline tested (Pollinations live + Pillow card verified)
- [x] Telegram bot configured + authorization tested (notify path verified local + CI; allowed-user-ID set)
- [x] Each platform's API requirements documented (platform-capabilities.md)
- [ ] Each connected platform authenticated + tested (Phase 5)
- [x] Dry-run publication completed (real tick, dry_run=1/2) · [x] Duplicate-post protection verified (tests)
- [x] Retry + failure handling tested (backoff/dead-letter tests) · [x] Scheduling/timezone behaviour verified (calendar tests + CI tick)
- [x] Deployment health checked (CI tick success, state commit-back, artifacts) · [x] Backup/restore procedures documented (DEPLOYMENT_STATUS.md)
- [ ] Production publishing enabled **only with approval** · [x] Remaining blockers + costs documented
