import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..agents.matcher import latest_profiles, run_scan
from ..agents.explainer import run_explainer
from ..agents.profiler import run_profiler
from ..agents.runner import Runner, get_runner
from ..config import settings
from ..db import engine, get_session
from ..evaluation import evaluate
from ..models import AgentRun, Alert, Client, ClientProfile, Document, Match, RegulatoryUpdate, now

router = APIRouter(tags=["alerts"])


def _require_key(runner: Runner) -> None:
    if getattr(runner, "requires_api_key", True) and not settings.llm_configured:
        raise HTTPException(400, "No Anthropic API key. Add ANTHROPIC_API_KEY to the .env file and restart the backend.")


def _running(session: Session, agent: str) -> list[AgentRun]:
    return session.exec(select(AgentRun).where(AgentRun.agent == agent, AgentRun.status == "running")).all()


def _ready_updates(session: Session) -> list[RegulatoryUpdate]:
    return [u for u in session.exec(select(RegulatoryUpdate).order_by(RegulatoryUpdate.id)).all()
            if u.summary and u.summary.get("relevant_for_companies")]


@router.get("/scan/status")
def scan_status(session: Session = Depends(get_session)):
    """What a scan would do right now."""
    ready = _ready_updates(session)
    scanned = {m.update_id for m in session.exec(select(Match)).all()}
    profiled = {c.id for c, _ in latest_profiles(session)}
    clients = session.exec(select(Client)).all()
    with_docs = {d.client_id for d in session.exec(select(Document)).all()}
    return {
        "updates_ready": len(ready),
        "updates_unscanned": sum(1 for u in ready if u.id not in scanned),
        "updates_not_analysed": sum(1 for u in session.exec(select(RegulatoryUpdate)).all() if not u.summary),
        "clients_total": len(clients),
        "clients_without_profile": sum(1 for c in clients if c.id not in profiled and c.id in with_docs),
        "scan_running": len(_running(session, "matcher")),
        "profiles_running": len(_running(session, "profiler")),
    }


class ScanRequest(BaseModel):
    rescan_all: bool = False


@router.post("/scan", status_code=202)
def scan(body: ScanRequest, background: BackgroundTasks, session: Session = Depends(get_session),
         runner: Runner = Depends(get_runner)):
    """Match analysed updates against all client profiles (only new updates unless rescan_all)."""
    _require_key(runner)
    if not latest_profiles(session):
        raise HTTPException(400, "Build at least one client profile before scanning.")
    if _running(session, "matcher"):
        raise HTTPException(409, "A scan is already running.")
    scanned = {m.update_id for m in session.exec(select(Match)).all()}
    todo = [u for u in _ready_updates(session) if body.rescan_all or u.id not in scanned]
    pipeline = uuid.uuid4().hex
    jobs = []
    for u in todo:
        run = AgentRun(pipeline_id=pipeline, agent="matcher", subject=f"update:{u.id}",
                       model=settings.model_reasoning.split("/", 1)[-1])
        session.add(run)
        session.commit()
        jobs.append((run.id, u.id))
    if jobs:
        background.add_task(run_scan, engine, jobs, runner)
    return {"queued": len(jobs)}


@router.post("/clients/build-missing-profiles", status_code=202)
def build_missing_profiles(background: BackgroundTasks, session: Session = Depends(get_session),
                           runner: Runner = Depends(get_runner)):
    _require_key(runner)
    profiled = {p.client_id for p in session.exec(select(ClientProfile)).all()}
    with_docs = {d.client_id for d in session.exec(select(Document)).all()}
    busy = {r.subject for r in _running(session, "profiler")}
    clients = [c for c in session.exec(select(Client).order_by(Client.id)).all()
               if c.id not in profiled and c.id in with_docs and f"client:{c.id}" not in busy]
    pipeline, jobs = uuid.uuid4().hex, []
    for c in clients:
        run = AgentRun(pipeline_id=pipeline, agent="profiler", subject=f"client:{c.id}",
                       model=settings.model_reasoning.split("/", 1)[-1])
        session.add(run)
        session.commit()
        jobs.append((run.id, c.id))

    def run_all():
        for run_id, client_id in jobs:
            run_profiler(engine, run_id, client_id, runner)

    if jobs:
        background.add_task(run_all)
    return {"queued": len(jobs)}


