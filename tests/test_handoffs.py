import datetime

import pytest

import app as app_module
import muse

ROLES = [{"id": "md", "title": "MD", "reports_to": None, "headcount": 1},
         {"id": "sales", "title": "Sales Lead", "reports_to": "md", "headcount": 2},
         {"id": "ops", "title": "Ops Lead", "reports_to": "md", "headcount": 3},
         {"id": "finance", "title": "Finance Lead", "reports_to": "md", "headcount": 2}]
GOOD = {"customer": "Acme", "route": "Hanoi-Haiphong", "pallets": 10, "price": 1800, "cost": 1500,
        "delivery_date": (datetime.date.today() + datetime.timedelta(days=10)).isoformat()}


@pytest.fixture
def client():
    # FAKE_AI is on: every model answer is demo mode, so the model layer says needs_human_check.
    return app_module.create_app().test_client()


@pytest.fixture
def team(client):
    h = {"X-Sandbox": client.post("/api/sandbox").json["sandbox"]}
    client.post("/api/company", json={"company": "Acme", "roles": ROLES, "size": 20}, headers=h)
    for role in ("sales", "ops", "finance"):
        client.post("/api/assistants", json={"role_id": role}, headers=h)

    def person(role):
        return client.post("/api/invites", json={"role_id": role}, headers=h).json["token"]
    return {"h": h, "sales": person("sales"), "sales2": person("sales"), "ops": person("ops"),
            "ops2": person("ops"), "finance": person("finance")}


def send(client, token, to="ops", due=None, values=None):
    return client.post("/api/handoffs", json={"token": token, "to_role": to, "due": due,
                                              "values": {**GOOD, **(values or {})}})


def decide(client, token, pid, decision, reason=None):
    return client.post(f"/api/handoffs/{pid}/decision",
                       json={"token": token, "decision": decision, "reason": reason})


def claim(client, token, pid):
    return client.post(f"/api/handoffs/{pid}/claim", json={"token": token})


def inbox(client, token):
    return client.get("/api/inbox", query_string={"token": token}).json


def test_handoff_only_along_a_declared_edge(client, team):
    assert send(client, team["sales"], to="finance").status_code == 403


def test_missing_fields_are_refused(client, team):
    r = send(client, team["sales"], values={"customer": ""})
    assert r.status_code == 400 and "customer" in r.json["message"]


def test_sent_package_sits_in_the_receiving_teams_queue(client, team):
    pid = send(client, team["sales"]).json["id"]
    got = inbox(client, team["ops"])
    assert [p["id"] for p in got["packages"]] == [pid]
    assert got["packages"][0]["can_claim"] is True and got["today"]["in_team_queue"] == 1
    assert inbox(client, team["finance"])["packages"] == []


def test_claim_is_exclusive_and_unclaim_releases(client, team):
    pid = send(client, team["sales"]).json["id"]
    assert claim(client, team["ops"], pid).status_code == 200
    assert claim(client, team["ops2"], pid).status_code == 409
    assert client.post(f"/api/handoffs/{pid}/unclaim", json={"token": team["ops"]}).status_code == 200
    assert claim(client, team["ops2"], pid).status_code == 200


def test_sender_cannot_claim_or_decide_their_own_package(client, team):
    pid = send(client, team["sales"]).json["id"]
    assert claim(client, team["sales"], pid).status_code in (403, 409)
    assert decide(client, team["sales"], pid, "accept").status_code in (403, 409)


def test_a_person_of_another_role_cannot_claim(client, team):
    pid = send(client, team["sales"]).json["id"]
    assert claim(client, team["finance"], pid).status_code == 403


def test_must_claim_before_deciding(client, team):
    pid = send(client, team["sales"]).json["id"]
    assert decide(client, team["ops"], pid, "accept").status_code == 409


def test_blocked_package_cannot_be_accepted_but_can_be_returned(client, team):
    pid = send(client, team["sales"], values={"price": 1000, "cost": 1500}).json["id"]
    claim(client, team["ops"], pid)
    assert decide(client, team["ops"], pid, "accept").status_code == 409
    assert decide(client, team["ops"], pid, "return").status_code == 400
    r = decide(client, team["ops"], pid, "return", "Price is below cost")
    assert r.json["state"] == "returned" and r.json["return_reason"] == "Price is below cost"


def test_returned_package_can_be_fixed_and_resent_only_by_the_sender(client, team):
    pid = send(client, team["sales"], values={"price": 1000, "cost": 1500}).json["id"]
    claim(client, team["ops"], pid)
    decide(client, team["ops"], pid, "return", "Fix the price")
    assert inbox(client, team["sales"])["today"]["returned_to_me"] == 1

    def resend(tok):
        return client.post(f"/api/handoffs/{pid}/resend", json={"token": tok, "values": GOOD})
    assert resend(team["sales2"]).status_code == 409
    r = resend(team["sales"])
    assert r.status_code == 200 and r.json["state"] == "sent" and r.json["check_status"] != "blocked"


