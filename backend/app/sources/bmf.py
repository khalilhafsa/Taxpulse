"""Fetch new tax publications from the Federal Ministry of Finance (BMF).

Source: the official "Steuern" RSS feed, which lists BMF letters (BMF-Schreiben),
laws and tax news. For each new item we download the full text: the attached PDF
when the page offers one (BMF letters are published as PDF), otherwise the page text.
"""
import hashlib
import html as html_lib
import io
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import urljoin

import httpx
from pypdf import PdfReader
from sqlmodel import Session, select

from ..config import settings
from ..models import RegulatoryUpdate

USER_AGENT = "TaxPulse/0.4 (portfolio project; reads the public BMF RSS feed)"
MAX_TEXT_CHARS = 40_000  # keeps agent calls cheap; BMF letters rarely need more


@dataclass
class FeedItem:
    title: str
    link: str
    published: date | None
    description: str


class FetchError(Exception):
    pass


def http_client() -> httpx.Client:
    """FastAPI dependency; tests replace it with a mocked client."""
    return httpx.Client(timeout=20, follow_redirects=True, headers={"User-Agent": USER_AGENT})


# ---------- feed ----------

def _text(el: ET.Element | None) -> str:
    return (el.text or "").strip() if el is not None else ""


def _parse_date(value: str) -> date | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).date()  # RSS: "Wed, 21 Oct 2026 10:00:00 +0200"
    except (TypeError, ValueError):
        pass
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()  # Atom
    except ValueError:
        return None


def parse_feed(xml: bytes) -> list[FeedItem]:
    """Parse RSS 2.0 or Atom."""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        # Pages copied out of a browser are sometimes not strict XML (a namespace prefix whose
        # declaration was lost, viewer markup around the feed). Read the items leniently instead.
        items = _parse_feed_loose(xml.decode("utf-8", errors="replace"))
        if items:
            return items
        raise FetchError(f"The feed is not valid XML ({exc}).")
    items = []
    encoded = "{http://purl.org/rss/1.0/modules/content/}encoded"
    for it in root.iter("item"):  # RSS 2.0; content:encoded carries the full text when the feed offers it
        full = html_to_text(_text(it.find(encoded)))
        short = html_to_text(_text(it.find("description")))
        items.append(FeedItem(title=_text(it.find("title")), link=_text(it.find("link")),
                              published=_parse_date(_text(it.find("pubDate"))),
                              description=full if len(full) > len(short) else short))
    atom = "{http://www.w3.org/2005/Atom}"
    for e in root.iter(f"{atom}entry"):
        link = e.find(f"{atom}link")
        items.append(FeedItem(title=_text(e.find(f"{atom}title")),
                              link=link.get("href", "") if link is not None else "",
                              published=_parse_date(_text(e.find(f"{atom}updated"))),
                              description=html_to_text(_text(e.find(f"{atom}summary")))))
    return [i for i in items if i.title and i.link]


def _loose_field(block: str, *names: str) -> str:
    for name in names:
        m = re.search(rf"<{re.escape(name)}\b[^>]*?(?:/>|>(.*?)</{re.escape(name)}>)", block, re.S | re.I)
        if m and m.group(1):
            value = m.group(1).strip()
            cdata = re.fullmatch(r"<!\[CDATA\[(.*)\]\]>", value, re.S)
            return cdata.group(1) if cdata else html_lib.unescape(value)
    return ""


def _parse_feed_loose(text: str) -> list[FeedItem]:
    """Regex fallback for RSS items when the XML parser refuses the document."""
    if not re.search(r"<item\b", text, re.I) and re.search(r"&lt;item\b", text, re.I):
        text = html_lib.unescape(text)  # the feed was shown as plain text inside a web page
    items = []
    for block in re.findall(r"<item\b[^>]*>(.*?)</item>", text, re.S | re.I):
        full = html_to_text(_loose_field(block, "content:encoded"))
        short = html_to_text(_loose_field(block, "description"))
        link = _loose_field(block, "link") or _loose_field(block, "guid")
        items.append(FeedItem(title=html_to_text(_loose_field(block, "title")), link=link.strip(),
                              published=_parse_date(_loose_field(block, "pubDate", "dc:date")),
                              description=full if len(full) > len(short) else short))
    return [i for i in items if i.title and i.link.startswith("http")]


# ---------- article text ----------

