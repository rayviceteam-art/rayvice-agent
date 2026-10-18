#!/usr/bin/env python3
"""Daily group content kit CLI.

Gh Actions se: python3 scripts/run_group_kit.py --send
Window: Sydney 7:00-10:59 (warna skip). Aaj bhej chuka to skip.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from social import calendar, db, group_kit  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--send", action="store_true", help="Telegram pe bhejo")
    ap.add_argument("--dry", action="store_true", help="print karo, bhejo mat")
    ap.add_argument("--force", action="store_true", help="window/sent gate ignore karo")
    ap.add_argument("--regen", action="store_true", help="naya content generate karo")
    a = ap.parse_args()

    db.ensure_schema()
    now = calendar.now_local()
    if not a.force and not (7 <= now.hour <= 10):
        print(f"kit window nahi hai (Sydney {now:%H:%M}) — skip")
        return 0

    res = group_kit.build_kit(force=a.regen)
    if not res.get("ok"):
        print("kit error:", res.get("error"))
        return 1
    if res.get("already_sent") and not a.force:
        print("aaj ka kit bhej diya gaya hai — skip")
        return 0

    if a.send and not a.dry:
        n = group_kit.send_kit(res)
        print(f"kit sent: {n} messages ({res.get('date')}, {res.get('source')})")
    else:
        for m in group_kit.format_messages(res):
            print(m)
            print("-" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
