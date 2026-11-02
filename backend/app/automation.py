"""The weekly check, so the advisor does not have to remember.

While TaxPulse is running, a small loop looks every minute whether the weekly slot (day and hour,
local time) has passed since the last check. If so it fetches new BMF publications, runs the
agent chain (Profiler, Analyst, Pre-filter, Matcher) and leaves a notification saying what is new.
If the computer was off at the scheduled time, the check runs as soon as TaxPulse starts again.
Nothing is ever sent to clients: the advisor still reviews every alert.
"""
import asyncio
import logging
import threading
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from .config import settings
from .db import engine
from .models import AgentRun, Alert, Automation, Client, Match, Notification, RegulatoryUpdate, now

log = logging.getLogger("taxpulse.automation")
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_running = threading.Lock()


def get_automation(session: Session) -> Automation:
    a = session.get(Automation, 1)
    if not a:
        a = Automation(id=1)
        session.add(a)
        session.commit()
        session.refresh(a)
    return a


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def last_slot(a: Automation, at: datetime) -> datetime:
    """The most recent scheduled moment at or before `at` (both in local time)."""
    slot = at.replace(hour=a.hour, minute=0, second=0, microsecond=0) - timedelta(days=(at.weekday() - a.weekday) % 7)
    return slot if slot <= at else slot - timedelta(days=7)


def next_slot(a: Automation, at: datetime) -> datetime:
    return last_slot(a, at) + timedelta(days=7)


def due(a: Automation, at: datetime) -> bool:
    """Due when the last slot has passed and no check ran since. The first slot after enabling counts."""
    if not a.enabled:
        return False
    last = _aware(a.last_run_at)
    return last is None or last < last_slot(a, at).astimezone(timezone.utc)


def notify(session: Session, title: str, body: str = "", link: str = "", kind: str = "info") -> None:
    session.add(Notification(kind=kind, title=title, body=body, link=link))
    session.commit()


