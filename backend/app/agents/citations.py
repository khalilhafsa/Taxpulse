"""Check that every citation points to a real page and that its quote is really on that page."""
import re
from collections import Counter

from .schemas import Citation, ProfileDraft


def _tokens(text: str) -> list[str]:
    text = text.lower().replace("-\n", "")
    return re.findall(r"[a-z0-9äöüß%€.,]+", text)


def quote_on_page(quote: str, page_text: str) -> bool:
    """True if the quote appears on the page, tolerating line breaks, spacing and minor PDF extraction noise."""
    q, p = _tokens(quote), _tokens(page_text)
    if not q:
        return False
    if " ".join(q) in " ".join(p):
        return True
    # Tables and hyphenation can scramble word order slightly: accept a 85 % word overlap.
    page_words = Counter(p)
    found = sum(min(n, page_words[w]) for w, n in Counter(q).items())
    return found / len(q) >= 0.85


def verify(draft: ProfileDraft, pages: dict[tuple[str, int], str]) -> tuple[int, int]:
    """Mark each citation as verified or not. `pages` maps (filename, page number) to page text.
    Returns (verified, total)."""
    citations: list[Citation] = []
    for fact in draft.key_facts + draft.open_points:
        citations += fact.citations
    for area in draft.tax_areas:
        for fact in area.facts:
            citations += fact.citations

    for c in citations:
        text = pages.get((c.document, c.page))
        c.verified = text is not None and quote_on_page(c.quote, text)
    return sum(c.verified for c in citations), len(citations)
