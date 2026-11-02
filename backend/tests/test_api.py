"""API smoke tests (demo data, clients, updates)."""


def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["llm_configured"] is False


def test_seed_is_idempotent_and_loads_demo_data(client):
    client.post("/api/demo/seed")
    again = client.post("/api/demo/seed").json()["added"]
    assert again == {"clients": 0, "documents": 0, "updates": 0}
    stats = client.get("/api/stats").json()
    assert stats["clients"] >= 4 and stats["updates"] == 6


def test_client_detail_lists_documents_with_pages(client):
    client.post("/api/demo/seed")
    mueller = next(x for x in client.get("/api/clients").json() if x["slug"] == "mueller_praezisionstechnik")
    assert mueller["document_count"] == 3
    detail = client.get(f"/api/clients/{mueller['id']}").json()
    assert [d["page_count"] for d in detail["documents"]] == [4, 2, 2]
    assert client.get("/api/clients/9999").status_code == 404


def test_updates_sorted_newest_first(client):
    client.post("/api/demo/seed")
    updates = client.get("/api/updates").json()
    dates = [u["published_on"] for u in updates]
    assert dates == sorted(dates, reverse=True)
    assert "raw_text" not in updates[0]
