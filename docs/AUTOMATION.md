# AUTOMATION — schedule (TIMEZONE wall-clock, restart-proof sqlite)

Default (badal sakte ho, hard-code nahi hai):

| Job | Time | Kaam |
|---|---|---|
| morning.research | 08:00 | market + content research |
| daily.content | 09:30 | post draft → Telegram approval |
| lead.hunt | 10:00 | details + ready msg (bhejna nahi) |
| website.check | har 6h | UP/DOWN + alert |
| evening.report | 20:00 | daily report |
| weekly.report | Mon 09:00 | weekly rollup |
| monthly.summary | 1st 09:00 | monthly rollup |

- `TIMEZONE` (default Asia/Kolkata — owner IST), `BUSINESS_TZ` (default Australia/Sydney).
- Duplicate guard: daily jobs ek din me ek baar hi chalenge (idempotency).
- Pause: `pause` bhejo (AUTOMATION_ENABLED=false) → external stop, research/report chalte rahenge. `resume` se wapas.
- `schedule` bhejo → live time-table dikhega.
