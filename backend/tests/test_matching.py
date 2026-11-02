"""Pre-filter, Impact Matcher (fake LLM), alerts and evaluation against the labelled demo answers."""
import json
import re

from sqlmodel import Session, select

from app.agents.matcher import prefilter
from app.agents.runner import AgentResult, get_runner
from app.agents.schemas import ClientMatch, Evidence, MatchList, ProfileDraft, UpdateAnalysis
from app.config import settings
from app.db import engine
from app.main import app
from app.models import AgentRun, Alert, Client, ClientProfile, Match, RegulatoryUpdate
from tests.conftest import fake_runner

LABELS = {(l["client"], l["update"]): l["label"] for l in json.loads(
    (settings.demo_dir / "expected_matches.json").read_text(encoding="utf-8"))["labels"]}

PROFILE_AREAS = {
    "mueller_praezisionstechnik": (["VAT", "Transfer pricing", "R&D incentives", "Wage tax"],
                                   ["contract manufacturing", "e-invoicing", "Sage 100", "Forschungszulage"]),
    "nordlicht_immobilien": (["Real estate transfer tax", "Trade tax", "Financing", "VAT"],
                             ["share deal", "photovoltaic", "interest barrier"]),
    "brightloop_software": (["Corporate income tax", "R&D incentives", "VAT", "International tax"],
                            ["loss carryforwards", "SaaS", "Stripe", "BSFZ"]),
    "kaiser_dental": (["VAT", "Corporate income tax", "Wage tax"], ["dental", "VAT-exempt", "healthcare"]),
}
UPDATE_AREAS = {
    "DEMO-BMF-01": ["VAT"], "DEMO-BFH-02": ["Corporate income tax"], "DEMO-BFH-03": ["Trade tax"],
    "DEMO-BMF-04": ["R&D incentives"], "DEMO-BMF-05": ["Transfer pricing"], "DEMO-BMF-06": ["VAT"],
}


def make_profile(slug: str) -> dict:
    cats, kws = PROFILE_AREAS[slug]
    cite = [{"document": "x.pdf", "page": 1, "quote": "q", "verified": True}]
    return ProfileDraft(
        company_name=slug, summary=f"Profile of {slug}.",
        key_facts=[{"label": "Business", "value": f"{slug} operates in Germany with documented activity",
                    "citations": cite}],
        tax_areas=[{"category": c, "title": f"{c} exposure", "assessment": "risk", "severity": "medium",
                    "summary": "s", "facts": [{"label": "f", "value": "v", "citations": cite}]} for c in cats],
        open_points=[], keywords=kws).model_dump()


def make_analysis(ext_id: str) -> dict:
    return UpdateAnalysis(title_en=ext_id, kind="bmf_letter", relevant_for_companies=True,
                          tax_categories=UPDATE_AREAS[ext_id], summary="s", who_is_affected="w",
                          trigger_criteria=["criterion"], exclusions=[], effective_date="2027",
                          keywords=["k"]).model_dump()


def fake_matcher(**kwargs) -> AgentResult:
    """Answers like a perfect Matcher would, from the labelled answers, plus one invented fact."""
    if kwargs["schema"] is not MatchList:
        return fake_runner(**kwargs)
    task = kwargs["task"]
    update = re.search(r"Title: (DEMO-\w+-\d+)", task).group(1)
    out = []
    for slug in re.findall(r"client_id: (\w+)", task):
        label = LABELS.get((slug, update), "not_affected")
        score, verdict = {"affected": (88, "affected"), "either": (45, "uncertain")}.get(label, (12, "not_affected"))
        out.append(ClientMatch(client_id=slug, score=score, verdict=verdict, reasoning=f"{label} by design",
                               evidence=[Evidence(client_fact=f"{slug} operates in Germany with documented activity",
                                                  criterion="criterion", supports_impact=True),
                                         Evidence(client_fact="The company sold its factory in 2025",
                                                  criterion="criterion", supports_impact=True)],
                               missing_information=[]))
    out.append(ClientMatch(client_id="invented_client", score=99, verdict="affected", reasoning="x",
                           evidence=[], missing_information=[]))
    return AgentResult(output=MatchList(matches=out), model="claude-sonnet-5-5",
                       tokens_in=6000, tokens_out=1500, duration_ms=900)


fake_matcher.requires_api_key = False


