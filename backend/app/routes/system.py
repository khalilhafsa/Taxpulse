from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlmodel import Session, func, select

from ..config import settings
from ..db import get_session
from ..models import Alert, Client, Document, EmailDraft, FirmSettings, RegulatoryUpdate
from ..seed import seed_demo

router = APIRouter(tags=["system"])


@router.get("/health")
def health():
    if settings.demo_mode:
        return {"status": "ok", "llm_configured": True, "key_problem": "", "demo_mode": True,
                "models": {"reasoning": settings.model_reasoning, "fast": settings.model_fast}}
    return {"status": "ok", "llm_configured": settings.llm_configured, "key_problem": settings.key_problem, "demo_mode": False,
            "models": {"reasoning": settings.model_reasoning, "fast": settings.model_fast}}


@router.get("/stats")
def stats(session: Session = Depends(get_session)):
    def count(model, *where):
        q = select(func.count()).select_from(model)
        for w in where:
            q = q.where(w)
        return session.exec(q).one()

    return {
        "clients": count(Client),
        "documents": count(Document),
        "updates": count(RegulatoryUpdate),
        "alerts_open": count(Alert, Alert.status == "new"),
        "drafts_open": count(EmailDraft, EmailDraft.status == "draft"),
    }


@router.post("/demo/seed")
def load_demo(session: Session = Depends(get_session)):
    """Load the fictional demo clients and updates (idempotent)."""
    return {"added": seed_demo(session)}


class FirmIn(BaseModel):
    firm_name: str = Field(default="", max_length=200)
    advisor_name: str = Field(default="", max_length=200)
    advisor_title: str = Field(default="", max_length=200)
    phone: str = Field(default="", max_length=80)
    email: str = Field(default="", max_length=200)
    address: str = Field(default="", max_length=300)
    website: str = Field(default="", max_length=200)
    monthly_budget_usd: float = Field(default=0.0, ge=0, le=10_000)


@router.get("/settings/firm")
def get_firm(session: Session = Depends(get_session)):
    from ..agents.runner import spent_this_month
    return {**(session.get(FirmSettings, 1) or FirmSettings(id=1)).model_dump(),
            "spent_this_month_usd": round(spent_this_month(), 4)}


@router.put("/settings/firm")
def save_firm(body: FirmIn, session: Session = Depends(get_session)):
    firm = session.get(FirmSettings, 1) or FirmSettings(id=1)
    for k, v in body.model_dump().items():
        setattr(firm, k, v.strip() if isinstance(v, str) else v)
    session.add(firm)
    session.commit()
    session.refresh(firm)
    return get_firm(session)
