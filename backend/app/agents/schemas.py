"""Structured outputs of the agents. Every client fact carries at least one citation."""
from typing import Literal

from pydantic import BaseModel, Field

# Fixed list so the pre-filter (step 5) can compare client tax areas with update tax areas.
TaxCategory = Literal[
    "VAT",
    "Corporate income tax",
    "Trade tax",
    "Transfer pricing",
    "Real estate transfer tax",
    "Wage tax",
    "R&D incentives",
    "International tax",
    "Financing",
    "Income tax",
    "Tax procedure",
    "Other",
]


class Citation(BaseModel):
    document: str = Field(description="Exact file name of the source document, e.g. '01_Tax_Due_Diligence_Report.pdf'")
    page: int = Field(ge=1, description="Page number in that document (first page = 1)")
    quote: str = Field(description="Short verbatim excerpt (5-25 words) copied exactly from that page")
    verified: bool = Field(default=False, description="Set by TaxPulse after checking the quote; leave false")


class Fact(BaseModel):
    label: str = Field(description="Short name of the fact, e.g. 'Revenue FY2023'")
    value: str = Field(description="The fact in one sentence or less")
    citations: list[Citation] = Field(min_length=1)


class TaxArea(BaseModel):
    category: TaxCategory
    title: str = Field(description="Specific title, e.g. 'Cost-plus remuneration of Polish contract manufacturer'")
    assessment: Literal["risk", "opportunity", "neutral"]
    severity: Literal["high", "medium", "low"]
    summary: str = Field(description="Two sentences on why this matters for future tax developments")
    facts: list[Fact] = Field(min_length=1)


class UpdateAnalysis(BaseModel):
    title_en: str = Field(description="Short English title of the publication")
    kind: Literal["bmf_letter", "bfh_ruling", "law", "press_release", "other"]
    relevant_for_companies: bool = Field(
        description="True if it changes the tax position of some businesses; false for speeches, statistics, "
                    "purely private-individual topics or organisational news")
    tax_categories: list[TaxCategory] = Field(min_length=1)
    summary: str = Field(description="Three plain-English sentences: what changes, from when, for whom")
    who_is_affected: str = Field(description="One sentence describing the companies affected")
    trigger_criteria: list[str] = Field(
        description="Concrete, checkable facts that make a company affected, e.g. 'Turnover above EUR 800,000'")
    criteria_logic: Literal["any", "all"] = Field(
        default="any",
        description="'all' only if a company must meet every trigger criterion at once (e.g. a threshold AND "
                    "an activity); 'any' if each criterion describes a separate situation that is enough on its own")
    exclusions: list[str] = Field(description="Cases the publication explicitly does not cover")
    effective_date: str = Field(description="Date or period it applies from, or 'not stated'")
    keywords: list[str] = Field(description="6-12 short matching tags in English")


class ProfileDraft(BaseModel):
    company_name: str
    summary: str = Field(description="Three sentences describing the company and its tax situation")
    key_facts: list[Fact] = Field(
        description="Legal form, seat, business activity, revenue, employees, ownership, cross-border activity, mandate"
    )
    tax_areas: list[TaxArea]
    open_points: list[Fact] = Field(description="Follow-ups flagged in the due diligence")
    keywords: list[str] = Field(description="8-15 short matching tags, e.g. 'contract manufacturing', 'e-invoicing'")


class Evidence(BaseModel):
    client_fact: str = Field(description="A fact copied word for word from the client profile")
    criterion: str = Field(description="The trigger criterion or exclusion of the update it relates to")
    supports_impact: bool = Field(description="True if this fact makes the client affected, false if it argues against")
    verified: bool = Field(default=False, description="Set by TaxPulse after checking the fact; leave false")


class ClientMatch(BaseModel):
    client_id: str = Field(description="The client_id exactly as given in the prompt")
    score: int = Field(ge=0, le=100, description="0 = clearly not affected, 100 = certainly and materially affected")
    verdict: Literal["affected", "not_affected", "uncertain"]
    reasoning: str = Field(description="Two sentences linking the client's facts to the update")
    evidence: list[Evidence]
    missing_information: list[str] = Field(description="Facts the profile lacks to be sure; empty if none")


class MatchList(BaseModel):
    matches: list[ClientMatch]


class ImpactMemo(BaseModel):
    headline: str = Field(description="One sentence, written for the advisor: what this means for the client")
    impact: str = Field(description="Three to five plain-language sentences: what changes for this client and why, "
                                    "using the client's own facts and figures")
    risk_or_opportunity: Literal["risk", "opportunity", "both"]
    urgency: Literal["high", "medium", "low"]
    deadline: str = Field(description="The relevant date or deadline from the update, or 'none stated'")
    recommended_actions: list[str] = Field(description="Two to four concrete next steps for the client")
    proposed_mandate: str = Field(description="The advisory engagement the firm could offer, in one line")
    questions_for_client: list[str] = Field(description="Facts to confirm with the client before advising")


class EmailDraftOut(BaseModel):
    subject: str = Field(description="Specific subject line naming the topic, max 80 characters")
    body: str = Field(description="Plain-text email body from the salutation to the courteous close, without "
                                  "closing formula or signature")
