"""Measure the Matcher against hand-labelled answers (data/demo/expected_matches.json).

Run from the backend folder:  python -m app.evaluation
"""
import json

from sqlmodel import Session, select

from .config import settings
from .db import engine, init_db
from .models import Client, Match, RegulatoryUpdate


def evaluate(session: Session) -> dict:
    labels = json.loads((settings.demo_dir / "expected_matches.json").read_text(encoding="utf-8"))["labels"]
    clients = {c.slug: c for c in session.exec(select(Client)).all()}
    updates = {u.external_id: u for u in session.exec(select(RegulatoryUpdate)).all()}

    rows, not_evaluated = [], 0
    for lab in labels:
        c, u = clients.get(lab["client"]), updates.get(lab["update"])
        m = c and u and session.exec(select(Match).where(Match.client_id == c.id, Match.update_id == u.id)).first()
        if not m or m.stage == "prefiltered":
            not_evaluated += 1
            continue
        flagged = m.stage == "scored" and (m.score or 0) >= settings.alert_threshold and m.verdict != "not_affected"
        rows.append({"client": c.name, "update": (u.summary or {}).get("title_en", u.title), "expected": lab["label"],
                     "score": m.score, "flagged": flagged, "stage": m.stage, "why_expected": lab["why"]})

    affected = [r for r in rows if r["expected"] == "affected"]
    not_affected = [r for r in rows if r["expected"] == "not_affected"]
    missed = [r for r in affected if not r["flagged"]]
    false_alerts = [r for r in not_affected if r["flagged"]]
    from .models import Alert
    demo_ids = {u.id for u in updates.values() if u.source == "demo"}
    alerts_demo = alerts_other = 0
    for a in session.exec(select(Alert)).all():
        m = session.get(Match, a.match_id)
        if m.update_id in demo_ids:
            alerts_demo += 1
        else:
            alerts_other += 1
    return {
        "alerts_on_demo_updates": alerts_demo,
        "alerts_on_other_updates": alerts_other,
        "labelled_pairs": len(labels),
        "evaluated_pairs": len(rows),
        "not_evaluated": not_evaluated,
        "affected_total": len(affected),
        "affected_found": len(affected) - len(missed),
        "not_affected_total": len(not_affected),
        "false_alerts": len(false_alerts),
        "missed": missed,
        "false_alert_details": false_alerts,
        "threshold": settings.alert_threshold,
    }


def main() -> None:
    init_db()
    with Session(engine) as session:
        r = evaluate(session)
    print(f"Evaluated {r['evaluated_pairs']} of {r['labelled_pairs']} labelled pairs "
          f"(threshold {r['threshold']}, {r['not_evaluated']} not scanned yet)")
    print(f"Affected clients found: {r['affected_found']} / {r['affected_total']}")
    print(f"False alerts:           {r['false_alerts']} / {r['not_affected_total']}")
    for m in r["missed"]:
        print(f"  MISSED  {m['client']} x {m['update']} (score {m['score']}) - expected because: {m['why_expected']}")
    for f in r["false_alert_details"]:
        print(f"  FALSE   {f['client']} x {f['update']} (score {f['score']})")


if __name__ == "__main__":
    main()