def test_accept_ends_a_one_stage_chain(client, team):
    pid = send(client, team["sales"]).json["id"]
    claim(client, team["ops"], pid)
    assert decide(client, team["ops"], pid, "accept").json["state"] == "accepted"


def test_price_above_the_limit_goes_to_the_top_role_after_the_receiver(client, team):
    pid = send(client, team["sales"], values={"price": 60000, "cost": 40000}).json["id"]
    assert inbox(client, team["ops"])["packages"][0]["chain"] == ["ops", "md"]
    claim(client, team["ops"], pid)
    assert decide(client, team["ops"], pid, "accept").json["state"] == "sent"
    md = client.post("/api/invites", json={"role_id": "md"}, headers=team["h"]).json["token"]
    assert claim(client, md, pid).status_code == 200
    assert decide(client, md, pid, "accept").json["state"] == "accepted"


def test_overdue_is_a_property_of_the_package(client, team):
    soon = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
    pid = send(client, team["sales"], due=soon).json["id"]
    assert inbox(client, team["ops"])["packages"][0]["overdue"] is False
    db = client.application.config["STORE"]
    sandbox = db.person_by_token(team["sales"])["sandbox_id"]
    package = db.get_package(sandbox, pid)  # time passes: the date falls behind
    package["due"] = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    db.save_package(sandbox, package)
    got = inbox(client, team["ops"])
    assert got["packages"][0]["overdue"] is True and got["today"]["overdue_for_my_role"] == 1


def test_precheck_stores_nothing(client, team):
    before = inbox(client, team["sales"])
    r = client.post("/api/precheck", json={"token": team["sales"], "values": {**GOOD, "price": 10}})
    assert r.status_code == 200 and r.json["status"] == "blocked"
    assert inbox(client, team["sales"]) == before


def test_model_can_only_raise_a_blocked_status(client, team, monkeypatch):
    monkeypatch.delenv("FAKE_AI", raising=False)
    clear = muse._result(muse.SPARK, False,
                         text='{"status": "clear", "findings": [], "summary": "fine"}')
    monkeypatch.setattr(muse, "complete", lambda *a, **k: clear)
    r = send(client, team["sales"], values={"price": 1000, "cost": 1500})
    assert r.json["check_status"] == "blocked"


def test_views_never_leak_tokens_and_decisions_name_roles_not_people(client, team):
    pid = send(client, team["sales"]).json["id"]
    claim(client, team["ops"], pid)
    decide(client, team["ops"], pid, "accept")
    dump = client.get("/api/inbox", query_string={"token": team["ops"]}).get_data(as_text=True)
    assert all(t not in dump for t in (team["sales"], team["ops"], team["ops2"]))
    db = client.application.config["STORE"]
    assert db.decisions_for(pid) == [{"kind": "accept", "role_id": "ops", "reason": "",
                                      "day": datetime.date.today().isoformat()}]


def test_expired_link_gets_410_on_every_inbox_route(client):
    assert client.get("/api/inbox", query_string={"token": "nope"}).status_code == 410
    assert client.post("/api/handoffs", json={"token": "nope"}).status_code == 410


def person_id(client, team, role, name):
    people = client.get("/api/people", headers=team["h"]).json["people"]
    return next(p["id"] for p in people if p["role_id"] == role and p["display_name"] == name)


def test_leaver_loses_access_at_once_and_the_browser_is_told_to_clear_data(client, team):
    named = client.post("/api/invites", json={"role_id": "finance", "display_name": "Binh"},
                        headers=team["h"]).json["token"]
    pid = person_id(client, team, "finance", "Binh")
    assert client.get("/api/inbox", query_string={"token": named}).status_code == 200
    assert client.post(f"/api/people/{pid}/offboard", headers=team["h"]).status_code == 200
    r = client.get("/api/inbox", query_string={"token": named})
    assert r.status_code == 410 and r.json["error"] == "link_revoked"
    assert r.headers["Clear-Site-Data"] == '"storage"'
    assert client.post("/api/chat", json={"token": named, "message": "hi"}).status_code == 410


def test_leaver_frees_the_seat_and_their_held_work_returns_to_the_queue(client, team):
    pid = send(client, team["sales"]).json["id"]
    assert claim(client, team["ops"], pid).status_code == 200
    ops_person = next(p["id"] for p in client.get("/api/people", headers=team["h"]).json["people"]
                      if p["role_id"] == "ops")
    client.post(f"/api/people/{ops_person}/offboard", headers=team["h"])
    got = inbox(client, team["ops2"])["packages"][0]
    assert got["can_claim"] is True
    assert claim(client, team["ops2"], pid).status_code == 200
    seats = [client.post("/api/invites", json={"role_id": "finance"}, headers=team["h"]).status_code
             for _ in range(2)]
    assert seats == [201, 409]  # finance had 2 seats, one already taken in the fixture


