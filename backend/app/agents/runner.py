"""How agents are executed.

`run_agent` is the single entry point for every LLM call. It runs a one-task CrewAI
crew with Claude and returns the validated Pydantic output plus token usage.
Tests swap it for a fake via the `get_runner` dependency, so no API calls are made.
"""
import json
import os
import re
import time
from dataclasses import dataclass
from typing import Callable, Type, TypeVar

from pydantic import BaseModel

from ..config import settings

T = TypeVar("T", bound=BaseModel)

# Client data stays local: switch off CrewAI's anonymous usage telemetry.
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")


@dataclass
class AgentSpec:
    role: str
    goal: str
    backstory: str


@dataclass
class AgentResult:
    output: BaseModel
    model: str
    tokens_in: int
    tokens_out: int
    duration_ms: int
    attempts: int = 1  # 2 or more when a temporary API error was retried


Runner = Callable[..., AgentResult]


def _parse(raw: str, schema: Type[T]) -> T:
    """Fallback when CrewAI could not convert the answer itself: take the JSON object from the text."""
    match = re.search(r"\{.*\}", raw, re.S)
    if not match:
        raise ValueError("The agent did not return JSON.")
    return schema.model_validate(json.loads(match.group(0)))


def crewai_runner(*, spec: AgentSpec, task: str, expected_output: str, schema: Type[T], model: str) -> AgentResult:
    from crewai import LLM, Agent, Crew, Process, Task

    if not settings.llm_configured:
        raise RuntimeError("No Anthropic API key. Add ANTHROPIC_API_KEY to the .env file and restart the backend.")

    # No `temperature`: current Claude models reject it and choose sampling themselves.
    llm = LLM(model=model, api_key=settings.anthropic_api_key, max_tokens=16000)
    agent = Agent(role=spec.role, goal=spec.goal, backstory=spec.backstory, llm=llm,
                  allow_delegation=False, verbose=False, max_iter=3)
    crew_task = Task(description=task, expected_output=expected_output, agent=agent, output_pydantic=schema)
    crew = Crew(agents=[agent], tasks=[crew_task], process=Process.sequential, verbose=False)

    start = time.perf_counter()
    result = crew.kickoff()
    duration = int((time.perf_counter() - start) * 1000)

    output = result.pydantic if result.pydantic is not None else _parse(result.raw, schema)
    usage = result.token_usage
    return AgentResult(output=output, model=model.split("/", 1)[-1],
                       tokens_in=usage.prompt_tokens or 0, tokens_out=usage.completion_tokens or 0,
                       duration_ms=duration)


def friendly_error(exc: Exception) -> str:
    """Turn common API failures into a message the advisor can act on."""
    text = str(exc)
    if "401" in text or "authentication_error" in text or "invalid x-api-key" in text:
        return ("Anthropic rejected the API key (401). Create a new key at platform.claude.com/settings/keys, "
                "paste it once after ANTHROPIC_API_KEY= in .env, then restart TaxPulse.")
    if "credit balance" in text.lower() or "billing" in text.lower():
        return "Your Anthropic credit balance is too low. Add credits at platform.claude.com/settings/billing."
    if isinstance(exc, BudgetExceeded):
        return text
    if "429" in text or "rate_limit" in text:
        return "Anthropic rate limit reached. Wait a minute and try again."
    if "529" in text or "overloaded" in text.lower():
        return "Claude is temporarily overloaded. Try again in a few minutes."
    return text[:1000]


class BudgetExceeded(RuntimeError):
    """The monthly AI budget set in Settings is used up; agents stop before calling Claude."""


# Temporary failures worth another try: rate limit, overload, server or network hiccups.
_TRANSIENT = re.compile(r"\b(429|500|502|503|504|529)\b|rate.?limit|overloaded|timed? ?out|timeout|"
                        r"connection (error|reset|aborted)|apiconnectionerror|temporarily unavailable", re.I)
_PERMANENT = re.compile(r"\b401\b|authentication_error|invalid x-api-key|credit balance|billing", re.I)
RETRY_DELAYS = (3.0, 10.0)  # seconds before the 2nd and 3rd attempt
_sleep = time.sleep  # replaced in tests


def is_transient(exc: Exception) -> bool:
    text = f"{type(exc).__name__}: {exc}"
    return not _PERMANENT.search(text) and bool(_TRANSIENT.search(text))


def with_retries(runner: Runner) -> Runner:
    """Retry temporary API errors twice, waiting a little longer each time."""
    def run(**kwargs) -> AgentResult:
        for attempt in range(1, len(RETRY_DELAYS) + 2):
            try:
                result = runner(**kwargs)
                result.attempts = attempt
                return result
            except Exception as exc:
                if attempt > len(RETRY_DELAYS) or not is_transient(exc):
                    raise
                _sleep(RETRY_DELAYS[attempt - 1])
        raise AssertionError("unreachable")
    run.requires_api_key = getattr(runner, "requires_api_key", True)
    return run


def spent_this_month() -> float:
    from sqlmodel import Session, func, select
    from ..db import engine
    from ..models import AgentRun, now
    start = now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    with Session(engine) as session:
        return float(session.exec(select(func.coalesce(func.sum(AgentRun.cost_usd), 0))
                                  .where(AgentRun.started_at >= start)).one())


def monthly_budget() -> float:
    from sqlmodel import Session
    from ..db import engine
    from ..models import FirmSettings
    with Session(engine) as session:
        firm = session.get(FirmSettings, 1)
        return float(firm.monthly_budget_usd) if firm else 0.0


def check_budget() -> None:
    budget = monthly_budget()
    if budget > 0:
        spent = spent_this_month()
        if spent >= budget:
            raise BudgetExceeded(f"The monthly AI budget of ${budget:.2f} is used up (${spent:.2f} spent this month). "
                                 "Raise it in Settings, or wait until next month.")


def with_budget(runner: Runner) -> Runner:
    def run(**kwargs) -> AgentResult:
        check_budget()
        return runner(**kwargs)
    run.requires_api_key = getattr(runner, "requires_api_key", True)
    return run


production_runner = with_budget(with_retries(crewai_runner))


def get_runner() -> Runner:
    """FastAPI dependency: the budget check, then Claude with retries. Overridden in tests.
    In the public demo the agents replay recorded results instead."""
    if settings.demo_mode:
        from ..replay import replay_runner
        return replay_runner
    return production_runner


def cost_usd(model: str, tokens_in: int, tokens_out: int) -> float:
    price_in, price_out = settings.prices_per_mtok.get(model, (0.0, 0.0))
    return round((tokens_in * price_in + tokens_out * price_out) / 1_000_000, 5)
