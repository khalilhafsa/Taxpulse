"""Agent 5 – Outreach Writer.

Writes one email per client that combines all accepted alerts with a memo. The
salutation comes from the client record and the closing and signature from the
firm settings, so they are always exact. The agent writes what lies in between.
The email is only a draft: the advisor edits and approves it; TaxPulse never sends it.
"""
import re

from sqlmodel import Session, select

from ..config import settings
from ..models import AgentRun, Alert, Client, EmailDraft, FirmSettings, Match, RegulatoryUpdate, now
from .runner import AgentSpec, Runner, cost_usd, friendly_error
from .schemas import EmailDraftOut

SPEC = AgentSpec(
    role="Senior Client Communications Writer",
    goal="Write a polished, partner-level email that gives a former client a concrete, well-founded reason to talk again",
    backstory=(
        "You write client correspondence for the partners of a German tax advisory firm. Your emails read "
        "like they come from a senior partner: precise, courteous, confident and brief. Executives answer "
        "them because every sentence is specific to their company and useful to them. You never use "
        "marketing language, exclamation marks, emojis or filler phrases such as 'I hope this email finds you well'."
    ),
)

CLOSING = "Kind regards,"

STRUCTURE = """Write the email body in this exact structure, in plain text (no markdown, no bold, no bullet symbols other than numbers):

1. Salutation: the first line is exactly: {salutation}
2. Opening (1-2 sentences): refer to the earlier engagement ({mandate}) and state the purpose of the email.
3. Topics: there are {n_topics} topic(s) in the memos below and the email must cover every one of them, none
   left out and none merged. For each development, one short paragraph. If there are two or more, number them "1." "2." and start
   each with a short title followed by a colon. In each paragraph say what changed and why it matters to
   {company} specifically, using the company's own facts. Mention a deadline only if the memo states one.
   Name the source as the client would recognise it (e.g. "a recent BMF letter", "a BFH ruling of <date>, case
   <number>" when the memo gives them). Phrase the impact with professional caution: "is likely to", "may".
   After the topics, add this sentence as its own paragraph: {caveat}
4. Proposed next step (1-2 sentences): offer a short call or meeting to review the points together, and say
   concretely what the firm would look at (based on the proposed engagements). Suggest a 30-minute call within
   the next two weeks.
5. Courteous close (1 sentence), e.g. inviting them to propose a time or to reply with questions.
Stop there. Do NOT write the closing formula, your name, the firm name or any signature: they are added automatically.

Style rules:
- British business English, formal but warm. Short sentences. Active voice.
- No guarantees and no definitive tax advice; describe the issue and offer to review it. Do not use "must",
  "will lose", "certainly", "clearly" or "mirrors" about the client's situation: write "would need to",
  "is likely to", "may", "appears similar to".
- Use only facts from the memos. Never invent figures, dates, names or legal references.
- Write as the advisor, never as a tool: never mention "the update", "the alert", "the memo", "the system",
  "TaxPulse" or what a source "does not define". If a detail is unknown (e.g. an end date), either leave it
  out or say it has not yet been confirmed.
- 150 to 230 words, excluding the salutation.
- Subject line: specific and professional, naming the company and the topic(s), max 80 characters, no 'Re:' and no punctuation at the end."""


def signature(firm: FirmSettings | None) -> str:
    if not firm or not (firm.advisor_name or firm.firm_name):
        return "[Your name]\n[Firm name]"
    lines = [firm.advisor_name, firm.advisor_title, firm.firm_name, firm.address]
    contact = " | ".join(x for x in [firm.phone, firm.email] if x)
    lines += [contact, firm.website]
    return "\n".join(x for x in lines if x)


def salutation_for(client: Client) -> str:
    s = client.salutation.strip()
    if s:
        return s if s.endswith(",") else s + ","
    return "Dear Sir or Madam,"


_CLOSINGS = re.compile(r"^\s*(kind regards|best regards|warm regards|regards|sincerely|yours sincerely|yours faithfully|"
                       r"best wishes|mit freundlichen grüßen)[,.!]?\s*$", re.I | re.M)


def assemble(body: str, salutation: str, firm: FirmSettings | None) -> str:
    """Enforce the exact salutation, drop any closing the model added, append closing and signature."""
    text = body.strip()
    m = _CLOSINGS.search(text)
    if m:
        text = text[:m.start()].rstrip()
    first, _, rest = text.partition("\n")
    if first.strip().lower().startswith("dear"):
        text = rest.lstrip("\n")
    return f"{salutation}\n\n{text.strip()}\n\n{CLOSING}\n\n{signature(firm)}"


