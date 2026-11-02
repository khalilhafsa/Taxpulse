"""Impact Explainer and Outreach Writer (fake LLM), and the draft approval workflow."""
from app.agents.runner import get_runner
from app.main import app
from tests.test_matching import fake_matcher, prepare_demo


def _salutation(client, cid):
    return client.get(f"/api/clients/{cid}").json()["salutation"]


def scanned(client):
    prepare_demo(client)
    app.dependency_overrides[get_runner] = lambda: fake_matcher
    client.post("/api/scan", json={})
    return client.get("/api/alerts").json()


def test_accepting_an_alert_writes_its_memo(client):
    alerts = scanned(client)
    a = client.post(f"/api/alerts/{alerts[0]['id']}/status", json={"status": "accepted"}).json()
    assert a["status"] == "accepted"

    a = next(x for x in client.get("/api/alerts").json() if x["id"] == alerts[0]["id"])
    assert a["memo_status"] == "done"
    assert a["memo"]["urgency"] == "high" and a["memo"]["proposed_mandate"] == "E-invoicing readiness review"

    runs = client.get("/api/runs").json()["runs"]
    explainer = next(r for r in runs if r["agent"] == "explainer")
    assert explainer["status"] == "done" and a["client"]["name"] in explainer["subject_label"]

    # Rewriting a memo is only possible for accepted alerts.
    other = alerts[1]["id"]
    assert client.post(f"/api/alerts/{other}/memo").status_code == 400


def test_without_api_key_accept_works_but_memo_waits(client):
    alerts = scanned(client)
    app.dependency_overrides.pop(get_runner)
    client.post(f"/api/alerts/{alerts[0]['id']}/status", json={"status": "accepted"})
    a = next(x for x in client.get("/api/alerts").json() if x["id"] == alerts[0]["id"])
    assert a["status"] == "accepted" and a["memo_status"] == "none"
    assert client.post(f"/api/alerts/{alerts[0]['id']}/memo").status_code == 400


def test_email_draft_workflow(client):
    alerts = scanned(client)
    target = alerts[0]
    cid = target["client"]["id"]
    assert client.post(f"/api/clients/{cid}/draft-email").status_code == 400  # nothing accepted yet

    for a in [x for x in alerts if x["client"]["id"] == cid]:
        client.post(f"/api/alerts/{a['id']}/status", json={"status": "accepted"})
    accepted = [x for x in alerts if x["client"]["id"] == cid]

    r = client.post(f"/api/clients/{cid}/draft-email")
    assert r.status_code == 202 and r.json()["alerts"] == len(accepted)

    entry = next(e for e in client.get("/api/outreach").json() if e["client"]["id"] == cid)
    assert entry["alerts_not_in_draft"] == 0 and len(entry["drafts"]) == 1
    draft = entry["drafts"][0]
    assert draft["status"] == "draft"
    body = draft["body"]
    salutation = _salutation(client, cid)
    assert salutation.startswith("Dear ") and body.startswith(salutation + "\n\nA new rule")
    assert "Best regards" not in body and "Someone" not in body and "[Your name]" not in body
    assert body.rstrip().endswith("weber-partner.example") and "Kind regards,\n\nDr Lena Weber" in body
    assert not draft["subject"].endswith(".")
    assert sorted(draft["alert_ids"]) == sorted(a["id"] for a in accepted)

    # Sending requires approval first; editing resets approval.
    assert client.post(f"/api/drafts/{draft['id']}/status", json={"status": "sent"}).status_code == 400
    client.post(f"/api/drafts/{draft['id']}/status", json={"status": "approved"})
    edited = client.put(f"/api/drafts/{draft['id']}", json={"subject": "New subject", "body": "Dear team, hello again."}).json()
    assert edited["status"] == "draft" and edited["edited_by_user"] is True
    client.post(f"/api/drafts/{draft['id']}/status", json={"status": "approved"})
    sent = client.post(f"/api/drafts/{draft['id']}/status", json={"status": "sent"}).json()
    assert sent["status"] == "sent"
    assert client.put(f"/api/drafts/{draft['id']}", json={"subject": "x" * 5, "body": "y" * 20}).status_code == 400
    assert client.delete(f"/api/drafts/{draft['id']}").status_code == 400


def test_assemble_enforces_salutation_closing_and_signature():
    from app.agents.writer import assemble
    from app.models import FirmSettings
    firm = FirmSettings(firm_name="Acme Tax", advisor_name="Jane Roe", advisor_title="Partner", email="j@acme.example")
    out = assemble("Dear team,\n\nBody text.\n\nYours sincerely,\nJohn", "Dear Ms Smith,", firm)
    assert out == "Dear Ms Smith,\n\nBody text.\n\nKind regards,\n\nJane Roe\nPartner\nAcme Tax\nj@acme.example"
    assert assemble("Body only.", "Dear Sir or Madam,", None).endswith("[Your name]\n[Firm name]")


