"""Task -> Task Classifier -> Model Router -> Provider/Model."""
import config
from ai_provider import get_provider

# Configurable routing: cheap/free first, stronger only when needed.
ROUTES = {
    "research": None,        # first free model
    "classify": None,
    "qualify": None,
    "draft": None,
    "code": None,
    "debug": None,
    "long_context": None,
    "vision": None,
}

def classify_task(task_type):
    t = (task_type or "research").lower()
    for k in ROUTES:
        if k in t:
            return k
    if any(x in t for x in ("lead", "search", "market")):
        return "research"
    if any(x in t for x in ("content", "post", "outreach", "reply")):
        return "draft"
    if any(x in t for x in ("bug", "fix", "deploy", "test", "code")):
        return "code"
    return "research"

def select_model(route):
    models = list(config.FREE_MODELS) or ["openrouter/free"]
    # All routes use free list for now (budget 0). Stronger = later in list.
    # research/classify -> models[0]; draft/code -> last model if exists.
    if route in ("draft", "code", "debug") and len(models) > 1:
        return models[-1]
    return models[0]

def run_task(task_type, messages, timeout=60):
    route = classify_task(task_type)
    model = ROUTES.get(route) or select_model(route)
    # 1) GROQ FIRST — fast, free, multi-key rotator (user preference).
    try:
        gp = get_provider("groq")
        if gp.keys:
            r = gp.chat(messages, timeout=timeout)
            if r.ok:
                return r
    except Exception:
        pass
    # 2) OpenRouter free list fallback.
    provider = get_provider("openrouter")
    res = provider.chat(messages, model=model, timeout=timeout)
    if not res.ok:
        for m in config.FREE_MODELS:
            if m == model:
                continue
            r2 = provider.chat(messages, model=m, timeout=timeout)
            if r2.ok:
                return r2
    return res
