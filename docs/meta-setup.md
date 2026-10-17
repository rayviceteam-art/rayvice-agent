# Meta Setup (Facebook + Instagram) — Rayvice Agent

Prerequisites (✅ owner confirms both done):
- Facebook Page (owner admin hai)
- Instagram Professional (Business/Creator) account, FB Page se linked

> App Review ki zaroorat NAHI hai — owner app ka admin hai, isliye Development mode me bhi
> apne Page/IG pe publish kar sakta hai.

## Step 1 — Meta App banao (~5 min)

1. `developers.facebook.com` kholo → FB se login (wahi account jo Page admin hai)
2. **My Apps → Create App**
3. App name: `Rayvice Agent` · Contact email: apna
4. Use case: **Other** → App type: **Business**
5. Create → **Settings → Basic** → yahan se copy karo:
   - **App ID** (public, safe)
   - **App Secret** (private! kisi ko mat dena, sirf agent me)

## Step 2 — Short-lived token (Graph Explorer, ~5 min)

1. `developers.facebook.com/tools/explorer` kholo
2. Right sidebar: **Meta App** = `Rayvice Agent` select karo
3. **Permissions** → Add a Permission (ye 6 add karo):
   - `pages_show_list`
   - `pages_read_engagement`
   - `pages_manage_posts`
   - `instagram_basic`
   - `instagram_content_publish`
   - `business_management`
4. **Generate Access Token** dabao → FB popup me:
   - Apna Page (Rayvice) select/allow karo
   - Instagram account allow karo (sab toggles ON)
5. Token copy karo — **ye ~1-2 ghante me expire hota hai**, jaldi bhejo

## Step 3 — Agent ko do (3 values)

App ID | App Secret | Short-lived token

Agent ye karega (automatic):
1. Short-lived → **long-lived user token** (~60 din) exchange
2. `/me/accounts` se **Page ID + Page Access Token** (Page token non-expiring hota hai
   jab long-lived user token se bane)
3. `/{page-id}?fields=instagram_business_account` se **INSTAGRAM_ACCOUNT_ID**
4. `.env` + GitHub Secrets me set: `META_APP_ID`, `META_APP_SECRET`, `META_ACCESS_TOKEN`,
   `META_PAGE_ID`, `INSTAGRAM_ACCOUNT_ID`
5. `python3 scripts/run_social.py --verify` → real authenticated check
6. Dry-run tick → IG image upload + dry publish

## Token refresh (60 din baad)

Long-lived user token expire hone se pehle (60 din), Graph Explorer se naya short-lived
token lo → agent dobara exchange kar dega. Reminder Telegram pe aa sakta hai (baad me).

## Troubleshooting

| Problem | Fix |
|---|---|
| Token generate karte waqt Page nahi dikh raha | Page admin rights check karo |
| IG account nahi dikh raha | IG Professional hai? Page se linked hai? (Page Settings → Linked accounts) |
| `instagram_content_publish` permission missing | Explorer me permission add karke naya token banao |
| Publish pe error 190 | Token expire — naya short-lived token bhejo |
| API version error | `META_GRAPH_VERSION` update karna hoga (config) |