def run_weekly_check(runner, http_client_factory, trigger: str = "manual", received: int | None = None) -> dict:
    """Fetch the sources, run the chain, notify. Returns a short report; problems never raise.

    `received` is set when the advisor just sent the BMF feed with the browser button: nothing is
    fetched then, the new publications are already stored.
    """
    from .agents.runner import BudgetExceeded, check_budget
    from .routes.dashboard import run_chain_now
    from .sources.bfh import ingest_bfh
    from .sources.bmf import BLOCKED_MESSAGE, FetchError, ingest_bmf_feed

    if not _running.acquire(blocking=False):
        return {"status": "busy"}
    try:
        with Session(engine) as session:
            a = get_automation(session)
            before = {al.id for al in session.exec(select(Alert)).all()}
            last_run_id = max((r.id for r in session.exec(select(AgentRun)).all()), default=0)
            fetch_bmf, fetch_bfh = a.fetch_bmf, a.fetch_bfh
        problems, parts, new_items, bmf_waiting = [], [], 0, False

        if received is not None:
            parts.append(f"BMF: {received} new {'publication' if received == 1 else 'publications'} received")
            new_items += received
        else:
            if fetch_bfh:
                try:
                    with Session(engine) as session, http_client_factory() as client:
                        n = ingest_bfh(session, client)["new"]
                    parts.append(f"BFH: {n} new {'publication' if n == 1 else 'publications'}")
                    new_items += n
                except FetchError as exc:
                    problems.append(f"BFH feed: {exc}")
                    parts.append("BFH: could not be checked")
            if fetch_bmf:
                try:
                    with Session(engine) as session, http_client_factory() as client:
                        n = ingest_bmf_feed(session, client)["new"]
                    parts.append(f"BMF: {n} new {'publication' if n == 1 else 'publications'}")
                    new_items += n
                except FetchError as exc:
                    if str(exc) == BLOCKED_MESSAGE:
                        bmf_waiting = True
                        parts.append("BMF: waiting for your click")
                    else:
                        problems.append(f"BMF feed: {exc}")
                        parts.append("BMF: could not be checked")
            if not parts:
                parts.append("No source checked (both switched off)")

        chain = "skipped"
        if getattr(runner, "requires_api_key", True) and not settings.llm_configured:
            problems.append("No Anthropic API key, so the agents could not run.")
        else:
            try:
                check_budget()
                chain = run_chain_now(runner)
                if chain == "busy":
                    problems.append("The agents were already busy, so this check did not run them. They will catch up next time.")
            except BudgetExceeded as exc:
                problems.append(str(exc))

        with Session(engine) as session:
            failed = [r for r in session.exec(select(AgentRun).where(AgentRun.id > last_run_id)).all() if r.status == "failed"]
            if failed:
                problems.append(f"{len(failed)} agent {'run' if len(failed) == 1 else 'runs'} failed: {failed[0].error[:200]} "
                                "See Agent runs for details.")
            new_alerts = [al for al in session.exec(select(Alert)).all() if al.id not in before]
            lines = []
            for al in sorted(new_alerts, key=lambda x: -(session.get(Match, x.match_id).score or 0)):
                m = session.get(Match, al.match_id)
                c, u = session.get(Client, m.client_id), session.get(RegulatoryUpdate, m.update_id)
                lines.append(f"{c.name}: {(u.summary or {}).get('title_en', u.title)} (score {m.score})")
            head = "; ".join(parts) + "."
            label = "Send to TaxPulse" if received is not None else "Weekly check"

            if new_alerts:
                notify(session, f"{label}: {len(new_alerts)} new {'alert' if len(new_alerts) == 1 else 'alerts'} to review",
                       head + "\n" + "\n".join(lines[:5]) + (f"\nand {len(lines) - 5} more" if len(lines) > 5 else ""),
                       "/alerts", "weekly")
            elif not problems:
                notify(session, f"{label}: nothing new for your clients", head + " No client is affected.", "/", "weekly")
            if problems:
                link = next(("/updates" if p.startswith(("BMF feed", "BFH feed")) else "/runs" if "agent run" in p
                             else "/settings" for p in problems), "/")
                notify(session, f"{label} needs your attention",
                       ("" if new_alerts else head + "\n\n") + "\n\n".join(problems), link, "problem")
            if bmf_waiting:
                notify(session, "BMF: one click to fetch this week's letters",
                       "The BMF website asks a person to pass a security check, so TaxPulse cannot read it alone. "
                       "Open the feed with this notification, pass the check, then click “Send to TaxPulse” "
                       "in your bookmarks bar.", settings.bmf_feed_url, "action")

            status = "problems" if problems else "action" if bmf_waiting else "done"
            if received is None:
                a = get_automation(session)
                a.last_run_at, a.last_trigger, a.last_status = now(), trigger, status
                a.last_summary = f"{'; '.join(parts)}; {len(new_alerts)} new {'alert' if len(new_alerts) == 1 else 'alerts'}" + \
                    (f"; {len(problems)} {'problem' if len(problems) == 1 else 'problems'}" if problems else "")
                session.add(a)
                session.commit()
            return {"status": status, "new_items": new_items, "new_alerts": len(new_alerts), "problems": problems,
                    "chain": chain, "bmf_waiting": bmf_waiting, "summary": "; ".join(parts)}
    except Exception as exc:  # last resort: record it rather than crash the loop
        log.exception("weekly check failed")
        with Session(engine) as session:
            if received is None:
                a = get_automation(session)
                a.last_run_at, a.last_trigger, a.last_status, a.last_summary = now(), trigger, "failed", str(exc)[:500]
                session.add(a)
                session.commit()
            notify(session, "Weekly check failed", str(exc)[:500], "/runs", "problem")
        return {"status": "failed", "error": str(exc)}
    finally:
        _running.release()


def tick(runner, http_client_factory, at: datetime | None = None) -> dict | None:
    """One look at the clock: run the check if it is due."""
    at = at or datetime.now().astimezone()
    with Session(engine) as session:
        a = get_automation(session)
        if not due(a, at):
            return None
        missed = at - last_slot(a, at) > timedelta(hours=1)
    return run_weekly_check(runner, http_client_factory, "catch_up" if missed else "schedule")


async def scheduler_loop(interval_s: int = 60) -> None:
    from .agents.runner import get_runner
    from .sources.bmf import http_client
    while True:
        try:
            await asyncio.to_thread(tick, get_runner(), http_client)
        except Exception:  # keep the loop alive whatever happens
            log.exception("scheduler tick failed")
        await asyncio.sleep(interval_s)


def is_running() -> bool:
    return _running.locked()



