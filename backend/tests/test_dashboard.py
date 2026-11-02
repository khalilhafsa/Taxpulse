"""Dashboard, relevance matrix, live chain view and the one-click chain run (fake LLM)."""
from app.agents.runner import get_runner
from app.main import app
from tests.test_matching import fake_matcher, prepare_demo


def test_empty_dashboard(client):
    d = client.get("/api/dashboard").json()
    assert d["counts"]["clients"] == 0 and d["todo"] == [] and d["top_clients"] == []
    assert client.get("/api/matrix").json()["rows"] == []
    stages = client.get("/api/pipeline").json()["stages"]
    assert [s["key"] for s in stages] == ["profiler", "analyst", "prefilter", "matcher", "explainer", "writer"]
    assert stages[2]["llm"] is False


def chain_runner(calls):
    """Records the order of agent calls; returns valid outputs for every schema."""
    import json
    from app.agents.runner import AgentResult
    from app.agents.schemas import MatchList, ProfileDraft, UpdateAnalysis
    from tests.conftest import FAKE_ANALYSIS, FIXTURES

    def runner(**kw):
        schema = kw["schema"]
        calls.append(schema.__name__)
        if schema is ProfileDraft:
            out = ProfileDraft.model_validate(json.loads((FIXTURES / "nordlicht_profile.json").read_text(encoding="utf-8")))
        elif schema is UpdateAnalysis:
            out = FAKE_ANALYSIS.model_copy()
        elif schema is MatchList:
            out = MatchList(matches=[])
        else:
            raise AssertionError(schema)
        return AgentResult(output=out, model="claude-sonnet-5-5", tokens_in=1000, tokens_out=100, duration_ms=10)
    runner.requires_api_key = False
    return runner


def test_one_click_chain_runs_profiler_then_analyst_then_matcher(client):
    client.post("/api/demo/seed")
    assert client.get("/api/pipeline").json()["pending"] == {"profiles": 4, "analyses": 6, "scans": 0, "total": 10}
    d = client.get("/api/dashboard").json()
    assert [t["key"] for t in d["todo"]] == ["profiles", "analyse"]
    assert d["todo"][0]["label"] == "Build 4 missing client profiles"

    calls = []
    app.dependency_overrides[get_runner] = lambda: chain_runner(calls)
    assert client.post("/api/pipeline/run").status_code == 202  # TestClient runs background tasks before returning

    # Strict order: every profile, then every analysis, then the matching.
    assert calls[:4] == ["ProfileDraft"] * 4 and calls[4:10] == ["UpdateAnalysis"] * 6
    assert set(calls[10:]) <= {"MatchList"}

    p = client.get("/api/pipeline").json()
    stages = {s["key"]: s for s in p["stages"]}
    assert p["chain"]["running"] is False and p["chain"]["error"] == "" and p["chain"]["finished_at"]
    assert p["chain"]["started_at"] and len(p["log"]) == 6 and p["log"][0]["agent"] == "matcher"
    assert p["waiting_for_review"] == 0  # the recording fake finds no affected client
    assert stages["profiler"]["done"] == stages["profiler"]["total"] == 4
    assert stages["analyst"]["done"] == stages["analyst"]["total"] == 6
    assert stages["matcher"]["runs"] == 6 and stages["matcher"]["failed"] == 0
    assert stages["prefilter"]["total"] == p["pairs"]["total"] == 24
    assert stages["profiler"]["cost_usd"] > 0 and stages["prefilter"]["cost_usd"] == 0
    runs = client.get("/api/runs").json()["runs"]
    assert len({r["pipeline_id"] for r in runs}) == 1  # one chain, one pipeline id

    d = client.get("/api/dashboard").json()
    assert d["counts"]["clients_missing_profile"] == 0 and d["counts"]["updates_not_analysed"] == 0
    assert d["counts"]["updates_unscanned"] == 0

    # Nothing left to do: a second run adds no agent calls.
    n = len(calls)
    assert p["pending"]["total"] == 0
    assert client.post("/api/pipeline/run").json() == {"pipeline_id": "", "nothing_to_do": True}
    assert len(calls) == n


def test_dashboard_top_alerts_and_todo_after_scan(client):
    prepare_demo(client)
    app.dependency_overrides[get_runner] = lambda: fake_matcher
    client.post("/api/scan", json={})
    d = client.get("/api/dashboard").json()
    assert d["counts"]["alerts_to_review"] > 0 and d["todo"][0]["key"] == "review"
    top = d["top_clients"]
    scores = [e["score"] for e in top]
    assert scores == sorted(scores, reverse=True) and 0 < len(scores) <= 4
    assert len({e["client_id"] for e in top}) == len(top)  # one line per client
    assert sum(len(e["topics"]) for e in top) == d["counts"]["alerts_to_review"]
    brightloop = next(e for e in top if e["client"].startswith("Brightloop"))
    assert len(brightloop["topics"]) >= 2 and brightloop["topics"][0]["score"] == brightloop["score"]
    assert d["recent_runs"] and d["recent_runs"][0]["agent"] == "matcher"


def test_matrix_shows_scores_and_alerts(client):
    prepare_demo(client)
    app.dependency_overrides[get_runner] = lambda: fake_matcher
    client.post("/api/scan", json={})
    m = client.get("/api/matrix").json()
    assert len(m["rows"]) == 4 and len(m["updates"]) == 6
    assert all(len(r["cells"]) == 6 for r in m["rows"])
    cells = [c for r in m["rows"] for c in r["cells"] if c]
    assert any(c["stage"] == "filtered_out" for c in cells)
    alerted = [c for c in cells if c["alert_id"]]
    assert alerted and all(c["score"] >= m["threshold"] for c in alerted)
    assert len(alerted) == client.get("/api/dashboard").json()["counts"]["alerts_to_review"]


def test_chain_refuses_without_key_and_when_busy(client):
    client.post("/api/demo/seed")
    assert client.post("/api/pipeline/run").status_code == 400  # no key, real runner
    from sqlmodel import Session
    from app.db import engine
    from app.models import AgentRun
    with Session(engine) as s:
        s.add(AgentRun(pipeline_id="x", agent="profiler", subject="client:1"))
        s.commit()
    app.dependency_overrides[get_runner] = lambda: fake_matcher
    assert client.post("/api/pipeline/run").status_code == 409
    current = {s["key"]: s for s in client.get("/api/pipeline").json()["stages"]}["profiler"]
    assert current["running"] == 1 and current["current"]


def test_failures_fixed_by_a_later_run_are_not_counted():
    from app.models import AgentRun
    from app.routes.dashboard import _unresolved_failures
    runs = [AgentRun(pipeline_id="p", agent="profiler", subject=s, status=st) for s, st in [
        ("client:1", "done"), ("client:2", "failed"), ("client:1", "failed"), ("client:1", "failed"), ("client:3", "running")]]
    assert _unresolved_failures(runs) == 1  # client:1 was fixed, client:2 still failing
