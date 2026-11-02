"""Retries, the monthly budget, recovery after a restart, the stability test and the Quality report."""
import pytest
from sqlmodel import Session, select

from app.agents import runner as R
from app.agents.runner import AgentResult, get_runner
from app.agents.schemas import ClientMatch, MatchList
from app.db import engine
from app.main import app
from app.models import AgentRun, FirmSettings
from app.quality import recover_interrupted
from tests.test_matching import fake_matcher, prepare_demo


def ok_result():
    return AgentResult(output=MatchList(matches=[]), model="claude-sonnet-5-5", tokens_in=1, tokens_out=1, duration_ms=1)


def test_transient_errors_are_retried_and_counted(monkeypatch):
    monkeypatch.setattr(R, "_sleep", lambda s: None)
    calls = []

    def flaky(**kw):
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError("Error code: 529 - overloaded_error")
        return ok_result()
    result = R.with_retries(flaky)()
    assert len(calls) == 3 and result.attempts == 3


@pytest.mark.parametrize("message", ["Error code: 401 - invalid x-api-key", "Your credit balance is too low",
                                     "The agent did not return JSON."])
def test_permanent_errors_are_not_retried(monkeypatch, message):
    monkeypatch.setattr(R, "_sleep", lambda s: None)
    calls = []

    def broken(**kw):
        calls.append(1)
        raise RuntimeError(message)
    with pytest.raises(RuntimeError):
        R.with_retries(broken)()
    assert len(calls) == 1


def test_retries_give_up_after_three_attempts(monkeypatch):
    monkeypatch.setattr(R, "_sleep", lambda s: None)
    calls = []

    def down(**kw):
        calls.append(1)
        raise TimeoutError("Request timed out")
    with pytest.raises(TimeoutError):
        R.with_retries(down)()
    assert len(calls) == 3


def test_budget_stops_agents_before_calling_claude(client):
    called = []
    guarded = R.with_budget(lambda **kw: called.append(1) or ok_result())
    guarded()  # no budget set: no limit
    client.put("/api/settings/firm", json={"monthly_budget_usd": 0.05})
    with Session(engine) as s:
        s.add(AgentRun(pipeline_id="p", agent="profiler", status="done", cost_usd=0.06))
        s.commit()
    with pytest.raises(R.BudgetExceeded) as err:
        guarded()
    assert len(called) == 1 and "$0.05" in str(err.value)
    assert "Raise it in Settings" in R.friendly_error(err.value)
    firm = client.get("/api/settings/firm").json()
    assert firm["monthly_budget_usd"] == 0.05 and firm["spent_this_month_usd"] == 0.06
    assert client.put("/api/settings/firm", json={"monthly_budget_usd": -1}).status_code == 422


def test_production_runner_checks_budget_then_retries():
    assert R.get_runner() is R.production_runner


def test_restart_marks_running_agents_as_interrupted(client):
    with Session(engine) as s:
        s.add(AgentRun(pipeline_id="p", agent="matcher", subject="update:1"))
        s.commit()
        assert recover_interrupted(s) == 1
        run = s.exec(select(AgentRun)).first()
        assert run.status == "failed" and run.error.startswith("Interrupted")
    assert client.get("/api/quality").json()["reliability"]["interrupted"] == 1


def test_stability_test_with_a_perfectly_stable_matcher(client):
    assert client.post("/api/quality/stability", json={"runs": 3}).status_code in (400,)  # no demo data yet
    prepare_demo(client)
    app.dependency_overrides[get_runner] = lambda: fake_matcher
    assert client.post("/api/quality/stability", json={"runs": 3}).status_code == 202

    st = client.get("/api/quality").json()["stability"]
    assert st["status"] == "done" and st["runs_done"] == 3 and st["error"] == ""
    assert st["consistency"] == 1.0 and st["unstable_pairs"] == [] and st["perfect_runs"] == 3
    assert st["clear_consistency"] == 1.0 and 0 < st["clear_pairs"] <= st["scored_pairs"]
    assert st["affected_found_min"] == st["affected_total"] == 7 and st["false_alerts_max"] == 0
    assert st["cost_usd"] > 0
    # Nothing was written to matches or alerts; every call was logged as a run.
    assert client.get("/api/alerts").json() == []
    runs = [r for r in client.get("/api/runs").json()["runs"] if r["subject"].startswith("eval:")]
    assert runs and all(r["subject_label"] == "Stability test (demo data)" for r in runs)


def test_stability_test_spots_a_pair_that_flips(client):
    prepare_demo(client)
    calls = {"n": 0}

    def flipping(**kw):
        result = fake_matcher(**kw)
        if kw["schema"] is MatchList and "DEMO-BMF-01" in kw["task"]:
            calls["n"] += 1
            if calls["n"] == 2:  # second run: Brightloop drops below the threshold
                result.output = MatchList(matches=[
                    ClientMatch(**{**m.model_dump(), "score": 40}) if m.client_id == "brightloop_software" else m
                    for m in result.output.matches])
        return result
    flipping.requires_api_key = False
    app.dependency_overrides[get_runner] = lambda: flipping
    client.post("/api/quality/stability", json={"runs": 3})

    st = client.get("/api/quality").json()["stability"]
    assert st["consistency"] < 1.0 and st["perfect_runs"] == 2
    flip = st["unstable_pairs"][0]
    assert flip["client"] == "brightloop_software" and flip["update"] == "DEMO-BMF-01"
    assert flip["scores"] == [88, 40, 88] and flip["expected"] == "affected"
    assert st["clear_consistency"] < 1.0
    assert st["affected_found_min"] == 6 and st["max_score_spread"] == 48


def test_stability_refuses_when_agents_are_busy_and_bounds_runs(client):
    prepare_demo(client)
    app.dependency_overrides[get_runner] = lambda: fake_matcher
    assert client.post("/api/quality/stability", json={"runs": 11}).status_code == 422
    with Session(engine) as s:
        s.add(AgentRun(pipeline_id="p", agent="profiler", subject="client:1"))
        s.commit()
    assert client.post("/api/quality/stability", json={"runs": 2}).status_code == 409


def test_quality_report_sections(client):
    prepare_demo(client)
    app.dependency_overrides[get_runner] = lambda: fake_matcher
    client.post("/api/scan", json={})
    q = client.get("/api/quality").json()
    assert set(q) == {"matcher_accuracy", "stability", "citations", "emails", "reliability", "per_agent", "budget"}
    assert q["matcher_accuracy"]["affected_found"] == 7 and q["stability"] is None
    assert q["per_agent"][0]["agent"] == "matcher" and q["per_agent"][0]["success_rate"] == 1.0
    with Session(engine) as s:
        assert s.get(FirmSettings, 1) is None or s.get(FirmSettings, 1).monthly_budget_usd == 0


def test_flip_on_an_ambiguous_pair_keeps_clear_cut_consistency():
    from app.models import EvalBatch
    from app.quality import summarise
    base = {"stage": "scored", "verdict": "affected"}
    runs = [{"index": i, "cost_usd": 0.1, "pairs": {
        "nordlicht_immobilien|DEMO-BMF-01": {**base, "score": s, "flagged": s >= 60},  # labelled "either"
        "brightloop_software|DEMO-BMF-01": {**base, "score": 88, "flagged": True},  # labelled "affected"
    }} for i, s in enumerate([62, 62, 45], start=1)]
    st = summarise(EvalBatch(id=1, runs=runs, runs_planned=3, status="done"))
    assert st["consistency"] == 0.5 and st["clear_pairs"] == 1 and st["clear_consistency"] == 1.0
    assert st["unstable_pairs"][0]["expected"] == "either"
