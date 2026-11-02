# TaxPulse – Product & Technical Specification

> Status: v1.0 · Step 1 (Scoping) · Owner: [Your Name]

## 1. Vision

**Turn one-off due diligence mandates into lasting client relationships.**

German tax advisory firms (Steuerberater, law firms with tax practices) analyse a company in depth during a due diligence mandate, deliver their report, and then lose contact with the client. Every year, new BMF letters (Federal Ministry of Finance guidance) and BFH rulings (Federal Fiscal Court) change the tax position of those former clients, but nobody connects the dots.

TaxPulse keeps a structured tax profile of every former client, monitors new tax developments, and tells the advisor **which former client is affected, why, and what to offer them**, with a ready-to-review outreach email.

## 2. Users

| Persona | Need | What TaxPulse gives them |
|---|---|---|
| **Tax advisor / manager** (primary) | Spot business opportunities without reading every BMF letter | An alert inbox ranked by relevance, with evidence |
| **Partner** (secondary) | Grow recurring revenue from existing relationships | Dashboard of open opportunities per client and per topic |

## 3. Core user journeys

1. **Onboard a former client**
   Advisor uploads the due diligence data room (PDFs) → *Profiler agent* builds a tax profile where **every fact cites its source document and page** → advisor reviews and corrects the profile → profile is saved.
2. **Ingest tax developments**
   New BMF letters and BFH rulings are fetched from official sources (manually or on a schedule) → *Regulatory Analyst agent* structures each one (tax area, affected companies, trigger criteria) → duplicates are skipped.
3. **Scan the portfolio**
   For every new update, the *Impact Matcher* scores every client (0–100) with written reasoning and evidence → scores above the threshold become **alerts**.
4. **Review an alert**
   Advisor opens an alert → sees the score, the evidence from both sides (client fact ↔ update criterion), and the *Impact Explainer*'s memo: impact, risk or opportunity, next steps, proposed mandate. Advisor can dismiss it (with a reason) or accept it.
5. **Reach out**
   *Outreach Writer* drafts one email per client combining its accepted alerts → advisor edits and approves → marks as sent. **TaxPulse never sends emails by itself.**
6. **Watch the agents work**
   Every run shows live progress agent by agent, and is logged with duration, tokens and cost.

## 4. Scope

**In scope (MVP)**
- Single firm, single user (no multi-tenant accounts)
- Upload of PDF data rooms, profile extraction with citations, manual profile editing
- Real source: BMF tax news feed; plus fictional demo updates clearly labelled
- 5-agent pipeline, two-stage matching, alert inbox, email drafts with approval
- Persistent storage of clients, profiles, updates, alerts, drafts and agent runs
- Dashboard: KPIs, relevance matrix, opportunities by topic
- Cost and token tracking per run
- Automated tests and an evaluation set for the agents

**Out of scope (for now)**
- Sending emails, CRM integrations
- User accounts, roles, multi-firm
- Real client data (all demo companies are fictional)
- German-language UI (UI and outputs are in English; sources may be German)

## 5. The agents

| # | Agent | Model | Input | Output |
|---|---|---|---|---|
| 1 | **Due Diligence Profiler** | Claude Sonnet | Text of data room PDFs (with page numbers) | `ClientProfile`: company facts, tax risk areas, open points, each with `source` (file + page) |
| 2 | **Regulatory Analyst** | Claude Haiku | Raw BMF letter / BFH ruling | `UpdateSummary`: tax area, summary, who is affected, trigger criteria, effective date, source URL |
| 3a | **Pre-filter** (no LLM) | — | Update + all profiles | Shortlist of candidate clients by tax-area / keyword overlap (cheap, avoids scoring every pair with an LLM) |
| 3b | **Impact Matcher** | Claude Sonnet | Update + shortlisted profiles | Per client: score 0–100, reasoning, evidence pairs (client fact ↔ criterion) |
| 4 | **Impact Explainer** | Claude Sonnet | Client profile + update + match | `ImpactMemo`: headline, impact, risk/opportunity, next steps, proposed mandate |
| 5 | **Outreach Writer** | Claude Sonnet | Client + its accepted memos | `EmailDraft`: subject, body (≤ 200 words), tone: professional, non-pushy |

