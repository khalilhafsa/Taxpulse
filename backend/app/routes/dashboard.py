"""Dashboard, relevance matrix and the live view of the agent chain (plus a one-click run of the chain)."""
import threading
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlmodel import Session, func, select

from ..agents.analyst import run_analyst
from ..agents.matcher import latest_profiles, run_matcher
from ..agents.profiler import run_profiler
from ..agents.runner import Runner, get_runner
from ..config import settings
from ..db import engine, get_session
from ..models import AgentRun, Alert, Client, ClientProfile, Document, EmailDraft, Match, RegulatoryUpdate, now
from .runs import subject_label

router = APIRouter(tags=["dashboard"])

# The chain, in order. The pre-filter is plain code (no LLM, no cost); explainer and writer
# start only after the advisor accepts an alert: the human stays in the loop.
STAGES = [
    {"key": "profiler", "name": "Profiler", "role": "Reads the data rooms and builds cited client profiles", "llm": True},
    {"key": "analyst", "name": "Regulatory Analyst", "role": "Structures each new BMF letter or ruling", "llm": True},
    {"key": "prefilter", "name": "Pre-filter", "role": "Drops client-update pairs with no shared tax area", "llm": False},
    {"key": "matcher", "name": "Impact Matcher", "role": "Scores how strongly each update affects each client", "llm": True},
    {"key": "explainer", "name": "Impact Explainer", "role": "Writes the memo once you accept an alert", "llm": True},
    {"key": "writer", "name": "Outreach Writer", "role": "Drafts one email per client, checked by the partner review", "llm": True},
]

# State of the one-click chain run. One process serves this local app, so module state is enough.
_chain = {"running": False, "step": "", "pipeline_id": "", "error": "", "started_at": None, "finished_at": None}
_lock = threading.Lock()


def _ready_updates(session: Session) -> list[RegulatoryUpdate]:
    return [u for u in session.exec(select(RegulatoryUpdate).order_by(RegulatoryUpdate.id)).all()
            if u.summary and u.summary.get("relevant_for_companies")]


def _title(u: RegulatoryUpdate) -> str:
    return (u.summary or {}).get("title_en", u.title)


def _running_any(session: Session) -> bool:
    return session.exec(select(AgentRun).where(AgentRun.status == "running")).first() is not None


def _pending(session: Session) -> dict:
    """What a chain run would do right now."""
    with_docs = {d.client_id for d in session.exec(select(Document)).all()}
    profiled = {p.client_id for p in session.exec(select(ClientProfile)).all()}
    scanned = {m.update_id for m in session.exec(select(Match)).all()}
    out = {
        "profiles": len(with_docs - profiled),
        "analyses": sum(1 for u in session.exec(select(RegulatoryUpdate)).all() if not u.summary),
        "scans": sum(1 for u in _ready_updates(session) if u.id not in scanned),
    }
    out["total"] = sum(out.values())
    return out


def _unresolved_failures(runs: list[AgentRun]) -> int:
    """Failures that were not fixed by a later successful run on the same client or update (runs newest first)."""
    latest: dict[str, str] = {}
    for r in runs:
        if r.status != "running":
            latest.setdefault(r.subject, r.status)
    return sum(1 for status in latest.values() if status == "failed")


