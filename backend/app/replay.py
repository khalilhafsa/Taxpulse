"""Public demo: the agents replay results that were recorded with Claude, so the hosted site needs no API key.

`python -m app.replay export <database>` writes data/demo/replay.json from a database in which the real
agents have processed the fictional demo data (demo clients and demo updates only, nothing else).
In demo mode (DEMO_MODE=true) `replay_runner` answers each agent call from that file, after a short
pause so the agent team can be watched at work.
"""
import json
import re
import sys
import time
from functools import lru_cache

from sqlmodel import Session, SQLModel, create_engine, select

from .agents.runner import AgentResult
from .agents.schemas import ClientMatch, EmailDraftOut, ImpactMemo, MatchList, ProfileDraft, UpdateAnalysis
from .config import settings
from .models import AgentRun, Alert, Client, ClientProfile, EmailDraft, EvalBatch, Match, RegulatoryUpdate

REPLAY_FILE = settings.demo_dir / "replay.json"
PAUSE_S = {"profiler": 4.0, "analyst": 2.0, "matcher": 3.0, "explainer": 3.0, "writer": 4.0}


class NotRecorded(RuntimeError):
    """The demo has no recorded answer for this call."""


# ---------- export (run once, on a database with real results) ----------

def _usage(run: AgentRun | None) -> dict:
    if not run:
        return {"model": "claude-sonnet-5-5", "tokens_in": 0, "tokens_out": 0, "duration_ms": 0}
    return {"model": run.model, "tokens_in": run.tokens_in, "tokens_out": run.tokens_out, "duration_ms": run.duration_ms}


def export(database_url: str) -> dict:
    from .agents.writer import email_core, review_email
    engine = create_engine(database_url)
    out = {"profiles": {}, "analyses": {}, "matches": {}, "memos": {}, "drafts": {}, "stability": None}
    with Session(engine) as s:
        clients = {c.id: c for c in s.exec(select(Client).where(Client.is_demo == True)).all()}  # noqa: E712
        updates = {u.id: u for u in s.exec(select(RegulatoryUpdate).where(RegulatoryUpdate.source == "demo")).all()}

        for c in clients.values():
            p = s.exec(select(ClientProfile).where(ClientProfile.client_id == c.id)
                       .order_by(ClientProfile.version.desc())).first()
            if p:
                data = {k: v for k, v in p.data.items() if k not in ("verification", "source_pages")}
                out["profiles"][c.slug] = {"name": c.name, "data": data, **_usage(s.get(AgentRun, p.run_id) if p.run_id else None)}

        for u in updates.values():
            if not u.summary:
                continue
            run = s.exec(select(AgentRun).where(AgentRun.agent == "analyst", AgentRun.subject == f"update:{u.id}",
                                                AgentRun.status == "done").order_by(AgentRun.id.desc())).first()
            out["analyses"][u.external_id] = {"title": u.title, "summary": u.summary, **_usage(run)}

        for m in s.exec(select(Match).where(Match.stage == "scored")).all():
            if m.client_id in clients and m.update_id in updates:
                u = updates[m.update_id]
                entry = out["matches"].setdefault(u.external_id, {"title": u.title, "clients": {}, **_usage(s.get(AgentRun, m.run_id) if m.run_id else None)})
                entry["clients"][clients[m.client_id].slug] = {
                    "score": m.score, "verdict": m.verdict, "reasoning": m.reasoning,
                    "evidence": [{k: v for k, v in e.items() if k != "verified"} for e in (m.evidence or [])],
                    "missing_information": m.missing_information or []}

        for a in s.exec(select(Alert)).all():
            m = s.get(Match, a.match_id)
            if a.memo and m.client_id in clients and m.update_id in updates:
                run = s.exec(select(AgentRun).where(AgentRun.agent == "explainer", AgentRun.subject == f"alert:{a.id}",
                                                    AgentRun.status == "done").order_by(AgentRun.id.desc())).first()
                key = f"{clients[m.client_id].slug}|{updates[m.update_id].external_id}"
                out["memos"][key] = {"memo": a.memo, **_usage(run)}

        for d in s.exec(select(EmailDraft).order_by(EmailDraft.id)).all():  # latest AI draft per client wins
            if d.client_id in clients and d.run_id and not d.edited_by_user and not review_email(d.body):
                update_ids = [s.get(Match, s.get(Alert, i).match_id).update_id for i in d.alert_ids if s.get(Alert, i)]
                if not update_ids or any(uid not in updates for uid in update_ids):
                    continue  # the email also covers real publications: not part of the demo
                topics = sorted(updates[uid].external_id for uid in update_ids)
                out["drafts"].setdefault(clients[d.client_id].slug, {})[",".join(topics)] = {
                    "subject": d.subject, "body": email_core(d.body), **_usage(s.get(AgentRun, d.run_id))}

        batch = s.exec(select(EvalBatch).where(EvalBatch.status == "done").order_by(EvalBatch.id.desc())).first()
        if batch:
            out["stability"] = {"runs_planned": batch.runs_planned, "runs": batch.runs, "cost_usd": batch.cost_usd}
    return out


