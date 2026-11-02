import json
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlmodel import Session, select

from ..agents.matcher import run_matcher_batch, sync_alert
from ..agents.prefilter import prefilter
from ..agents.runner import Runner, get_runner
from ..config import settings
from ..db import engine, get_session
from ..models import AgentRun, Alert, Client, ClientProfile, Match, RegulatoryUpdate, now

router = APIRouter(tags=["matching"])


def latest_profiles(session: Session) -> dict[int, ClientProfile]:
    rows = session.exec(select(ClientProfile).order_by(ClientProfile.version)).all()
    return {p.client_id: p for p in rows}


def matcher_runs(session: Session) -> dict[int, AgentRun]:
    """Most recent matcher run per match id."""
    runs = session.exec(select(AgentRun).where(AgentRun.agent == "matcher").order_by(AgentRun.id)).all()
    return {int(r.subject.split(":")[1]): r for r in runs}


def plan(session: Session, updates: list[RegulatoryUpdate], force: bool) -> tuple[list[tuple[int, int]], dict]:
    """Run the pre-filter for every client with a profile and create one matcher run per shortlisted pair.
    Without `force`, pairs already scored on the current profile version are kept as they are."""
    profiles = latest_profiles(session)
    runs = matcher_runs(session)
    pipeline = uuid.uuid4().hex
    clients = session.exec(select(Client)).all()
    jobs, counts = [], {"shortlisted": 0, "filtered_out": 0, "queued": 0, "unchanged": 0,
                        "clients_without_profile": len(clients) - len(profiles)}
    for u in updates:
        if not u.summary:
            continue
        for client_id, profile in profiles.items():
            m = session.exec(select(Match).where(Match.client_id == client_id, Match.update_id == u.id)).first()
            if m and runs.get(m.id) and runs[m.id].status == "running":
                continue
            decision = prefilter(u.summary, profile.data)
            if not m:
                m = Match(client_id=client_id, update_id=u.id)
            m.prefilter_reason = decision.reason
            if not decision.shortlisted:
                counts["filtered_out"] += 1
                m.stage, m.score, m.verdict, m.reasoning, m.evidence = "filtered_out", None, None, "", []
                m.updated_at = now()
                session.add(m)
                session.flush()
                sync_alert(session, m)
                continue
            counts["shortlisted"] += 1
            if not force and m.stage == "scored" and m.profile_version == profile.version:
                counts["unchanged"] += 1
                session.add(m)
                continue
            session.add(m)
            session.flush()
            run = AgentRun(pipeline_id=pipeline, agent="matcher", subject=f"match:{m.id}",
                           model=settings.model_reasoning.split("/", 1)[-1])
            session.add(run)
            session.flush()
            jobs.append((run.id, m.id))
    session.commit()
    counts["queued"] = len(jobs)
    return jobs, counts


def _start(session: Session, updates: list[RegulatoryUpdate], force: bool, background: BackgroundTasks, runner: Runner):
    if getattr(runner, "requires_api_key", True) and not settings.llm_configured:
        raise HTTPException(400, "No Anthropic API key. Add ANTHROPIC_API_KEY to the .env file and restart the backend.")
    if not latest_profiles(session):
        raise HTTPException(400, "No client has a profile yet. Open a client and click Build profile first.")
    jobs, counts = plan(session, updates, force)
    if jobs:
        background.add_task(run_matcher_batch, engine, jobs, runner)
    return counts


@router.post("/updates/{update_id}/match", status_code=202)
def match_update(update_id: int, background: BackgroundTasks, session: Session = Depends(get_session),
                 runner: Runner = Depends(get_runner)):
    """Pre-filter all clients for this update and score the shortlisted ones again."""
    u = session.get(RegulatoryUpdate, update_id)
    if not u:
        raise HTTPException(404, "Update not found")
    if not u.summary:
        raise HTTPException(400, "Analyse this update first: the Matcher needs the Analyst's criteria.")
    return _start(session, [u], True, background, runner)


@router.post("/matching/scan", status_code=202)
def scan_portfolio(background: BackgroundTasks, session: Session = Depends(get_session),
                   runner: Runner = Depends(get_runner)):
    """Match every analysed update against every client profile; pairs already scored are skipped."""
    updates = session.exec(select(RegulatoryUpdate).order_by(RegulatoryUpdate.id)).all()
    return _start(session, list(updates), False, background, runner)


