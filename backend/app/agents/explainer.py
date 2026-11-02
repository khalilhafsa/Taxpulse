"""Agent 4 – Impact Explainer.

When the advisor accepts an alert, this agent writes an impact memo: what the update
means for this specific client, how urgent it is, what to do, and which engagement
the firm could propose. It works only from the client profile, the update and the
Matcher's evidence.
"""
from sqlmodel import Session, select

from ..config import settings
from ..models import AgentRun, Alert, Client, ClientProfile, Match, RegulatoryUpdate, now
from .matcher import profile_text, update_text
from .runner import AgentSpec, Runner, cost_usd, friendly_error
from .schemas import ImpactMemo

SPEC = AgentSpec(
    role="Client Impact Explainer",
    goal="Explain in plain language what a tax development means for one specific client and what to do about it",
    backstory=(
        "You are a senior tax advisor known for turning complex German tax rules into clear business "
        "consequences. Partners read your memos in two minutes before calling a client."
    ),
)

RULES = """Rules:
- Use only facts from the client profile, the update and the Matcher's evidence. Never invent figures, dates or legal references.
- Plain language: a managing director without tax training must understand the impact.
- Name the client's own figures when they show the stakes (amounts, employees, systems).
- If something must be confirmed before advising, put it in questions_for_client instead of assuming it.
- Do not promise outcomes; describe risks and options.
- Write in English."""


def run_explainer(engine, run_id: int, alert_id: int, runner: Runner) -> None:
    with Session(engine) as session:
        run = session.get(AgentRun, run_id)
        try:
            alert = session.get(Alert, alert_id)
            m = session.get(Match, alert.match_id)
            client = session.get(Client, m.client_id)
            update = session.get(RegulatoryUpdate, m.update_id)
            profile = session.exec(select(ClientProfile).where(ClientProfile.client_id == client.id)
                                   .order_by(ClientProfile.version.desc())).first()
            evidence = "\n".join(
                f"- {'supports' if e['supports_impact'] else 'argues against'}: {e['client_fact']} (criterion: {e['criterion']})"
                for e in m.evidence) or "- none"
            result = runner(
                spec=SPEC,
                task=(f"Write an impact memo for {client.name} about this tax update.\n\n{RULES}\n\n"
                      f"--- MATCHER'S ASSESSMENT ---\nRelevance {m.score}/100. {m.reasoning}\nEvidence:\n{evidence}\n"
                      f"Open questions: {'; '.join(m.missing_information or []) or 'none'}\n\n"
                      f"--- UPDATE ---\n{update_text(update)}\n\n"
                      f"--- CLIENT PROFILE ---\n{profile_text(client.slug, client.name, profile.data)}"),
                expected_output="A short, plain-language impact memo for the advisor.",
                schema=ImpactMemo,
                model=settings.model_reasoning,
            )
            alert.memo = {**result.output.model_dump(), "run_id": run_id, "written_at": now().isoformat()}
            session.add(alert)
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