# ---------- replay ----------

@lru_cache(maxsize=1)
def recordings() -> dict:
    if not REPLAY_FILE.exists():
        return {"profiles": {}, "analyses": {}, "matches": {}, "memos": {}, "drafts": {}, "stability": None}
    return json.loads(REPLAY_FILE.read_text(encoding="utf-8"))


def _result(output, rec: dict) -> AgentResult:
    return AgentResult(output=output, model=rec.get("model") or "claude-sonnet-5-5", tokens_in=rec.get("tokens_in", 0),
                       tokens_out=rec.get("tokens_out", 0), duration_ms=rec.get("duration_ms", 0))


def _update_in(task: str, table: dict) -> tuple[str, dict]:
    for ext_id, rec in table.items():
        if rec.get("title") and rec["title"] in task:
            return ext_id, rec
    raise NotRecorded("This tax update is not part of the recorded demo.")


def _client_named(task: str) -> str:
    for slug, rec in recordings()["profiles"].items():
        if rec["name"] in task:
            return slug
    raise NotRecorded("This client is not part of the recorded demo.")


def replay_runner(*, spec, task: str, expected_output: str, schema, model: str, pause: bool = True) -> AgentResult:
    r = recordings()
    agent = {ProfileDraft: "profiler", UpdateAnalysis: "analyst", MatchList: "matcher",
             ImpactMemo: "explainer", EmailDraftOut: "writer"}.get(schema)
    if pause and agent:
        time.sleep(PAUSE_S[agent])

    if schema is ProfileDraft:
        rec = r["profiles"][_client_named(task.split("\n", 1)[0])]
        return _result(ProfileDraft.model_validate(rec["data"]), rec)
    if schema is UpdateAnalysis:
        _, rec = _update_in(task, r["analyses"])
        return _result(UpdateAnalysis.model_validate(rec["summary"]), rec)
    if schema is MatchList:
        _, rec = _update_in(task, r["matches"])
        slugs = re.findall(r"client_id: (\w+)", task)
        matches = [ClientMatch.model_validate({"client_id": slug, **rec["clients"][slug]})
                   for slug in slugs if slug in rec["clients"]]
        return _result(MatchList(matches=matches), rec)
    if schema is ImpactMemo:
        slug = _client_named(task.split("\n", 1)[0])
        ext_id, _ = _update_in(task, r["analyses"])
        rec = r["memos"].get(f"{slug}|{ext_id}")
        if not rec:
            raise NotRecorded("No memo was recorded for this alert in the demo.")
        return _result(ImpactMemo.model_validate(rec["memo"]), rec)
    if schema is EmailDraftOut:
        slug = _client_named(task.split("\n", 1)[0])
        topics = sorted(ext for ext, rec in r["analyses"].items()
                        if rec["summary"].get("title_en") and f": {rec['summary']['title_en']}\n" in task)
        options = r["drafts"].get(slug) or {}
        rec = options.get(",".join(topics)) or (max(options.values(), key=lambda d: len(d["body"])) if options else None)
        if not rec:
            raise NotRecorded("No email was recorded for this client in the demo.")
        return _result(EmailDraftOut(subject=rec["subject"], body=rec["body"]), rec)
    raise NotRecorded("This step is not part of the recorded demo.")


replay_runner.requires_api_key = False


def reset_demo(engine) -> None:
    """Fresh demo: fictional clients with their data rooms and the six demo updates, nothing analysed yet.
    The recorded stability test is restored so the Quality page has its result."""
    from .seed import backfill_demo_details, seed_demo
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        seed_demo(session)
        backfill_demo_details(session)
        st = recordings().get("stability")
        if st:
            session.add(EvalBatch(runs_planned=st["runs_planned"], runs=st["runs"], cost_usd=st["cost_usd"], status="done"))
            session.commit()


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "export":
        sys.exit("usage: python -m app.replay export <database path>")
    data = export(f"sqlite:///{sys.argv[2]}")
    REPLAY_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    counts = {k: (len(v) if isinstance(v, dict) else bool(v)) for k, v in data.items()}
    print(f"Wrote {REPLAY_FILE}: {counts}")