def serialize_match(m: Match, run: AgentRun | None) -> dict:
    data = m.model_dump()
    data["status"] = ("running" if run and run.status == "running"
                      else "failed" if run and run.status == "failed" and m.stage != "scored"
                      else m.stage)
    data["error"] = run.error if run and run.status == "failed" else None
    data["is_alert"] = m.stage == "scored" and (m.score or 0) >= settings.alert_threshold
    return data


@router.get("/updates/{update_id}/matches")
def update_matches(update_id: int, session: Session = Depends(get_session)):
    if not session.get(RegulatoryUpdate, update_id):
        raise HTTPException(404, "Update not found")
    runs = matcher_runs(session)
    rows = session.exec(select(Match, Client).join(Client, Client.id == Match.client_id)
                        .where(Match.update_id == update_id)).all()
    items = [{**serialize_match(m, runs.get(m.id)), "client_name": c.name} for m, c in rows]
    items.sort(key=lambda x: (x["score"] is None, -(x["score"] or 0), x["client_name"]))
    profiled = set(latest_profiles(session))
    missing = [c.name for c in session.exec(select(Client).order_by(Client.name)).all() if c.id not in profiled]
    return {"threshold": settings.alert_threshold, "matches": items, "clients_without_profile": missing}


@router.get("/alerts")
def list_alerts(session: Session = Depends(get_session)):
    rows = session.exec(select(Alert, Match, Client, RegulatoryUpdate)
                        .join(Match, Match.id == Alert.match_id)
                        .join(Client, Client.id == Match.client_id)
                        .join(RegulatoryUpdate, RegulatoryUpdate.id == Match.update_id)).all()
    items = [{
        "id": a.id, "status": a.status, "created_at": a.created_at,
        "score": m.score, "verdict": m.verdict, "reasoning": m.reasoning,
        "evidence_count": len(m.evidence or []),
        "client_id": c.id, "client_name": c.name, "client_is_demo": c.is_demo,
        "update_id": u.id, "update_title": (u.summary or {}).get("title_en") or u.title,
        "update_kind": (u.summary or {}).get("kind") or u.kind, "update_source": u.source,
    } for a, m, c, u in rows]
    items.sort(key=lambda x: (-(x["score"] or 0), x["client_name"]))
    return {"threshold": settings.alert_threshold, "alerts": items}


# ---------- evaluation against the hand-labelled ground truth ----------

def evaluate(session: Session) -> dict:
    labels = json.loads((settings.demo_dir / "expected_matches.json").read_text(encoding="utf-8"))["labels"]
    clients = {c.slug: c for c in session.exec(select(Client)).all()}
    updates = {u.external_id: u for u in session.exec(select(RegulatoryUpdate)).all()}
    rows, counts = [], {"correct": 0, "missed": 0, "false_alert": 0, "borderline": 0, "pending": 0}
    for lab in labels:
        c, u = clients.get(lab["client"]), updates.get(lab["update"])
        m = (session.exec(select(Match).where(Match.client_id == c.id, Match.update_id == u.id)).first()
             if c and u else None)
        if not m or m.stage == "prefiltered":
            outcome, alert = "pending", None
        else:
            alert = m.stage == "scored" and (m.score or 0) >= settings.alert_threshold
            outcome = ("borderline" if lab["label"] == "either"
                       else "correct" if alert == (lab["label"] == "affected")
                       else "missed" if lab["label"] == "affected" else "false_alert")
        counts[outcome] += 1
        rows.append({
            "client": c.name if c else lab["client"], "client_id": c.id if c else None,
            "update": (u.summary or {}).get("title_en") or u.title if u else lab["update"],
            "update_id": u.id if u else None, "expected": lab["label"], "why": lab["why"],
            "stage": m.stage if m else None, "score": m.score if m else None,
            "alert": alert, "outcome": outcome,
        })
    judged = counts["correct"] + counts["missed"] + counts["false_alert"]
    must_flag = sum(1 for lab in labels if lab["label"] == "affected")
    flagged_right = sum(1 for r in rows if r["expected"] == "affected" and r["outcome"] == "correct")
    return {
        "threshold": settings.alert_threshold,
        "pairs": len(labels), "judged": judged, **counts,
        "recall": round(flagged_right / must_flag, 3) if must_flag else None,
        "false_alerts_per_10": round(10 * counts["false_alert"] / judged, 2) if judged else None,
        "complete": counts["pending"] == 0,
        "passed": counts["pending"] == 0 and counts["missed"] == 0 and counts["false_alert"] * 10 <= judged,
        "rows": rows,
    }


@router.get("/evaluation")
def evaluation(session: Session = Depends(get_session)):
    """Compare the Matcher's alerts with data/demo/expected_matches.json (spec section 9)."""
    return evaluate(session)
