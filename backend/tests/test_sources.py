"""BFH feeds (automatic) and the "Send to TaxPulse" browser button for the BMF feed."""
import json

import httpx
from sqlmodel import Session, select

from app.agents.runner import get_runner
from app.db import engine
from app.main import app
from app.models import Notification, RegulatoryUpdate
from app.sources.bmf import http_client
from tests.feeds import all_sources_client, bfh_news_rss
from tests.test_automation import demo_runner
from tests.test_matching import prepare_demo
from tests.test_updates import CAPTCHA_PAGE, RSS

BMF = "https://www.bundesfinanzministerium.de"


def test_bfh_feed_uses_full_text_and_skips_old_items(client):
    app.dependency_overrides[http_client] = all_sources_client
    r = client.post("/api/updates/fetch-bfh").json()
    assert r["new"] == 1 and r["problems"] == []
    with Session(engine) as s:
        [u] = s.exec(select(RegulatoryUpdate)).all()
    assert u.source == "bfh_feed" and u.kind == "press_release" and u.external_id.startswith("bfh:")
    assert "Frühstück" in u.raw_text and len(u.raw_text) > 600  # content:encoded, not the short description
    assert client.post("/api/updates/fetch-bfh").json()["new"] == 0  # no duplicates


def test_bfh_unreachable_gives_a_clear_error(client):
    app.dependency_overrides[http_client] = lambda: httpx.Client(
        transport=httpx.MockTransport(lambda r: (_ for _ in ()).throw(httpx.ConnectError("offline"))))
    r = client.post("/api/updates/fetch-bfh")
    assert r.status_code == 503 and "BFH feeds could not be read" in r.json()["detail"]


def send(client, xml, origin=BMF):
    return client.post("/api/updates/receive-feed", content=json.dumps({"url": BMF + "/feed.xml", "xml": xml}),
                       headers={"Origin": origin, "Content-Type": "text/plain;charset=UTF-8"})


def test_browser_button_stores_the_feed_and_starts_the_agents(client):
    prepare_demo(client)
    app.dependency_overrides[get_runner] = demo_runner
    r = send(client, RSS.decode())
    assert r.status_code == 200 and r.json()["new"] == 3 and r.json()["agents_started"] is True
    assert r.headers["access-control-allow-origin"] == BMF  # the BMF page may read the answer
    with Session(engine) as s:
        notes = s.exec(select(Notification)).all()
    assert notes[0].title == "Send to TaxPulse: 7 new alerts to review"
    assert notes[0].body.startswith("BMF: 3 new publications received.")
    assert send(client, RSS.decode()).json()["new"] == 0  # sending twice adds nothing


def test_browser_button_refuses_other_sites_and_wrong_pages(client):
    assert send(client, RSS.decode(), origin="https://evil.example").status_code == 403
    r = send(client, CAPTCHA_PAGE)
    assert r.status_code == 400 and "security check page" in r.json()["detail"]
    r = client.post("/api/updates/receive-feed", content="not json", headers={"Origin": BMF})
    assert r.status_code == 400


def test_private_network_preflight_is_answered(client):
    r = client.options("/api/updates/receive-feed", headers={
        "Origin": BMF, "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Private-Network": "true"})
    assert r.status_code == 200
    assert r.headers["access-control-allow-private-network"] == "true"
    assert r.headers["access-control-allow-origin"] == BMF


def test_without_key_the_feed_is_stored_but_agents_wait(client):
    r = send(client, RSS.decode())
    assert r.json()["new"] == 3 and r.json()["agents_started"] is False
    assert bfh_news_rss()  # fixture sanity


def test_feed_copied_from_the_browser_with_a_lost_namespace_still_imports(client):
    # What Chrome's XML viewer can hand over: viewer markup around the feed and an undeclared prefix.
    copied = """<?xml version="1.0"?><html xmlns="http://www.w3.org/1999/xhtml"><body><div id="webkit-xml-viewer-source-xml">
<rss version="2.0"><channel><atom:link href="https://www.bundesfinanzministerium.de/x.xml" rel="self"/>
<item><title>BMF-Schreiben: E-Rechnung &amp; Übergangsregeln</title>
<link>https://www.bundesfinanzministerium.de/Content/DE/a.html</link><pubDate>Mon, 26 Oct 2026 10:00:00 +0100</pubDate>
<dc:creator>BMF</dc:creator><description><![CDATA[<p>Das BMF hat ein Schreiben zur Ausstellung von E-Rechnungen veröffentlicht.</p>]]></description></item>
<item><title>Monatsbericht</title><link>https://www.bundesfinanzministerium.de/Content/DE/b.html</link>
<description>Der Monatsbericht des BMF für Oktober 2026 mit Analysen zur Steuerentwicklung.</description></item>
</channel></rss></div></body></html>"""
    r = send(client, copied)
    assert r.status_code == 200 and r.json()["new"] == 2
    with Session(engine) as s:
        titles = {u.title: u for u in s.exec(select(RegulatoryUpdate)).all()}
    u = titles["BMF-Schreiben: E-Rechnung & Übergangsregeln"]
    assert u.raw_text.startswith("Das BMF hat ein Schreiben") and u.published_on.isoformat() == "2026-10-26"
    assert u.kind == "bmf_letter"


def test_feed_shown_as_plain_text_in_a_page_still_imports(client):
    import html
    raw = RSS.decode()
    page = f'<html xmlns="http://www.w3.org/1999/xhtml"><head></head><body><pre style="word-wrap: break-word;">{html.escape(raw)}</pre></body></html>'
    page = page.replace("<pre", "<x:pre")  # plus a broken prefix, as in the field
    r = send(client, page)
    assert r.status_code == 200 and r.json()["new"] == 3


def test_a_refused_feed_is_kept_for_diagnosis(client):
    from app.config import settings
    send(client, "<html><body>" + "Nothing useful here. " * 50 + "</body></html>")
    saved = (settings.upload_dir / "last-feed-received.txt").read_text(encoding="utf-8")
    assert saved.startswith("url: https://www.bundesfinanzministerium.de/feed.xml") and "Nothing useful" in saved