@router.get("/dashboard")
def dashboard(session: Session = Depends(get_session)):
    clients = session.exec(select(Client)).all()
    with_docs = {d.client_id for d in session.exec(select(Document)).all()}
    profiled = {p.client_id for p in session.exec(select(ClientProfile)).all()}
    updates = session.exec(select(RegulatoryUpdate)).all()
    ready = _ready_updates(session)
    scanned = {m.update_id for m in session.exec(select(Match)).all()}
    alerts = session.exec(select(Alert)).all()
    drafts = session.exec(select(EmailDraft).order_by(EmailDraft.id.desc())).all()
    cost = session.exec(select(func.coalesce(func.sum(AgentRun.cost_usd), 0))).one()

    accepted = [a for a in alerts if a.status == "accepted"]
    accepted_clients = {session.get(Match, a.match_id).client_id for a in accepted if a.memo}
    latest_draft = {}
    for d in drafts:
        latest_draft.setdefault(d.client_id, d)
    drafting = {c for c in accepted_clients if c not in latest_draft}

    n = {
        "clients": len(clients),
        "clients_profiled": len(profiled & {c.id for c in clients}),
        "clients_missing_profile": sum(1 for c in clients if c.id in with_docs and c.id not in profiled),
        "updates": len(updates),
        "updates_not_analysed": sum(1 for u in updates if not u.summary),
        "updates_relevant": len(ready),
        "updates_unscanned": sum(1 for u in ready if u.id not in scanned),
        "alerts_to_review": sum(1 for a in alerts if a.status == "new"),
        "alerts_accepted": len(accepted),
        "clients_to_draft": len(drafting),
        "drafts_to_review": sum(1 for d in latest_draft.values() if d.status == "draft"),
        "drafts_ready": sum(1 for d in latest_draft.values() if d.status == "approved"),
        "emails_sent": sum(1 for d in drafts if d.status == "sent"),
        "cost_usd": round(cost, 4),
    }

    def plural(k, one, many):
        return one if n[k] == 1 else many

    todo = []
    if n["clients_missing_profile"]:
        todo.append({"key": "profiles", "count": n["clients_missing_profile"], "to": "/clients",
                     "label": f"Build {n['clients_missing_profile']} missing client {plural('clients_missing_profile', 'profile', 'profiles')}"})
    if n["updates_not_analysed"]:
        todo.append({"key": "analyse", "count": n["updates_not_analysed"], "to": "/updates",
                     "label": f"Analyse {n['updates_not_analysed']} new tax {plural('updates_not_analysed', 'update', 'updates')}"})
    if n["updates_unscanned"]:
        todo.append({"key": "scan", "count": n["updates_unscanned"], "to": "/alerts",
                     "label": f"Match {n['updates_unscanned']} {plural('updates_unscanned', 'update', 'updates')} against your clients"})
    if n["alerts_to_review"]:
        todo.append({"key": "review", "count": n["alerts_to_review"], "to": "/alerts",
                     "label": f"Review {n['alerts_to_review']} {plural('alerts_to_review', 'alert', 'alerts')}"})
    if n["clients_to_draft"]:
        todo.append({"key": "draft", "count": n["clients_to_draft"], "to": "/outreach",
                     "label": f"Draft {n['clients_to_draft']} client {plural('clients_to_draft', 'email', 'emails')}"})
    if n["drafts_to_review"]:
        todo.append({"key": "approve", "count": n["drafts_to_review"], "to": "/outreach",
                     "label": f"Read and approve {n['drafts_to_review']} {plural('drafts_to_review', 'email', 'emails')}"})
    if n["drafts_ready"]:
        todo.append({"key": "send", "count": n["drafts_ready"], "to": "/outreach",
                     "label": f"Send {n['drafts_ready']} approved {plural('drafts_ready', 'email', 'emails')} from your email app"})

    # One line per client: who to call first, with every open topic for that client.
    by_client: dict[int, dict] = {}
    for a in alerts:
        if a.status != "new":
            continue
        m = session.get(Match, a.match_id)
        c, u = session.get(Client, m.client_id), session.get(RegulatoryUpdate, m.update_id)
        e = by_client.setdefault(c.id, {"client": c.name, "client_id": c.id, "score": 0, "alert_id": a.id, "topics": []})
        e["topics"].append({"title": _title(u), "score": m.score or 0, "kind": (u.summary or {}).get("kind", u.kind)})
        if (m.score or 0) > e["score"]:
            e.update(score=m.score or 0, alert_id=a.id)
    top = sorted(by_client.values(), key=lambda e: (-e["score"], -len(e["topics"]), e["client"]))[:5]
    for e in top:
        e["topics"].sort(key=lambda t: -t["score"])

    runs = session.exec(select(AgentRun).order_by(AgentRun.id.desc()).limit(8)).all()
    recent = [{"id": r.id, "agent": r.agent, "status": r.status, "cost_usd": r.cost_usd, "duration_ms": r.duration_ms,
               "started_at": r.started_at, "label": subject_label(session, r.subject)} for r in runs]
    return {"counts": n, "todo": todo, "top_clients": top, "recent_runs": recent}


