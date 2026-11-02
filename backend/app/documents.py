"""Store data room PDFs and their page texts."""
import re
import shutil
from pathlib import Path

from sqlmodel import Session

from .config import settings
from .models import Client, Document, DocumentPage
from .pdf import extract_pages


def safe_filename(name: str) -> str:
    stem, dot, ext = Path(name).name.rpartition(".")
    stem = re.sub(r"[^\w\-]+", "_", stem or ext).strip("_") or "document"
    return f"{stem}.pdf"


def store_document(session: Session, client: Client, source: Path, filename: str | None = None) -> Document:
    """Copy a PDF into the client's upload folder, extract its pages and save both."""
    target_dir = settings.upload_dir / client.slug
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / (filename or source.name)
    if source.resolve() != target.resolve():
        shutil.copyfile(source, target)
    pages = extract_pages(target)
    doc = Document(client_id=client.id, filename=target.name, path=str(target), page_count=len(pages))
    session.add(doc)
    session.flush()
    for i, text in enumerate(pages, start=1):
        session.add(DocumentPage(document_id=doc.id, page_number=i, text=text))
    return doc
