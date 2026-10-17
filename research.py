"""Free research layer. No ToS bypass, no CAPTCHA/login bypass. Official/public only."""
import json
import os
import urllib.request
import urllib.parse

def tavily_search(query, max_results=8):
    """Optional: works only if TAVILY_API_KEY set (free 1000/mo, no card)."""
    key = os.environ.get("TAVILY_API_KEY", "")
    if not key:
        return None  # not configured -> caller falls back
    try:
        payload = json.dumps({"api_key": key, "query": query, "max_results": max_results,
                              "search_depth": "basic",
                              "include_answer": False}).encode()
        req = urllib.request.Request("https://api.tavily.com/search", data=payload,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=25) as r:
            d = json.loads(r.read().decode())
        return [{"text": f"{x.get('title','')}: {x.get('content','')[:300]}",
                 "url": x.get("url", "")} for x in d.get("results", [])]
    except Exception as e:
        return [{"error": f"tavily failed (non-fatal): {str(e)[:200]}"}]

def web_search(query, max_results=8):
    """Best available: Tavily if key present, else DuckDuckGo (weak but free)."""
    t = tavily_search(query, max_results)
    if t is not None:
        return t
    return duckduckgo_search(query, max_results)

def duckduckgo_search(query, max_results=8):
    # Free, no key. Best-effort; failure must not crash agent.
    try:
        q = urllib.parse.urlencode({"q": query, "format": "json", "no_html": 1})
        req = urllib.request.Request(f"https://api.duckduckgo.com/?{q}",
                                     headers={"User-Agent": "Rayvice-Agent/1.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.loads(r.read().decode())
        out = []
        for t in (d.get("RelatedTopics") or [])[:max_results]:
            if isinstance(t, dict) and t.get("Text"):
                out.append({"text": t["Text"], "url": t.get("FirstURL", "")})
        return out
    except Exception as e:
        return [{"error": f"search failed (non-fatal): {e}"}]

def fetch_url_text(url, max_chars=8000):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Rayvice-Agent/1.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            html = r.read().decode("utf-8", errors="ignore")
        # crude text extract, no JS bypass
        import re
        txt = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
        txt = re.sub(r"<style.*?</style>", " ", txt, flags=re.S | re.I)
        txt = re.sub(r"<[^>]+>", " ", txt)
        txt = re.sub(r"\s+", " ", txt).strip()
        return txt[:max_chars]
    except Exception as e:
        return f"fetch failed (non-fatal): {e}"