def test_firm_settings_and_client_contact(client):
    client.post("/api/demo/seed")
    assert client.get("/api/settings/firm").json()["firm_name"] == "Weber & Partner Steuerberatung"
    saved = client.put("/api/settings/firm", json={"firm_name": " My Firm ", "advisor_name": "Me"}).json()
    assert saved["firm_name"] == "My Firm" and saved["phone"] == ""
    cid = client.get("/api/clients").json()[0]["id"]
    c = client.put(f"/api/clients/{cid}/contact", json={"contact_name": "Eva Lang", "contact_title": "CEO",
                                                        "salutation": "Dear Ms Lang,"}).json()
    assert c["salutation"] == "Dear Ms Lang,"


# --- Partner review ---------------------------------------------------------
from app.agents.writer import caveat_sentence, ensure_caveat, review_email  # noqa: E402

REAL_DRAFT = """Dear Mr Becker,

Following our tax due diligence for Brightloop's Series B financing in 2024, I am writing about two developments.

1. E-invoicing obligation: From 1 January 2027, Brightloop must issue structured e-invoices. Your PDF invoices will not be permitted once the transition period ends, which the update does not define.

2. Loss carryforwards: Brightloop's 2023 product mirrors the facts in the ruling.

I suggest a 30-minute call within the next two weeks.

Please propose a time that suits you."""


def test_review_flags_the_three_faults_of_a_real_draft():
    issues = " ".join(review_email(REAL_DRAFT))
    assert '"the update"' in issues and '"does not define"' in issues  # internal source
    assert '"must"' in issues and '"mirrors"' in issues and '"will not be permitted"' in issues  # definitive
    assert "Missing the caveat" in issues


def test_clean_draft_passes_review():
    clean = ensure_caveat(REAL_DRAFT.replace("must", "will need to").replace(", which the update does not define", "")
                          .replace("will not be permitted", "are unlikely to be accepted").replace("mirrors", "appears similar to"),
                          "Tax due diligence – Series B financing (2024)")
    assert review_email(clean) == []


def test_caveat_goes_just_before_the_proposed_call():
    out = ensure_caveat(REAL_DRAFT, "Tax due diligence – Series B financing (2024)")
    paras = out.split("\n\n")
    i = paras.index(caveat_sentence("Series B (2024)"))
    assert "our 2024 review" in paras[i] and paras[i + 1].startswith("I suggest a 30-minute call")
    assert ensure_caveat(out, "x") == out  # never added twice


def test_flawed_first_draft_is_sent_back_once(client):
    from app.agents.runner import AgentResult
    from app.agents.schemas import EmailDraftOut
    alerts = scanned(client)
    cid = alerts[0]["client"]["id"]
    client.post(f"/api/alerts/{alerts[0]['id']}/status", json={"status": "accepted"})
    tasks = []

    def runner(**kw):
        if kw["schema"] is not EmailDraftOut:
            return fake_matcher(**kw)
        tasks.append(kw["task"])
        body = REAL_DRAFT if len(tasks) == 1 else REAL_DRAFT.replace("must", "will need to")
        return AgentResult(output=EmailDraftOut(subject="Brightloop: two tax developments", body=body),
                           model="claude-sonnet-5-5", tokens_in=1000, tokens_out=200, duration_ms=100)
    runner.requires_api_key = False
    app.dependency_overrides[get_runner] = lambda: runner

    client.post(f"/api/clients/{cid}/draft-email")
    assert len(tasks) == 2 and "PARTNER REVIEW" in tasks[1] and '"must"' in tasks[1]
    d = next(e for e in client.get("/api/outreach").json() if e["client"]["id"] == cid)["drafts"][0]
    assert d["revised"] and "our 2024 review, and your position may have changed since." in d["body"]
    assert '"the update"' in d["review_notes"] and '"must"' not in d["review_notes"]
    run = next(r for r in client.get("/api/runs").json()["runs"] if r["agent"] == "writer")
    assert run["tokens_in"] == 2000  # both rounds are billed and logged

    # The advisor fixes it by hand: the checks run again on the edited text.
    fixed = d["body"].replace(", which the update does not define", "").replace("will not be permitted", "are unlikely to be accepted").replace("mirrors", "appears similar to")
    assert client.put(f"/api/drafts/{d['id']}", json={"subject": d["subject"], "body": fixed}).json()["review_notes"] == ""


