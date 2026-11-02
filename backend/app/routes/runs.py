from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, func, select

from ..db import get_session
from ..models import AgentRun, Alert, Client, Match, RegulatoryUpdate

router = APIRouter(prefix="/runs", tags=["runs"])


def subject_label(session: Session, subject: str) -> str:
    kind, _, ident = subject.partition(":")
    if kind == "client" and ident.isdigit():
        client = session.get(Client, int(ident))
        return client.name if client else subject
    if kind == "alert" and ident.isdigit():
        alert = session.get(Alert, int(ident))
        if alert:
            m = session.get(Match, alert.match_id)
            c, u = session.get(Client, m.client_id), session.get(RegulatoryUpdate, m.update_id)
            return f"{c.name} · {(u.summary or {}).get('title_en', u.title)}"
        return subject
    if kind == "eval":
        return "Stability test (demo data)"
    if kind == "update" and ident.isdigit():
        update = session.get(RegulatoryUpdate, int(ident))
        return update.title if update else subject
    return subject


@router.get("")
def list_runs(limit: int = 50, session: Session = Depends(get_session)):
    runs = session.exec(select(AgentRun).order_by(AgentRun.id.desc()).limit(min(limit, 200))).all()
    totals = session.exec(select(func.count(), func.coalesce(func.sum(AgentRun.cost_usd), 0),
                                 func.coalesce(func.sum(AgentRun.tokens_in + AgentRun.tokens_out), 0))
                          .select_from(AgentRun)).one()
    return {
        "runs": [{**r.model_dump(), "subject_label": subject_label(session, r.subject)} for r in runs],
        "totals": {"runs": totals[0], "cost_usd": round(totals[1], 4), "tokens": totals[2]},
    }


@router.get("/{run_id}")
def get_run(run_id: int, session: Session = Depends(get_session)):
    run = session.get(AgentRun, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return {**run.model_dump(), "subject_label": subject_label(session, run.subject)}
