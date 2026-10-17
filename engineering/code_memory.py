"""Technical knowledge base for Rayvice. Discovered facts only, secrets never.
IMPORTANT: values below came from the owner's repo docs. Anything else = UNKNOWN."""
import json
import os

PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "knowledge", "technical.json")

DEFAULTS = {
    "frontend": {"stack": "Next.js App Router + React + TS + Tailwind", "host": "Vercel rayvice.com"},
    "backend": {"stack": "Node Express + TS + Prisma + Zod", "host": "Render rayvice-backend.onrender.com (SAME RAKHNA HAI)"},
    "database": {"engine": "PostgreSQL Neon, tenant-isolated via businessId"},
    "auth": {"modes": "JWT access/refresh + Google OAuth 2.0", "hash": "Argon2id"},
    "payments": {"provider": "Stripe $24/$44 AUD (repo me Paddle sandbox ka bhi zikr hai — UNKNOWN kaunsa live hai)"},
    "trial": "9-day free trial, 1 participant limit",
    "known_bugs": [],
    "known_limitations": ["Free Postgres expiry (Render) — monitor karta hu", "Cold starts on free tier"],
    "testing": "backend: tests/ dir, frontend: eslint",
    "rule": "PRODUCTION KO HAATH NAHI LAGANA — monitor only, fix = plan + approval",
}

def read():
    try:
        with open(PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return dict(DEFAULTS)

def update(patch):
    d = read()
    d.update(patch)
    txt = json.dumps(d).lower()
    for bad in ("sk-", "gsk_", "secret", "password", "token"):
        if bad in txt:
            raise ValueError("Secret technical memory me nahi jayega bhai, .env me rakho")
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    tmp = PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2)
    os.replace(tmp, PATH)
    return d

def text():
    d = read()
    lines = ["🔧 Rayvice technical (discovered, same rakhna hai):"]
    for k in ("frontend", "backend", "database", "auth", "payments", "trial", "rule"):
        lines.append(f"• {k}: {d.get(k)}")
    bugs = d.get("known_bugs", [])
    lines.append(f"• known_bugs: {len(bugs)}" + (f" — {bugs[:5]}" if bugs else " (koi record nahi)"))
    return "\n".join(str(x)[:1500] for x in lines)