@router.get("/matrix")
def matrix(session: Session = Depends(get_session)):
    """Clients (rows) x relevant updates (columns) with the Matcher's score in each cell."""
    clients = [c for c, _ in latest_profiles(session)]
    updates = _ready_updates(session)
    matches = {(m.client_id, m.update_id): m for m in session.exec(select(Match)).all()}
    alerts = {a.match_id: a for a in session.exec(select(Alert)).all()}
    rows = []
    for c in sorted(clients, key=lambda c: c.name):
        cells = []
        for u in updates:
            m = matches.get((c.id, u.id))
            a = alerts.get(m.id) if m else None
            cells.append(None if not m else {
                "stage": m.stage, "score": m.score, "verdict": m.verdict,
                "alert_id": a.id if a else None, "alert_status": a.status if a else None})
        rows.append({"client": {"id": c.id, "name": c.name, "is_demo": c.is_demo}, "cells": cells})
    cols = [{"id": u.id, "title": _title(u), "kind": (u.summary or {}).get("kind", u.kind),
             "categories": (u.summary or {}).get("tax_categories", []), "external_id": u.external_id,
             "scanned": any(r["cells"][i] is not None for r in rows)} for i, u in enumerate(updates)]
    return {"updates": cols, "rows": rows, "threshold": settings.alert_threshold}


@router.get("/pipeline")
def pipeline(session: Session = Depends(get_session)):
    """Progress, cost and activity of each stage of the agent chain."""
    clients = session.exec(select(Client)).all()
    with_docs = {d.client_id for d in session.exec(select(Document)).all()}
    profiled = {p.client_id for p in session.exec(select(ClientProfile)).all()}
    updates = session.exec(select(RegulatoryUpdate)).all()
    ready = _ready_updates(session)
    matches = session.exec(select(Match)).all()
    alerts = session.exec(select(Alert)).all()
    accepted = [a for a in alerts if a.status == "accepted"]
    accepted_clients = {session.get(Match, a.match_id).client_id for a in accepted}
    drafted_clients = {d.client_id for d in session.exec(select(EmailDraft)).all()}

    progress = {
        "profiler": (len(profiled & with_docs), len(with_docs), "profiles built"),
        "analyst": (sum(1 for u in updates if u.summary), len(updates), "updates analysed"),
        "prefilter": (sum(1 for m in matches if m.stage != "filtered_out"), len(matches), "pairs kept for the Matcher"),
        "matcher": (sum(1 for m in matches if m.stage == "scored"), sum(1 for m in matches if m.stage != "filtered_out"),
                    "pairs scored"),
        "explainer": (sum(1 for a in accepted if a.memo), len(accepted), "memos for accepted alerts"),
        "writer": (len(accepted_clients & drafted_clients), len(accepted_clients), "clients with an email draft"),
    }
    out = []
    for st in STAGES:
        k = st["key"]
        done, total, unit = progress[k]
        stats = {"runs": 0, "cost_usd": 0.0, "avg_duration_ms": 0, "running": 0, "failed": 0, "model": "",
                 "current": ""}
        if st["llm"]:
            runs = session.exec(select(AgentRun).where(AgentRun.agent == k).order_by(AgentRun.id.desc())).all()
            finished = [r for r in runs if r.status == "done"]
            running = [r for r in runs if r.status == "running"]
            stats.update(runs=len(runs), cost_usd=round(sum(r.cost_usd for r in runs), 4),
                         avg_duration_ms=int(sum(r.duration_ms for r in finished) / len(finished)) if finished else 0,
                         running=len(running), failed=_unresolved_failures(runs),
                         model=runs[0].model if runs else "",
                         current=subject_label(session, running[0].subject) if running else "")
        out.append({**st, "done": done, "total": total, "unit": unit, **stats})
    log = session.exec(select(AgentRun).order_by(AgentRun.id.desc()).limit(6)).all()
    return {"stages": out, "chain": dict(_chain), "pending": _pending(session),
            "waiting_for_review": sum(1 for a in alerts if a.status == "new"),
            "log": [{"id": r.id, "agent": r.agent, "status": r.status, "label": subject_label(session, r.subject),
                     "duration_ms": r.duration_ms, "cost_usd": r.cost_usd, "started_at": r.started_at,
                     "finished_at": r.finished_at} for r in log],
            "pairs": {"total": len(clients) * len(ready),
                      "filtered_out": sum(1 for m in matches if m.stage == "filtered_out")}}


