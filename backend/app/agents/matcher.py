"""Agent 3 – Impact Matcher.

For one analysed tax update:
1. Pre-filter (no AI, free): keep only clients that share a tax area or a keyword with the update.
2. Matcher (Claude Sonnet): score each remaining client 0-100 with evidence taken from its profile.
3. Verify that every piece of evidence really appears in the client profile.
4. Turn scores above the threshold into alerts for the advisor.
"""
import re

from sqlmodel import Session, select

from ..config import settings
from ..models import AgentRun, Alert, Client, ClientProfile, Match, RegulatoryUpdate, now
from .citations import quote_on_page
from .runner import AgentSpec, Runner, cost_usd, friendly_error
from .schemas import MatchList

SPEC = AgentSpec(
    role="Impact Matcher",
    goal="Decide which former clients are concretely affected by a new tax development, and prove it",
    backstory=(
        "You are a tax partner who knows every former client file. You only flag a client when the "
        "client's own documented facts meet the update's criteria, and you always check the exclusions. "
        "A false alarm costs the firm credibility; a missed client costs a mandate."
    ),
)

RULES = """The score answers one question: should the firm contact this client about this update?
It combines (a) whether the client meets the criteria and (b) whether the impact is material enough
to justify advice: a change in tax burden, a new obligation needing preparation, a risk, or an opportunity.

Scoring guide:
- 80-100: the client's documented facts clearly meet the core criteria and the impact is material.
- 60-79: very likely affected and material, but one criterion is not documented in the profile.
- 30-59: possibly affected; important facts are missing.
- 0-29: not affected, an exclusion applies, OR the client is technically in scope but the update is
  routine with nothing to advise on (e.g. a new form template, a reporting format with no change
  in substance, an editorial correction). Say so in the reasoning.

How to read the criteria:
- If "Criteria logic" is "any", each trigger criterion is a separate situation: meeting ONE is enough.
  A client that clearly meets one criterion must not be scored down because other criteria do not apply.
- If it is "all", the client must meet every criterion.
- A concrete, documented risk to a benefit the client already claims or relies on (a missing certificate,
  a deadline, a document gap putting an amount at stake) is material and worth contacting the client.

Rules:
- Use only facts written in the client profiles below. Never assume facts that are not there.
- Check every exclusion of the update against each client.
- Each evidence item's client_fact must be copied word for word from the client profile.
- Give exactly one entry per client_id listed, using the client_id exactly as written.
- Write in English."""

STOPWORDS = {
    "tax", "taxes", "taxation", "rule", "rules", "new", "from", "with", "and", "for", "the", "based", "german",
    "germany", "company", "companies", "business", "businesses", "general", "law", "letter", "bmf", "bfh",
    "ruling", "other", "update", "applies", "year", "years", "guidance", "relief", "treatment", "case",
}
GENERIC_CATEGORIES = {"Other"}


def _tokens(texts: list[str]) -> set[str]:
    words = set()
    for t in texts:
        for w in re.findall(r"[a-zäöüß0-9§]+", t.lower()):
            if len(w) >= 3 and w not in STOPWORDS:
                words.add(w)
    return words


def prefilter(analysis: dict, profile: dict) -> tuple[bool, str]:
    """Cheap first pass. Generous on purpose: the Matcher makes the real decision."""
    u_cats = set(analysis.get("tax_categories", [])) - GENERIC_CATEGORIES
    c_cats = {a["category"] for a in profile.get("tax_areas", [])} - GENERIC_CATEGORIES
    shared = sorted(u_cats & c_cats)
    if shared:
        return True, "Shared tax area: " + ", ".join(shared)
    u_words = _tokens(analysis.get("keywords", []) + analysis.get("trigger_criteria", []))
    c_words = _tokens(profile.get("keywords", []) + [a["title"] for a in profile.get("tax_areas", [])])
    common = sorted(u_words & c_words)
    if common:
        return True, "Shared keywords: " + ", ".join(common[:5])
    return False, "No shared tax area or keyword with this update."


def profile_text(slug: str, name: str, p: dict) -> str:
    lines = [f"client_id: {slug}", f"Name: {name}", f"Summary: {p.get('summary', '')}", "Key facts:"]
    lines += [f"- {f['label']}: {f['value']}" for f in p.get("key_facts", [])]
    lines.append("Tax areas:")
    for a in p.get("tax_areas", []):
        lines.append(f"- [{a['category']} | {a['assessment']}, {a['severity']}] {a['title']}: {a['summary']}")
        lines += [f"  - {f['label']}: {f['value']}" for f in a.get("facts", [])]
    lines.append("Open points:")
    lines += [f"- {f['label']}: {f['value']}" for f in p.get("open_points", [])]
    return "\n".join(lines)