# --- Quality review -------------------------------------------------------
# Deterministic checks a partner would make before sending. The model gets one
# chance to revise; the caveat is then guaranteed by code, and anything still
# wrong is shown to the advisor next to the draft.

INTERNAL = re.compile(
    r"\b(the|this|that|our) (update|alert|memo|memos|system|tool|database|data room profile)\b"
    r"|\btaxpulse\b|\bdoes not (define|specify|state|mention|say)\b|\bnot (defined|specified) in\b", re.I)
DEFINITIVE = re.compile(
    r"\bmust\b|\bwill (lose|not be (permitted|allowed|accepted|deductible))\b|\bwill be (lost|denied|disallowed)\b"
    r"|\b(certainly|definitely|clearly|undoubtedly|guarantee[sd]?)\b|\bmirrors?\b|\bis not allowed\b", re.I)
CAVEAT = re.compile(r"\b(may|might|could) have changed\b|\bhas since changed\b", re.I)


def review_email(body: str) -> list[str]:
    """Return the problems a senior partner would flag; empty list means ready for the advisor."""
    issues = []
    for m in sorted({m.group(0) for m in INTERNAL.finditer(body)}, key=str.lower):
        issues.append(f'Refers to an internal source ("{m}"). Write as the advisor and name the source as the client knows it, or leave the detail out.')
    for m in sorted({m.group(0) for m in DEFINITIVE.finditer(body)}, key=str.lower):
        issues.append(f'Definitive wording ("{m}"). Rephrase with professional caution, e.g. "is likely to", "may", "would need to".')
    if not CAVEAT.search(body):
        issues.append("Missing the caveat that the assessment rests on the earlier review and the position may have changed since.")
    # Count the letter itself: the salutation, closing and signature are added by TaxPulse.
    words = len(email_core(body).split())
    if words > 250:
        issues.append(f"Too long ({words} words without the signature). Keep it between 150 and 230 words.")
    return issues


def caveat_sentence(mandate: str) -> str:
    year = re.search(r"\b(19|20)\d{2}\b", mandate or "")
    review = f"our {year.group(0)} review" if year else "our earlier review"
    return f"This assessment is based on the information from {review}, and your position may have changed since."


def ensure_caveat(body: str, mandate: str) -> str:
    """Insert the caveat as its own paragraph just before the proposed next step."""
    if CAVEAT.search(body):
        return body
    paras = [p for p in re.split(r"\n\s*\n", body.strip()) if p.strip()]
    idx = next((i for i, p in enumerate(paras) if i > 0 and re.search(r"\b(call|meeting|meet|discuss)\b", p, re.I)),
               len(paras) - 1 if len(paras) > 3 else len(paras))
    paras.insert(idx, caveat_sentence(mandate))
    return "\n\n".join(paras)


def topic_coverage(body: str, n_topics: int) -> list[str]:
    """With two or more topics, each must have its own numbered paragraph."""
    if n_topics < 2:
        return []
    numbered = {int(n) for n in re.findall(r"(?m)^\s*(\d+)[.)]\s", email_core(body))}
    covered = len(numbered & set(range(1, n_topics + 1)))
    if covered < n_topics:
        return [f"Covers {covered} of {n_topics} topics. Every topic in the memos needs its own numbered paragraph."]
    return []


def accepted_without_memo(session: Session, client_id: int) -> list[Alert]:
    """Accepted alerts of this client whose memo is not written yet (running, failed or missing)."""
    out = []
    for a in session.exec(select(Alert).where(Alert.status == "accepted").order_by(Alert.id)).all():
        if session.get(Match, a.match_id).client_id == client_id and not a.memo:
            out.append(a)
    return out


def alerts_for_email(session: Session, client_id: int) -> list[Alert]:
    """Accepted alerts of this client that already have a memo."""
    out = []
    for a in session.exec(select(Alert).where(Alert.status == "accepted").order_by(Alert.id)).all():
        m = session.get(Match, a.match_id)
        if m.client_id == client_id and a.memo:
            out.append(a)
    return out


def email_core(body: str) -> str:
    """The part of a stored email the writer may change: without salutation, closing and signature."""
    text = body.split(f"\n\n{CLOSING}\n\n")[0].strip()
    first, _, rest = text.partition("\n")
    return rest.strip() if first.strip().lower().startswith("dear") else text


