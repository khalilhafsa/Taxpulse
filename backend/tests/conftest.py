"""Test setup: a temporary database and upload folder, and no real API key.
These environment variables must be set before the app is imported."""
import json
import os
import tempfile
from pathlib import Path

import pytest

_tmp = Path(tempfile.mkdtemp())
os.environ["DATABASE_URL"] = f"sqlite:///{(_tmp / 'test.db').as_posix()}"
os.environ["UPLOAD_DIR"] = str(_tmp / "uploads")
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["SCHEDULER"] = "false"

from fastapi.testclient import TestClient  # noqa: E402

from app.agents.runner import AgentResult, get_runner  # noqa: E402
from app.agents.schemas import EmailDraftOut, ImpactMemo, ProfileDraft, UpdateAnalysis  # noqa: E402
from app.main import app  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


FAKE_ANALYSIS = UpdateAnalysis(
    title_en="Mandatory B2B e-invoicing", kind="bmf_letter", relevant_for_companies=True,
    tax_categories=["VAT"], summary="From 2027 larger businesses must issue structured e-invoices.",
    who_is_affected="Businesses with turnover above EUR 800,000 making domestic B2B supplies",
    trigger_criteria=["Prior-year turnover above EUR 800,000", "Domestic B2B supplies", "PDF-only invoicing"],
    exclusions=["VAT-exempt supplies", "Cross-border supplies"], effective_date="2027-01-01",
    keywords=["e-invoicing", "XRechnung", "ZUGFeRD", "VAT"])


def fake_runner(**kwargs) -> AgentResult:
    """Stands in for Claude: returns hand-written outputs depending on the agent."""
    schema = kwargs["schema"]
    if schema is ProfileDraft:
        draft = ProfileDraft.model_validate(json.loads((FIXTURES / "nordlicht_profile.json").read_text(encoding="utf-8")))
        assert "=== Document: 02_Property_Schedule.pdf | Page 2 ===" in kwargs["task"]
        return AgentResult(output=draft, model="claude-sonnet-5-5", tokens_in=9000, tokens_out=3000, duration_ms=1234)
    if schema is UpdateAnalysis:
        assert "--- TEXT ---" in kwargs["task"] and kwargs["model"].endswith("haiku-5-5")
        return AgentResult(output=FAKE_ANALYSIS.model_copy(), model="claude-haiku-5-5",
                           tokens_in=2000, tokens_out=500, duration_ms=800)
    if schema is ImpactMemo:
        assert "--- MATCHER'S ASSESSMENT ---" in kwargs["task"] and "--- CLIENT PROFILE ---" in kwargs["task"]
        return AgentResult(output=ImpactMemo(
            headline="The client must change its invoicing before 2027.",
            impact="Its invoicing system cannot issue structured e-invoices.",
            risk_or_opportunity="risk", urgency="high", deadline="1 January 2027",
            recommended_actions=["Check the ERP", "Plan the migration"],
            proposed_mandate="E-invoicing readiness review", questions_for_client=["Which ERP version?"]),
            model="claude-sonnet-5-5", tokens_in=4000, tokens_out=600, duration_ms=700)
    if schema is EmailDraftOut:
        assert "Headline: The client must change its invoicing before 2027." in kwargs["task"]
        assert "Do NOT write the closing formula" in kwargs["task"]
        return AgentResult(output=EmailDraftOut(
            subject="E-invoicing from 2027: what it means for you.",
            body="Dear management,\n\nA new rule affects your invoicing.\n\nBest regards,\nSomeone"),
            model="claude-sonnet-5-5", tokens_in=1500, tokens_out=300, duration_ms=500)
    raise AssertionError(f"No fake output for {schema}")


fake_runner.requires_api_key = False
fake_profiler_runner = fake_runner  # backwards-compatible name


@pytest.fixture
def client():
    """Each test starts with an empty database."""
    from sqlmodel import SQLModel

    from app.db import engine
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def fake_llm():
    app.dependency_overrides[get_runner] = lambda: fake_runner
    yield
    app.dependency_overrides.pop(get_runner, None)
