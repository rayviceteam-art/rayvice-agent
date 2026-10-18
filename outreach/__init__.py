"""Outreach: daily low-volume, compliance-aware cold-email lead gen for Rayvice.

Design:
- Official/public sources only (web search + providers' own published contact pages).
- Australian Spam Act 2003 aware: accurate sender id, business relevance, functional
  unsubscribe (reply "stop"), suppression list, low volume (10/day).
- Dry-run first: nothing sent until OUTREACH_DRYRUN=false + OUTREACH_ENABLED=true.
"""
