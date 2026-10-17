# Platform Capabilities — Rayvice Social Automation

Last verified: **2026-10-17** (official docs + pricing pages)
Rule: koi platform "connected" nahi maana jata jab tak real authenticated `verify()` pass na ho.
Auto-publish sirf credential + permission verify hone ke baad enable hota hai.

| | Instagram | Facebook | LinkedIn | Reddit | X |
|---|---|---|---|---|---|
| **Official method** | Meta Instagram Content Publishing API (Graph) | Meta Graph API — Page feed/photos | LinkedIn REST (ugcPosts) | Reddit OAuth API `/api/submit` | X API v2 `POST /2/tweets` |
| **Account type** | Instagram Professional (Business/Creator) + linked FB Page | Facebook Page (personal profile publishing NOT supported) | Member (w_member_social) ya Company Page admin (w_organization_social) | Reddit account + "script" app | Any (paid credits needed) |
| **OAuth scopes** | instagram_basic, instagram_content_publish, pages_show_list, pages_read_engagement | pages_show_list, pages_read_engagement, pages_manage_posts | openid, profile, w_member_social / w_organization_social | identity, submit, read | tweet.write, users.read |
| **Access available?** | ✅ CONNECTED (@rayviceofficial, Page: Rayvice) | ✅ CONNECTED (Page: Rayvice) | App review ke baad (BLOCKED abhi) | Script app = approval nahi (BLOCKED abhi) | ❌ BLOCKED_API_ACCESS |
| **Free?** | ✅ Haan | ✅ Haan | ✅ Haan | ✅ Haan | ❌ Nahi (Feb 2026 se) |
| **Quota / rate limits** | ~25 API posts / 24h; 1 container step + 1 publish step | Page rate limits (generous); free | Share API rate limits apply | OAuth ~100 QPM | pay-per-use: $0.015/post ($0.20 if URL), card required |
| **Known limitations** | Image public URL zaroori; text-only post nahi hota; carousel flow multi-step | Page token expiry handle karna padta hai (60-day tokens) | Some permissions need app review (Community Management); image upload flow Phase 5 | Subreddit rules + self-promotion restrictions; daily forced post = spam risk | Koi free tier nahi; unofficial scraping/bots = policy violation (ham kabhi nahi karenge) |
| **Test result** | ✅ VERIFIED 2026-10-17 — @rayviceofficial read OK; media container create OK (no post) | ✅ VERIFIED 2026-10-17 — Page read OK (Rayvice) | NOT TESTED (credentials pending) | NOT TESTED (credentials pending) | NOT AVAILABLE ON FREE TIER |
| **Exact blocker** | — (connected; LIVE enable owner approval pe) | — (connected; LIVE enable owner approval pe) | LinkedIn app + OAuth token + (page ke liye) approval | client_id + secret + refresh_token + approved subreddit list | Card chahiye — budget ₹0 policy ke against. Owner decision required. |

## Capability statuses (master prompt vocabulary)

- `COMPLETE` — implemented + tests pass
- `TESTED` — real authenticated test pass hua
- `RUNNING` — production me actually chal raha hai (scheduler + verify)
- `BLOCKED` — credentials/approval pending (owner action chahiye)
- `NOT TESTED` — code ready hai lekin real credentials se verify nahi hua
- `NOT AVAILABLE ON FREE TIER` — free me possible hi nahi

X ke liye final decision: **NOT AVAILABLE ON FREE TIER** — adapter code maujood hai (`social/platforms/x.py`) lekin
publishing disabled hai; koi unofficial workaround nahi banega (policy + master prompt rule).

## Verification commands

```bash
python3 scripts/run_social.py --capabilities   # matrix (yahi file update karo jab bhi change ho)
python3 scripts/run_social.py --verify         # real authenticated check (jab credentials set ho)
```

Telegram se bhi: `social verify` / `social capabilities`
