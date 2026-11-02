"""Outreach: email drafts per client. TaxPulse never sends emails; the advisor does."""
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..agents.runner import Runner, get_runner
from ..agents.writer import accepted_without_memo, alerts_for_email, review_email, run_writer
from ..config import settings
from ..db import engine, get_session
from ..models import AgentRun, Alert, Client, EmailDraft, Match, RegulatoryUpdate, now

router = APIRouter(tags=["outreach"])


def _writer_running(session: Session, client_id: int) -> AgentRun | None:
    return session.exec(select(AgentRun).where(AgentRun.agent == "writer", AgentRun.subject == f"client:{client_id}",
                                               AgentRun.status == "running")).first()


def _last_writer_error(session: Session, client_id: int) -> str:
    run = session.exec(select(AgentRun).where(AgentRun.agent == "writer", AgentRun.subject == f"client:{client_id}")
                       .order_by(AgentRun.id.desc())).first()
    return run.error if run and run.status == "failed" else ""


def _draft_view(d: EmailDraft) -> dict:
    view = d.model_dump()
    if d.status != "sent":  # checks are re-run so drafts benefit from improvements to the partner review
        view["review_notes"] = "\n".join(review_email(d.body))
    return view


@router.get("/outreach")
def outreach(session: Session = Depends(get_session)):
    """Clients with accepted alerts, their memos and their email drafts."""
    by_client: dict[int, dict] = {}
    for a in session.exec(select(Alert).where(Alert.status == "accepted").order_by(Alert.id)).all():
        m = session.get(Match, a.match_id)
        c = session.get(Client, m.client_id)
        u = session.get(RegulatoryUpdate, m.update_id)
        entry = by_client.setdefault(c.id, {"client": {"id": c.id, "name": c.name, "mandate": c.mandate,
                                                       "contact_name": c.contact_name, "contact_title": c.contact_title,
                                                       "salutation": c.salutation},
                                            "alerts": [], "drafts": []})
        entry["alerts"].append({"id": a.id, "score": m.score, "title": (u.summary or {}).get("title_en", u.title),
                                "has_memo": bool(a.memo),
                                "headline": (a.memo or {}).get("headline"),
                                "urgency": (a.memo or {}).get("urgency")})
    for cid, entry in by_client.items():
        drafts = session.exec(select(EmailDraft).where(EmailDraft.client_id == cid)
                              .order_by(EmailDraft.id.desc())).all()
        entry["drafts"] = [_draft_view(d) for d in drafts]
        entry["writer_running"] = _writer_running(session, cid) is not None
        entry["writer_error"] = _last_writer_error(session, cid)
        covered = {i for d in drafts for i in d.alert_ids}
        entry["alerts_not_in_draft"] = sum(1 for a in entry["alerts"] if a["has_memo"] and a["id"] not in covered)
    return sorted(by_client.values(), key=lambda e: -max(a["score"] or 0 for a in e["alerts"]))


def _require_all_memos(session: Session, client_id: int) -> None:
    """An email must cover every accepted alert: refuse while a memo is missing, so no paid draft has to be redone."""
    waiting = accepted_without_memo(session, client_id)
    if waiting:
        titles = []
        for a in waiting:
            u = session.get(RegulatoryUpdate, session.get(Match, a.match_id).update_id)
            titles.append((u.summary or {}).get("title_en", u.title))
        raise HTTPException(409, f"Wait until every accepted alert has its memo, so the email covers all of them. "
                                 f"Missing: {'; '.join(titles)}. If a memo failed, use Write memo on the Alerts page.")


