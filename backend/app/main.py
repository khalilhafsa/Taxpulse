"""TaxPulse API.

Run from the backend folder:  uvicorn app.main:app --reload
Interactive API docs:          http://localhost:8000/docs
"""
import asyncio
import inspect
import re
import time
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from sqlmodel import Session

from .config import settings
from .db import engine, init_db
from .seed import backfill_demo_details
from .quality import recover_interrupted
from .routes import alerts, automation, clients, dashboard, documents, outreach, quality, runs, system, updates


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    if settings.demo_mode:
        from .replay import reset_demo
        reset_demo(engine)
    with Session(engine) as session:
        backfill_demo_details(session)
        recover_interrupted(session)
    task = None
    if settings.scheduler and not settings.demo_mode:
        from .automation import scheduler_loop
        task = asyncio.create_task(scheduler_loop())
    yield
    if task:
        task.cancel()


app = FastAPI(title="TaxPulse API", version="0.9.0", lifespan=lifespan)

# The BMF website may call this local app, but only for the "Send to TaxPulse" browser button. Chrome asks
# such public pages for permission before they reach a local app ("private network access").
_cors_extra = {"allow_private_network": True} if "allow_private_network" in inspect.signature(CORSMiddleware).parameters else {}
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://127.0.0.1:5173", *settings.feed_sender_origins],
    allow_methods=["*"],
    allow_headers=["*"],
    **_cors_extra,
)

app.include_router(system.router, prefix="/api")
app.include_router(clients.router, prefix="/api")
app.include_router(updates.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(runs.router, prefix="/api")
app.include_router(alerts.router, prefix="/api")
app.include_router(outreach.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(quality.router, prefix="/api")
app.include_router(automation.router, prefix="/api")


# ---------- public demo ----------

DEMO_BLOCKED = [  # (method, path pattern): things a stranger should not do on the shared demo
    ("POST", r"/api/clients"), ("PUT", r"/api/clients/\d+/contact"), ("POST", r"/api/clients/\d+/documents"),
    ("POST", r"/api/updates"), ("POST", r"/api/updates/(fetch|fetch-bfh|import-feed|receive-feed)"),
    ("PUT", r"/api/settings/firm"), ("PUT", r"/api/automation"), ("POST", r"/api/automation/run"),
    ("POST", r"/api/quality/stability"), ("POST", r"/api/drafts/\d+/revise"), ("DELETE", r"/api/documents/.*"),
]
_last_seen = {"t": time.monotonic()}


@app.middleware("http")
async def public_demo_guard(request, call_next):
    if settings.demo_mode and request.url.path.startswith("/api"):
        for method, pattern in DEMO_BLOCKED:
            if request.method == method and re.fullmatch(pattern, request.url.path):
                return JSONResponse({"detail": "Switched off in the public demo, which replays recorded agent "
                                               "results. Run TaxPulse locally to use this."}, status_code=403)
        # The demo is shared: after a quiet spell the next visitor starts from a fresh state.
        now_t = time.monotonic()
        if now_t - _last_seen["t"] > settings.demo_idle_reset_minutes * 60 and not _agents_busy():
            from .replay import reset_demo
            reset_demo(engine)
        _last_seen["t"] = now_t
    return await call_next(request)


def _agents_busy() -> bool:
    from sqlmodel import select
    from .models import AgentRun
    with Session(engine) as s:
        return s.exec(select(AgentRun).where(AgentRun.status == "running")).first() is not None


@app.post("/api/demo/reset")
def demo_reset():
    if not settings.demo_mode:
        raise HTTPException(404, "Not found")
    if _agents_busy():
        raise HTTPException(409, "The agents are working. Reset when they have finished.")
    from .replay import reset_demo
    reset_demo(engine)
    return {"reset": True}


# One container for the public demo: serve the built frontend, with the app's routes falling back to index.html.
if settings.static_dir and Path(settings.static_dir).is_dir():
    _static = Path(settings.static_dir)
    app.mount("/assets", StaticFiles(directory=_static / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "Not found")
        file = (_static / path).resolve()
        if path and file.is_file() and _static.resolve() in file.parents:
            return FileResponse(file)
        return FileResponse(_static / "index.html")
