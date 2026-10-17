#!/usr/bin/env python3
"""Social pipeline CLI — GitHub Actions / manual use.

Usage:
  python3 scripts/run_social.py --tick          # ek pipeline tick (dry-run unless env SOCIAL_DRYRUN=false)
  python3 scripts/run_social.py --status
  python3 scripts/run_social.py --errors
  python3 scripts/run_social.py --week          # weekly content plan
  python3 scripts/run_social.py --verify        # platform credentials ka real authenticated test
  python3 scripts/run_social.py --retry-dead    # dead-letter items ko ek aur chance
  python3 scripts/run_social.py --capabilities  # platform capability matrix

LIVE publishing sirf tab jab env me SOCIAL_DRYRUN=false ho — CLI ise override nahi karta.
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import config  # noqa: E402


def _print(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            print(f"{k}: {v}")
    else:
        print(obj)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tick", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--errors", action="store_true")
    ap.add_argument("--week", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--retry-dead", action="store_true")
    ap.add_argument("--capabilities", action="store_true")
    ap.add_argument("--force-window", action="store_true", help="publish window ignore karo (manual run)")
    ap.add_argument("--no-notify", action="store_true")
    args = ap.parse_args()

    from social import calendar, db, pipeline
    db.ensure_schema()

    if args.status:
        print(pipeline.status_text())
        return 0
    if args.errors:
        print(pipeline.errors_text())
        return 0
    if args.week:
        for p in calendar.week_plan():
            print(f"{p['date']} [{p['category']}] {p['topic']}")
        return 0
    if args.capabilities:
        for cap in __import__("social.platforms", fromlist=["capabilities"]).capabilities():
            print(f"{cap['platform']}: available={cap['available']} configured={cap['configured']} "
                  f"free={cap['free']} — {(cap.get('blocker') or 'OK')[:120]}")
        return 0
    if args.verify:
        from social.platforms import capabilities, get_adapter
        any_ok = False
        for cap in capabilities():
            a = get_adapter(cap["platform"])
            if a and a.configured():
                ok, msg = a.verify()
                any_ok = any_ok or ok
                print(f"{cap['platform']}: {'OK' if ok else 'FAIL'} — {msg}")
            else:
                print(f"{cap['platform']}: not configured — {(cap.get('blocker') or '')[:100]}")
        return 0 if any_ok else 2
    if args.retry_dead:
        n = pipeline.retry_dead()
        print(f"{n} items re-queued")
        return 0

    res = pipeline.daily_tick(force_window=args.force_window, notify=not args.no_notify)
    _print(res)
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
