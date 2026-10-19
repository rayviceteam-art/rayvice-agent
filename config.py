"""Central config. No hard-coded secrets. All secrets from .env only."""
import os

def load_dotenv(path=".env"):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and v and k not in os.environ:
                os.environ[k] = v

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
load_dotenv(".env")

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
AI_MODE = os.environ.get("AI_MODE", "free").lower()
ALLOW_PAID_AI = os.environ.get("ALLOW_PAID_AI", "false").lower() == "true"
FREE_MODELS = [m.strip() for m in os.environ.get("FREE_MODELS", "openrouter/free").split(",") if m.strip()]
FREE_DAILY_LIMIT = int(os.environ.get("FREE_DAILY_LIMIT", "180") or 180)
# Groq free tier (primary AI). Multiple keys -> rotator (429 pe agli key).
_grk = os.environ.get("GROQ_API_KEYS", "") or os.environ.get("GROQ_API_KEY", "")
GROQ_API_KEYS = [k.strip() for k in _grk.split(",") if k.strip()]
GROQ_API_KEY = GROQ_API_KEYS[0] if GROQ_API_KEYS else ""
GROQ_BASE_URL = os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
GROQ_MODELS = [m.strip() for m in os.environ.get(
    "GROQ_MODELS", "openai/gpt-oss-120b,qwen/qwen3.8-27b,openai/gpt-oss-20b").split(",") if m.strip()]
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
AGENT_DB_PATH = os.environ.get("AGENT_DB_PATH", "data/agent.db")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
RAYVICE_SITE = os.environ.get("RAYVICE_SITE", "https://www.rayvice.com")
RAYVICE_BACKEND = os.environ.get("RAYVICE_BACKEND", "https://rayvice-backend.onrender.com")
# Owner language: hinglish (roman) by default. All owner-facing replies follow this.
AGENT_LANG = os.environ.get("AGENT_LANG", "hinglish").lower()
# Timezones: TIMEZONE drives the scheduler wall-clock (owner operates IST).
# BUSINESS_TZ is Australia/Sydney per spec (business-side dates). Both configurable.
TIMEZONE = os.environ.get("TIMEZONE", "Asia/Kolkata")
BUSINESS_TZ = os.environ.get("BUSINESS_TZ", "Australia/Sydney")
# Emergency stop: false = all external actions stop (research/reporting may continue).
AUTOMATION_ENABLED = os.environ.get("AUTOMATION_ENABLED", "true").lower() == "true"
# Agent mode: OBSERVE | ASSIST | SUPERVISED_AUTO | FULL_AUTO (default safe)
AGENT_MODE = os.environ.get("AGENT_MODE", "SUPERVISED_AUTO").upper()
# GitHub (optional, read-only until token + approval). Never hard-code.
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "")
# Deployment map (discovered, not assumed). Rayvice API server stays as-is.
DEPLOY_FRONTEND = os.environ.get("DEPLOY_FRONTEND", "vercel:rayvice.com")
DEPLOY_BACKEND = os.environ.get("DEPLOY_BACKEND", "render:rayvice-backend.onrender.com")
DEPLOY_DB = os.environ.get("DEPLOY_DB", "neon-postgres")

