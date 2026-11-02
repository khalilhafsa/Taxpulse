import hashlib
import uuid
from datetime import date

import httpx
import json

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..agents.analyst import run_analyst_batch
from ..agents.runner import Runner, get_runner
from ..config import settings
from ..db import engine, get_session
from ..models import AgentRun, RegulatoryUpdate
from ..sources.bfh import ingest_bfh
from ..sources.bmf import FetchError, content_hash, http_client, import_feed_file, ingest_bmf_feed

router = APIRouter(prefix="/updates", tags=["updates"])


def latest_runs(session: Session) -> dict[int, AgentRun]:
    """Most recent analyst run per update id."""
    runs = session.exec(select(AgentRun).where(AgentRun.agent == "analyst").order_by(AgentRun.id)).all()
    return {int(r.subject.split(":")[1]): r for r in runs}


def status_of(u: RegulatoryUpdate, run: AgentRun | None) -> str:
    if run and run.status == "running":
        return "running"
    if u.summary:
        return "done"
    if run and run.status == "failed":
        return "failed"
    return "pending"


def serialize(u: RegulatoryUpdate, run: AgentRun | None, full: bool = False) -> dict:
    data = u.model_dump(exclude={"content_hash"} if full else {"content_hash", "raw_text"})
    data["analysis_status"] = status_of(u, run)
    data["analysis_error"] = run.error if run and run.status == "failed" else None
    return data


@router.get("")
def list_updates(session: Session = Depends(get_session)):
    rows = session.exec(select(RegulatoryUpdate)
                        .order_by(RegulatoryUpdate.published_on.desc(), RegulatoryUpdate.id.desc())).all()
    runs = latest_runs(session)
    return [serialize(u, runs.get(u.id)) for u in rows]


@router.get("/{update_id}")
def get_update(update_id: int, session: Session = Depends(get_session)):
    u = session.get(RegulatoryUpdate, update_id)
    if not u:
        raise HTTPException(404, "Update not found")
    return serialize(u, latest_runs(session).get(u.id), full=True)


class NewUpdate(BaseModel):
    title: str = Field(min_length=3, max_length=300)
    kind: str = Field(default="other", pattern="^(bmf_letter|bfh_ruling|law|press_release|other)$")
    published_on: date | None = None
    url: str | None = None
    text: str = Field(min_length=40, max_length=60_000)


@router.post("", status_code=201)
def add_update(body: NewUpdate, session: Session = Depends(get_session)):
    """Add a publication by hand (e.g. a ruling pasted from a newsletter)."""
    h = content_hash(body.text)
    if session.exec(select(RegulatoryUpdate).where(RegulatoryUpdate.content_hash == h)).first():
        raise HTTPException(409, "This text is already in TaxPulse.")
    u = RegulatoryUpdate(external_id="manual:" + hashlib.sha1(h.encode()).hexdigest()[:16], kind=body.kind,
                         title=body.title.strip(), published_on=body.published_on or date.today(),
                         source="manual", url=body.url, raw_text=body.text.strip(), content_hash=h)
    session.add(u)
    session.commit()
    session.refresh(u)
    return serialize(u, None)


@router.post("/fetch")
def fetch_bmf(session: Session = Depends(get_session), client: httpx.Client = Depends(http_client)):
    """Download new items from the BMF 'Steuern' RSS feed."""
    try:
        with client:
            return ingest_bmf_feed(session, client)
    except FetchError as exc:
        raise HTTPException(503, str(exc))


@router.post("/fetch-bfh")
def fetch_bfh(session: Session = Depends(get_session), client: httpx.Client = Depends(http_client)):
    """Download new decisions and press releases from the Federal Fiscal Court feeds."""
    try:
        with client:
            return ingest_bfh(session, client)
    except FetchError as exc:
        raise HTTPException(503, str(exc))


