"""Database engine and session helpers (SQLite via SQLModel)."""
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

from .config import settings

if settings.database_url.startswith("sqlite:///"):
    Path(settings.database_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})


def _sql_default(col) -> str | None:
    """SQL literal for a column's simple Python default (bool, int, float, str), else None."""
    arg = getattr(col.default, "arg", None)
    if isinstance(arg, bool):
        return "1" if arg else "0"
    if isinstance(arg, (int, float)):
        return str(arg)
    if isinstance(arg, str):
        return "'" + arg.replace("'", "''") + "'"
    return None


def _add_missing_columns() -> None:
    """Lightweight migration: add columns that were added to the models after the
    database file was created (SQLite cannot do this through create_all).
    Non-nullable columns are added with their default value so existing rows stay valid."""
    insp = inspect(engine)
    with engine.begin() as conn:
        for table in SQLModel.metadata.sorted_tables:
            if not insp.has_table(table.name):
                continue
            existing = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name in existing:
                    continue
                ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {col.type.compile(engine.dialect)}'
                default = _sql_default(col)
                if not col.nullable:
                    if default is None:
                        raise RuntimeError(f"Cannot add required column {table.name}.{col.name} without a default.")
                    ddl += f" NOT NULL DEFAULT {default}"
                elif default is not None:
                    ddl += f" DEFAULT {default}"
                conn.execute(text(ddl))


def init_db() -> None:
    from . import models  # noqa: F401  (registers tables)
    SQLModel.metadata.create_all(engine)
    _add_missing_columns()


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
