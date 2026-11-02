"""Quality checks: Matcher stability over repeated runs, and the figures behind the Quality page.

An LLM does not answer identically every time. The stability test asks the Impact Matcher to score
the hand-labelled demo pairs several times (nothing is written to matches or alerts) and measures
how often each run finds the affected clients, how many false alerts it raises, and whether the
alert decision for each pair stays the same from run to run.
"""
import json
import statistics
import uuid

from sqlmodel import Session, select

from .agents.matcher import call_matcher, is_flagged, latest_profiles, prefilter, profile_text
from .agents.runner import Runner, cost_usd, friendly_error
from .config import settings
from .models import AgentRun, EmailDraft, EvalBatch, RegulatoryUpdate, now


def labels() -> dict[tuple[str, str], str]:
    data = json.loads((settings.demo_dir / "expected_matches.json").read_text(encoding="utf-8"))["labels"]
    return {(lab["client"], lab["update"]): lab["label"] for lab in data}


def stability_inputs(session: Session):
    """Demo clients with a profile and analysed demo updates; None and a reason if not ready."""
    profiles = [(c, p) for c, p in latest_profiles(session) if c.is_demo]
    updates = [u for u in session.exec(select(RegulatoryUpdate).where(RegulatoryUpdate.source == "demo")
                                       .order_by(RegulatoryUpdate.id)).all() if u.summary]
    if not profiles or not updates:
        return None, ("The stability test uses the demo data. Load the demo data, then run the agents "
                      "so the demo clients have profiles and the demo updates are analysed.")
    return (profiles, updates), ""


def run_stability(engine, batch_id: int, runner: Runner) -> None:
    """Background job: n repetitions of the Matcher on every demo update. Each call is logged as a run."""
    pipeline = f"eval-{batch_id}-{uuid.uuid4().hex[:6]}"
    with Session(engine) as session:
        batch = session.get(EvalBatch, batch_id)
        try:
            inputs, why = stability_inputs(session)
            if not inputs:
                raise ValueError(why)
            profiles, updates = inputs
            for index in range(1, batch.runs_planned + 1):
                pairs, cost = {}, 0.0
                for u in updates:
                    shortlist = []
                    for c, p in profiles:
                        keep, _ = prefilter(u.summary, p.data)
                        if keep:
                            shortlist.append((c, p))
                        else:
                            pairs[f"{c.slug}|{u.external_id}"] = {"stage": "filtered_out", "score": 0,
                                                                  "verdict": "not_affected", "flagged": False}
                    if not shortlist:
                        continue
                    run = AgentRun(pipeline_id=pipeline, agent="matcher", subject=f"eval:{batch_id}",
                                   model=settings.model_reasoning.split("/", 1)[-1])
                    session.add(run)
                    session.commit()
                    try:
                        texts = {c.slug: profile_text(c.slug, c.name, p.data) for c, p in shortlist}
                        result = call_matcher(runner, u, texts)
                        for cm in result.output.matches:
                            if cm.client_id in texts:
                                pairs[f"{cm.client_id}|{u.external_id}"] = {
                                    "stage": "scored", "score": cm.score, "verdict": cm.verdict,
                                    "flagged": is_flagged("scored", cm.score, cm.verdict)}
                        run.status, run.model = "done", result.model
                        run.tokens_in, run.tokens_out = result.tokens_in, result.tokens_out
                        run.cost_usd = cost_usd(result.model, result.tokens_in, result.tokens_out)
                        run.duration_ms, run.attempts = result.duration_ms, result.attempts
                        cost += run.cost_usd
                    except Exception as exc:
                        run.status, run.error = "failed", friendly_error(exc)
                        raise
                    finally:
                        run.finished_at = now()
                        session.add(run)
                        session.commit()
                batch = session.get(EvalBatch, batch_id)
                batch.runs = [*batch.runs, {"index": index, "pairs": pairs, "cost_usd": round(cost, 5)}]
                batch.cost_usd = round(batch.cost_usd + cost, 5)
                session.add(batch)
                session.commit()
            batch.status = "done"
        except Exception as exc:
            session.rollback()
            batch = session.get(EvalBatch, batch_id)
            batch.status, batch.error = "failed", friendly_error(exc)
        batch.finished_at = now()
        session.add(batch)
        session.commit()


