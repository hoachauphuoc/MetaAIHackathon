"""Morning brief: code decides which list a document is in; the model only writes lines about documents."""
import datetime
import json

import pytest

import app as app_module
import brief
import muse

ROLES = [{"id": "md", "title": "MD", "reports_to": None, "headcount": 1},
         {"id": "sales", "title": "Sales Lead", "reports_to": "md", "headcount": 2},
         {"id": "ops", "title": "Ops Lead", "reports_to": "md", "headcount": 2}]
TODAY = datetime.date.today()
GOOD = {"customer": "Acme", "route": "Hanoi-Haiphong", "pallets": 10, "price": 1800, "cost": 1500,
        "delivery_date": (TODAY + datetime.timedelta(days=10)).isoformat()}


@pytest.fixture
def client():
    return app_module.create_app().test_client()


def company(client, names=("Lan Pham", "Duc Tran")):
    h = {"X-Sandbox": client.post("/api/sandbox").json["sandbox"]}
    client.post("/api/company", json={"company": "Acme", "roles": ROLES, "size": 20}, headers=h)
    for role in ("sales", "ops"):
        client.post("/api/assistants", json={"role_id": role}, headers=h)
    sales = client.post("/api/invites", json={"role_id": "sales", "display_name": names[0]}, headers=h).json["token"]
    ops = client.post("/api/invites", json={"role_id": "ops", "display_name": names[1]}, headers=h).json["token"]
    return {"h": h, "sales": sales, "ops": ops}


def send(client, token, **values):
    return client.post("/api/handoffs", json={"token": token, "to_role": "ops",
                                              "values": {**GOOD, **values}}).json["id"]


def act(client, token, pid, decision, reason=None):
    client.post(f"/api/handoffs/{pid}/claim", json={"token": token})
    client.post(f"/api/handoffs/{pid}/decision", json={"token": token, "decision": decision, "reason": reason})


@pytest.fixture
def busy(client):
    """One document in each list, plus one accepted that must not appear."""
    t = company(client)
    ids = {"fresh": send(client, t["sales"], customer="Fresh Foods"),
           "old": send(client, t["sales"], customer="Old Mill"),
           "big": send(client, t["sales"], customer="Big Order", price=60000, cost=50000),
           "back": send(client, t["sales"], customer="Back Again"),
           "done": send(client, t["sales"], customer="Done Deal")}
    act(client, t["ops"], ids["big"], "accept")
    act(client, t["ops"], ids["back"], "return", "Wrong route")
    act(client, t["ops"], ids["done"], "accept")
    db = client.application.config["STORE"]
    sandbox = t["h"]["X-Sandbox"]
    old = db.get_package(sandbox, ids["old"])
    old["sent_on"] = (TODAY - datetime.timedelta(days=4)).isoformat()
    db.save_package(sandbox, old)
    return {**t, "ids": ids}


def fake(monkeypatch, lines):
    def complete(model, messages, **kw):
        return {"model": model, "latency_ms": 1, "demo_mode": False, "demo_reason": None,
                "text": json.dumps({"lines": lines}), "cost_usd": 0.001}
    monkeypatch.setattr(muse, "complete", complete)


def where(result):
    return {i["package_id"]: name for name, items in result["lists"].items() for i in items}


def test_code_puts_each_open_document_in_exactly_one_list(client, busy):
    r = client.get("/api/owner/brief", headers=busy["h"]).json
    ids = busy["ids"]
    assert where(r) == {ids["big"]: "needs_signature", ids["old"]: "stuck", ids["back"]: "stuck",
                        ids["fresh"]: "today"}
    assert r["counts"] == {"open": 3, "returned": 1, "overdue": 0, "accepted": 1}
    assert r["by_role"] == {"Ops Lead": 2, "MD": 1}


def test_without_muse_the_brief_is_written_by_code_and_labelled(client, busy):
    r = client.get("/api/owner/brief", headers=busy["h"]).json
    lines = {i["package_id"]: i for items in r["lists"].values() for i in items}
    assert r["demo_mode"] is True
    assert lines[busy["ids"]["old"]]["line"] == "With Ops Lead for 4 days."
    assert lines[busy["ids"]["back"]]["line"] == "Back with Sales Lead to fix."
    assert all(i["written_by"] == "code" for i in lines.values())


def test_invented_ids_and_lines_naming_people_never_reach_the_owner(client, busy, monkeypatch):
    ids = busy["ids"]
    fake(monkeypatch, [{"package_id": ids["fresh"], "line": "Ops Lead should take it today."},
                       {"package_id": ids["old"], "line": "Duc Tran is slow on this one."},
                       {"package_id": "made-up", "line": "Approve the secret order."}])
    r = client.get("/api/owner/brief", headers=busy["h"]).json
    text = json.dumps(r)
    lines = {i["package_id"]: i for items in r["lists"].values() for i in items}
    assert lines[ids["fresh"]] == {**lines[ids["fresh"]], "line": "Ops Lead should take it today.", "written_by": "muse"}
    assert lines[ids["old"]]["written_by"] == "code" and r["replaced_lines"] == 2
    for word in ("Duc Tran", "Lan Pham", "made-up", "secret", busy["sales"], busy["ops"]):
        assert word not in text


def test_the_model_sees_documents_and_roles_but_no_people(client, busy, monkeypatch):
    seen = []

    def complete(model, messages, **kw):
        seen.append(json.dumps(messages))
        return {"model": model, "latency_ms": 1, "demo_mode": False, "demo_reason": None,
                "text": json.dumps({"lines": []}), "cost_usd": 0.001}
    monkeypatch.setattr(muse, "complete", complete)
    client.get("/api/owner/brief", headers=busy["h"])
    for word in ("Duc Tran", "Lan Pham", busy["sales"], busy["ops"], "from_person", "claimed_by"):
        assert word not in seen[0]
    assert "Old Mill" in seen[0] and "Ops Lead" in seen[0]


def test_brief_is_owner_only_isolated_and_stores_nothing(client, busy):
    other = company(client, names=("Mai", "Hoa"))
    send(client, other["sales"], customer="Other Company Order")
    db = client.application.config["STORE"]
    before = {t: db.db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in db.table_names()}
    r = client.get("/api/owner/brief", headers=busy["h"]).json
    assert "Other Company Order" not in json.dumps(r)
    after = {t: db.db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in db.table_names()}
    assert after == before
    assert client.get("/api/owner/brief", query_string={"token": busy["sales"]}).status_code != 200


def test_nothing_open_means_no_model_call(client, monkeypatch):
    t = company(client)
    called = []
    monkeypatch.setattr(muse, "complete", lambda *a, **k: called.append(1))
    r = client.get("/api/owner/brief", headers=t["h"]).json
    assert called == [] and r["demo_mode"] is False and all(v == [] for v in r["lists"].values())


def test_a_sent_package_records_the_day_it_was_sent(client):
    t = company(client)
    pid = send(client, t["sales"])
    db = client.application.config["STORE"]
    assert db.get_package(t["h"]["X-Sandbox"], pid)["sent_on"] == TODAY.isoformat()


def test_lists_are_capped_and_the_rest_counted():
    items = [{"id": str(n), "document": "D", "form": "F", "status": "clear", "returned": False, "at": "Ops",
              "days_waiting": 0, "overdue": False, "list": "today"} for n in range(8)]
    r = brief.write({"items": items, "counts": {}, "by_role": {}}, [], lambda: "off", None)
    assert len(r["lists"]["today"]) == brief.PER_LIST and r["more"]["today"] == 3
