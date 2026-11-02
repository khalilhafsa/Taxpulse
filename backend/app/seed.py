"""Load the fictional demo data (clients, data room PDFs, regulatory updates).

Run from the backend folder:  python -m app.seed
Safe to run several times: existing records are skipped.
"""
import hashlib
import json
from datetime import date

from sqlmodel import Session, select

from .config import settings
from .db import engine, init_db
from .documents import store_document
from .models import Client, FirmSettings, RegulatoryUpdate


def content_hash(text: str) -> str:
    return hashlib.sha256(" ".join(text.split()).encode()).hexdigest()


def backfill_demo_details(session: Session) -> None:
    """Fill demo contacts and the demo firm when they are missing (older databases)."""
    demo = settings.demo_dir
    for c in json.loads((demo / "clients.json").read_text(encoding="utf-8")):
        client = session.exec(select(Client).where(Client.slug == c["slug"], Client.is_demo == True)).first()  # noqa: E712
        if client and not client.contact_name:
            client.contact_name, client.contact_title = c.get("contact_name", ""), c.get("contact_title", "")
            client.salutation = c.get("salutation", "")
            session.add(client)
    if not session.get(FirmSettings, 1) and session.exec(select(Client).where(Client.is_demo == True)).first():  # noqa: E712
        session.add(FirmSettings(id=1, **json.loads((demo / "firm.json").read_text(encoding="utf-8"))))
    session.commit()


def seed_demo(session: Session) -> dict:
    added = {"clients": 0, "documents": 0, "updates": 0}
    demo = settings.demo_dir

    for c in json.loads((demo / "clients.json").read_text(encoding="utf-8")):
        existing = session.exec(select(Client).where(Client.slug == c["slug"])).first()
        if existing:
            continue
        client = Client(slug=c["slug"], name=c["name"], mandate=c["mandate"], is_demo=True,
                        contact_name=c.get("contact_name", ""), contact_title=c.get("contact_title", ""),
                        salutation=c.get("salutation", ""))
        session.add(client)
        session.flush()
        added["clients"] += 1
        for pdf in sorted((demo / "data_rooms" / c["slug"]).glob("*.pdf")):
            store_document(session, client, pdf)
            added["documents"] += 1

    for u in json.loads((demo / "updates.json").read_text(encoding="utf-8")):
        h = content_hash(u["text"])
        exists = session.exec(select(RegulatoryUpdate).where(
            (RegulatoryUpdate.external_id == u["external_id"]) | (RegulatoryUpdate.content_hash == h))).first()
        if exists:
            continue
        session.add(RegulatoryUpdate(
            external_id=u["external_id"], kind=u["kind"], title=u["title"],
            published_on=date.fromisoformat(u["published_on"]), source=u["source"],
            url=u["url"], raw_text=u["text"], content_hash=h))
        added["updates"] += 1

    session.commit()
    backfill_demo_details(session)
    return added


def main() -> None:
    init_db()
    with Session(engine) as session:
        print("Seeded:", seed_demo(session))


if __name__ == "__main__":
    main()