**Agent rules (guardrails)**
- Only use facts from the documents given; never invent figures, deadlines or legal references.
- Every claim about a client must point to its evidence.
- When unsure, say so and lower the score rather than raise a false alarm.
- All outputs are structured (Pydantic schemas) and validated; invalid outputs are retried.

## 6. Data model

```
Client ──< Document (PDF, pages)
   │
   └──< ClientProfile (versioned; facts with citations; edited_by_user flag)

RegulatoryUpdate (source, url, type, date, raw_text, summary, hash for dedup)

Match (client × update): score, reasoning, evidence, stage (prefiltered / scored)
   └── Alert (score ≥ threshold): status new / accepted / dismissed, dismiss_reason
         └── ImpactMemo

EmailDraft (client, alerts[], subject, body, status draft / approved / sent)

AgentRun: agent, input refs, output ref, model, tokens in/out, cost, duration, status, error
```

## 7. Architecture

```
┌───────────────────────────┐        REST + Server-Sent Events        ┌──────────────────────────────┐
│  Frontend (React + Vite)  │  ───────────────────────────────────►   │  Backend (FastAPI, Python)   │
│  Dashboard · Clients ·    │  ◄───────────────────────────────────   │  API · pipeline · scheduler  │
│  Updates · Alerts · Runs  │        live agent progress              │                              │
└───────────────────────────┘                                         │  CrewAI agents ──► Claude API│
                                                                      │  Source fetchers ──► BMF feed│
                                                                      │  SQLite (SQLModel)           │
                                                                      └──────────────────────────────┘
```

- **Backend**: FastAPI exposes the REST API, runs pipelines as background jobs, and streams progress events (SSE) to the UI.
- **Agents**: CrewAI, one Crew per step so results can be stored and shown step by step.
- **Storage**: SQLite file via SQLModel (simple, no server; can move to PostgreSQL later).
- **Frontend**: React + TypeScript + Vite + Tailwind CSS.

## 8. Tech stack

| Layer | Choice | Why |
|---|---|---|
| Language (backend) | Python 3.13 | CrewAI does not support 3.14 yet |
| Agents | CrewAI | Role-based multi-agent orchestration |
| LLM | Claude Sonnet (reasoning), Claude Haiku (structuring) via Anthropic API | Quality where it matters, low cost elsewhere |
| API | FastAPI | Fast, typed, auto-generated docs |
| Database | SQLite + SQLModel | Zero setup, persistent |
| PDF | pypdf | Page-level text extraction for citations |
| Frontend | React, TypeScript, Vite, Tailwind CSS | Professional, modern UI |
| Tests | pytest (backend), agent eval set | Quality you can prove |

## 9. Quality, cost and safety

- **Evaluation set**: hand-labelled expected matches (client × update → affected / not affected). Target: no missed high-relevance match, ≤ 1 false alert per 10 pairs.
- **Cost control**: pre-filter before LLM matching; Haiku for cheap steps; tokens and cost recorded per run and shown in the UI.
- **Secrets**: Anthropic API key only in `.env`, never committed.
- **Data**: only fictional companies; disclaimer in the UI: *not tax advice*.
- **Human in the loop**: nothing leaves the app without advisor approval.

## 10. Roadmap and "done" criteria

| Step | Deliverable | Done when |
|---|---|---|
| 1 | Scoping | This spec is validated |
| 2 | Project setup + demo data | Repo on GitHub, backend and frontend start, 3 fictional data rooms as PDFs, demo updates |
| 3 | Profiler agent | Uploading a PDF produces a profile with page citations, saved in the DB |
| 4 | Regulatory feed | Real BMF items fetched and structured, duplicates skipped |
| 5 | Matching | Pre-filter + scoring with evidence; passes the evaluation set |
| 6 | Explainer + Writer | Memos and email drafts, approve / dismiss flow |
| 7 | Frontend | Dashboard, clients, updates, alert inbox, live run view |
| 8 | Quality | Tests green, eval report, error handling, cost tracking |
| 9 | Automation | Scheduled weekly scan + notification |
| 10 | Launch | Deployed demo link, README, demo video, LinkedIn post |

## 11. Demo success criteria

In under 2 minutes, a viewer sees: a data room uploaded → profile with citations → a new BMF letter arrives → agents work live → the right client is flagged with evidence → a ready email appears.

---
*All companies and sample updates are fictional. TaxPulse does not provide tax advice. Concept inspired by commercial tools for tax advisors; independent implementation.*
