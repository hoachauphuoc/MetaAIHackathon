"""Kind exit: the leaver's draft is private, the handover goes to their own team, and the leaver
can never accept their own handover."""
import datetime
import json

import pytest

import app as app_module
import handoffs
import muse
import rules

ROLES = [{"id": "md", "title": "MD", "reports_to": None, "headcount": 1},
         {"id": "sales", "title": "Sales Lead", "reports_to": "md", "headcount": 2},
         {"id": "ops", "title": "Ops Lead", "reports_to": "md", "headcount": 1}]
GOOD = {"customer": "Acme", "route": "Hanoi-Haiphong", "pallets": 10, "price": 1800, "cost": 1500,
        "delivery_date": (datetime.date.today() + datetime.timedelta(days=10)).isoformat()}
NOTE = {"subject": "Handover: Sales Lead", "open_work": "- Acme quote: waiting for Ops Lead",
        "tips": "Acme prefers morning calls.", "who_to_ask": "- Ops Lead: pallet quotes"}


@pytest.fixture
def client():
    return app_module.create_app().test_client()


@pytest.fixture
def team(client):
    h = {"X-Sandbox": client.post("/api/sandbox").json["sandbox"]}
    client.post("/api/company", json={"company": "Acme", "roles": ROLES, "size": 20}, headers=h)
    for role in ("sales", "ops"):
        client.post("/api/assistants", json={"role_id": role}, headers=h)

    def person(role):
        return client.post("/api/invites", json={"role_id": role}, headers=h).json["token"]
    return {"h": h, "leaver": person("sales"), "mate": person("sales"), "ops": person("ops"), "md": person("md")}


def inbox(client, token):
    return client.get("/api/inbox", query_string={"token": token}).json["packages"]


def counts(client):
    db = client.application.config["STORE"]
    return {t: db.db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in db.table_names()}


def test_the_draft_lists_only_the_leavers_open_documents_and_stores_nothing(client, team):
    for token, customer in ((team["leaver"], "Leaver Order"), (team["mate"], "Teammate Order")):
        client.post("/api/handoffs", json={"token": token, "to_role": "ops", "values": {**GOOD, "customer": customer}})
    before = counts(client)
    r = client.post("/api/handover/draft", json={"token": team["leaver"], "notes": "Call Acme before 10."}).json
    assert counts(client) == before
    assert r["demo_mode"] is True and r["source"] == "code" and r["documents"] == 1
    assert "Leaver Order" in r["values"]["open_work"] and "Teammate Order" not in r["values"]["open_work"]
    assert r["values"]["tips"] == "Call Acme before 10." and "Ops Lead" in r["values"]["who_to_ask"]


def test_a_muse_draft_is_cleaned_to_the_form_and_never_sees_tokens(client, team, monkeypatch):
    seen = []

    def complete(model, messages, **kw):
        seen.append(json.dumps(messages))
        return {"model": model, "latency_ms": 1, "demo_mode": False, "demo_reason": None, "cost_usd": 0.001,
                "text": json.dumps({**NOTE, "tips": "x" * 5000})}
    monkeypatch.setattr(muse, "complete", complete)
    r = client.post("/api/handover/draft", json={"token": team["leaver"], "notes": "Mine."}).json
    assert r["source"] == "muse" and len(r["values"]["tips"]) == 2000 and "notes" not in r["values"]
    assert team["leaver"] not in seen[0] and "Mine." in seen[0]


def test_the_handover_goes_to_the_own_team_and_the_leaver_cannot_accept_it(client, team):
    r = client.post("/api/handover", json={"token": team["leaver"], "values": NOTE})
    pid = r.json["id"]
    assert r.status_code == 201 and r.json["chain"] == ["sales"] and r.json["schema"]["id"] == "handover"
    assert r.json["check_status"] == "clear"
    assert client.post(f"/api/handoffs/{pid}/claim", json={"token": team["leaver"]}).status_code == 403
    assert [p["id"] for p in inbox(client, team["ops"])] == []
    assert client.post(f"/api/handoffs/{pid}/claim", json={"token": team["mate"]}).status_code == 200
    done = client.post(f"/api/handoffs/{pid}/decision", json={"token": team["mate"], "decision": "accept"})
    assert done.json["state"] == "accepted"


def test_a_one_seat_role_hands_over_to_the_top_role_and_the_top_role_alone_is_refused(client, team):
    r = client.post("/api/handover", json={"token": team["ops"], "values": NOTE})
    assert r.json["chain"] == ["md"]
    assert client.post("/api/handover", json={"token": team["md"], "values": NOTE}).status_code == 409


def test_the_handover_stays_with_the_team_after_the_leaver_is_removed(client, team):
    pid = client.post("/api/handover", json={"token": team["leaver"], "values": NOTE}).json["id"]
    people = client.get("/api/people", headers=team["h"]).json["people"]
    leaver_id = next(p["id"] for p in people if p["role_id"] == "sales")
    client.post(f"/api/people/{leaver_id}/offboard", headers=team["h"])
    assert client.post("/api/handover/draft", json={"token": team["leaver"]}).status_code == 410
    assert [p["id"] for p in inbox(client, team["mate"])] == [pid]


def test_a_handover_needs_open_work_and_a_returned_one_is_rechecked_by_rules_only(client, team, monkeypatch):
    assert client.post("/api/handover", json={"token": team["leaver"],
                                              "values": {**NOTE, "open_work": ""}}).status_code == 400
    pid = client.post("/api/handover", json={"token": team["leaver"], "values": NOTE}).json["id"]
    client.post(f"/api/handoffs/{pid}/claim", json={"token": team["mate"]})
    client.post(f"/api/handoffs/{pid}/decision", json={"token": team["mate"], "decision": "return",
                                                      "reason": "Which Acme contact?"})
    monkeypatch.setattr(muse, "complete", lambda *a, **k: pytest.fail("no model check on a handover"))
    r = client.post(f"/api/handoffs/{pid}/resend", json={"token": team["leaver"],
                                                         "values": {**NOTE, "tips": "Ask the front desk."}})
    assert r.json["state"] == "sent" and r.json["values"]["tips"] == "Ask the front desk."


def test_longtext_is_part_of_the_form_vocabulary_but_the_handover_form_cannot_be_claimed(client, team):
    assert rules.validate_handoff_schema(rules.HANDOVER_SCHEMA) == []
    assert len(handoffs.clean_values({"open_work": "y" * 3000}, rules.HANDOVER_SCHEMA)["open_work"]) == 2000
    r = client.post("/api/handoff-schema", json={"schema": rules.HANDOVER_SCHEMA}, headers=team["h"])
    assert r.json["schema"]["id"] == "custom"
