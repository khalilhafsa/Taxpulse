"""The weekly check: schedule maths, the check itself (fake LLM, mocked BMF feed), notifications, API."""
from datetime import datetime, timedelta, timezone

import httpx
from sqlmodel import Session, select

from app.agents.runner import AgentResult, get_runner
from app.agents.schemas import MatchList
from app.automation import due, get_automation, last_slot, next_slot, run_weekly_check, tick
from app.db import engine
from app.main import app
from app.models import Automation, Notification
from app.sources.bmf import http_client
from tests.test_matching import fake_matcher, prepare_demo
from tests.feeds import BFH_DECISIONS, BFH_NEWS, all_sources_client as mocked_client, bfh_news_rss
from tests.test_updates import CAPTCHA_PAGE, RSS

TZ = timezone(timedelta(hours=1))
WED = datetime(2026, 10, 28, 15, 0, tzinfo=TZ)  # a Wednesday


def monday_8(**kw):
    return Automation(id=1, enabled=True, weekday=0, hour=8, **kw)


def test_slots_follow_day_and_hour():
    a = monday_8()
    assert last_slot(a, WED) == datetime(2026, 10, 26, 8, 0, tzinfo=TZ)
    assert next_slot(a, WED) == datetime(2026, 11, 2, 8, 0, tzinfo=TZ)
    just_before = datetime(2026, 10, 26, 7, 59, tzinfo=TZ)
    assert last_slot(a, just_before) == datetime(2026, 10, 19, 8, 0, tzinfo=TZ)
    assert last_slot(a, datetime(2026, 10, 26, 8, 0, tzinfo=TZ)) == datetime(2026, 10, 26, 8, 0, tzinfo=TZ)


def test_due_only_once_per_slot_and_only_when_enabled():
    slot_utc = datetime(2026, 10, 26, 7, 0, tzinfo=timezone.utc)
    assert due(monday_8(last_run_at=slot_utc - timedelta(days=2)), WED)
    assert not due(monday_8(last_run_at=slot_utc + timedelta(minutes=5)), WED)
    assert not due(Automation(id=1, enabled=False, last_run_at=None), WED)
    assert due(monday_8(last_run_at=slot_utc.replace(tzinfo=None) - timedelta(days=1)), WED)  # naive = UTC


def demo_runner():
    """Fake agents; the Matcher scores demo updates by the labels and finds nobody for real BMF items."""
    def run(**kw):
        if kw["schema"] is MatchList and "Title: DEMO-" not in kw["task"]:
            return AgentResult(output=MatchList(matches=[]), model="claude-sonnet-5-5", tokens_in=10, tokens_out=5, duration_ms=5)
        return fake_matcher(**kw)
    run.requires_api_key = False
    return run


def notes():
    with Session(engine) as s:
        return s.exec(select(Notification).order_by(Notification.id)).all()


def test_weekly_check_fetches_runs_the_chain_and_notifies(client):
    prepare_demo(client)  # demo profiles and analyses, not scanned yet
    report = run_weekly_check(demo_runner(), mocked_client, "manual")
    assert report["status"] == "done", report
    assert report["new_items"] == 4 and report["new_alerts"] == 7 and report["chain"] == "done"

    [n] = notes()
    assert n.kind == "weekly" and n.title == "Weekly check: 7 new alerts to review" and n.link == "/alerts"
    assert n.body.startswith("BFH: 1 new publication; BMF: 3 new publications.") and "(score 88)" in n.body
    assert "and 2 more" in n.body
    with Session(engine) as s:
        a = get_automation(s)
        assert a.last_trigger == "manual" and a.last_status == "done" and "7 new alerts" in a.last_summary


def bmf_blocked_client():
    def h(request):
        if "bundesfinanzhof" in str(request.url):
            return httpx.Response(200, content=bfh_news_rss() if str(request.url) == BFH_NEWS else b"<rss><channel/></rss>")
        return httpx.Response(503, text=CAPTCHA_PAGE)
    return httpx.Client(transport=httpx.MockTransport(h))


def test_blocked_bmf_asks_for_one_click_and_bfh_still_works(client):
    prepare_demo(client)
    report = run_weekly_check(demo_runner(), bmf_blocked_client, "schedule")
    assert report["status"] == "action" and report["bmf_waiting"] and report["problems"] == []
    assert report["summary"] == "BFH: 1 new publication; BMF: waiting for your click"
    alerts_note, action = notes()
    assert alerts_note.title == "Weekly check: 7 new alerts to review"
    assert action.kind == "action" and action.link.startswith("https://www.bundesfinanzministerium.de/")
    assert "Send to TaxPulse" in action.body
    with Session(engine) as s:
        assert get_automation(s).last_status == "action"


