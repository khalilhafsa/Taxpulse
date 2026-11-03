"""Public demo: export recorded agent results, then replay them with no API key and no uploads."""
import json

import pytest

from app import replay
from app.agents.runner import get_runner
from app.agents.schemas import ProfileDraft, UpdateAnalysis
from app.config import settings
from app.db import engine
from app.main import app
from tests.conftest import FIXTURES
from tests.test_matching import fake_matcher, prepare_demo


def record(client) -> dict:
    """What a real session leaves behind: profiles, analyses, scores, two memos and an email."""
    prepare_demo(client)
    app.dependency_overrides[get_runner] = lambda: fake_matcher
    client.post("/api/scan", json={})
    alerts = client.get("/api/alerts").json()
    brightloop = [a for a in alerts if a["client"]["name"].startswith("Brightloop")]
    for a in brightloop:
        client.post(f"/api/alerts/{a['id']}/status", json={"status": "accepted"})
    client.post(f"/api/clients/{brightloop[0]['client']['id']}/draft-email")
    data = replay.export(settings.database_url)
    # The demo fakes write simplified profiles; give each client a complete one, as the real Profiler does.
    full = json.loads((FIXTURES / "nordlicht_profile.json").read_text(encoding="utf-8"))
    for rec in data["profiles"].values():
        rec["data"] = full
    app.dependency_overrides.clear()
    return data


@pytest.fixture
def demo(client, monkeypatch):
    data = record(client)
    monkeypatch.setattr(replay, "recordings", lambda: data)
    monkeypatch.setattr(replay, "PAUSE_S", {k: 0 for k in replay.PAUSE_S})
    monkeypatch.setattr(settings, "demo_mode", True)
    replay.reset_demo(engine, prefilled=False)
    return data


def test_export_keeps_only_demo_results(client):
    data = record(client)
    assert len(data["profiles"]) == 4 and len(data["analyses"]) == 6 and len(data["matches"]) == 6
    assert len(data["memos"]) == len([k for k in data["memos"] if k.startswith("brightloop_software|")]) >= 2
    [(topics, draft)] = data["drafts"]["brightloop_software"].items()
    assert topics.count("DEMO-") >= 2 and not draft["body"].startswith("Dear") and "Kind regards" not in draft["body"]
    UpdateAnalysis.model_validate(data["analyses"]["DEMO-BMF-01"]["summary"])


def test_replay_runs_the_whole_chain_without_a_key(client, demo):
    h = client.get("/api/health").json()
    assert h["demo_mode"] is True and h["llm_configured"] is True
    assert client.get("/api/alerts").json() == []  # fresh demo
    assert client.post("/api/pipeline/run").status_code == 202
    stages = {s["key"]: s for s in client.get("/api/pipeline").json()["stages"]}
    assert stages["profiler"]["done"] == 4 and stages["analyst"]["done"] == 6 and stages["matcher"]["failed"] == 0
    alerts = client.get("/api/alerts").json()
    # The recorded scores come back unchanged (this test gives every client the same profile, so the
    # free pre-filter keeps fewer pairs than in the recording).
    recorded = {(slug, ext): c["score"] for ext, m in demo["matches"].items() for slug, c in m["clients"].items()}
    by_name = {rec["name"]: slug for slug, rec in demo["profiles"].items()}
    assert alerts and all(recorded[(by_name[a["client"]["name"]], a["update"]["original_title"] and
                                    next(e for e, m in demo["matches"].items() if m["title"] == a["update"]["original_title"]))]
                          == a["score"] for a in alerts)

    b = next(a for a in alerts if a["client"]["name"].startswith("Brightloop"))
    client.post(f"/api/alerts/{b['id']}/status", json={"status": "accepted"})
    memo = next(a for a in client.get("/api/alerts").json() if a["id"] == b["id"])
    assert memo["memo_status"] == "done"

    other = next((a for a in alerts if not a["client"]["name"].startswith("Brightloop")), None)
    if other:  # no memo was recorded for other clients: the demo says so instead of inventing one
        client.post(f"/api/alerts/{other['id']}/status", json={"status": "accepted"})
        failed = next(a for a in client.get("/api/alerts").json() if a["id"] == other["id"])
        assert failed["memo_status"] == "failed" and "was recorded" in failed["memo_error"]

    cid = b["client"]["id"]
    client.post(f"/api/clients/{cid}/draft-email")
    draft = next(e for e in client.get("/api/outreach").json() if e["client"]["id"] == cid)["drafts"][0]
    assert draft["body"].startswith("Dear Mr Becker,") and "Dr Lena Weber" in draft["body"]
    runs = client.get("/api/runs").json()["runs"]
    assert all(r["status"] in ("done", "failed") for r in runs) and runs[0]["agent"] == "writer"


@pytest.mark.parametrize("method,path", [
    ("post", "/api/clients"), ("post", "/api/clients/1/documents"), ("post", "/api/updates"),
    ("post", "/api/updates/fetch"), ("post", "/api/updates/fetch-bfh"), ("post", "/api/updates/receive-feed"),
    ("put", "/api/settings/firm"), ("put", "/api/automation"), ("post", "/api/automation/run"),
    ("post", "/api/quality/stability"), ("post", "/api/drafts/1/revise"),
])
def test_risky_actions_are_switched_off(client, demo, method, path):
    r = getattr(client, method)(path, json={})
    assert r.status_code == 403 and "public demo" in r.json()["detail"]


def test_reset_opens_on_recorded_results(client, demo):
    assert client.post("/api/demo/reset").json() == {"reset": True}
    alerts = client.get("/api/alerts").json()
    assert alerts and len(client.get("/api/clients").json()) == 4
    # One client is already reviewed: its alerts accepted, memos written, email drafted.
    accepted = [a for a in alerts if a["status"] == "accepted"]
    assert accepted and all(a["memo_status"] == "done" for a in accepted)
    outreach = client.get("/api/outreach").json()
    assert len(outreach) == 1 and outreach[0]["drafts"][0]["body"].startswith("Dear ")
    assert any(a["status"] == "new" for a in alerts)  # others are left for the visitor to review
    assert client.get("/api/pipeline").json()["pending"]["total"] == 0


def test_watch_starts_over_and_runs_the_chain(client, demo):
    client.post("/api/demo/reset")
    r = client.post("/api/demo/watch")
    assert r.status_code == 202  # TestClient runs the chain before returning
    stages = {s["key"]: s for s in client.get("/api/pipeline").json()["stages"]}
    assert stages["profiler"]["done"] == 4 and stages["matcher"]["failed"] == 0
    assert all(a["status"] == "new" for a in client.get("/api/alerts").json())


def test_watch_is_not_available_outside_the_demo(client):
    assert client.post("/api/demo/watch").status_code == 404


def test_reset_is_not_available_outside_the_demo(client):
    assert client.post("/api/demo/reset").status_code == 404


def test_idle_demo_starts_fresh(client, demo, monkeypatch):
    from app import main
    client.post("/api/pipeline/run")
    client.post(f"/api/alerts/{client.get('/api/alerts').json()[0]['id']}/status", json={"status": "dismissed", "reason": "x"})
    monkeypatch.setitem(main._last_seen, "t", main._last_seen["t"] - 3600)
    assert not any(a["status"] == "dismissed" for a in client.get("/api/alerts").json())  # fresh, prefilled demo


def test_profile_replay_validates(demo):
    rec = next(iter(demo["profiles"].values()))
    ProfileDraft.model_validate(rec["data"])
