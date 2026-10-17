"""Rayvice social media automation package.

Modules:
- db        : schema + migrations (SQLite, same DB as agent)
- validators: brand/compliance/length/duplicate checks
- calendar  : weekly content calendar (Australia/Sydney aware)
- media     : image generation (provider adapter + Pillow fallback) + public URLs
- generator : platform-specific structured content generation
- platforms : official-API publishing adapters (meta/reddit/linkedin/x)
- publish_queue: idempotent queue, retry/backoff, dead-letter
- pipeline  : daily orchestration (plan -> generate -> media -> publish -> report)
"""
