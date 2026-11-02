"""BMF feed ingestion (with a mocked website) and the Regulatory Analyst (with a fake LLM)."""
import io

import httpx
from reportlab.pdfgen import canvas

from app.main import app
from app.sources.bmf import http_client, parse_feed

FEED = "https://www.bundesfinanzministerium.de/SiteGlobals/Functions/RSSFeed/DE/Steuern/RSSSteuern.xml"

RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>BMF Steuern</title>
<item><title>BMF-Schreiben: Ausstellung von E-Rechnungen</title>
  <link>https://www.bundesfinanzministerium.de/Content/letter.html</link>
  <pubDate>Mon, 19 Oct 2026 10:00:00 +0200</pubDate>
  <description>&lt;p&gt;Neues BMF-Schreiben zur E-Rechnung.&lt;/p&gt;</description></item>
<item><title>Jahressteuergesetz 2026 verabschiedet</title>
  <link>https://www.bundesfinanzministerium.de/Content/news.html</link>
  <pubDate>Fri, 16 Oct 2026 09:00:00 +0200</pubDate>
  <description>Der Bundestag hat das Jahressteuergesetz beschlossen.</description></item>
<item><title>Artikel ohne Seite</title>
  <link>https://www.bundesfinanzministerium.de/Content/missing.html</link>
  <pubDate>Thu, 15 Oct 2026 09:00:00 +0200</pubDate>
  <description>Kurzfassung aus dem Feed, lang genug um gespeichert zu werden, mit Details zur Grundsteuer.</description></item>
