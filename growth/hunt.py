"""Client hunting: finds public opportunities, sends DETAILS + draft msg to owner.
NEVER sends anything externally. No scraping against ToS — search APIs + public pages only."""
import re
from urllib.parse import urlparse

import research
import tasks
from growth import leads
from logs_sys import audit
from growth.learning import record_outcome

HUNT_QUERIES = [
    "NDIS support worker sole trader Australia invoicing help",
    "independent support worker Australia admin paperwork forum",
    "NDIS provider directory sole trader support worker",
    "site:reddit.com NDIS support worker invoices admin",
]

AUS_HINTS = ["australia", "sydney", "melbourne", "brisbane", "perth", "adelaide",
             "victoria", "queensland", "nsw", "tasmania", "canberra", "darwin"]

def _guess_name(text, url):
    try:
        host = urlparse(url).netloc.replace("www.", "") or "public web"
    except Exception:
        host = "public web"
    first = (text or "").strip().split(".")[0][:90]
    return (first or host)[:90]

def _guess_location(text):
    low = (text or "").lower()
    for h in AUS_HINTS:
        if h in low:
            return "Australia (" + h + " mentioned)"
    return ""

def hunt_leads(max_new=8):
    tid = tasks.create("lead.hunt", risk_level="LOW")
    tasks.set_status(tid, "RUNNING")
    seen_urls, added = set(), []
    for q in HUNT_QUERIES:
        for hit in research.web_search(q, 6):
            if hit.get("error") or not hit.get("url"):
                continue
            url = hit["url"]
            if url in seen_urls:
                continue
            seen_urls.add(url)
            text = hit.get("text", "")
            info = {
                "name": _guess_name(text, url),
                "business_name": "",
                "role": "possible NDIS sole-trader lead (unverified)",
                "public_profile_url": url,
                "business_url": url,
                "location": _guess_location(text),
                "business_type": "independent support worker (to verify)",
                "source": f"public-search: {q[:60]}",
                "relevance_reason": text[:250],
                "tags": ["auto-hunt", "unverified"],
            }
            lid, score, reasons = leads.upsert(info)
            if score >= 20:
                leads.set_status(lid, "RESEARCHED")
            added.append({"lead_id": lid, "score": score, "reasons": reasons,
                          "url": url, "snippet": text[:220]})
            if len(added) >= max_new:
                break
        if len(added) >= max_new:
            break
    tasks.set_status(tid, "COMPLETED", result=f"{len(added)} opportunities")
    audit("growth", tid, "hunt", str(HUNT_QUERIES), f"{len(added)} found", "AUTO", "", "", "")
    record_outcome("hunt", f"{len(added)} opportunities", "queued for owner")
    return added

def template_msg(lead):
    # Customer-facing draft -> ALWAYS Australian English (client Aussie hai).
    return (f"Hi {lead.get('name','there')}, I noticed your NDIS support work. "
            f"Many sole traders tell me invoice admin eats their Sunday. "
            f"Rayvice makes NDIS billing + rate-splits easier — 9-day free trial, no card. "
            f"Worth a 2-min look at rayvice.com? (draft only — edit karke tum bhejoge)")

def digest_text(items):
    if not items:
        return ("Bhai hunt karke aaya, is baar koi strong public opportunity nahi mili (halki wali chhod di, jhootha lead nahi banaya). "
                "Tavily free key lagte hi hunting strong ho jayegi. Tab tak koi profile/link mujhe forward kar de, mai qualify + msg bana dunga.")
    lines = [f"🎯 Bhai aaj {len(items)} opportunity mili (sirf details bhej raha hu, kisi ko kuch bheja NAHI hai):"]
    for it in sorted(items, key=lambda x: -x["score"])[:8]:
        lines.append(f"\n• {it['lead_id']} | score {it['score']}\n  {it['url']}\n  Kyu fit hai: {', '.join(it['reasons'][:3])}")
    lines.append("\nKisi pe personal msg chahiye to bol `outreach <lead_id>` - mai AI se bana dunga. Bhejna hamesha TU khud karega.")
    return "\n".join(lines)