def _run_chain(pipeline_id: str, runner: Runner) -> None:
    """Profiler -> Analyst -> Pre-filter + Matcher, one after the other, on whatever is not done yet."""
    def new_run(agent: str, subject: str, model: str) -> int:
        with Session(engine) as s:
            run = AgentRun(pipeline_id=pipeline_id, agent=agent, subject=subject, model=model.split("/", 1)[-1])
            s.add(run)
            s.commit()
            return run.id

    try:
        _chain["step"] = "profiler"
        with Session(engine) as s:
            with_docs = {d.client_id for d in s.exec(select(Document)).all()}
            profiled = {p.client_id for p in s.exec(select(ClientProfile)).all()}
            todo = [c.id for c in s.exec(select(Client).order_by(Client.id)).all()
                    if c.id in with_docs and c.id not in profiled]
        for cid in todo:
            run_profiler(engine, new_run("profiler", f"client:{cid}", settings.model_reasoning), cid, runner)

        _chain["step"] = "analyst"
        with Session(engine) as s:
            todo = [u.id for u in s.exec(select(RegulatoryUpdate).order_by(RegulatoryUpdate.id)).all() if not u.summary]
        for uid in todo:
            run_analyst(engine, new_run("analyst", f"update:{uid}", settings.model_fast), uid, runner)

        _chain["step"] = "matcher"
        with Session(engine) as s:
            has_profiles = bool(latest_profiles(s))
            scanned = {m.update_id for m in s.exec(select(Match)).all()}
            todo = [u.id for u in _ready_updates(s) if u.id not in scanned]
        if has_profiles:
            for uid in todo:
                run_matcher(engine, new_run("matcher", f"update:{uid}", settings.model_reasoning), uid, runner)
        _chain["error"] = ""
    except Exception as exc:  # the agents log their own failures; this catches anything around them
        _chain["error"] = str(exc)
    finally:
        _chain.update(running=False, step="", finished_at=now())


def claim_chain(session: Session) -> str:
    """Reserve the chain for one run: returns a pipeline id, or "busy" / "nothing"."""
    with _lock:
        if _chain["running"] or _running_any(session):
            return "busy"
        if _pending(session)["total"] == 0:
            return "nothing"
        pid = uuid.uuid4().hex
        _chain.update(running=True, step="profiler", pipeline_id=pid, error="", started_at=now(), finished_at=None)
        return pid


def run_chain_now(runner: Runner) -> str:
    """Run the chain synchronously (used by the weekly check). Returns "done", "busy" or "nothing"."""
    with Session(engine) as session:
        claim = claim_chain(session)
    if claim in ("busy", "nothing"):
        return claim
    _run_chain(claim, runner)
    return "done"


@router.post("/pipeline/run", status_code=202)
def run_chain(background: BackgroundTasks, session: Session = Depends(get_session),
              runner: Runner = Depends(get_runner)):
    """Run every automatic stage of the chain on what is not done yet. Stops before the advisor's review."""
    if getattr(runner, "requires_api_key", True) and not settings.llm_configured:
        raise HTTPException(400, "No Anthropic API key. Add ANTHROPIC_API_KEY to the .env file and restart the backend.")
    claim = claim_chain(session)
    if claim == "busy":
        raise HTTPException(409, "Agents are already working. Wait until they finish.")
    if claim == "nothing":
        return {"pipeline_id": "", "nothing_to_do": True}
    pid = claim
    background.add_task(_run_chain, pid, runner)
    return {"pipeline_id": pid}
