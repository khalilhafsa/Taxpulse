from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..agents.runner import Runner, get_runner
from ..config import settings
from ..db import engine, get_session
from ..models import AgentRun, EvalBatch
from ..quality import report, run_stability, stability_inputs

router = APIRouter(prefix="/quality", tags=["quality"])


@router.get("")
def quality(session: Session = Depends(get_session)):
    return report(session)


class StabilityRequest(BaseModel):
    runs: int = Field(default=5, ge=2, le=10)


@router.post("/stability", status_code=202)
def start_stability(body: StabilityRequest, background: BackgroundTasks, session: Session = Depends(get_session),
                    runner: Runner = Depends(get_runner)):
    """Score the labelled demo pairs `runs` times with the real Matcher and measure how stable it is."""
    if getattr(runner, "requires_api_key", True) and not settings.llm_configured:
        raise HTTPException(400, "No Anthropic API key. Add ANTHROPIC_API_KEY to the .env file and restart the backend.")
    if session.exec(select(AgentRun).where(AgentRun.status == "running")).first():
        raise HTTPException(409, "Agents are working. Start the test when they have finished.")
    inputs, why = stability_inputs(session)
    if not inputs:
        raise HTTPException(400, why)
    batch = EvalBatch(runs_planned=body.runs)
    session.add(batch)
    session.commit()
    background.add_task(run_stability, engine, batch.id, runner)
    return {"batch_id": batch.id}