def test_advisor_remarks_produce_a_revised_version(client):
    from app.agents.runner import AgentResult
    from app.agents.schemas import EmailDraftOut
    alerts = scanned(client)
    cid = alerts[0]["client"]["id"]
    client.post(f"/api/alerts/{alerts[0]['id']}/status", json={"status": "accepted"})
    client.post(f"/api/clients/{cid}/draft-email")
    first = next(e for e in client.get("/api/outreach").json() if e["client"]["id"] == cid)["drafts"][0]
    tasks = []

    def runner(**kw):
        if kw["schema"] is not EmailDraftOut:
            return fake_matcher(**kw)
        tasks.append(kw["task"])
        return AgentResult(output=EmailDraftOut(subject="Shorter subject", body="Short version. Shall we speak next week?"),
                           model="claude-sonnet-5-5", tokens_in=1000, tokens_out=200, duration_ms=100)
    runner.requires_api_key = False
    app.dependency_overrides[get_runner] = lambda: runner

    assert client.post(f"/api/drafts/{first['id']}/revise", json={"remarks": "x"}).status_code == 422
    assert client.post(f"/api/drafts/{first['id']}/revise", json={"remarks": "Make it shorter."}).status_code == 202
    task = tasks[0]
    assert "THE ADVISOR'S REMARKS ---\nMake it shorter." in task
    assert "A new rule affects your invoicing." in task and "Dr Lena Weber" not in task.split("CURRENT EMAIL")[1]

    drafts = next(e for e in client.get("/api/outreach").json() if e["client"]["id"] == cid)["drafts"]
    assert len(drafts) == 2 and drafts[1]["id"] == first["id"]  # old version kept
    new = drafts[0]
    assert new["remarks"] == "Make it shorter." and new["status"] == "draft"
    assert new["body"].startswith(_salutation(client, cid)) and "Kind regards,\n\nDr Lena Weber" in new["body"]
    assert sorted(new["alert_ids"]) == sorted(first["alert_ids"])
    assert client.post("/api/drafts/9999/revise", json={"remarks": "Shorter"}).status_code == 404


def test_length_check_ignores_salutation_and_signature():
    from app.agents.writer import CLOSING, review_email
    letter = " ".join(["word"] * 225) + " The position may have changed since."
    signature = "\n".join(["Dr Lena Weber", "Partner, Tax Advisor (Steuerberaterin)", "Weber & Partner Steuerberatung",
                           "Berlin, Germany", "+49 30 000 000 00 | l.weber@weber-partner.example", "weber-partner.example"])
    body = f"Dear Mr Becker,\n\n{letter}\n\n{CLOSING}\n\n{signature}"
    assert len(body.split()) > 250 and review_email(body) == []
    assert any("Too long" in i for i in review_email(body.replace(letter, letter + " more" * 40)))


def _two_accepted(client):
    alerts = scanned(client)
    cid = next(a["client"]["id"] for a in alerts if a["client"]["name"].startswith("Brightloop"))
    mine = [a for a in alerts if a["client"]["id"] == cid]
    assert len(mine) >= 2
    for a in mine:
        client.post(f"/api/alerts/{a['id']}/status", json={"status": "accepted"})
    return cid, mine


def test_no_email_while_an_accepted_alert_has_no_memo(client):
    from sqlmodel import Session
    from app.db import engine
    from app.models import Alert
    cid, mine = _two_accepted(client)
    with Session(engine) as s:
        a = s.get(Alert, mine[1]["id"])
        a.memo = None
        s.add(a)
        s.commit()
    r = client.post(f"/api/clients/{cid}/draft-email")
    assert r.status_code == 409 and "every accepted alert has its memo" in r.json()["detail"]
    assert mine[1]["update"]["title"] in r.json()["detail"]


def test_email_must_cover_every_topic(client):
    from app.agents.runner import AgentResult
    from app.agents.schemas import EmailDraftOut
    cid, mine = _two_accepted(client)
    tasks = []

    def runner(**kw):
        if kw["schema"] is not EmailDraftOut:
            return fake_matcher(**kw)
        tasks.append(kw["task"])
        n = len(mine) if len(tasks) > 1 else 1  # the first draft forgets topics, the revision covers them all
        body = "\n\n".join(f"{i}. Topic {i}: it may affect you." for i in range(1, n + 1)) + \
            "\n\nThe position may have changed since. Shall we speak?"
        return AgentResult(output=EmailDraftOut(subject="Two topics", body=body), model="claude-sonnet-5-5",
                           tokens_in=10, tokens_out=10, duration_ms=1)
    runner.requires_api_key = False
    app.dependency_overrides[get_runner] = lambda: runner
    client.post(f"/api/clients/{cid}/draft-email")
    assert f"there are {len(mine)} topic(s)" in tasks[0]
    assert len(tasks) == 2 and f"Covers 1 of {len(mine)} topics" in tasks[1]
    d = next(e for e in client.get("/api/outreach").json() if e["client"]["id"] == cid)["drafts"][0]
    assert d["revised"] and "Covers" not in d["review_notes"]


def test_rewrite_includes_alerts_accepted_since(client):
    alerts = scanned(client)
    cid = next(a["client"]["id"] for a in alerts if a["client"]["name"].startswith("Brightloop"))
    mine = [a for a in alerts if a["client"]["id"] == cid]
    client.post(f"/api/alerts/{mine[0]['id']}/status", json={"status": "accepted"})
    client.post(f"/api/clients/{cid}/draft-email")
    first = next(e for e in client.get("/api/outreach").json() if e["client"]["id"] == cid)["drafts"][0]
    assert first["alert_ids"] == [mine[0]["id"]]
    client.post(f"/api/alerts/{mine[1]['id']}/status", json={"status": "accepted"})
    client.post(f"/api/drafts/{first['id']}/revise", json={"remarks": "Shorter please."})
    latest = next(e for e in client.get("/api/outreach").json() if e["client"]["id"] == cid)["drafts"][0]
    assert sorted(latest["alert_ids"]) == sorted([mine[0]["id"], mine[1]["id"]])
