# ARCHITECTURE — Rayvice Agent

```
OWNER (Telegram, Hinglish)
  ↓
RayviceOrchestrator
  ↓
Planner → Memory → Tool Selection → Execution → Verification → Approval → Audit
  ↓
Growth | Content | Sales | Support | Engineering | Analytics  (agents)
  ↓
TOOL LAYER: search | browser-fetch | github | website | scheduler | DB
  ↓
MEMORY: knowledge/*.md + sqlite (agent.db)
```

- **AI Gateway / Model Router:** Task → Classifier → Router → OpenRouter (`openrouter/free` first, fallback next free). OmniRouter-style self-hosted gateway baad me jud sakta hai (same interface).
- **Task-specific models:** research/classify/qualify = cheap-free; draft/code = stronger free; paid = blocked (`ALLOW_PAID_AI=false`).
- **Isolation:** `/root/rayvice-agent/` — apna `.env`, DB, logs, memory. Rayvice SaaS + purane agents untouched.
- Har component: clear responsibility, input/output, error handling, logging, tests, config.

## Social automation (master prompt implementation)

```
GitHub Actions (hourly cron, Sydney window gate in app)
  ↓ scripts/run_social.py --tick
social/pipeline.py  (run lock -> plan -> generate -> media -> enqueue -> publish -> report)
  ├─ calendar.py        weekly themes (Australia/Sydney, DST-safe window)
  ├─ generator.py       per-platform structured JSON drafts (OpenRouter free)
  ├─ validators.py      brand/compliance/length/AU-English/duplicate checks
  ├─ media.py           Pollinations adapter + Pillow branded-card fallback
  ├─ platforms/         meta | reddit | linkedin | x(BLOCKED) — official APIs only
  └─ publish_queue.py   idempotency keys, exponential backoff, Retry-After, dead-letter
       ↓
social.db (data/social.db)  ← public repo me sirf yehi jata hai (no leads/chat data)
media/                       ← public images (raw.githubusercontent URLs)
Telegram                     ← notifications + /commands (owner-only user ID)
```

- **Scheduler:** GitHub Actions hourly tick (phone OFF hone par bhi chalta hai). App ke andar
  Sydney-local publish-hours gate (09:00, 12:30, 17:30 default) — DST automatic safe.
- **DB split:** `data/agent.db` (leads/chat/approvals — gitignored, sensitive) vs
  `data/social.db` (marketing state — commit hota hai so GH Actions ke runs persistent rehte hain).
- **Idempotency:** draft key `draft:{platform}:{date}:{topic-hash}`, queue key `pub:{platform}:{draft_id}` —
  unique constraints; ambiguous failure par pehle state verify phir retry.
- **Dry-run:** `SOCIAL_DRYRUN=true` default. LIVE sirf owner approval + env switch ke baad.
- **No secrets in DB/repo:** sirf env var *names* accounts table me; values kabhi nahi.
