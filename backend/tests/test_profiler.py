"""Profiler agent: background run, citation verification, uploads and cost tracking.
Claude is replaced by a fake runner, so these tests make no API calls."""
from pathlib import Path

from app.agents.citations import quote_on_page

DEMO = Path(__file__).resolve().parents[2] / "data" / "demo" / "data_rooms"


def nordlicht_id(client) -> int:
    client.post("/api/demo/seed")
    return next(c["id"] for c in client.get("/api/clients").json() if c["slug"] == "nordlicht_immobilien")


def test_quote_matching_tolerates_line_breaks_but_rejects_inventions():
    page = "The partnership claims the extended trade tax\nreduction under § 9 No. 1 sentence 2 GewStG for its rental\nincome."
    assert quote_on_page("claims the extended trade tax reduction under § 9 No. 1", page)
    assert not quote_on_page("The partnership sold all buildings in 2024", page)


def test_build_profile_without_api_key_is_refused(client):
    cid = nordlicht_id(client)
    r = client.post(f"/api/clients/{cid}/profile")
    assert r.status_code == 400
    assert "ANTHROPIC_API_KEY" in r.json()["detail"]


def test_build_profile_verifies_citations_and_logs_cost(client, fake_llm):
    cid = nordlicht_id(client)
    run_id = client.post(f"/api/clients/{cid}/profile").json()["run_id"]

    run = client.get(f"/api/runs/{run_id}").json()
    assert run["status"] == "done", run["error"]
    assert run["agent"] == "profiler" and run["subject_label"] == "Nordlicht Immobilien GmbH & Co. KG"
    assert run["tokens_in"] == 9000 and run["cost_usd"] == 0.048  # 9k x $2 + 3k x $10 per million

    profile = client.get(f"/api/clients/{cid}").json()["profile"]
    assert profile["version"] == 1 and profile["run_id"] == run_id
    data = profile["data"]
    # The fixture cites a page 9 that does not exist: exactly that citation must fail.
    assert data["verification"] == {"verified": 13, "total": 14}
    assert data["open_points"][2]["citations"][0]["verified"] is False
    assert data["tax_areas"][1]["facts"][1]["citations"][0]["verified"] is True

    # Rebuilding creates version 2 and keeps version 1.
    client.post(f"/api/clients/{cid}/profile")
    assert client.get(f"/api/clients/{cid}").json()["profile"]["version"] == 2

    runs = client.get("/api/runs").json()
    assert runs["totals"]["runs"] >= 2 and runs["totals"]["cost_usd"] >= 0.096


def test_page_text_endpoint(client):
    cid = nordlicht_id(client)
    doc = client.get(f"/api/clients/{cid}").json()["documents"][1]
    page = client.get(f"/api/documents/{doc['id']}/pages/2").json()
    assert page["filename"] == "02_Property_Schedule.pdf" and "EUR 1.3m" in page["text"]
    assert client.get(f"/api/documents/{doc['id']}/pages/99").status_code == 404
    assert client.get(f"/api/documents/{doc['id']}/file").headers["content-type"] == "application/pdf"


def test_create_client_and_upload_pdfs(client):
    new = client.post("/api/clients", json={"name": "Test Holding GmbH", "mandate": "Tax DD 2025"}).json()
    pdf = (DEMO / "kaiser_dental" / "01_Tax_Due_Diligence_Report.pdf").read_bytes()

    r = client.post(f"/api/clients/{new['id']}/documents",
                    files=[("files", ("My Report (final).pdf", pdf, "application/pdf"))])
    assert r.status_code == 201
    assert r.json()["added"][0]["filename"] == "My_Report_final.pdf"
    assert r.json()["added"][0]["page_count"] == 2

    duplicate = client.post(f"/api/clients/{new['id']}/documents",
                            files=[("files", ("My Report (final).pdf", pdf, "application/pdf"))])
    assert duplicate.status_code == 409
    not_pdf = client.post(f"/api/clients/{new['id']}/documents",
                          files=[("files", ("notes.pdf", b"hello", "application/pdf"))])
    assert not_pdf.status_code == 400

    same_name = client.post("/api/clients", json={"name": "Test Holding GmbH"}).json()
    assert same_name["slug"] == "test_holding_gmbh_2"