@router.post("/receive-feed")
async def receive_feed(request: Request, background: BackgroundTasks, runner: Runner = Depends(get_runner)):
    """Called by the "Send to TaxPulse" browser button on the BMF feed page, after the advisor passed the
    security check. Stores the new publications, then runs the agents and reports under the bell."""
    origin = request.headers.get("origin", "")
    allowed = set(settings.feed_sender_origins) | {settings.frontend_origin, "http://127.0.0.1:5173", "http://localhost:8000"}
    if origin and origin not in allowed:
        raise HTTPException(403, "Only the BMF website can send its feed to TaxPulse.")
    raw = await request.body()
    if len(raw) > 6 * 1024 * 1024:
        raise HTTPException(400, "This page is too large to be the BMF feed.")
    try:
        payload = json.loads(raw)
        xml = str(payload["xml"])
    except (ValueError, KeyError, TypeError):
        raise HTTPException(400, "TaxPulse expected the feed sent by the browser button.")
    try:
        with Session(engine) as session:
            result = import_feed_file(session, xml.encode("utf-8"))
    except FetchError as exc:
        # Keep what arrived (on this computer only) so the problem can be diagnosed.
        try:
            settings.upload_dir.mkdir(parents=True, exist_ok=True)
            (settings.upload_dir / "last-feed-received.txt").write_text(
                f"url: {payload.get('url', '')}\n\n{xml}", encoding="utf-8")
        except OSError:
            pass
        raise HTTPException(400, f"{exc} Open the BMF RSS feed (the link in the TaxPulse notification) and click again.")
    result["agents_started"] = False
    if result["new"] and not (getattr(runner, "requires_api_key", True) and not settings.llm_configured):
        from ..automation import run_weekly_check
        background.add_task(run_weekly_check, runner, http_client, "browser_button", result["new"])
        result["agents_started"] = True
    return result


@router.post("/import-feed")
async def import_feed(file: UploadFile = File(...), session: Session = Depends(get_session)):
    """Import a BMF RSS file saved from the browser (the live feed is behind a CAPTCHA)."""
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(400, "This file is too large to be an RSS feed.")
    try:
        return import_feed_file(session, content)
    except FetchError as exc:
        raise HTTPException(400, str(exc))


def _queue(session: Session, updates: list[RegulatoryUpdate], background: BackgroundTasks, runner: Runner):
    if getattr(runner, "requires_api_key", True) and not settings.llm_configured:
        raise HTTPException(400, "No Anthropic API key. Add ANTHROPIC_API_KEY to the .env file and restart the backend.")
    runs = latest_runs(session)
    jobs = []
    pipeline = uuid.uuid4().hex
    for u in updates:
        if runs.get(u.id) and runs[u.id].status == "running":
            continue
        run = AgentRun(pipeline_id=pipeline, agent="analyst", subject=f"update:{u.id}",
                       model=settings.model_fast.split("/", 1)[-1])
        session.add(run)
        session.commit()
        jobs.append((run.id, u.id))
    if jobs:
        background.add_task(run_analyst_batch, engine, jobs, runner)
    return {"queued": len(jobs)}


@router.post("/{update_id}/analyze", status_code=202)
def analyze_one(update_id: int, background: BackgroundTasks, session: Session = Depends(get_session),
                runner: Runner = Depends(get_runner)):
    u = session.get(RegulatoryUpdate, update_id)
    if not u:
        raise HTTPException(404, "Update not found")
    return _queue(session, [u], background, runner)


@router.post("/analyze-pending", status_code=202)
def analyze_pending(background: BackgroundTasks, session: Session = Depends(get_session),
                    runner: Runner = Depends(get_runner)):
    """Analyse every update that has no analysis yet."""
    # JSON columns store "no value" as JSON null, so filter in Python rather than with IS NULL.
    pending = [u for u in session.exec(select(RegulatoryUpdate).order_by(RegulatoryUpdate.id)).all() if not u.summary]
    return _queue(session, pending, background, runner)