</channel></rss>"""


def make_pdf(text: str) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    y = 800
    for line in text.split("\n"):
        c.drawString(40, y, line)
        y -= 16
    c.save()
    return buf.getvalue()


LETTER_PDF = make_pdf("Bundesministerium der Finanzen\nBETREFF: Ausstellung von Rechnungen nach Paragraph 14 UStG\n"
                      "Ab dem 1. Januar 2027 muessen Unternehmer mit einem Vorjahresumsatz von mehr als 800.000 Euro\n"
                      "E-Rechnungen im strukturierten Format ausstellen. Dieses Schreiben wird im BStBl I veroeffentlicht.")
LETTER_PAGE = """<html><body><nav>Menu Home Service</nav><main><h1>E-Rechnung</h1>
<p>Kurze Einleitung.</p><a href="/Content/letter.pdf?__blob=publicationFile">Download (PDF)</a></main></body></html>"""
NEWS_PAGE = """<html><head><script>var x=1;</script></head><body><header>BMF</header><main><h1>Jahressteuergesetz</h1>
<p>Der Bundestag hat das Jahressteuergesetz 2026 verabschiedet. Es enthaelt Aenderungen bei der Abschreibung
und bei der Umsatzsteuer fuer kleine Unternehmen.</p></main><footer>Impressum</footer></body></html>"""


def handler(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    if url == FEED:
        return httpx.Response(200, content=RSS, headers={"content-type": "application/rss+xml"})
    if url.endswith("/Content/letter.html"):
        return httpx.Response(200, text=LETTER_PAGE, headers={"content-type": "text/html"})
    if "letter.pdf" in url:
        return httpx.Response(200, content=LETTER_PDF, headers={"content-type": "application/pdf"})
    if url.endswith("/Content/news.html"):
        return httpx.Response(200, text=NEWS_PAGE, headers={"content-type": "text/html"})
    return httpx.Response(404)


def mocked_client():
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)


def test_parse_feed_reads_rss_items():
    items = parse_feed(RSS)
    assert [i.title for i in items][0] == "BMF-Schreiben: Ausstellung von E-Rechnungen"
    assert str(items[0].published) == "2026-10-19"
    assert items[0].description == "Neues BMF-Schreiben zur E-Rechnung."


def test_fetch_bmf_stores_full_text_and_skips_duplicates(client):
    app.dependency_overrides[http_client] = mocked_client
    first = client.post("/api/updates/fetch").json()
    assert first["found"] == 3 and first["new"] == 3
    assert any("Artikel ohne Seite" in p for p in first["problems"])  # 404 page -> feed summary used

    updates = {u["title"]: u for u in client.get("/api/updates").json() if u["source"] == "bmf_feed"}
    letter = client.get(f"/api/updates/{updates['BMF-Schreiben: Ausstellung von E-Rechnungen']['id']}").json()
    assert letter["kind"] == "bmf_letter" and "800.000 Euro" in letter["raw_text"]  # text taken from the PDF
    news = client.get(f"/api/updates/{updates['Jahressteuergesetz 2026 verabschiedet']['id']}").json()
    assert news["kind"] == "law" and "Abschreibung" in news["raw_text"] and "Impressum" not in news["raw_text"]

    second = client.post("/api/updates/fetch").json()
    assert second["new"] == 0 and second["already_known"] == 3


def test_fetch_reports_unreachable_feed(client):
    app.dependency_overrides[http_client] = lambda: httpx.Client(
        transport=httpx.MockTransport(lambda r: (_ for _ in ()).throw(httpx.ConnectError("offline"))))
    r = client.post("/api/updates/fetch")
    assert r.status_code == 503 and "internet connection" in r.json()["detail"]


def test_add_update_manually_and_reject_duplicates(client):
    body = {"title": "BFH ruling on company cars", "kind": "bfh_ruling",
            "text": "The BFH decided that the 1% rule also applies to electric company cars used privately in 2026."}
    r = client.post("/api/updates", json=body)
    assert r.status_code == 201 and r.json()["analysis_status"] == "pending"
    assert client.post("/api/updates", json=body).status_code == 409


def test_analyze_pending_stores_analysis_and_logs_runs(client, fake_llm):
    client.post("/api/demo/seed")
    queued = client.post("/api/updates/analyze-pending").json()["queued"]
    assert queued >= 6

    updates = client.get("/api/updates").json()
    assert all(u["analysis_status"] == "done" for u in updates)
    detail = client.get(f"/api/updates/{updates[0]['id']}").json()
    assert detail["summary"]["exclusions"] == ["VAT-exempt supplies", "Cross-border supplies"]

    runs = client.get("/api/runs").json()["runs"]
    analyst = [r for r in runs if r["agent"] == "analyst"]
    assert analyst and analyst[0]["cost_usd"] == 0.00045  # 2k x $0.10 + 0.5k x $0.50 per million
    assert analyst[0]["subject_label"] != analyst[0]["subject"]

    # Nothing left to analyse.
    assert client.post("/api/updates/analyze-pending").json()["queued"] == 0


def test_analyze_without_key_is_refused(client):
    client.post("/api/demo/seed")
    uid = client.get("/api/updates").json()[0]["id"]
    assert client.post(f"/api/updates/{uid}/analyze").status_code == 400


CAPTCHA_PAGE = """<html><body><h1>Security</h1><h2>Sicherheitsüberprüfung</h2>
<p>Unsere Systeme haben ungewöhnlichen Datenverkehr festgestellt.</p><p>Powered by Myra Security</p></body></html>"""


def test_fetch_explains_captcha_block(client):
    app.dependency_overrides[http_client] = lambda: httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(503, text=CAPTCHA_PAGE)))
    r = client.post("/api/updates/fetch")
    assert r.status_code == 503 and "Import feed file" in r.json()["detail"]


def test_import_feed_file_uses_feed_summaries(client):
    r = client.post("/api/updates/import-feed", files={"file": ("bmf.xml", RSS, "application/xml")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["found"] == 3
    imported = [u for u in client.get("/api/updates").json() if u["source"] == "bmf_feed"]
    assert {u["title"] for u in imported} >= {"Jahressteuergesetz 2026 verabschiedet"}

    again = client.post("/api/updates/import-feed", files={"file": ("bmf.xml", RSS, "application/xml")}).json()
    assert again["new"] == 0


def test_import_rejects_the_captcha_page(client):
    r = client.post("/api/updates/import-feed", files={"file": ("bmf.html", CAPTCHA_PAGE.encode(), "text/html")})
    assert r.status_code == 400 and "security check page" in r.json()["detail"]


def test_guess_kind_uses_bmf_link_structure():
    from app.sources.bmf import guess_kind
    assert guess_kind("Gewinnermittlung bei Handelsschiffen", "https://www.bundesfinanzministerium.de/Content/DE/Downloads/BMF_Schreiben/Steuerarten/Einkommensteuer/x.html") == "bmf_letter"
    assert guess_kind("Stabile Entwicklung 2026", "https://www.bundesfinanzministerium.de/Content/DE/Pressemitteilungen/Finanzpolitik/x.html") == "press_release"