# --- Social media automation (Rayvice master prompt) ---
# DRY-RUN default TRUE: koi real post nahi jayega jab tak explicitly off na kiya jaye.
SOCIAL_DRYRUN = os.environ.get("SOCIAL_DRYRUN", "true").lower() == "true"
# Social state apni alag SQLite file me (public repo me sirf marketing state jata hai,
# leads/chat wala agent.db kabhi nahi).
SOCIAL_DB_PATH = os.environ.get("SOCIAL_DB_PATH", "data/social.db")
# Business timezone for publishing wall-clock + DST-aware gating.
SOCIAL_TZ = os.environ.get("SOCIAL_TZ", "Australia/Sydney")
# Sydney-local publish hours (comma list). Tick bahar hai to skip, isliye DST safe.
SOCIAL_PUBLISH_HOURS = [h.strip() for h in os.environ.get("SOCIAL_PUBLISH_HOURS", "09:00,12:30,17:30").split(",") if h.strip()]
# Platforms jinka intent enabled hai (x hamesha blocked rahega).
SOCIAL_PLATFORMS = [p.strip().lower() for p in os.environ.get("SOCIAL_PLATFORMS", "instagram,facebook,linkedin").split(",") if p.strip()]
# Reddit: sirf in subreddits me, aur tab hi jab rules allow kare.
SOCIAL_REDDIT_SUBS = [s.strip() for s in os.environ.get("SOCIAL_REDDIT_SUBS", "").split(",") if s.strip()]
# Media: image provider chain + public base (GitHub raw) publishing APIs ke liye.
IMAGE_PROVIDER = os.environ.get("IMAGE_PROVIDER", "card").lower()
IMAGE_API_KEY = os.environ.get("IMAGE_API_KEY", "")
MEDIA_PUBLIC_BASE = os.environ.get("MEDIA_PUBLIC_BASE", "").rstrip("/")
# Retry policy
SOCIAL_MAX_ATTEMPTS = int(os.environ.get("SOCIAL_MAX_ATTEMPTS", "5") or 5)
SOCIAL_RETRY_BASE_SECONDS = int(os.environ.get("SOCIAL_RETRY_BASE_SECONDS", "60") or 60)
# Telegram: sirf is user ID ke commands chalenge (set karna zaroori hai for production).
TELEGRAM_ALLOWED_USER_ID = os.environ.get("TELEGRAM_ALLOWED_USER_ID", "")
# --- Outreach (daily cold-email lead gen; Spam Act aware) ---
OUTREACH_ENABLED = os.environ.get("OUTREACH_ENABLED", "false").lower() == "true"
OUTREACH_DRYRUN = os.environ.get("OUTREACH_DRYRUN", "true").lower() == "true"
OUTREACH_FROM_NAME = os.environ.get("OUTREACH_FROM_NAME", "Rayvice")
OUTREACH_FROM_EMAIL = os.environ.get("OUTREACH_FROM_EMAIL", "")
OUTREACH_REPLY_TO = os.environ.get("OUTREACH_REPLY_TO", "") or os.environ.get("OUTREACH_FROM_EMAIL", "")
OUTREACH_SMTP_HOST = os.environ.get("OUTREACH_SMTP_HOST", "smtp.gmail.com")
OUTREACH_SMTP_PORT = int(os.environ.get("OUTREACH_SMTP_PORT", "465") or 465)
OUTREACH_IMAP_HOST = os.environ.get("OUTREACH_IMAP_HOST", "imap.gmail.com")
OUTREACH_IMAP_PORT = int(os.environ.get("OUTREACH_IMAP_PORT", "993") or 993)
OUTREACH_EMAIL_PASS = os.environ.get("OUTREACH_EMAIL_PASS", "") or os.environ.get("OUTREACH_SMTP_PASS", "")
OUTREACH_DAILY_CAP = int(os.environ.get("OUTREACH_DAILY_CAP", "30") or 30)
OUTREACH_STATES = [s.strip().upper() for s in os.environ.get("OUTREACH_STATES", "NSW,VIC,QLD").split(",") if s.strip()]
OUTREACH_FOLLOWUP_DAYS = int(os.environ.get("OUTREACH_FOLLOWUP_DAYS", "4") or 4)
OUTREACH_FOLLOWUP_CAP = int(os.environ.get("OUTREACH_FOLLOWUP_CAP", "3") or 3)
OUTREACH_SENDER_ABN = os.environ.get("OUTREACH_SENDER_ABN", "")
# Meta (Facebook Page + Instagram professional)
META_GRAPH_VERSION = os.environ.get("META_GRAPH_VERSION", "v23.0")
META_APP_ID = os.environ.get("META_APP_ID", "")
META_APP_SECRET = os.environ.get("META_APP_SECRET", "")
META_ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN", "")
META_PAGE_ID = os.environ.get("META_PAGE_ID", "")
INSTAGRAM_ACCOUNT_ID = os.environ.get("INSTAGRAM_ACCOUNT_ID", "")
# X (blocked: no free API tier since Feb 2026)
X_CLIENT_ID = os.environ.get("X_CLIENT_ID", "")
X_CLIENT_SECRET = os.environ.get("X_CLIENT_SECRET", "")
X_ACCESS_TOKEN = os.environ.get("X_ACCESS_TOKEN", "")
# Reddit (script app OAuth)
REDDIT_CLIENT_ID = os.environ.get("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.environ.get("REDDIT_CLIENT_SECRET", "")
REDDIT_REFRESH_TOKEN = os.environ.get("REDDIT_REFRESH_TOKEN", "")
REDDIT_USER_AGENT = os.environ.get("REDDIT_USER_AGENT", "rayvice-agent/0.1 by rayviceteam-art")
# LinkedIn
LINKEDIN_CLIENT_ID = os.environ.get("LINKEDIN_CLIENT_ID", "")
LINKEDIN_CLIENT_SECRET = os.environ.get("LINKEDIN_CLIENT_SECRET", "")
LINKEDIN_ACCESS_TOKEN = os.environ.get("LINKEDIN_ACCESS_TOKEN", "")
LINKEDIN_AUTHOR_URN = os.environ.get("LINKEDIN_AUTHOR_URN", "")
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "")
# One style line injected into every AI prompt + used for static replies.
HINGLISH_STYLE = ("Reply in Roman Hinglish (Hindi written in English letters, like 'samajh gaya bhai'), "
                  "simple words, short lines, friendly. No heavy English.")

# Never log these
SECRET_KEYS = {"OPENROUTER_API_KEY", "TELEGRAM_BOT_TOKEN", "GITHUB_TOKEN", "TAVILY_API_KEY",
               "META_APP_SECRET", "META_ACCESS_TOKEN", "X_CLIENT_SECRET", "X_ACCESS_TOKEN",
               "REDDIT_CLIENT_SECRET", "REDDIT_REFRESH_TOKEN", "LINKEDIN_CLIENT_SECRET",
               "LINKEDIN_ACCESS_TOKEN", "IMAGE_API_KEY",
               "OUTREACH_EMAIL_PASS", "OUTREACH_SMTP_PASS", "GROQ_API_KEY", "GROQ_API_KEYS"}

def has_secrets():
    return bool(OPENROUTER_API_KEY and TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)

def redacted(key, value):
    if key in SECRET_KEYS and value:
        return value[:4] + "..." + value[-4:] if len(value) > 8 else "****"
    return value