def prepare_demo(client):
    """Demo data with profiles and analyses written directly (no LLM needed)."""
    client.post("/api/demo/seed")
    with Session(engine) as s:
        for c in s.exec(select(Client).where(Client.is_demo == True)).all():  # noqa: E712
            if not s.exec(select(ClientProfile).where(ClientProfile.client_id == c.id)).first():
                s.add(ClientProfile(client_id=c.id, version=1, data=make_profile(c.slug)))
        for u in s.exec(select(RegulatoryUpdate).where(RegulatoryUpdate.source == "demo")).all():
            u.summary = make_analysis(u.external_id)
            s.add(u)
        s.commit()


def test_matcher_prompt_explains_criteria_logic():
    from app.agents.matcher import update_text
    u = RegulatoryUpdate(external_id="x", kind="bmf_letter", title="t", source="demo", raw_text="text",
                         content_hash="h", summary=make_analysis("DEMO-BMF-04"))
    assert "Criteria logic: any (one criterion is enough)" in update_text(u)
    u.summary = {**u.summary, "criteria_logic": "all"}
    assert "every criterion must be met" in update_text(u)


def test_prefilter_keeps_shared_areas_and_drops_unrelated():
    vat = make_analysis("DEMO-BMF-01")
    assert prefilter(vat, make_profile("kaiser_dental"))[0] is True
    trade = make_analysis("DEMO-BFH-03")
    keep, why = prefilter(trade, make_profile("brightloop_software"))
    assert keep is False and "No shared" in why
    keep, why = prefilter(trade, make_profile("nordlicht_immobilien"))
    assert keep and "Trade tax" in why


def test_scan_requires_profiles_and_key(client):
    client.post("/api/demo/seed")
    assert client.post("/api/scan", json={}).status_code == 400


def test_scan_creates_alerts_and_passes_evaluation(client):
    prepare_demo(client)
    app.dependency_overrides[get_runner] = lambda: fake_matcher

    status = client.get("/api/scan/status").json()
    assert status["updates_unscanned"] >= 6

    assert client.post("/api/scan", json={}).json()["queued"] >= 6
    alerts = client.get("/api/alerts").json()
    pairs = {(a["client"]["name"], a["update"]["title"]) for a in alerts}
    assert ("Brightloop Software GmbH", "DEMO-BFH-02") in pairs
    assert not any(a["client"]["name"] == "Kaiser Dental MVZ GmbH" for a in alerts)
    assert alerts == sorted(alerts, key=lambda a: -a["score"])

    # Evidence copied from the profile is verified; the invented fact is not.
    ev = alerts[0]["evidence"]
    assert ev[0]["verified"] is True and ev[1]["verified"] is False

    # Kaiser x trade tax ruling never reached the AI.
    with Session(engine) as s:
        kaiser = s.exec(select(Client).where(Client.slug == "kaiser_dental")).one()
        bfh03 = s.exec(select(RegulatoryUpdate).where(RegulatoryUpdate.external_id == "DEMO-BFH-03")).one()
        m = s.exec(select(Match).where(Match.client_id == kaiser.id, Match.update_id == bfh03.id)).one()
        assert m.stage == "filtered_out"
        assert s.exec(select(AgentRun).where(AgentRun.agent == "matcher")).first().cost_usd == 0.027

    report = client.get("/api/evaluation").json()
    assert report["affected_total"] == 7 and report["affected_found"] == 7
    assert report["false_alerts"] == 0 and report["not_evaluated"] == 0
    assert report["alerts_on_demo_updates"] == len(alerts) and report["alerts_on_other_updates"] == 0

    # Nothing new to scan; a full rescan keeps decisions and does not duplicate alerts.
    assert client.post("/api/scan", json={}).json()["queued"] == 0
    target = alerts[0]["id"]
    assert client.post(f"/api/alerts/{target}/status", json={"status": "dismissed"}).status_code == 400
    r = client.post(f"/api/alerts/{target}/status", json={"status": "dismissed", "reason": "Client already advised"})
    assert r.json()["status"] == "dismissed"
    client.post("/api/scan", json={"rescan_all": True})
    after = client.get("/api/alerts").json()
    assert len(after) == len(alerts)
    assert next(a for a in after if a["id"] == target)["status"] == "dismissed"
    with Session(engine) as s:
        assert len(s.exec(select(Alert)).all()) == len(alerts)


def test_matrix_lists_all_pairs(client):
    prepare_demo(client)
    app.dependency_overrides[get_runner] = lambda: fake_matcher
    client.post("/api/scan", json={"rescan_all": True})
    stages = {m["stage"] for m in client.get("/api/matches").json()}
    assert stages <= {"scored", "filtered_out"} and "scored" in stages
