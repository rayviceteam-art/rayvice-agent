"""Lead discovery: public web search -> provider websites -> published contact emails.

Compliance-aware, low-volume only:
- Sirf woh emails jo provider ne khud apni public website par publish kiye hain
  (B2B inferred consent, Australian Spam Act 2003).
- Directories / social platforms / big orgs blocklist se hataye jaate hain.
- Ek domain = ek lead; per-run chhota volume; robots.txt respect.
"""
import re
import urllib.request
from urllib import robotparser
from urllib.parse import urlparse

import research

BLOCKED_DOMAINS = {
    "facebook.com", "instagram.com", "linkedin.com", "twitter.com", "x.com", "youtube.com",
    "tiktok.com", "pinterest.com", "indeed.com", "seek.com.au", "glassdoor.com", "wikipedia.org",
    "ndis.gov.au", "ndiscommission.gov.au", "health.gov.au", "servicesaustralia.gov.au",
    "healthdirect.gov.au", "yellowpages.com.au", "whitepages.com.au", "truelocal.com.au",
    "yellowpages.com.au", "localsearch.com.au", "startlocal.com.au", "hotfrog.com.au", "dlook.com.au",
    "australia.gov.au", "gov.au", "data.gov.au", "abn.business.gov.au", "abr.business.gov.au",
    "google.com", "bing.com", "tripadvisor.com", "medium.com", "reddit.com", "quora.com",
    "productreview.com.au", "trustpilot.com", "hipages.com.au", "oneflare.com.au", "airtasker.com",
    "wordpress.com", "blogspot.com", "comparendisservices.com.au", "ndisproviderfinder.com.au",
    "clickability.com.au", "hireup.com.au", "mable.com.au", "likefamily.com.au", "care.com",
    "bettercaring.com.au", "ndisreview.gov.au", "trove.nla.gov.au", "gumtree.com.au",
    "linkedin.com", "tiktok.com", "wixsite.com", "godaddysites.com", "weebly.com",
}

# Known large providers — chhote businesses target hain, inhe skip karo.
BIG_ORGS = {
    "aruma.com.au", "northcott.com.au", "cerebralpalsy.org.au", "achieveaustralia.org.au",
    "yooralla.com.au", "scopeaust.org.au", "melbasupport.com.au", "planpartners.com.au",
    "endeavour.com.au", "multicap.org.au", "cpl.org.au", "wmq.org.au", "nulsen.org.au",
    "activ.asn.au", "rockybay.org.au", "identitywa.com.au", "mindainc.com.au", "cara.org.au",
    "lwb.org.au", "anglicaresa.com.au", "sunnyfield.org.au", "afford.com.au", "genu.org.au",
    "sjog.org.au", "abilityoptions.org.au", "interaction.org.au", "lifestylesolutions.org.au",
    "focuscare.com.au", "claroagedcare.com.au", "hcah.com.au", "envigor.com.au", "karingal.org.au",
    "housewithnosteps.com.au", "stgiles.org.au", "therapyfocus.org.au", "novita.org.au",
    "goodshepherd.org.au", "unitingcare.org.au", "baptcare.org.au", "vmch.com.au",
    "helpinghand.com.au", "myhorizon.org.au", "choicepassionandlife.com.au", "cpl.org.au",
    "kambu.org.au", "cairnsdisabilityservices.org.au", "communitysolutions.com.au",
    "hendercare.com.au", "feroscare.com.au", "integratedliving.org.au", "justbettercare.com.au",
    "rightathome.net.au", "homeinstead.com.au", "hammond.com.au", "anglicare.org.au",
    "catholichealthcare.com.au", "mecwacare.org.au", "calvarycare.org.au", "boltonclarke.com.au",
    "regis.com.au", "estiahealth.com.au", "southerncrosscare.org.au", "uniting.org",
    "catholiccare.org.au", "tlcc.com.au", "boystown.org.au", "saledisabilities.org.au",
    "endofthelinecommunityservices.com.au", "oncallgroup.com.au", "craigcare.com.au",
    "silchoice.com.au", "focusindividualised.com.au", "harmonycare.com.au", "carechoice.com.au",
}

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
MAILTO_RE = re.compile(r"mailto:([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})", re.I)
GENERIC_LOCAL = ("info", "hello", "admin", "enquiries", "enquiry", "contact", "support",
                 "office", "team", "accounts", "billing", "invoices", "service", "services",
                 "reception", "intake", "manager", "careers", "hr", "admin")
BAD_LOCAL = ("no-reply", "noreply", "donotreply", "postmaster", "abuse", "webmaster", "example", "sentry")
FREE_MAIL = ("gmail.com", "hotmail.com", "outlook.com", "bigpond.com", "yahoo.com.au",
             "yahoo.com", "optusnet.com.au", "iinet.net.au", "live.com.au", "icloud.com",
             "outlook.com.au", "msn.com", "aapt.net.au", "tpg.com.au")

