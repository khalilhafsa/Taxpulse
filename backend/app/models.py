"""Database tables. Mirrors section 6 of docs/SPEC.md."""
from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel


def now() -> datetime:
    return datetime.now(timezone.utc)


class Client(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    slug: str = Field(index=True, unique=True)
    name: str
    mandate: str = ""
    is_demo: bool = False
    contact_name: str = ""        # e.g. "Jonas Becker"
    contact_title: str = ""       # e.g. "Co-founder and CFO"
    salutation: str = ""          # e.g. "Dear Mr Becker,"
    created_at: datetime = Field(default_factory=now)


class FirmSettings(SQLModel, table=True):
    """The advisory firm using TaxPulse; used for email signatures. One row (id=1)."""
    id: Optional[int] = Field(default=1, primary_key=True)
    firm_name: str = ""
    advisor_name: str = ""
    advisor_title: str = ""
    phone: str = ""
    email: str = ""
    address: str = ""
    website: str = ""
    monthly_budget_usd: float = 0.0  # 0 = no limit; agents stop once this month's spend reaches it


class Document(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: int = Field(foreign_key="client.id", index=True)
    filename: str
    path: str
    page_count: int = 0
    uploaded_at: datetime = Field(default_factory=now)


class DocumentPage(SQLModel, table=True):
    """Text of one PDF page, kept so agents can cite 'document + page'."""
    id: Optional[int] = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="document.id", index=True)
    page_number: int
    text: str


class ClientProfile(SQLModel, table=True):
    """Versioned tax profile; every save (agent or advisor edit) adds a new version."""
    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: int = Field(foreign_key="client.id", index=True)
    version: int = 1
    data: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    edited_by_user: bool = False
    run_id: Optional[int] = Field(default=None, foreign_key="agentrun.id")
    created_at: datetime = Field(default_factory=now)


class RegulatoryUpdate(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    external_id: str = Field(index=True, unique=True)
    kind: str  # bmf_letter | bfh_ruling | other
    title: str
    published_on: Optional[date] = None
    source: str  # demo | bmf_feed | manual
    url: Optional[str] = None
    raw_text: str
    content_hash: str = Field(index=True, unique=True)  # deduplication
    summary: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    fetched_at: datetime = Field(default_factory=now)


class Match(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("client_id", "update_id"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: int = Field(foreign_key="client.id", index=True)
    update_id: int = Field(foreign_key="regulatoryupdate.id", index=True)
    stage: str = "prefiltered"  # prefiltered | filtered_out | scored
    score: Optional[int] = None
    verdict: Optional[str] = None  # affected | not_affected | uncertain
    reasoning: str = ""
    evidence: list[Any] = Field(default_factory=list, sa_column=Column(JSON))
    missing_information: Optional[list[Any]] = Field(default=None, sa_column=Column(JSON))
    run_id: Optional[int] = Field(default=None, foreign_key="agentrun.id")
    created_at: datetime = Field(default_factory=now)


class Alert(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    match_id: int = Field(foreign_key="match.id", unique=True)
    status: str = "new"  # new | accepted | dismissed
    dismiss_reason: str = ""
    updated_at: Optional[datetime] = None
    memo: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))  # ImpactMemo
    created_at: datetime = Field(default_factory=now)


class EmailDraft(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: int = Field(foreign_key="client.id", index=True)
    alert_ids: list[int] = Field(default_factory=list, sa_column=Column(JSON))
    subject: str
    body: str
    status: str = "draft"  # draft | approved | sent
    edited_by_user: bool = False
    revised: bool = False  # the partner review sent the first draft back once
    review_notes: str = ""  # quality issues still open after the revision, one per line
    remarks: str = ""  # the advisor's remarks this version was revised from, if any
    run_id: Optional[int] = Field(default=None, foreign_key="agentrun.id")
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)


class AgentRun(SQLModel, table=True):
    """One agent call: what ran, on what, how long, how many tokens, what it cost."""
    id: Optional[int] = Field(default=None, primary_key=True)
    pipeline_id: str = Field(index=True)
    agent: str
    status: str = "running"  # running | done | failed
    model: str = ""
    subject: str = ""  # e.g. "client:3" or "update:5"
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    duration_ms: int = 0
    error: str = ""
    attempts: int = 1  # more than 1 when temporary API errors were retried
    started_at: datetime = Field(default_factory=now)
    finished_at: Optional[datetime] = None


class EvalBatch(SQLModel, table=True):
    """A stability test: the Matcher scores the labelled demo pairs several times; each run is kept."""
    id: Optional[int] = Field(default=None, primary_key=True)
    kind: str = "stability"
    runs_planned: int = 5
    status: str = "running"  # running | done | failed
    error: str = ""
    runs: list[Any] = Field(default_factory=list, sa_column=Column(JSON))  # [{index, pairs:{key:{score,verdict,flagged,stage}}, cost_usd}]
    cost_usd: float = 0.0
    started_at: datetime = Field(default_factory=now)
    finished_at: Optional[datetime] = None


class Automation(SQLModel, table=True):
    """The weekly check: fetch new BMF items, run the agent chain, tell the advisor. One row (id=1)."""
    id: Optional[int] = Field(default=1, primary_key=True)
    enabled: bool = False
    weekday: int = 0  # 0 = Monday
    hour: int = 8  # local time on the advisor's computer
    fetch_bmf: bool = True
    fetch_bfh: bool = True  # Federal Fiscal Court feeds: open to software, fully automatic
    last_run_at: Optional[datetime] = None
    last_trigger: str = ""  # schedule | catch_up | manual
    last_status: str = ""  # done | action (BMF waits for the browser button) | problems | failed
    last_summary: str = ""


class Notification(SQLModel, table=True):
    """A message for the advisor: shown under the bell and, if allowed, as a desktop notification."""
    id: Optional[int] = Field(default=None, primary_key=True)
    kind: str = "info"  # weekly | action | problem | info
    title: str
    body: str = ""
    link: str = ""
    read: bool = False
    created_at: datetime = Field(default_factory=now)