def update_text(u: RegulatoryUpdate) -> str:
    a = u.summary
    return "\n".join([
        f"Title: {a['title_en']} ({u.title})",
        f"Type: {a['kind']}, published {u.published_on or 'unknown'}",
        f"Tax areas: {', '.join(a['tax_categories'])}",
        f"Summary: {a['summary']}",
        f"Who is affected: {a['who_is_affected']}",
        f"Criteria logic: {a.get('criteria_logic', 'any')} "
        f"({'every criterion must be met' if a.get('criteria_logic') == 'all' else 'one criterion is enough'})",
        "Trigger criteria:", *[f"- {c}" for c in a["trigger_criteria"]],
        "Exclusions:", *([f"- {c}" for c in a["exclusions"]] or ["- none stated"]),
        f"Applies from: {a['effective_date']}",
        "", "Original text (extract):", u.raw_text[:6000],
    ])


def latest_profiles(session: Session) -> list[tuple[Client, ClientProfile]]:
    out = []
    for c in session.exec(select(Client).order_by(Client.id)).all():
        p = session.exec(select(ClientProfile).where(ClientProfile.client_id == c.id)
                         .order_by(ClientProfile.version.desc())).first()
        if p:
            out.append((c, p))
    return out


def _upsert_match(session: Session, client_id: int, update_id: int) -> Match:
    m = session.exec(select(Match).where(Match.client_id == client_id, Match.update_id == update_id)).first()
    return m or Match(client_id=client_id, update_id=update_id)


def _sync_alert(session: Session, m: Match) -> None:
    alert = session.exec(select(Alert).where(Alert.match_id == m.id)).first()
    flagged = is_flagged(m.stage, m.score, m.verdict)
    if flagged and not alert:
        session.add(Alert(match_id=m.id))
    elif not flagged and alert and alert.status == "new":
        session.delete(alert)  # a rescan withdrew an alert nobody has acted on yet


def call_matcher(runner: Runner, u: RegulatoryUpdate, texts: dict[str, str]):
    """One Matcher call: score every shortlisted client (texts: slug -> profile text) for one update."""
    return runner(
        spec=SPEC,
        task=(f"Score how strongly each client below is affected by this tax update.\n\n{RULES}\n\n"
              f"--- UPDATE ---\n{update_text(u)}\n\n--- CLIENTS ---\n" + "\n\n".join(texts.values())),
        expected_output="One scored entry per client, with evidence copied from the profiles.",
        schema=MatchList,
        model=settings.model_reasoning,
    )


def is_flagged(stage: str, score: int | None, verdict: str | None) -> bool:
    """The alert rule, shared by alerts, the evaluation and the stability test."""
    return stage == "scored" and (score or 0) >= settings.alert_threshold and verdict != "not_affected"


def run_matcher(engine, run_id: int, update_id: int, runner: Runner) -> None:
    """Background job for one update. Errors are stored on the run, never raised."""
    with Session(engine) as session:
        run = session.get(AgentRun, run_id)
        try:
            u = session.get(RegulatoryUpdate, update_id)
            if not u.summary:
                raise ValueError("Analyse this update before scanning.")
            shortlist = []
            for client, prof in latest_profiles(session):
                keep, why = prefilter(u.summary, prof.data)
                m = _upsert_match(session, client.id, u.id)
                if keep:
                    shortlist.append((client, prof))
                else:
                    m.stage, m.score, m.verdict, m.reasoning = "filtered_out", 0, "not_affected", why
                    m.evidence, m.missing_information, m.run_id = [], [], run_id
                session.add(m)
                session.flush()
                _sync_alert(session, m)

            if shortlist:
                texts = {c.slug: profile_text(c.slug, c.name, p.data) for c, p in shortlist}
                result = call_matcher(runner, u, texts)
                by_slug = {c.slug: c for c, _ in shortlist}
                for cm in result.output.matches:
                    client = by_slug.get(cm.client_id)
                    if not client:
                        continue  # ignore any client the agent invented
                    for ev in cm.evidence:
                        ev.verified = quote_on_page(ev.client_fact, texts[cm.client_id])
                    m = _upsert_match(session, client.id, u.id)
                    m.stage, m.score, m.verdict, m.reasoning = "scored", cm.score, cm.verdict, cm.reasoning
                    m.evidence = [e.model_dump() for e in cm.evidence]
                    m.missing_information, m.run_id = cm.missing_information, run_id
                    session.add(m)
                    session.flush()
                    _sync_alert(session, m)
                missing = set(by_slug) - {cm.client_id for cm in result.output.matches}
                if missing:  # keep the scores we got, flag the gap on the run
                    run.error = f"The Matcher skipped: {', '.join(sorted(missing))}. Scan this update again."
                run.model = result.model
                run.tokens_in, run.tokens_out = result.tokens_in, result.tokens_out
                run.cost_usd = cost_usd(result.model, result.tokens_in, result.tokens_out)
                run.duration_ms = result.duration_ms
                run.attempts = result.attempts
            run.status = "done"
        except Exception as exc:
            session.rollback()
            run = session.get(AgentRun, run_id)
            run.status = "failed"
            run.error = friendly_error(exc)
        run.finished_at = now()
        session.add(run)
        session.commit()


def run_scan(engine, jobs: list[tuple[int, int]], runner: Runner) -> None:
    for run_id, update_id in jobs:
        run_matcher(engine, run_id, update_id, runner)
