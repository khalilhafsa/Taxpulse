"""Fetch new publications from the Federal Fiscal Court (Bundesfinanzhof, BFH).

The BFH offers two official RSS feeds (new decisions and press releases, see
bundesfinanzhof.de/en/rss-feed/). Unlike the BMF website, they are open to software,
so TaxPulse reads them on its own. Press releases carry the full text in the feed.
"""
from datetime import date, timedelta

import httpx
from sqlmodel import Session

from ..config import settings
from .bmf import FetchError, ingest_items, looks_blocked, parse_feed


def ingest_bfh(session: Session, client: httpx.Client) -> dict:
    """Store new items from every BFH feed. Raises FetchError only if no feed could be read."""
    total = {"found": 0, "new": 0, "already_known": 0, "problems": []}
    cutoff = date.today() - timedelta(days=settings.bfh_max_age_days)
    errors = []
    for url, kind in settings.bfh_feeds.items():
        try:
            resp = client.get(url)
        except httpx.HTTPError as exc:
            errors.append(f"could not reach {url} ({exc.__class__.__name__})")
            continue
        if resp.status_code >= 400 or looks_blocked(resp.text[:3000]):
            errors.append(f"{url} answered with error {resp.status_code}")
            continue
        items = [i for i in parse_feed(resp.content) if i.published is None or i.published >= cutoff]
        r = ingest_items(session, items, client, source="bfh_feed", prefix="bfh", kind=kind, enough_text=600)
        for k in ("found", "new", "already_known"):
            total[k] += r[k]
        total["problems"] += r["problems"]
    if errors and len(errors) == len(settings.bfh_feeds):
        raise FetchError("The BFH feeds could not be read: " + "; ".join(errors) + ". Check your internet connection.")
    total["problems"] += errors
    return total