class _PageParser(HTMLParser):
    """Collects visible text (preferring <main>) and links to PDF downloads."""
    SKIP = {"script", "style", "nav", "header", "footer", "noscript", "form"}

    def __init__(self):
        super().__init__()
        self.skip_depth = 0
        self.in_main = 0
        self.all_text: list[str] = []
        self.main_text: list[str] = []
        self.pdf_links: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip_depth += 1
        if tag == "main" or dict(attrs).get("id") in {"content", "main"}:
            self.in_main += 1
        if tag == "a":
            href = dict(attrs).get("href") or ""
            if ".pdf" in href.lower() or "publicationFile" in href:
                self.pdf_links.append(href)
        if tag in {"p", "br", "li", "h1", "h2", "h3", "h4", "tr", "div"}:
            self._add("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip_depth:
            self.skip_depth -= 1
        if tag == "main" and self.in_main:
            self.in_main -= 1

    def handle_data(self, data):
        if not self.skip_depth:
            self._add(data)

    def _add(self, s):
        self.all_text.append(s)
        if self.in_main:
            self.main_text.append(s)


def _clean(text: str) -> str:
    text = re.sub(r"[ \t ]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def html_to_text(html: str) -> str:
    if "<" not in html:
        return html.strip()
    p = _PageParser()
    p.feed(html)
    return _clean("".join(p.all_text))


def fetch_full_text(client: httpx.Client, url: str) -> str:
    """Prefer the attached PDF (the actual BMF letter); fall back to the page text."""
    page = client.get(url)
    page.raise_for_status()
    if page.headers.get("content-type", "").startswith("application/pdf"):
        return pdf_text(page.content)
    parser = _PageParser()
    parser.feed(page.text)
    for href in parser.pdf_links[:2]:
        try:
            pdf = client.get(urljoin(url, href))
            if pdf.status_code == 200 and pdf.content.startswith(b"%PDF"):
                text = pdf_text(pdf.content)
                if len(text) > 150:
                    return text
        except httpx.HTTPError:
            continue
    body = "".join(parser.main_text) or "".join(parser.all_text)
    return _clean(body)[:MAX_TEXT_CHARS]


def pdf_text(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content))
    return _clean("\n".join(p.extract_text() or "" for p in reader.pages))[:MAX_TEXT_CHARS]


# ---------- ingestion ----------

def content_hash(text: str) -> str:
    return hashlib.sha256(" ".join(text.split()).encode()).hexdigest()


def guess_kind(title: str, link: str = "") -> str:
    l = link.lower()
    if "/bmf_schreiben/" in l:
        return "bmf_letter"
    if "/pressemitteilungen/" in l:
        return "press_release"
    t = title.lower()
    if "bmf-schreiben" in t or "schreiben" in t:
        return "bmf_letter"
    if "bfh" in t or "urteil" in t or "beschluss" in t:
        return "bfh_ruling"
    if "gesetz" in t or "verordnung" in t:
        return "law"
    return "other"


SECURITY_MARKERS = ("sicherheitsüberprüfung", "security check", "captcha", "myra")


def looks_blocked(text: str) -> bool:
    """True if the BMF bot protection answered instead of the real content."""
    head = text[:3000].lower()
    return any(m in head for m in SECURITY_MARKERS)


BLOCKED_MESSAGE = ("The BMF website asked for a security check (CAPTCHA), so TaxPulse cannot fetch the feed "
                   "on its own. Open the feed in your browser, pass the check, then click “Send to TaxPulse” in "
                   "your bookmarks bar (set it up once in Settings). Or save the page with Ctrl+S and use “Import feed file”.")


def ingest_items(session: Session, items: list[FeedItem], client: httpx.Client | None, limit: int = 30,
                 source: str = "bmf_feed", prefix: str = "bmf", kind: str | None = None,
                 enough_text: int | None = None) -> dict:
    """Store new feed items. With a client, try to download each item's full text (skipped when the
    feed text is already `enough_text` characters long); without one (imported file), keep the feed text."""
    items = items[:limit]
    result = {"found": len(items), "new": 0, "already_known": 0, "problems": []}
    for item in items:
        ext_id = f"{prefix}:" + hashlib.sha1(item.link.encode()).hexdigest()[:16]
        if session.exec(select(RegulatoryUpdate).where(RegulatoryUpdate.external_id == ext_id)).first():
            result["already_known"] += 1
            continue
        text = ""
        if client is not None and not (enough_text and len(item.description) >= enough_text):
            try:
                text = fetch_full_text(client, item.link)
                if looks_blocked(text):
                    result["problems"].append(f"{item.title}: page protected by a security check, used the feed summary")
                    text = ""
            except Exception as exc:  # keep going with the summary from the feed
                result["problems"].append(f"{item.title}: full text unavailable ({exc.__class__.__name__}), used the feed summary")
        text = text if len(text) >= len(item.description) else item.description
        if len(text) < 40:
            text = f"{item.title}. {text}".strip()
        if len(text) < 40:
            result["problems"].append(f"{item.title}: no readable text, skipped")
            continue
        h = content_hash(text)
        if session.exec(select(RegulatoryUpdate).where(RegulatoryUpdate.content_hash == h)).first():
            result["already_known"] += 1
            continue
        session.add(RegulatoryUpdate(external_id=ext_id, kind=kind or guess_kind(item.title, item.link), title=item.title,
                                     published_on=item.published, source=source, url=item.link,
                                     raw_text=text, content_hash=h))
        session.commit()
        result["new"] += 1
    return result


def ingest_bmf_feed(session: Session, client: httpx.Client, limit: int = 30) -> dict:
    """Download the feed over the internet. Raises FetchError with a clear message when blocked."""
    try:
        resp = client.get(settings.bmf_feed_url)
    except httpx.HTTPError as exc:
        raise FetchError(f"Could not reach the BMF feed ({exc.__class__.__name__}). Check your internet connection.")
    if resp.status_code in (403, 429, 503) or looks_blocked(resp.text[:3000]):
        raise FetchError(BLOCKED_MESSAGE)
    if resp.status_code >= 400:
        raise FetchError(f"The BMF website answered with error {resp.status_code}. Try again later.")
    return ingest_items(session, parse_feed(resp.content), client, limit)


def import_feed_file(session: Session, content: bytes) -> dict:
    """Import a feed the user saved from the browser after passing the security check."""
    text = content[:3000].decode("utf-8", errors="ignore")
    if looks_blocked(text) and "<rss" not in text and "<feed" not in text:
        raise FetchError("This file is the security check page, not the feed. Pass the check first, "
                         "wait until you see the list of <item> entries, then save with Ctrl+S.")
    items = parse_feed(content)
    if not items:
        raise FetchError("No publications found in this file. Make sure you saved the BMF RSS feed (.xml).")
    return ingest_items(session, items, client=None)
