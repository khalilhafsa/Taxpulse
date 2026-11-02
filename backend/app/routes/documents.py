from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from ..db import get_session
from ..models import Document, DocumentPage

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/{document_id}/pages/{page_number}")
def get_page(document_id: int, page_number: int, session: Session = Depends(get_session)):
    """Text of one page, used to show the source of a citation."""
    doc = session.get(Document, document_id)
    page = session.exec(select(DocumentPage).where(DocumentPage.document_id == document_id,
                                                   DocumentPage.page_number == page_number)).first()
    if not doc or not page:
        raise HTTPException(404, "Page not found")
    return {"document_id": doc.id, "filename": doc.filename, "page_number": page_number,
            "page_count": doc.page_count, "text": page.text}


@router.get("/{document_id}/file")
def get_file(document_id: int, session: Session = Depends(get_session)):
    doc = session.get(Document, document_id)
    if not doc or not Path(doc.path).exists():
        raise HTTPException(404, "File not found")
    return FileResponse(doc.path, media_type="application/pdf", filename=doc.filename,
                        content_disposition_type="inline")