def run_writer(engine, run_id: int, client_id: int, alert_ids: list[int], runner: Runner,
               previous_id: int | None = None, remarks: str = "") -> None:
    """Write a new email, or (with previous_id and remarks) revise an existing one following the advisor's remarks."""
    with Session(engine) as session:
        run = session.get(AgentRun, run_id)
        try:
            client = session.get(Client, client_id)
            firm = session.get(FirmSettings, 1)
            salutation = salutation_for(client)
            blocks = []
            for i, aid in enumerate(alert_ids, start=1):
                a = session.get(Alert, aid)
                u = session.get(RegulatoryUpdate, session.get(Match, a.match_id).update_id)
                memo = a.memo
                blocks.append(
                    f"Topic {i}: {(u.summary or {}).get('title_en', u.title)}\n"
                    f"Headline: {memo['headline']}\nImpact: {memo['impact']}\n"
                    f"Urgency: {memo['urgency']} (deadline: {memo['deadline']})\n"
                    f"Suggested next steps: {'; '.join(memo['recommended_actions'])}\n"
                    f"Engagement the firm can offer: {memo['proposed_mandate']}")
            recipient = ", ".join(x for x in [client.contact_name, client.contact_title] if x) or "the management"
            task = (f"Write an email from {firm.advisor_name if firm and firm.advisor_name else 'a partner'} of "
                    f"{firm.firm_name if firm and firm.firm_name else 'our firm'} to {recipient} at {client.name}.\n\n"
                    + STRUCTURE.format(salutation=salutation, mandate=client.mandate or "our earlier work",
                                       company=client.name, caveat=caveat_sentence(client.mandate),
                                       n_topics=len(alert_ids))
                    + "\n\n--- MEMOS ---\n" + "\n\n".join(blocks))
            if previous_id:
                prev = session.get(EmailDraft, previous_id)
                task += ("\n\n--- CURRENT EMAIL (written earlier, possibly edited by the advisor) ---\nSubject: "
                         + prev.subject + "\n\n" + email_core(prev.body)
                         + "\n\n--- THE ADVISOR'S REMARKS ---\n" + remarks.strip()
                         + "\n\nRevise the CURRENT EMAIL so that every remark is applied. The advisor's remarks take "
                           "priority over the structure and style rules above. Facts the advisor states in the remarks "
                           "may be used. Keep everything the remarks do not ask to change. Return the full revised "
                           "subject and body.")
            calls = [runner(spec=SPEC, task=task, schema=EmailDraftOut, model=settings.model_reasoning,
                            expected_output="A subject line and the email body from the salutation to the courteous close.")]
            draft = calls[-1].output
            issues = review_email(draft.body) + topic_coverage(draft.body, len(alert_ids))
            if issues:  # one revision round, like a partner sending a draft back
                calls.append(runner(
                    spec=SPEC, schema=EmailDraftOut, model=settings.model_reasoning,
                    task=(task + "\n\n--- YOUR DRAFT ---\nSubject: " + draft.subject + "\n\n" + draft.body
                          + "\n\n--- PARTNER REVIEW: fix every point, keep everything else ---\n- " + "\n- ".join(issues)),
                    expected_output="The revised subject line and email body."))
                draft = calls[-1].output
            body = ensure_caveat(assemble(draft.body, salutation, firm).split(f"\n\n{CLOSING}\n\n")[0],
                                 client.mandate)
            body = f"{body}\n\n{CLOSING}\n\n{signature(firm)}"
            remaining = [i for i in review_email(body) + topic_coverage(body, len(alert_ids))
                         if not i.startswith("Missing the caveat")]
            session.add(EmailDraft(client_id=client_id, alert_ids=alert_ids,
                                   subject=draft.subject.strip().rstrip("."), body=body,
                                   review_notes="\n".join(remaining), revised=len(calls) > 1,
                                   remarks=remarks.strip(), run_id=run_id))
            result = calls[-1]
            tokens_in, tokens_out = sum(c.tokens_in for c in calls), sum(c.tokens_out for c in calls)
            run.status = "done"
            run.model = result.model
            run.tokens_in, run.tokens_out = tokens_in, tokens_out
            run.cost_usd = cost_usd(result.model, tokens_in, tokens_out)
            run.duration_ms = sum(c.duration_ms for c in calls)
            run.attempts = 1 + sum(c.attempts - 1 for c in calls)
        except Exception as exc:
            session.rollback()
            run = session.get(AgentRun, run_id)
            run.status = "failed"
            run.error = friendly_error(exc)
        run.finished_at = now()
        session.add(run)
        session.commit()
