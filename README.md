# TaxPulse

**Turn one-off due diligence mandates into lasting client relationships.**

TaxPulse is a multi-agent AI application for German tax advisors. It keeps a tax profile of every former due diligence client, monitors new BMF letters and BFH rulings, and tells the advisor which former client is affected, with evidence and a ready-to-review outreach email.

**Live demo:** https://taxpulse-demo.onrender.com (fictional companies; the agents replay results recorded with Claude, so the first visit may take a minute to wake the free server)
**Code:** https://github.com/khalilhafsa/taxpulse · **Spec and roadmap:** [docs/SPEC.md](docs/SPEC.md)

## How it works

```
Data room PDFs ─► Profiler ─► client profiles (with page citations) ─┐
                                                                     ├─► Pre-filter ─► Impact Matcher ─► alerts
BMF / BFH feed ─► Regulatory Analyst ─► structured criteria ─────────┘                       │
                                                     Outreach Writer ◄── Impact Explainer ◄──┘
                                                     (email draft, advisor approves)
```

Five Claude-powered agents orchestrated with CrewAI, a FastAPI backend with SQLite, and a React frontend.

## Status

| Step | | Status |
|---|---|---|
| 1 | Scoping and specification | ✅ |
| 2 | Project setup, demo data, app shell | ✅ |
| 3 | Profiler agent with verified page citations | ✅ |
| 4 | BMF feed + Regulatory Analyst agent | ✅ |
| 5 | Pre-filter + Impact Matcher + evaluation | ✅ |
| 6 | Impact Explainer + Outreach Writer, approval workflow | ✅ |
| 7 | Full frontend: dashboard, relevance matrix, live agent team | ✅ |
| 8 | Quality: stability test, retries, budget, Quality page | ✅ |
| 9 | Automation: weekly check (BFH automatic, BMF one-click button) and notifications | ✅ |
| 10 | Launch | |

## Run it locally

**Requirements:** Python 3.13 (CrewAI does not support 3.14 yet), Node.js 20+.

### Windows
1. Double-click `setup.bat` (once).
2. Double-click `start.bat`. The app opens at http://localhost:5173.
3. Click **Load demo data**.

### macOS / Linux
```bash
python3.13 -m venv backend/.venv && backend/.venv/bin/pip install -r backend/requirements.txt
cp .env.example .env
(cd frontend && npm install)
(cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000) &
(cd frontend && npm run dev)
```

**Agents:** add your Anthropic API key to `.env` (`ANTHROPIC_API_KEY=...`), restart, open a client and click **Build profile**.

**Evaluate the Matcher** against the labelled demo answers: `cd backend && .venv/Scripts/python -m app.evaluation` (or see the Alerts page).

API documentation: http://localhost:8000/docs · Tests: `test.bat` or `cd backend && .venv/bin/pytest`

## Project structure

```
backend/          FastAPI app (app/), tests (tests/)
frontend/         React + TypeScript + Vite + Tailwind
data/demo/        Fictional data rooms (PDF), sample tax updates, labelled expected matches
docs/SPEC.md      Product and technical specification
```

## Demo data

Four fictional companies with realistic due diligence data rooms: a precision engineering manufacturer, a Berlin real estate partnership, a VC-backed SaaS startup and a dental care group (a control case that should rarely be flagged). Regenerate the PDFs with `python data/demo/build_data_rooms.py`.

**All companies, documents and sample updates are fictional. TaxPulse does not provide tax advice.**

Concept inspired by commercial tools for tax advisors; this is an independent implementation.

## Public demo

The hosted demo runs the same app in **replay mode** (`DEMO_MODE=true`): the agents answer from
`data/demo/replay.json`, results the real Claude agents produced on the fictional demo data, so the
public site needs no API key and costs nothing. Uploads, settings and source fetching are switched
off there, and the shared demo starts fresh after 45 quiet minutes or with “Start the demo over”.

- Record: run the agents locally on the demo data, accept the demo alerts, draft the emails, then
  `cd backend && python -m app.replay export ../data/taxpulse.db`.
- Deploy: the `Dockerfile` builds one container (API plus built frontend). `render.yaml` deploys it on
  Render's free plan: New, Blueprint, pick this repository.

## License

MIT
