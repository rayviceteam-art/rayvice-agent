"""Customer feedback loop: classify, count frequency, product insights. No fake data."""
import json
import os
from collections import Counter

import memory as mem

KINDS = ["BUG", "FEATURE_REQUEST", "CONFUSION", "MISSING_FEATURE",
         "PRICING", "UX", "PERFORMANCE", "OTHER"]

def collect(text, kind="OTHER", source="owner"):
    if kind not in KINDS:
        kind = "OTHER"
    return mem.append_list("product", "feedback", {"text": text[:400], "kind": kind, "source": source})

def insights_text():
    d = mem.read("product")
    items = d.get("feedback", [])
    if not items:
        return "Feedback abhi 0 hai bhai. Customer msg/support wale text aayenge to mai gin ke batayunga."
    by_kind = Counter(i.get("kind", "OTHER") for i in items)
    by_text = Counter(i.get("text", "")[:80] for i in items)
    lines = [f"💡 Product feedback ({len(items)} total):"]
    for k, n in by_kind.most_common():
        lines.append(f"• {k}: {n}")
    lines.append("Top repeated:")
    for t, n in by_text.most_common(5):
        if n > 1:
            lines.append(f"• {n}x: {t}")
    lines.append("Proposal chahiye to bol `roadmap` — bina approval ke kuch nahi banega.")
    return "\n".join(lines)

def roadmap_proposal(title, problem, evidence, users="UNKNOWN", freq="UNKNOWN"):
    return (f"PRODUCT PROPOSAL (approval chahiye):\nProblem: {problem}\nEvidence: {evidence}\n"
            f"Users: {users}\nFrequency: {freq}\nTitle: {title}\n"
            f"Risk/Complexity: owner batayega review karke. Banaun kya? Ha/Na bolo.")
