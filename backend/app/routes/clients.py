import re
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlmodel import Session, func, select

from ..agents.profiler import run_profiler
from ..agents.runner import Runner, get_runner
from ..config import settings
from ..db import engine, get_session
from ..documents import safe_filename, store_document
from ..models import AgentRun, Client, ClientProfile, Document, DocumentPage

router = APIRouter(prefix="/clients", tags=["clients"])


def latest_profile(session: Session, client_id: int):
    return session.exec(select(ClientProfile).where(ClientProfile.client_id == client_id)
                        .order_by(ClientProfile.version.desc())).first()


def get_client_or_404(session: Session, client_id: int) -> Client:
    client = session.get(Client, client_id)
    if not client:
        raise HTTPException(404, "Client not found")
    return client


@router.get("")
def list_clients(session: Session = Depends(get_session)):
    rows = session.exec(
        select(Client, func.count(Document.id))
        .join(Document, Document.client_id == Client.id, isouter=True)
        .group_by(Client.id).order_by(Client.name)
    ).all()
    return [
        {**c.model_dump(), "document_count": n, "has_profile": latest_profile(session, c.id) is not None}
        for c, n in rows
    ]


class NewClient(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    mandate: str = Field(default="", max_length=300)
    contact_name: str = Field(default="", max_length=200)
    contact_title: str = Field(default="", max_length=200)
    salutation: str = Field(default="", max_length=200)


@router.post("", status_code=201)
def create_client(body: NewClient, session: Session = Depends(get_session)):
    base = re.sub(r"[^a-z0-9]+", "_", body.name.lower()).strip("_")[:50] or "client"
    slug, n = base, 2
    while session.exec(select(Client).where(Client.slug == slug)).first():
        slug, n = f"{base}_{n}", n + 1
    client = Client(slug=slug, name=body.name.strip(), mandate=body.mandate.strip(),
                    contact_name=body.contact_name.strip(), contact_title=body.contact_title.strip(),
                    salutation=body.salutation.strip())
    session.add(client)
    session.commit()
    session.refresh(client)
    return client


class ContactIn(BaseModel):
    contact_name: str = Field(default="", max_length=200)
    contact_title: str = Field(default="", max_length=200)
    salutation: str = Field(default="", max_length=200)


@router.put("/{client_id}/contact")
def save_contact(client_id: int, body: ContactIn, session: Session = Depends(get_session)):
    client = get_client_or_404(session, client_id)
    client.contact_name, client.contact_title = body.contact_name.strip(), body.contact_title.strip()
    client.salutation = body.salutation.strip()
    session.add(client)
    session.commit()
    session.refresh(client)
    return client.model_dump()


@router.get("/{client_id}")
def get_client(client_id: int, session: Session = Depends(get_session)):
    client = get_client_or_404(session, client_id)
    docs = session.exec(select(Document).where(Document.client_id == client_id)
                        .order_by(Document.filename)).all()
    profile = latest_profile(session, client_id)
    profile_run = session.get(AgentRun, profile.run_id) if profile and profile.run_id else None
    active = session.exec(select(AgentRun).where(AgentRun.subject == f"client:{client_id}",
                                                 AgentRun.status == "running")).first()
    return {
        **client.model_dump(),
        "documents": [d.model_dump(exclude={"path"}) for d in docs],
        "profile": profile.model_dump() if profile else None,
        "profile_run": profile_run.model_dump() if profile_run else None,
        "active_run_id": active.id if active else None,
    }


@router.post("/{client_id}/documents", status_code=201)
async def upload_documents(client_id: int, files: list[UploadFile] = File(...),
                           session: Session = Depends(get_session)):
    client = get_client_or_404(session, client_id)
    existing = {d.filename for d in session.exec(select(Document).where(Document.client_id == client_id)).all()}
    added, warnings = [], []
    for f in files:
        content = await f.read()
        name = safe_filename(f.filename or "document.pdf")
        if not content.startswith(b"%PDF"):
            raise HTTPException(400, f"{f.filename} is not a PDF file.")
        if len(content) > settings.max_upload_mb * 1024 * 1024:
            raise HTTPException(400, f"{f.filename} is larger than {settings.max_upload_mb} MB.")
        if name in existing:
            raise HTTPException(409, f"{name} is already in this data room.")
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / name
            src.write_bytes(content)
            try:
                doc = store_document(session, client, src, name)
            except Exception:
                raise HTTPException(400, f"{f.filename} could not be read as a PDF.")
        existing.add(name)
        added.append(doc.model_dump(exclude={"path"}))
        # Scanned PDFs have no text layer: warn instead of failing silently later.
        empty = session.exec(select(func.count()).select_from(DocumentPage)
                             .where(DocumentPage.document_id == doc.id,
                                    func.length(func.trim(DocumentPage.text)) < 20)).one()
        if empty:
            warnings.append(f"{name}: {empty} of {doc.page_count} pages have no readable text "
                            "(scanned images are not supported yet).")
    session.commit()
    return {"added": added, "warnings": warnings}


@router.post("/{client_id}/profile", status_code=202)
def build_profile(client_id: int, background: BackgroundTasks, session: Session = Depends(get_session),
                  runner: Runner = Depends(get_runner)):
    """Start the Profiler agent in the background. Poll GET /runs/{run_id} for progress."""
    get_client_or_404(session, client_id)
    if getattr(runner, "requires_api_key", True) and not settings.llm_configured:
        raise HTTPException(400, "No Anthropic API key. Add ANTHROPIC_API_KEY to the .env file and restart the backend.")
    if not session.exec(select(Document).where(Document.client_id == client_id)).first():
        raise HTTPException(400, "Upload at least one PDF before building the profile.")
    running = session.exec(select(AgentRun).where(AgentRun.subject == f"client:{client_id}",
                                                  AgentRun.status == "running")).first()
    if running:
        return {"run_id": running.id}

    run = AgentRun(pipeline_id=uuid.uuid4().hex, agent="profiler", subject=f"client:{client_id}",
                   model=settings.model_reasoning.split("/", 1)[-1])
    session.add(run)
    session.commit()
    background.add_task(run_profiler, engine, run.id, client_id, runner)
    return {"run_id": run.id}