CONTACT_PATHS = ["", "contact", "contact-us", "about", "get-in-touch", "contact.html", "contact-us.html"]

QUERIES = [
    "NDIS registered provider {state} contact us our team",
    "NDIS disability support services {state} support workers contact",
    "small NDIS support provider {state} community access contact",
    "NDIS support coordination {state} provider contact us",
    "NDIS plan managed self managed provider {state} contact",
    "independent NDIS support worker team {state} contact email",
]

# --- Ideal Customer Profile (ICP) gate ---------------------------------------------------
# Rayvice ka target: chhota Australian NDIS/disability support provider jiske paas support
# workers hain. Sirf wahi site pass hogi jisme asli NDIS/support signals hon.
STRONG_SIGNALS = (
    "ndis", "support worker", "disability support", "disability service",
    "plan managed", "plan-managed", "self managed", "self-managed",
    "support coordination", "community access", "community participation",
    "psychosocial", "supported independent living", "specialist disability accommodation",
    "core supports", "core support", "capacity building",
)
STRONG_REGEX = (r"\bndis\b", r"\bsil\b", r"\bsda\b", r"\bparticipants?\b")
MEDIUM_SIGNALS = (
    "disability", "support services", "care workers", "in home support",
    "respite", "individual support", "person centred", "person-centered",
)
# Ye mile to site target provider nahi (directory / job board) -> seedha reject.
HARD_NEGATIVES = (
    "find an ndis provider", "ndis provider directory", "find a provider", "provider directory",
    "compare providers", "browse providers", "top 10 ndis", "best ndis providers",
    "recruitment agency", "job vacancies", "jobs available", "apply now", "we are hiring", "job board",
)
# Ye mile to points kate jayenge par reject nahi (real provider ke footer/blog me aate hain).
SOFT_NEGATIVES = (
    "solicitor", "lawyer", "conveyancing", "legal advice", "tax agent", "bookkeeper",
    "financial planner", "mortgage broker", "insurance broker",
)


def html_text(html):
    t = re.sub(r"<script.*?</script>", " ", html or "", flags=re.S | re.I)
    t = re.sub(r"<style.*?</style>", " ", t, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def icp_evaluate(text, domain=""):
    """Return {ok, score, strong, negatives} — site Rayvice ke target provider jaisi hai ya nahi."""
    t = " " + re.sub(r"\s+", " ", (text or "").lower()) + " "
    strong = {s for s in STRONG_SIGNALS if s in t}
    for rx in STRONG_REGEX:
        if re.search(rx, t):
            strong.add(rx.strip("\\b"))
    med = {m for m in MEDIUM_SIGNALS if m in t}
    negs = [n for n in HARD_NEGATIVES if n in t]
    soft = [n for n in SOFT_NEGATIVES if n in t]
    score = min(len(strong), 3) * 3 + min(len(med), 3) - 2 * len(soft)
    ok = bool(strong) and score >= 4 and not negs
    return {"ok": ok, "score": score, "strong": sorted(strong), "negatives": negs,
            "soft_negatives": soft}


def _domain(url):
    try:
        d = urlparse(url).netloc.lower()
        return d[4:] if d.startswith("www.") else d
    except Exception:
        return ""


# Common two-part public suffixes so 'x.com.au' -> registrable 'x.com.au'.
TWO_LEVEL = {"com.au", "net.au", "org.au", "edu.au", "gov.au", "asn.au", "id.au", "au.com",
             "co.uk", "org.uk", "com.nz", "co.nz", "com.fiji"}


def _registrable(domain):
    if not domain:
        return ""
    parts = domain.split(".")
    if len(parts) <= 2:
        return domain
    if ".".join(parts[-2:]) in TWO_LEVEL:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def is_blocked(url):
    d = _domain(url)
    if not d:
        return True
    r = _registrable(d)
    if r in BLOCKED_DOMAINS or r in BIG_ORGS or d in BLOCKED_DOMAINS:
        return True
    return any(d == x or d.endswith("." + x) for x in BLOCKED_DOMAINS)


def _aussie_ok(domain):
    return domain.endswith((".au", ".au.com", ".com.au", ".net.au", ".org.au", ".id.au"))


def _robots(page_html):
    # Bounded fetch (robotparser.read() me timeout nahi hota -> hang risk).
    try:
        rp = robotparser.RobotFileParser()
        p = urlparse(page_html)
        txt = _fetch(f"{p.scheme}://{p.netloc}/robots.txt", timeout=6)
        rp.parse((txt or "").splitlines())
        return rp
    except Exception:
        return None


def _fetch(url, timeout=10):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; RayviceBot/1.0)"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            ctype = r.headers.get("Content-Type", "")
            if "html" not in ctype.lower() and "text" not in ctype.lower():
                return ""
            raw = r.read(400000)
        return raw.decode("utf-8", "ignore")
    except Exception:
        return ""


