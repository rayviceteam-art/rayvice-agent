# TOOLS — registry (`tools_setup.py` startup pe load hota hai)

| Tool | Kya karta hai | Limit key |
|---|---|---|
| `web_search` | Tavily (key ho to) else DuckDuckGo | search |
| `fetch_url` | Public page text (no JS-bypass) | search |
| `website_check` | Site + backend health | monitor |
| `content_draft` | Post draft + quality check | openrouter |
| `lead_hunt` | Public opportunity hunt | search |

- `tools_registry.run(name)` → rate-limit check → retry + backoff → circuit-breaker (5 fail = 5 min open).
- Ek tool fail = baaki kaam rukega nahi (non-fatal, audit me record).
- Naya tool: function banao + `tools_setup.py` me register karo + `TOOL_RATE_MAP` me limit jodo + test likho.
