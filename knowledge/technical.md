# Technical — Rayvice (same rakhna hai, monitor only)

- Frontend: Next.js App Router + React + TS + Tailwind → Vercel (rayvice.com).
- Backend: Node Express + TS + Prisma + Zod → Render (rayvice-backend.onrender.com). **SAME RAKHNA HAI.**
- DB: Neon PostgreSQL, businessId tenant isolation.
- Auth: JWT access/refresh + Google OAuth 2.0, Argon2id.
- AI/voice: Groq Whisper + Gemini Flash (repo docs ke hisab se).
- Rule: production ko haath NAHI lagana. Fix = isolated plan + approval.
- Machine-readable copy: knowledge/technical.json.