def extract_emails(html):
    if not html:
        return []
    found = list(MAILTO_RE.findall(html)) + EMAIL_RE.findall(re.sub(r"<[^>]+>", " ", html))
    out = []
    for e in found:
        e = e.strip().strip(".,;:").lower()
        if e.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".css", ".js")):
            continue
        local, _, dom = e.partition("@")
        if not local or "." not in dom or any(x in local for x in BAD_LOCAL):
            continue
        out.append(e)
    return out


def best_email(emails, site_domain):
    if not emails:
        return ""
    b = _registrable(site_domain)

    def score(e):
        local, _, dom = e.partition("@")
        s = 0
        if _registrable(dom) == b:
            s += 100
        if local in GENERIC_LOCAL:
            s += 50
        if any(local.startswith(g) for g in GENERIC_LOCAL):
            s += 20
        if dom in FREE_MAIL:
            s += 10
        return s

    ranked = sorted(set(emails), key=score, reverse=True)
    top = ranked[0]
    local, _, dom = top.partition("@")
    generic = local in GENERIC_LOCAL or any(local.startswith(g) for g in GENERIC_LOCAL)
    # Personal-looking email at an unrelated domain -> probably not the business.
    if not generic and _registrable(dom) != b and dom not in FREE_MAIL:
        return ""
    return top


def page_title(html):
    m = re.search(r"<title[^>]*>(.*?)</title>", html or "", re.I | re.S)
    if not m:
        return ""
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(1))).strip()
    return re.split(r"\s+[|\-–—]\s+", t)[0].strip()[:120]


def _fetch_path(base, rp, path):
    u = base + ("/" + path if path else "")
    try:
        if rp and not rp.can_fetch("RayviceBot", u):
            return None
    except Exception:
        pass
    html = _fetch(u)
    return (u, html) if html else None


def _unreachable():
    return {"email": "", "source_url": "", "title": "", "text": "",
            "icp": {"ok": False, "score": 0, "strong": [], "negatives": ["unreachable"]}}


def evaluate_site(domain):
    """Fast path: homepage se hi email + ICP mil jaye to sirf 1 fetch.

    Returns {email, source_url, title, text, icp}. icp.ok=True = real target provider.
    """
    base = f"https://{domain}"
    rp = _robots(base + "/")
    first = _fetch_path(base, rp, "")
    if not first:
        return _unreachable()
    pages = [first]
    home_text = html_text(first[1])
    title = page_title(first[1])

    def combined():
        return " ".join(html_text(h) for _, h in pages)

    icp = icp_evaluate(combined(), domain)
    email, source_url = "", ""
    e = best_email(extract_emails(first[1]), domain)
    if e:
        email, source_url = e, first[0]

    if not (icp["ok"] and email):
        for path in ("contact", "contact-us", "about"):
            got = _fetch_path(base, rp, path)
            if not got:
                continue
            pages.append(got)
            if not email:
                e = best_email(extract_emails(got[1]), domain)
                if e:
                    email, source_url = e, got[0]
            icp = icp_evaluate(combined(), domain)
            if icp["ok"] and email:
                break

    if len(combined().split()) < 60:
        icp = {**icp, "ok": False, "negatives": icp["negatives"] + ["thin/placeholder page"]}
    return {"email": email, "source_url": source_url, "title": title, "text": home_text[:600], "icp": icp}


def discover_from_site(domain):
    """Backward-compatible: (email, source_url, title)."""
    ev = evaluate_site(domain)
    return ev["email"], ev["source_url"], ev["title"]


def find_candidates(states, per_query=8, max_candidates=60):
    """Web search -> candidate provider domains (blocklist filtered, deduped)."""
    seen, out = set(), []
    for st in states:
        for q in QUERIES:
            for r in (research.web_search(q.format(state=st), per_query) or []):
                if r.get("error"):
                    continue
                url = r.get("url", "")
                d = _domain(url)
                if not d or d in seen or is_blocked(url):
                    continue
                if not _aussie_ok(d):
                    continue
                seen.add(d)
                text = r.get("text", "")
                name = text.split(":", 1)[0][:120].strip()
                out.append({"domain": d, "url": url, "name": name, "state": st,
                            "snippet": text[:280], "source": "websearch", "aussie": _aussie_ok(d)})
                if len(out) >= max_candidates:
                    return out
    out.sort(key=lambda x: (not x["aussie"],))  # .au sites pehle
    return out
