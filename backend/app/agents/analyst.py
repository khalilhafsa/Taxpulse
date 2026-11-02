"""Agent 2 – Regulatory Analyst.

Reads a new BMF letter, BFH ruling or tax news item (often in German) and turns it
into checkable criteria: which tax areas, which companies, which facts trigger it,
and which cases are explicitly excluded. The Impact Matcher (step 5) uses this.
"""
from sqlmodel import Session

from ..config import settings
from ..models import AgentRun, RegulatoryUpdate, now
from .runner import AgentSpec, Runner, cost_usd, friendly_error
from .schemas import UpdateAnalysis

SPEC = AgentSpec(
    role="Regulatory Update Analyst",
    goal="Read new German tax publications and state precisely which companies they affect and why",
    backstory=(
        "You are a German tax law researcher who reads every BMF letter, BFH ruling and tax law change "
        "for a tax advisory firm. You translate them into short, precise criteria that a colleague can "
        "check against a client file in seconds. You are careful to note who is NOT affected."
    ),
)

RULES = """Rules:
- Use only what the publication says. Do not add requirements, thresholds or dates that are not in the text.
- Write in English, even if the source is German. Keep German legal references as written (e.g. § 14 UStG).
- Trigger criteria must be concrete facts about a company (size, activity, transaction type, structure), not vague topics.
- Write each trigger criterion so it stands on its own. Use criteria_logic 'all' only when the publication requires the conditions together; otherwise 'any'.
- If the publication does not change anything for businesses, set relevant_for_companies to false and keep the lists short.
- Routine administrative publications (new form templates such as 'Vordruckmuster', statistics, editorial corrections) are not relevant_for_companies unless they change a tax obligation in substance."""


def run_analyst(engine, run_id: int, update_id: int, runner: Runner) -> None:
    """Background job. Stores the analysis on the update; errors are stored on the run."""
    with Session(engine) as session:
        run = session.get(AgentRun, run_id)
        try:
            u = session.get(RegulatoryUpdate, update_id)
            result = runner(
                spec=SPEC,
                task=(f"Analyse this German tax publication.\n\n{RULES}\n\n"
                      f"Title: {u.title}\nPublished: {u.published_on or 'unknown'}\nSource: {u.url or u.source}\n\n"
                      f"--- TEXT ---\n{u.raw_text}"),
                expected_output="A structured analysis of who is affected and why.",
                schema=UpdateAnalysis,
                model=settings.model_fast,
            )
            u.summary = result.output.model_dump()
            session.add(u)
            run.status = "done"
            run.model = result.model
            run.tokens_in, run.tokens_out = result.tokens_in, result.tokens_out
            run.cost_usd = cost_usd(result.model, result.tokens_in, result.tokens_out)
            run.duration_ms = result.duration_ms
            run.attempts = result.attempts
        except Exception as exc:
            session.rollback()
            run = session.get(AgentRun, run_id)
            run.status = "failed"
            run.error = friendly_error(exc)
        run.finished_at = now()
        session.add(run)
        session.commit()


def run_analyst_batch(engine, jobs: list[tuple[int, int]], runner: Runner) -> None:
    """Analyse several updates one after another: jobs = [(run_id, update_id), ...]."""
    for run_id, update_id in jobs:
        run_analyst(engine, run_id, update_id, runner)