def test_sent_documents_of_a_leaver_stay_with_the_company(client, team):
    pid = send(client, team["sales"]).json["id"]
    sales_person = next(p["id"] for p in client.get("/api/people", headers=team["h"]).json["people"]
                        if p["role_id"] == "sales")
    client.post(f"/api/people/{sales_person}/offboard", headers=team["h"])
    assert [p["id"] for p in inbox(client, team["ops"])["packages"]] == [pid]


def test_people_list_has_no_activity_or_metrics(client, team):
    person = client.get("/api/people", headers=team["h"]).json["people"][0]
    assert set(person) == {"id", "role_id", "display_name", "status"}


def test_resend_stores_the_edited_values_and_a_new_due_date(client, team):
    pid = send(client, team["sales"], values={"price": 1000, "cost": 1500}).json["id"]
    claim(client, team["ops"], pid)
    decide(client, team["ops"], pid, "return", "Fix the price")
    later = (datetime.date.today() + datetime.timedelta(days=5)).isoformat()
    r = client.post(f"/api/handoffs/{pid}/resend",
                    json={"token": team["sales"], "values": {**GOOD, "price": 2100}, "due": later})
    assert r.json["values"]["price"] == 2100 and r.json["due"] == later
    assert r.json["check_status"] != "blocked"


def test_a_past_answer_needed_by_date_is_refused_everywhere(client, team):
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    sent = send(client, team["sales"], due=yesterday)
    assert sent.status_code == 400 and "in the past" in sent.json["message"]
    pre = client.post("/api/precheck", json={"token": team["sales"], "values": GOOD, "due": yesterday}).json
    assert pre["status"] == "blocked" and "in the past" in pre["findings"][0]["message"]
    pid = send(client, team["sales"]).json["id"]
    claim(client, team["ops"], pid)
    decide(client, team["ops"], pid, "return", "x")
    r = client.post(f"/api/handoffs/{pid}/resend",
                    json={"token": team["sales"], "values": GOOD, "due": yesterday})
    assert r.status_code == 400


def test_view_names_roles_by_title_and_hides_who_holds_a_package(client, team):
    pid = send(client, team["sales"], values={"price": 60000, "cost": 40000}).json["id"]
    claim(client, team["ops"], pid)
    mine = inbox(client, team["ops"])["packages"][0]
    other = inbox(client, team["ops2"])
    seen = other["packages"][0]
    assert seen["chain_titles"] == ["Ops Lead", "MD"] and seen["held_by_teammate"] is True
    assert mine["held_by_teammate"] is False and mine["i_hold_it"] is True
    assert seen["can_claim"] is False and other["today"]["handled_by_teammates"] == 1
    assert other["today"]["in_team_queue"] == 0
    assert team["ops"] not in str(seen)


def test_invite_returns_role_titles(client, team):
    titles = client.get(f"/api/invite/{team['sales']}").json["role_titles"]
    assert titles["ops"] == "Ops Lead"


def test_model_finding_that_only_repeats_the_rules_is_dropped(client, team, monkeypatch):
    monkeypatch.delenv("FAKE_AI", raising=False)
    text = ('{"status": "clear", "findings": ["Rule check result is blocked", "Customer name looks '
            'unusual"], "summary": "x"}')
    monkeypatch.setattr(muse, "complete", lambda *a, **k: muse._result(muse.SPARK, False, text=text))
    r = send(client, team["sales"], values={"price": 1000, "cost": 1500}).json
    messages = [f["message"] for f in r["findings"]]
    assert "Customer name looks unusual" in messages
    assert not any("rule check" in m.lower() for m in messages)


def test_returned_package_is_only_in_the_senders_inbox_and_keeps_its_history_on_resend(client, team):
    pid = send(client, team["sales"], values={"price": 1000, "cost": 1500}).json["id"]
    claim(client, team["ops"], pid)
    decide(client, team["ops"], pid, "return", "Fix the price")
    assert inbox(client, team["ops2"])["packages"] == []
    assert [p["id"] for p in inbox(client, team["sales"])["packages"]] == [pid]
    r = client.post(f"/api/handoffs/{pid}/resend", json={"token": team["sales"], "values": GOOD})
    history = r.json["history"]
    assert history[0]["reason"] == "Fix the price" and r.json["return_reason"] is None
    assert any(c.startswith("price: 1000") for c in history[0]["changes"])
    assert [p["id"] for p in inbox(client, team["ops2"])["packages"]] == [pid]


def test_empty_optional_notes_are_not_reported_by_the_model(monkeypatch):
    import json
    import workflow
    reply = {"status": "needs_attention", "summary": "x",
             "findings": ["Notes field is empty", "Delivery date looks odd"]}
    monkeypatch.setattr(muse, "complete", lambda *a, **k: {
        "model": "m", "latency_ms": 1, "demo_mode": False, "text": json.dumps(reply)})
    verdict, _ = workflow.soft_check({"id": "s", "title": "t"}, {}, "clear", muse.complete, lambda: None, [])
    assert verdict["findings"] == ["Delivery date looks odd"]