def test_missing_key_is_a_problem(client):
    prepare_demo(client)
    from app.agents.runner import production_runner
    report = run_weekly_check(production_runner, mocked_client, "schedule")  # real runner, no API key in tests
    assert report["status"] == "problems" and report["chain"] == "skipped"
    [n] = notes()
    assert n.kind == "problem" and "No Anthropic API key" in n.body and n.link == "/settings"
    assert n.body.startswith("BFH: 1 new publication; BMF: 3 new publications.")


def test_unreachable_sources_are_problems(client):
    prepare_demo(client)
    offline = lambda: httpx.Client(transport=httpx.MockTransport(lambda r: (_ for _ in ()).throw(httpx.ConnectError("offline"))))  # noqa: E731
    report = run_weekly_check(demo_runner(), offline, "manual")
    assert report["status"] == "problems"
    assert any(p.startswith("BFH feed:") for p in report["problems"]) and any(p.startswith("BMF feed:") for p in report["problems"])
    assert report["summary"] == "BFH: could not be checked; BMF: could not be checked"


def test_failed_agent_runs_are_reported(client):
    prepare_demo(client)

    def broken(**kw):
        raise RuntimeError("The agent did not return JSON.")
    broken.requires_api_key = False
    report = run_weekly_check(broken, mocked_client, "manual")
    assert report["status"] == "problems"
    assert any("agent runs failed" in p and "did not return JSON" in p for p in report["problems"])
    [n] = notes()
    assert n.kind == "problem" and n.link == "/runs" and "did not return JSON" in n.body


def test_tick_runs_a_missed_check_as_catch_up(client):
    prepare_demo(client)
    with Session(engine) as s:
        a = get_automation(s)
        a.enabled, a.weekday, a.hour, a.fetch_bmf, a.fetch_bfh = True, 0, 8, False, False
        a.last_run_at = datetime(2026, 10, 20, 9, 0, tzinfo=timezone.utc)
        s.add(a)
        s.commit()
    report = tick(demo_runner(), mocked_client, at=WED)
    assert report and report["new_alerts"] == 7
    with Session(engine) as s:
        assert get_automation(s).last_trigger == "catch_up"
    assert tick(demo_runner(), mocked_client, at=WED) is None  # done for this week
    assert notes()[0].body.startswith("No source checked (both switched off).")


def test_automation_and_notification_api(client):
    a = client.get("/api/automation").json()
    assert a["enabled"] is False and a["next_run_at"] is None and a["days"][0] == "Monday"
    assert client.put("/api/automation", json={"enabled": True, "weekday": 2, "hour": 24}).status_code == 422
    a = client.put("/api/automation", json={"enabled": True, "weekday": 2, "hour": 7, "fetch_bmf": False}).json()
    assert a["enabled"] and a["weekday"] == 2 and a["next_run_at"] and a["last_run_at"]  # counts from now

    prepare_demo(client)
    app.dependency_overrides[get_runner] = demo_runner
    app.dependency_overrides[http_client] = mocked_client
    assert client.post("/api/automation/run").status_code == 202
    n = client.get("/api/notifications").json()
    assert n["unread"] == 1 and n["items"][0]["title"].startswith("Weekly check: 7 new alerts")
    client.post(f"/api/notifications/{n['items'][0]['id']}/read")
    assert client.get("/api/notifications").json()["unread"] == 0
    with Session(engine) as s:
        s.add(Notification(title="x"))
        s.add(Notification(title="y"))
        s.commit()
    client.post("/api/notifications/read-all")
    assert client.get("/api/notifications").json()["unread"] == 0
    assert client.post("/api/notifications/999/read").status_code == 404


def test_second_check_finds_nothing_new(client):
    prepare_demo(client)
    run_weekly_check(demo_runner(), mocked_client, "manual")
    report = run_weekly_check(demo_runner(), mocked_client, "manual")
    assert report["new_items"] == 0 and report["new_alerts"] == 0 and report["chain"] == "nothing"
    assert notes()[-1].title == "Weekly check: nothing new for your clients"
