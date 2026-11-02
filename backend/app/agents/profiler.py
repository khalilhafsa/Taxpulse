"""Agent 1 – Due Diligence Profiler.

Reads every page of a client's data room and builds a tax profile in which each
fact cites its document, page and a verbatim quote. Quotes are then checked
against the stored page text, so the advisor can see which citations are proven.
"""
from sqlmodel import Session, select

from ..config import settings
from ..models import AgentRun, Client, ClientProfile, Document, DocumentPage, now
from .citations import verify
from .runner import AgentSpec, Runner, cost_usd, friendly_error
from .schemas import ProfileDraft

SPEC = AgentSpec(
    role="Due Diligence Profiler",
    goal="Turn a due diligence data room into a precise, reusable tax profile in which every fact is traceable to its source page",
    backstory=(
        "You are a senior tax manager at a German tax advisory firm. You have reviewed hundreds of "
        "data rooms and know which facts will matter years later when tax law changes: legal form, "
        "size thresholds, cross-border flows, related-party transactions, incentives, losses and "
        "the open points the team flagged."
    ),
)

RULES = """Rules:
- Use only information that is written in the documents. Never invent facts, figures, dates or legal references.
- Every fact needs at least one citation: the exact file name, the page number shown in the page header of this prompt, and a verbatim quote of 5 to 25 words copied character for character from that page.
- Prefer the most specific source (e.g. the contract or financial statements rather than a summary) and cite both when they agree.
- Cover every tax area discussed in the data room, including low-risk ones. Use 'opportunity' for unused incentives or savings.
- Write in English. Keep German legal terms (e.g. Organschaft, Forschungszulage) where they are used in the documents."""


def data_room_text(session: Session, client_id: int) -> tuple[str, dict[tuple[str, int], str], int]:
    """Concatenate all pages with clear markers. Returns (prompt text, page lookup, page count)."""
    docs = session.exec(select(Document).where(Document.client_id == client_id).order_by(Document.filename)).all()
    parts, lookup = [], {}
    for doc in docs:
        pages = session.exec(select(DocumentPage).where(DocumentPage.document_id == doc.id)
                             .order_by(DocumentPage.page_number)).all()
        for p in pages:
            lookup[(doc.filename, p.page_number)] = p.text
            parts.append(f"=== Document: {doc.filename} | Page {p.page_number} ===\n{p.text}")
    return "\n\n".join(parts), lookup, len(lookup)


def run_profiler(engine, run_id: int, client_id: int, runner: Runner) -> None:
    """Background job: build the profile and record the run. Never raises; errors are stored on the run."""
    with Session(engine) as session:
        run = session.get(AgentRun, run_id)
        try:
            client = session.get(Client, client_id)
            text, lookup, page_count = data_room_text(session, client_id)
            if page_count == 0:
                raise ValueError("This client has no readable pages. Upload text-based PDF files first.")

            result = runner(
                spec=SPEC,
                task=(f"Build the tax profile of {client.name} (mandate: {client.mandate}).\n\n{RULES}\n\n"
                      f"--- DATA ROOM ({page_count} pages) ---\n{text}"),
                expected_output="A complete tax profile in which every fact has verbatim citations.",
                schema=ProfileDraft,
                model=settings.model_reasoning,
            )
            draft: ProfileDraft = result.output
            verified, total = verify(draft, lookup)

            last = session.exec(select(ClientProfile).where(ClientProfile.client_id == client_id)
                                .order_by(ClientProfile.version.desc())).first()
            data = draft.model_dump()
            data["verification"] = {"verified": verified, "total": total}
            data["source_pages"] = page_count
            session.add(ClientProfile(client_id=client_id, version=(last.version + 1) if last else 1,
                                      data=data, run_id=run_id))

            run.status = "done"
            run.model = result.model
            run.tokens_in, run.tokens_out = result.tokens_in, result.tokens_out
            run.cost_usd = cost_usd(result.model, result.tokens_in, result.tokens_out)
            run.duration_ms = result.duration_ms
            run.attempts = result.attempts
        except Exception as exc:  # store any failure on the run so the UI can show it
            session.rollback()
            run = session.get(AgentRun, run_id)
            run.status = "failed"
            run.error = friendly_error(exc)
        run.finished_at = now()
        session.add(run)
        session.commit()
