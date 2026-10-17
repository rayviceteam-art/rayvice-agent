"""Persistent scheduler with fixed daily times. Jobs survive restart via sqlite."""
import json
import sqlite3
import os
from datetime import datetime, timedelta, time as dtime, timezone

import config

def _tz():
    """IANA timezone from TIMEZONE env, fallback fixed +05:30. Never hard-code."""
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(config.TIMEZONE or "Asia/Kolkata")
    except Exception:
        return timezone(timedelta(hours=5, minutes=30))

def _now_utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)

# name, kind, interval_hours, run_at_IST(HH:MM or None=interval only), payload
DEFAULT_JOBS = [
    ("morning.research", "daily", 24, "08:00", {"tasks": ["market research", "lead discovery", "content research", "health check"]}),
    ("daily.content", "daily", 24, "09:30", {"tasks": ["content draft for manual post"]}),
    ("lead.hunt", "daily", 24, "10:00", {"tasks": ["public client hunting, details only, no sending"]}),
    ("evening.report", "daily", 24, "20:00", {"tasks": ["daily growth report to Telegram"]}),
    ("website.check", "interval", 6, None, {"tasks": ["site + api health"]}),
    ("weekly.report", "weekly", 168, "MON-09:00", {"tasks": ["sales/lead/content/feedback report"]}),
    ("monthly.summary", "monthly", 720, "01-09:00", {"tasks": ["business summary"]}),
]

def _db():
    os.makedirs(os.path.dirname(config.AGENT_DB_PATH) or ".", exist_ok=True)
    c = sqlite3.connect(config.AGENT_DB_PATH)
    c.execute("""CREATE TABLE IF NOT EXISTS jobs(
      name TEXT PRIMARY KEY, kind TEXT, interval_hours REAL,
      last_run TEXT, next_run TEXT, payload TEXT, enabled INTEGER, run_at TEXT)""")
    cols = [r[1] for r in c.execute("PRAGMA table_info(jobs)").fetchall()]
    if "run_at" not in cols:
        c.execute("ALTER TABLE jobs ADD COLUMN run_at TEXT")
    return c

def _now_utc():
    return datetime.utcnow()

def _next_run_utc(run_at, interval_hours):
    """Next occurrence in TIMEZONE wall-clock, returned as naive UTC. run_at: HH:MM | MON-HH:MM | DD-HH:MM | None."""
    now = _now_utc()
    tz = _tz()
    now_tz = now.replace(tzinfo=timezone.utc).astimezone(tz)
    if not run_at:
        return now + timedelta(hours=interval_hours)
    try:
        if run_at.startswith("MON-"):
            hh, mm = map(int, run_at[4:].split(":"))
            days_ahead = (0 - now_tz.weekday()) % 7  # Monday=0
            cand = datetime.combine(now_tz.date(), dtime(hh, mm)).replace(tzinfo=tz) + timedelta(days=days_ahead)
            if cand <= now_tz:
                cand += timedelta(days=7)
            return cand.astimezone(timezone.utc).replace(tzinfo=None)
        if "-" in run_at and len(run_at) == 8:  # DD-HH:MM monthly
            dd = int(run_at[:2])
            hh, mm = map(int, run_at[3:].split(":"))
            y, mo = now_tz.year, now_tz.month
            def cand_for(y, mo):
                import calendar
                last = calendar.monthrange(y, mo)[1]
                return datetime(y, mo, min(dd, last), hh, mm, tzinfo=tz)
            cand = cand_for(y, mo)
            if cand <= now_tz:
                mo += 1
                if mo > 12:
                    mo, y = 1, y + 1
                cand = cand_for(y, mo)
            return cand.astimezone(timezone.utc).replace(tzinfo=None)
        hh, mm = map(int, run_at.split(":"))
        cand = datetime.combine(now_tz.date(), dtime(hh, mm)).replace(tzinfo=tz)
        if cand <= now_tz:
            cand += timedelta(days=1)
        return cand.astimezone(timezone.utc).replace(tzinfo=None)
    except Exception:
        return now + timedelta(hours=interval_hours)

def ensure_defaults():
    c = _db()
    for name, kind, hrs, run_at, payload in DEFAULT_JOBS:
        r = c.execute("SELECT run_at, next_run FROM jobs WHERE name=?", (name,)).fetchone()
        nxt = (_next_run_utc(run_at, hrs).isoformat() + "Z")
        if not r:
            c.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?)",
                      (name, kind, hrs, "", nxt, json.dumps(payload), 1, run_at or ""))
        elif (r[0] or "") != (run_at or ""):
            # schedule definition changed -> repair to proper fixed time
            c.execute("UPDATE jobs SET kind=?, interval_hours=?, next_run=?, payload=?, run_at=? WHERE name=?",
                      (kind, hrs, nxt, json.dumps(payload), run_at or "", name))
    # drop legacy jobs no longer defined
    names = [j[0] for j in DEFAULT_JOBS]
    c.execute(f"DELETE FROM jobs WHERE name NOT IN ({','.join('?'*len(names))})", names)
    c.commit()
    c.close()

def due():
    ensure_defaults()
    c = _db()
    c.row_factory = sqlite3.Row
    now = _now_utc().isoformat() + "Z"
    rows = c.execute("SELECT * FROM jobs WHERE enabled=1 AND next_run<=?", (now,)).fetchall()
    c.close()
    return [dict(r) for r in rows]

def mark_done(name, interval_hours, run_at=None):
    c = _db()
    if run_at is None:
        r = c.execute("SELECT run_at, interval_hours FROM jobs WHERE name=?", (name,)).fetchone()
        if r:
            run_at, interval_hours = r[0] or None, r[1]
    now = _now_utc()
    nxt = (_next_run_utc(run_at, interval_hours).isoformat() + "Z")
    c.execute("UPDATE jobs SET last_run=?, next_run=? WHERE name=?",
              (now.isoformat() + "Z", nxt, name))
    c.commit()
    c.close()

def timetable():
    """Human-readable timetable in configured TIMEZONE for owner."""
    ensure_defaults()
    tz = _tz()
    tzname = getattr(tz, "key", config.TIMEZONE)
    c = _db()
    c.row_factory = sqlite3.Row
    rows = c.execute("SELECT name, run_at, interval_hours, next_run FROM jobs WHERE enabled=1 ORDER BY next_run").fetchall()
    c.close()
    lines = []
    for r in rows:
        try:
            nxt_utc = datetime.fromisoformat(r["next_run"].replace("Z", "")).replace(tzinfo=timezone.utc)
            nxt_local = nxt_utc.astimezone(tz).strftime(f"%d %b %H:%M {tzname}")
        except Exception:
            nxt_local = r["next_run"]
        when = r["run_at"] or f"every {r['interval_hours']}h"
        lines.append(f"{r['name']}: {when} -> next {nxt_local}")
    return "\n".join(lines)
