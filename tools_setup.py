"""Registers real functions as tools. Run once at startup."""
import tools_registry as TR
import research
from growth import monitor, content
from growth import hunt as hunt_mod

TR.REGISTRY["web_search"] = TR.Tool("web_search", research.web_search)
TR.REGISTRY["fetch_url"] = TR.Tool("fetch_url", research.fetch_url_text)
TR.REGISTRY["website_check"] = TR.Tool("website_check", monitor.check_all)
TR.REGISTRY["content_draft"] = TR.Tool("content_draft", lambda topic="", category="billing-edu": content.draft_post(topic or "NDIS invoice admin pain (Example)", category))
TR.REGISTRY["lead_hunt"] = TR.Tool("lead_hunt", hunt_mod.hunt_leads)