def summarise(batch: EvalBatch) -> dict:
    """Recall, false alerts and consistency across the runs of one stability test."""
    lab = labels()
    per_run = []
    for r in batch.runs:
        pairs = r["pairs"]
        aff = [k for k, v in lab.items() if v == "affected" and f"{k[0]}|{k[1]}" in pairs]
        neg = [k for k, v in lab.items() if v == "not_affected" and f"{k[0]}|{k[1]}" in pairs]
        per_run.append({
            "index": r["index"], "cost_usd": r["cost_usd"],
            "affected_found": sum(1 for k in aff if pairs[f"{k[0]}|{k[1]}"]["flagged"]), "affected_total": len(aff),
            "false_alerts": sum(1 for k in neg if pairs[f"{k[0]}|{k[1]}"]["flagged"]), "not_affected_total": len(neg),
        })

    # Consistency: pairs the Matcher actually scored in every run, same alert decision each time.
    keys = set.intersection(*(set(k for k, v in r["pairs"].items() if v["stage"] == "scored") for r in batch.runs)) \
        if batch.runs else set()
    unstable, spreads = [], []
    for key in sorted(keys):
        scores = [r["pairs"][key]["score"] for r in batch.runs]
        flags = [r["pairs"][key]["flagged"] for r in batch.runs]
        spreads.append(max(scores) - min(scores))
        if len(set(flags)) > 1:
            client, update = key.split("|")
            unstable.append({"client": client, "update": update, "scores": scores, "flagged": flags,
                             "expected": lab.get((client, update), "unlabelled")})
    n = len(keys)
    clear = [k for k in keys if lab.get(tuple(k.split("|"))) in ("affected", "not_affected")]
    clear_unstable = sum(1 for u in unstable if u["expected"] in ("affected", "not_affected"))
    found = [r["affected_found"] for r in per_run]
    false = [r["false_alerts"] for r in per_run]
    return {
        "id": batch.id, "status": batch.status, "error": batch.error, "runs_planned": batch.runs_planned,
        "runs_done": len(batch.runs), "cost_usd": round(batch.cost_usd, 4),
        "started_at": batch.started_at, "finished_at": batch.finished_at,
        "per_run": per_run,
        "scored_pairs": n,
        "consistent_pairs": n - len(unstable),
        "consistency": round((n - len(unstable)) / n, 3) if n else None,
        "clear_pairs": len(clear),
        "clear_consistency": round((len(clear) - clear_unstable) / len(clear), 3) if clear else None,
        "mean_score_spread": round(statistics.mean(spreads), 1) if spreads else None,
        "max_score_spread": max(spreads) if spreads else None,
        "affected_found_min": min(found) if found else None,
        "affected_found_mean": round(statistics.mean(found), 2) if found else None,
        "false_alerts_max": max(false) if false else None,
        "affected_total": per_run[0]["affected_total"] if per_run else None,
        "not_affected_total": per_run[0]["not_affected_total"] if per_run else None,
        "unstable_pairs": unstable,
        "perfect_runs": sum(1 for r in per_run if r["affected_found"] == r["affected_total"] and r["false_alerts"] == 0),
    }


def report(session: Session) -> dict:
    """Everything on the Quality page."""
    from .evaluation import evaluate
    from .agents.runner import monthly_budget, spent_this_month

    batch = session.exec(select(EvalBatch).order_by(EvalBatch.id.desc())).first()

    verified = total = 0
    for _, p in latest_profiles(session):
        v = (p.data or {}).get("verification") or {}
        verified += v.get("verified", 0)
        total += v.get("total", 0)

    drafts = session.exec(select(EmailDraft)).all()
    ai_drafts = [d for d in drafts if d.run_id]
    runs = session.exec(select(AgentRun)).all()
    finished = [r for r in runs if r.status != "running"]
    agents = {}
    for r in finished:
        a = agents.setdefault(r.agent, {"agent": r.agent, "runs": 0, "failed": 0, "cost_usd": 0.0, "duration_ms": 0,
                                        "tokens": 0, "model": r.model})
        a["runs"] += 1
        a["failed"] += r.status == "failed"
        a["cost_usd"] += r.cost_usd
        a["duration_ms"] += r.duration_ms if r.status == "done" else 0
        a["tokens"] += r.tokens_in + r.tokens_out
    order = ["profiler", "analyst", "matcher", "explainer", "writer"]
    per_agent = []
    for k in order:
        if k in agents:
            a = agents[k]
            ok = a["runs"] - a["failed"]
            per_agent.append({**a, "cost_usd": round(a["cost_usd"], 4),
                              "avg_cost_usd": round(a["cost_usd"] / a["runs"], 4),
                              "avg_duration_ms": int(a["duration_ms"] / ok) if ok else 0,
                              "success_rate": round(ok / a["runs"], 3)})

    return {
        "matcher_accuracy": evaluate(session),
        "stability": summarise(batch) if batch else None,
        "citations": {"verified": verified, "total": total, "profiles": len(latest_profiles(session))},
        "emails": {"drafts": len(ai_drafts),
                   "passed_first_time": sum(1 for d in ai_drafts if not d.revised and not d.review_notes),
                   "fixed_by_revision": sum(1 for d in ai_drafts if d.revised and not d.review_notes),
                   "still_flagged": sum(1 for d in ai_drafts if d.review_notes)},
        "reliability": {"runs": len(finished), "failed": sum(1 for r in finished if r.status == "failed"),
                        "retried": sum(1 for r in finished if r.attempts > 1),
                        "interrupted": sum(1 for r in finished if r.error.startswith("Interrupted"))},
        "per_agent": per_agent,
        "budget": {"monthly_usd": monthly_budget(), "spent_this_month_usd": round(spent_this_month(), 4)},
    }


def recover_interrupted(session: Session) -> int:
    """At start-up, runs still marked running were cut off by a restart: mark them failed so nothing waits on them."""
    stuck = session.exec(select(AgentRun).where(AgentRun.status == "running")).all()
    for r in stuck:
        r.status = "failed"
        r.error = "Interrupted: TaxPulse was restarted while this agent was working. Run it again."
        r.finished_at = now()
        session.add(r)
    for b in session.exec(select(EvalBatch).where(EvalBatch.status == "running")).all():
        b.status, b.error, b.finished_at = "failed", "Interrupted: TaxPulse was restarted during the test.", now()
        session.add(b)
    session.commit()
    return len(stuck)