def _memo_status(session: Session, a: Alert) -> tuple[str, str]:
    run = session.exec(select(AgentRun).where(AgentRun.agent == "explainer", AgentRun.subject == f"alert:{a.id}")
                       .order_by(AgentRun.id.desc())).first()
    if run and run.status == "running":
        return "running", ""
    if a.memo:
        return "done", ""
    if run and run.status == "failed":
        return "failed", run.error
    return "none", ""


def _alert_view(session: Session, a: Alert) -> dict:
    m = session.get(Match, a.match_id)
    c = session.get(Client, m.client_id)
    u = session.get(RegulatoryUpdate, m.update_id)
    s = u.summary or {}
    return {
        "id": a.id, "status": a.status, "dismiss_reason": a.dismiss_reason, "created_at": a.created_at,
        "score": m.score, "verdict": m.verdict, "reasoning": m.reasoning, "evidence": m.evidence,
        "missing_information": m.missing_information or [],
        "client": {"id": c.id, "name": c.name, "is_demo": c.is_demo},
        "update": {"id": u.id, "title": s.get("title_en", u.title), "original_title": u.title, "kind": s.get("kind", u.kind),
                   "published_on": u.published_on, "tax_categories": s.get("tax_categories", []),
                   "source": u.source},
        "memo": a.memo,
        "memo_status": _memo_status(session, a)[0],
        "memo_error": _memo_status(session, a)[1],
    }


@router.get("/alerts")
def list_alerts(status: str | None = None, session: Session = Depends(get_session)):
    q = select(Alert)
    if status:
        q = q.where(Alert.status == status)
    views = [_alert_view(session, a) for a in session.exec(q).all()]
    return sorted(views, key=lambda v: (-(v["score"] or 0), v["client"]["name"]))


class Decision(BaseModel):
    status: str = Field(pattern="^(new|accepted|dismissed)$")
    reason: str = Field(default="", max_length=500)


def _queue_memo(session: Session, a: Alert, background: BackgroundTasks, runner: Runner) -> bool:
    """Start the Impact Explainer for this alert unless it is already running or no key is set."""
    if getattr(runner, "requires_api_key", True) and not settings.llm_configured:
        return False
    if _memo_status(session, a)[0] == "running":
        return False
    run = AgentRun(pipeline_id=uuid.uuid4().hex, agent="explainer", subject=f"alert:{a.id}",
                   model=settings.model_reasoning.split("/", 1)[-1])
    session.add(run)
    session.commit()
    background.add_task(run_explainer, engine, run.id, a.id, runner)
    return True


@router.post("/alerts/{alert_id}/status")
def set_status(alert_id: int, body: Decision, background: BackgroundTasks, session: Session = Depends(get_session),
               runner: Runner = Depends(get_runner)):
    """Accepting an alert starts the Impact Explainer automatically."""
    a = session.get(Alert, alert_id)
    if not a:
        raise HTTPException(404, "Alert not found")
    if body.status == "dismissed" and not body.reason.strip():
        raise HTTPException(400, "Say briefly why you dismiss this alert. It helps improve the Matcher.")
    a.status, a.dismiss_reason, a.updated_at = body.status, body.reason.strip(), now()
    session.add(a)
    session.commit()
    if a.status == "accepted" and not a.memo:
        _queue_memo(session, a, background, runner)
    return _alert_view(session, a)


@router.post("/alerts/{alert_id}/memo", status_code=202)
def write_memo(alert_id: int, background: BackgroundTasks, session: Session = Depends(get_session),
               runner: Runner = Depends(get_runner)):
    """(Re)write the impact memo of an accepted alert."""
    _require_key(runner)
    a = session.get(Alert, alert_id)
    if not a:
        raise HTTPException(404, "Alert not found")
    if a.status != "accepted":
        raise HTTPException(400, "Accept the alert before writing its memo.")
    _queue_memo(session, a, background, runner)
    return _alert_view(session, a)


@router.get("/matches")
def matrix(session: Session = Depends(get_session)):
    """All scores, for the relevance matrix: clients x updates."""
    out = []
    for m in session.exec(select(Match)).all():
        out.append({"client_id": m.client_id, "update_id": m.update_id, "score": m.score,
                    "stage": m.stage, "verdict": m.verdict, "reasoning": m.reasoning})
    return out


@router.get("/evaluation")
def evaluation(session: Session = Depends(get_session)):
    return evaluate(session)
