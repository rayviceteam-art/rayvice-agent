"""Social schema + migrations. Idempotent, additive-only (never drops data).

Design rules:
- UTC timestamps internally (ISO + 'Z'), display TZ conversion happens at edges.
- Unique idempotency keys prevent duplicate publication.
- Tokens/secret values DB me save nahi hote — sirf env var names (reference).
"""
import os
import sqlite3
from datetime import datetime, timezone

import config

SCHEMA_VERSION = 1

DDL = [
    """CREATE TABLE IF NOT EXISTS schema_version(
      component TEXT PRIMARY KEY, version INTEGER, applied TEXT)""",
    """CREATE TABLE IF NOT EXISTS social_ideas(
      id TEXT PRIMARY KEY, ts TEXT, theme TEXT, topic TEXT, category TEXT,
      source TEXT, status TEXT, detail TEXT)""",
    """CREATE TABLE IF NOT EXISTS social_drafts(
      id TEXT PRIMARY KEY, ts TEXT, idea_id TEXT, platform TEXT, format TEXT,
      hook TEXT, body TEXT, cta TEXT, hashtags TEXT, media_id TEXT,
      status TEXT, validation TEXT, model TEXT, prompt_version TEXT,
      idempotency_key TEXT UNIQUE, content_hash TEXT)""",
    """CREATE TABLE IF NOT EXISTS social_media(
      id TEXT PRIMARY KEY, ts TEXT, kind TEXT, path TEXT, url TEXT, provider TEXT,
      prompt TEXT, width INTEGER, height INTEGER, bytes INTEGER, sha256 TEXT,
      status TEXT, notes TEXT)""",
    """CREATE TABLE IF NOT EXISTS social_queue(
      id TEXT PRIMARY KEY, ts TEXT, draft_id TEXT, platform TEXT,
      scheduled_utc TEXT, status TEXT, attempts INTEGER, next_attempt_utc TEXT,
      idempotency_key TEXT UNIQUE, last_error TEXT, retry_after INTEGER,
      dead_letter_reason TEXT, updated TEXT)""",
    """CREATE TABLE IF NOT EXISTS social_accounts(
      platform TEXT PRIMARY KEY, enabled INTEGER, account_type TEXT, account_ref TEXT,
      token_env TEXT, scopes TEXT, status TEXT, last_verified TEXT, notes TEXT)""",
    """CREATE TABLE IF NOT EXISTS social_publications(
      id TEXT PRIMARY KEY, ts TEXT, queue_id TEXT, draft_id TEXT, platform TEXT,
      platform_post_id TEXT, url TEXT, status TEXT, dry_run INTEGER, raw TEXT)""",
    """CREATE TABLE IF NOT EXISTS social_runs(
      run_id TEXT PRIMARY KEY, workflow TEXT, started TEXT, ended TEXT,
      status TEXT, detail TEXT)""",
    """CREATE TABLE IF NOT EXISTS social_errors(
      id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, run_id TEXT, platform TEXT,
      category TEXT, code TEXT, message TEXT, retryable INTEGER)""",
    """CREATE TABLE IF NOT EXISTS social_quota(
      id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, platform TEXT, metric TEXT,
      value REAL, note TEXT)""",
    """CREATE TABLE IF NOT EXISTS social_backups(
      id TEXT PRIMARY KEY, ts TEXT, path TEXT, sha256 TEXT, bytes INTEGER, status TEXT)""",
    """CREATE TABLE IF NOT EXISTS social_config(
      key TEXT PRIMARY KEY, value TEXT, updated TEXT)""",
    """CREATE TABLE IF NOT EXISTS social_locks(
      name TEXT PRIMARY KEY, owner TEXT, acquired_utc TEXT, expires_utc TEXT)""",
    """CREATE TABLE IF NOT EXISTS social_group_kit(
      date TEXT PRIMARY KEY, ts TEXT, sent_at TEXT, status TEXT,
      prompt_version TEXT, payload TEXT)""",
]

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_queue_status ON social_queue(status, next_attempt_utc)",
    "CREATE INDEX IF NOT EXISTS idx_pub_platform ON social_publications(platform, ts)",
    "CREATE INDEX IF NOT EXISTS idx_drafts_platform ON social_drafts(platform, ts)",
    "CREATE INDEX IF NOT EXISTS idx_errors_ts ON social_errors(ts)",
]


def connect():
    path = getattr(config, "SOCIAL_DB_PATH", "") or "data/social.db"
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    c = sqlite3.connect(path, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    return c


def utcnow():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_schema():
    c = connect()
    for stmt in DDL + INDEXES:
        c.execute(stmt)
    row = c.execute("SELECT version FROM schema_version WHERE component='social'").fetchone()
    if not row:
        c.execute("INSERT INTO schema_version VALUES('social',?,?)", (SCHEMA_VERSION, utcnow()))
    elif row["version"] < SCHEMA_VERSION:
        c.execute("UPDATE schema_version SET version=?, applied=? WHERE component='social'",
                  (SCHEMA_VERSION, utcnow()))
    c.commit()
    c.close()


def log_error(run_id, platform, category, message, code="", retryable=False):
    c = connect()
    c.execute("INSERT INTO social_errors(ts,run_id,platform,category,code,message,retryable) VALUES(?,?,?,?,?,?,?)",
              (utcnow(), run_id or "", platform or "", category or "", str(code), str(message)[:2000],
               1 if retryable else 0))
    c.commit()
    c.close()


def record_run(run_id, workflow, status="RUNNING", detail=""):
    c = connect()
    r = c.execute("SELECT run_id FROM social_runs WHERE run_id=?", (run_id,)).fetchone()
    if not r:
        c.execute("INSERT INTO social_runs VALUES(?,?,?,?,?,?)", (run_id, workflow, utcnow(), "", status, detail[:2000]))
    else:
        ended = "" if status == "RUNNING" else utcnow()
        c.execute("UPDATE social_runs SET status=?, detail=?, ended=? WHERE run_id=?",
                  (status, detail[:2000], ended, run_id))
    c.commit()
    c.close()