@router.post("/clients/{client_id}/draft-email", status_code=202)
def draft_email(client_id: int, background: BackgroundTasks, session: Session = Depends(get_session),
                runner: Runner = Depends(get_runner)):
    """Let the Outreach Writer draft one email covering all accepted alerts with a memo."""
    if getattr(runner, "requires_api_key", True) and not settings.llm_configured:
        raise HTTPException(400, "No Anthropic API key. Add ANTHROPIC_API_KEY to the .env file and restart the backend.")
    if not session.get(Client, client_id):
        raise HTTPException(404, "Client not found")
    _require_all_memos(session, client_id)
    alerts = alerts_for_email(session, client_id)
    if not alerts:
        raise HTTPException(400, "Accept at least one alert for this client and wait for its memo first.")
    if _writer_running(session, client_id):
        raise HTTPException(409, "An email for this client is already being written.")
    run = AgentRun(pipeline_id=uuid.uuid4().hex, agent="writer", subject=f"client:{client_id}",
                   model=settings.model_reasoning.split("/", 1)[-1])
    session.add(run)
    session.commit()
    background.add_task(run_writer, engine, run.id, client_id, [a.id for a in alerts], runner)
    return {"run_id": run.id, "alerts": len(alerts)}


class DraftRemarks(BaseModel):
    remarks: str = Field(min_length=3, max_length=2000)


@router.post("/drafts/{draft_id}/revise", status_code=202)
def revise_draft(draft_id: int, body: DraftRemarks, background: BackgroundTasks,
                 session: Session = Depends(get_session), runner: Runner = Depends(get_runner)):
    """Let the Outreach Writer rewrite a draft following the advisor's remarks; the result is a new version."""
    if getattr(runner, "requires_api_key", True) and not settings.llm_configured:
        raise HTTPException(400, "No Anthropic API key. Add ANTHROPIC_API_KEY to the .env file and restart the backend.")
    d = session.get(EmailDraft, draft_id)
    if not d:
        raise HTTPException(404, "Draft not found")
    if _writer_running(session, d.client_id):
        raise HTTPException(409, "An email for this client is already being written.")
    _require_all_memos(session, d.client_id)
    # The new version covers every alert accepted now, including any accepted since the draft was written.
    alert_ids = [a.id for a in alerts_for_email(session, d.client_id)] or d.alert_ids
    run = AgentRun(pipeline_id=uuid.uuid4().hex, agent="writer", subject=f"client:{d.client_id}",
                   model=settings.model_reasoning.split("/", 1)[-1])
    session.add(run)
    session.commit()
    background.add_task(run_writer, engine, run.id, d.client_id, alert_ids, runner, d.id, body.remarks)
    return {"run_id": run.id}


class DraftEdit(BaseModel):
    subject: str = Field(min_length=3, max_length=200)
    body: str = Field(min_length=10, max_length=10_000)


class DraftStatus(BaseModel):
    status: str = Field(pattern="^(draft|approved|sent)$")


def _get(session: Session, draft_id: int) -> EmailDraft:
    d = session.get(EmailDraft, draft_id)
    if not d:
        raise HTTPException(404, "Draft not found")
    return d


@router.put("/drafts/{draft_id}")
def edit_draft(draft_id: int, body: DraftEdit, session: Session = Depends(get_session)):
    d = _get(session, draft_id)
    if d.status == "sent":
        raise HTTPException(400, "This email is marked as sent and can no longer be edited.")
    d.subject, d.body, d.edited_by_user, d.updated_at = body.subject.strip(), body.body.strip(), True, now()
    d.status = "draft"  # an edited email needs approving again
    d.review_notes = "\n".join(review_email(d.body))  # re-run the partner checks on the advisor's text
    session.add(d)
    session.commit()
    session.refresh(d)
    return _draft_view(d)


@router.post("/drafts/{draft_id}/status")
def set_draft_status(draft_id: int, body: DraftStatus, session: Session = Depends(get_session)):
    d = _get(session, draft_id)
    if body.status == "sent" and d.status != "approved":
        raise HTTPException(400, "Approve the email before marking it as sent.")
    d.status, d.updated_at = body.status, now()
    session.add(d)
    session.commit()
    session.refresh(d)
    return _draft_view(d)


@router.delete("/drafts/{draft_id}")
def delete_draft(draft_id: int, session: Session = Depends(get_session)):
    d = _get(session, draft_id)
    if d.status == "sent":
        raise HTTPException(400, "Sent emails are kept as a record.")
    session.delete(d)
    session.commit()
    return {"deleted": draft_id}
