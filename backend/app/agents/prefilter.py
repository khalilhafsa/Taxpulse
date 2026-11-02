"""Agent 3a – Pre-filter (no LLM).

Decides cheaply which clients are worth sending to the Impact Matcher for an update:
a shared tax area, or a shared keyword. Errs on the side of keeping a client, because
a client dropped here can never become an alert; the Matcher removes the noise.
"""
import re
from dataclasses import dataclass

# Tags the Analyst adds to almost every publication; they say nothing about the client.
GENERIC = {
    "bmf", "bfh", "bmf letter", "bmf-schreiben", "bfh ruling", "press release", "tax", "taxes",
    "germany", "german", "companies", "businesses", "law", "draft bill", "form", "form template",
    "publication", "case law", "income tax", "einkommensteuer", "steuern",
}


@dataclass
class Decision:
    shortlisted: bool
    reason: str


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w§%€.\- ]+", " ", text.lower())).strip()


def _useful(keywords: list[str]) -> list[str]:
    return [k for k in (_norm(k) for k in keywords) if len(k) >= 3 and k not in GENERIC]


def _contains(blob: str, keyword: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", blob) is not None


def client_text(profile: dict) -> str:
    parts = [profile.get("summary", ""), *profile.get("keywords", [])]
    for fact in profile.get("key_facts", []) + profile.get("open_points", []):
        parts += [fact.get("label", ""), fact.get("value", "")]
    for area in profile.get("tax_areas", []):
        parts += [area.get("title", ""), area.get("summary", "")]
        parts += [f.get("value", "") for f in area.get("facts", [])]
    return _norm(" ".join(parts))


def update_text(analysis: dict) -> str:
    parts = [analysis.get("summary", ""), analysis.get("who_is_affected", ""), *analysis.get("trigger_criteria", [])]
    return _norm(" ".join(parts))


def prefilter(analysis: dict, profile: dict) -> Decision:
    if not analysis.get("relevant_for_companies", True):
        return Decision(False, "The Analyst found no impact on businesses.")

    update_areas = set(analysis.get("tax_categories", [])) - {"Other"}
    client_areas = {a.get("category") for a in profile.get("tax_areas", [])} - {"Other"}
    shared = sorted(update_areas & client_areas)
    if shared:
        return Decision(True, f"Shared tax area: {', '.join(shared)}.")

    c_text, u_text = client_text(profile), update_text(analysis)
    hits = [k for k in _useful(analysis.get("keywords", [])) if _contains(c_text, k)]
    hits += [k for k in _useful(profile.get("keywords", [])) if _contains(u_text, k) and k not in hits]
    if hits:
        return Decision(True, f"Shared keywords: {', '.join(hits[:5])}.")

    areas = ", ".join(sorted(update_areas)) or "no specific tax area"
    return Decision(False, f"No shared tax area or keyword (the update concerns {areas}).")
