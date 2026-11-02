from datetime import datetime

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, func, select

from ..agents.runner import Runner, get_runner
from ..automation import DAYS, get_automation, is_running, next_slot, run_weekly_check
from ..config import settings
from ..db import get_session
from ..models import Notification
from ..sources.bmf import http_client

router = APIRouter(tags=["automation"])


def _view(session: Session) -> dict:
    a = get_automation(session)
    nxt = next_slot(a, datetime.now().astimezone()) if a.enabled else None
    return {**a.model_dump(), "running": is_running(), "days": DAYS, "bmf_feed_url": settings.bmf_feed_url,
            "next_run_at": nxt.isoformat() if nxt else None}


@router.get("/automation")
def get_settings(session: Session = Depends(get_session)):
    return _view(session)


class AutomationIn(BaseModel):
    enabled: bool
    weekday: int = Field(ge=0, le=6)
    hour: int = Field(ge=0, le=23)
    fetch_bmf: bool = True
    fetch_bfh: bool = True


@router.put("/automation")
def save_settings(body: AutomationIn, session: Session = Depends(get_session)):
    a = get_automation(session)
    was_enabled = a.enabled
    for k, v in body.model_dump().items():
        setattr(a, k, v)
    if body.enabled and not was_enabled:
        # Start counting from now: switching it on should not fire for a slot that passed earlier this week.
        from ..models import now
        a.last_run_at = a.last_run_at or now()
    session.add(a)
    session.commit()
    return _view(session)


@router.post("/automation/run", status_code=202)
def run_now(background: BackgroundTasks, runner: Runner = Depends(get_runner),
            client: httpx.Client = Depends(http_client)):
    """Run the weekly check now, whatever the schedule."""
    if is_running():
        raise HTTPException(409, "The weekly check is already running.")
    background.add_task(run_weekly_check, runner, lambda: client, "manual")
    return {"started": True}


@router.get("/notifications")
def notifications(session: Session = Depends(get_session)):
    items = session.exec(select(Notification).order_by(Notification.id.desc()).limit(30)).all()
    unread = session.exec(select(func.count()).select_from(Notification).where(Notification.read == False)).one()  # noqa: E712
    return {"items": [n.model_dump() for n in items], "unread": unread}


@router.post("/notifications/read-all")
def read_all(session: Session = Depends(get_session)):
    for n in session.exec(select(Notification).where(Notification.read == False)).all():  # noqa: E712
        n.read = True
        session.add(n)
    session.commit()
    return {"ok": True}


@router.post("/notifications/{notification_id}/read")
def read_one(notification_id: int, session: Session = Depends(get_session)):
    n = session.get(Notification, notification_id)
    if not n:
        raise HTTPException(404, "Notification not found")
    n.read = True
    session.add(n)
    session.commit()
    return n.model_dump()
