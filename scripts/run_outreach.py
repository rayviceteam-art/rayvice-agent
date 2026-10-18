#!/usr/bin/env python3
"""Daily outreach CLI (lead gen + cold email).

Gh Actions: python3 scripts/run_outreach.py --daily
Window: Sydney Mon-Fri 09:00-11:59 (warna skip). Dry-run default ON.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402
from social import calendar  # noqa: E402
from outreach import pipeline  # noqa: E402
import telegram_bot  # noqa: E402


def _notify(text):
    try:
        telegram_bot.send(text)
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--daily", action="store_true", help="window + enabled gate ke saath daily run")
    ap.add_argument("--preview", action="store_true", help="leads + emails banao, Telegram pe preview")
    ap.add_argument("--send", action="store_true", help="queued emails bhejo (dry-run off ho to)")
    ap.add_argument("--scan", action="store_true", help="inbox scan: replies/unsub/bounce")
    ap.add_argument("--stats", action="store_true", help="outreach stats Telegram pe")
    ap.add_argument("--count", type=int, default=0)
    ap.add_argument("--dry", action="store_true", help="kuch bhejo mat (preview only)")
    ap.add_argument("--force", action="store_true", help="window/enabled gate ignore")
    a = ap.parse_args()

    n = a.count or config.OUTREACH_DAILY_CAP

    if a.stats:
        print(pipeline.status_text())
        _notify(pipeline.status_text())
        return 0

    if a.scan:
        print(pipeline.scan())
        return 0

    if a.daily and not a.force:
        now = calendar.now_local()
        if not config.OUTREACH_ENABLED:
            print("outreach disabled (OUTREACH_ENABLED=false) — skip")
            return 0
        if now.weekday() > 4:
            print(f"weekend (Sydney {now:%a %H:%M}) — skip")
            return 0
        if not (9 <= now.hour <= 11):
            print(f"outreach window nahi (Sydney {now:%H:%M}) — skip")
            return 0

    built = pipeline.build_daily(count=n)
    if not built.get("generated"):
        msg = f"📪 Outreach: aaj koi naya lead+email nahi bana (no_email={built.get('no_email')})."
        print(msg)
        if a.preview:
            _notify(msg)
        return 0

    if a.preview or a.dry or config.OUTREACH_DRYRUN:
        text = pipeline.format_preview(built["items"])
        print(text)
        _notify(text)
        return 0

    res = pipeline.send_daily(count=n, dry=False)
    _notify(pipeline.format_sent(res["items"], res["sent"], res["dry"]))
    print(f"sent={res['sent']} failed={res['failed']} queued={res['would_send']}")
    sc = pipeline.scan()
    print("scan:", sc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
