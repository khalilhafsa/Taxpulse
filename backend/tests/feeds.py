"""Fake BFH feeds for tests: one recent press release with full text, one item too old to import."""
from datetime import date, timedelta
from email.utils import format_datetime
from datetime import datetime, timezone

import httpx

from tests.test_updates import handler as bmf_handler

BFH_NEWS = "https://www.bundesfinanzhof.de/de/news.rss"
BFH_DECISIONS = "https://www.bundesfinanzhof.de/de/precedent.rss"


def _rfc(d: date) -> str:
    return format_datetime(datetime(d.year, d.month, d.day, 9, 59, tzinfo=timezone.utc))


def bfh_news_rss() -> bytes:
    recent, old = date.today() - timedelta(days=3), date.today() - timedelta(days=400)
    body = ("Der Bundesfinanzhof hat entschieden, dass die Steuersatzermäßigung für Übernachtungen im Hotel "
            "nicht für das Frühstück gilt. " * 8)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel><title>BFH</title>
<item><title>Steuersatzermäßigung im Hotel</title><link>https://www.bundesfinanzhof.de/de/presse/hotel/</link>
<pubDate>{_rfc(recent)}</pubDate><description>Kurz</description><content:encoded><![CDATA[<p>{body}</p>]]></content:encoded></item>
<item><title>Alte Pressemitteilung</title><link>https://www.bundesfinanzhof.de/de/presse/alt/</link>
<pubDate>{_rfc(old)}</pubDate><description>Eine sehr alte Mitteilung über ein längst bekanntes Urteil.</description></item>
</channel></rss>""".encode()


EMPTY = b'<?xml version="1.0"?><rss version="2.0"><channel><title>BFH-Entscheidungen</title></channel></rss>'


def handler(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    if url == BFH_NEWS:
        return httpx.Response(200, content=bfh_news_rss(), headers={"content-type": "application/rss+xml"})
    if url == BFH_DECISIONS:
        return httpx.Response(200, content=EMPTY, headers={"content-type": "application/rss+xml"})
    return bmf_handler(request)


def all_sources_client():
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
