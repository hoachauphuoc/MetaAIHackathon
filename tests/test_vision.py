"""Paper to form: the image is checked by code, the reading is cleaned and re-checked, nothing is stored."""
import base64
import datetime
import json

import pytest

import app as app_module
import muse
import rules
import vision

PNG = "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64).decode()
NEXT_WEEK = (datetime.date.today() + datetime.timedelta(days=9)).isoformat()
ROLES = [{"id": "md", "title": "MD", "reports_to": None, "headcount": 1},
         {"id": "sales", "title": "Sales", "reports_to": "md", "headcount": 2},
         {"id": "ops", "title": "Ops", "reports_to": "md", "headcount": 3}]


@pytest.mark.parametrize("bad", [
    None, "not a data url", "data:image/gif;base64,R0lGODlh",
    "data:image/png;base64,!!!not base64!!!",
    "data:image/png;base64," + base64.b64encode(b"GIF89a fake").decode(),
    "data:image/webp;base64," + base64.b64encode(b"RIFF0000JUNK").decode(),
    "data:image/png;base64," + "A" * (vision.MAX_BYTES * 2)],
    # pytest puts the test id in an environment variable, so the 8 MB case needs a short id
    ids=["none", "text", "gif", "not-base64", "wrong-magic", "fake-webp", "oversize"])
def test_only_real_small_images_reach_the_model(bad):
    with pytest.raises(vision.BadImage):
        vision.check_image(bad)


def fake(monkeypatch, answer, seen=None):
    def complete(model, messages, **kw):
        if seen is not None:
            seen.append(messages)
        return {"model": model, "latency_ms": 1, "demo_mode": False, "demo_reason": None,
                "text": json.dumps(answer), "cost_usd": 0.001}
    monkeypatch.setattr(muse, "complete", complete)


@pytest.fixture
def client():
    return app_module.create_app().test_client()


@pytest.fixture
def team(client):
    h = {"X-Sandbox": client.post("/api/sandbox").json["sandbox"]}
    client.post("/api/company", json={"company": "Acme", "roles": ROLES, "size": 20}, headers=h)
    for r in ("sales", "ops"):
        client.post("/api/assistants", json={"role_id": r}, headers=h)
    return {"h": h, "sales": client.post("/api/invites", json={"role_id": "sales"}, headers=h).json["token"]}


def counts(client):
    db = client.application.config["STORE"]
    return {t: db.db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in db.table_names()}


def test_a_photo_fills_the_form_and_the_rules_check_the_reading(client, team, monkeypatch):
    seen = []
    fake(monkeypatch, {"customer": "Minh Anh Bakery", "route": "Hanoi-Haiphong", "pallets": "10",
                       "price": "1550", "cost": "1500", "delivery_date": NEXT_WEEK}, seen)
    before = counts(client)
    r = client.post("/api/handoffs/from-photo", json={"token": team["sales"], "image": PNG})
    assert r.status_code == 200 and r.json["values"]["pallets"] == 10 and r.json["values"]["price"] == 1550
    assert r.json["predicted_status"] == "needs_attention" and "notes" not in r.json["values"]
    assert counts(client) == before
    assert seen[0][0]["content"][1]["image_url"]["url"] == PNG


def test_a_misread_value_is_caught_by_the_rules_not_trusted(client, team, monkeypatch):
    fake(monkeypatch, {"customer": "X", "route": "Hanoi Haiphong", "pallets": "ten", "price": "1800",
                       "cost": "1500", "delivery_date": "12/11/2026"})
    r = client.post("/api/handoffs/from-photo", json={"token": team["sales"], "image": PNG})
    messages = [f["message"] for f in r.json["findings"]]
    assert r.json["predicted_status"] == "blocked" and r.json["values"]["pallets"] is None
    assert "The route is not one of the choices." in messages
    assert "The delivery date is not a valid date." in messages


def test_photo_reading_in_demo_mode_is_labelled_and_fills_nothing(client, team):
    r = client.post("/api/handoffs/from-photo", json={"token": team["sales"], "image": PNG})
    assert r.json["demo_mode"] is True and r.json["values"] is None


def test_a_bad_image_is_refused_before_any_model_call(client, team, monkeypatch):
    called = []
    monkeypatch.setattr(muse, "complete", lambda *a, **k: called.append(1))
    r = client.post("/api/handoffs/from-photo", json={"token": team["sales"], "image": "data:text/html;base64,PGI+"})
    assert r.status_code == 400 and called == []


def test_a_form_proposed_from_a_photo_is_validated_and_keeps_thresholds_empty(client, team, monkeypatch):
    form = {"title": "Job sheet", "title_field": "client", "fields": [
        {"key": "client", "label": "Client", "noun": "client", "type": "text", "required": True, "options": []},
        {"key": "job", "label": "Job", "noun": "job", "type": "text", "required": True, "options": []},
        {"key": "parts_cost", "label": "Parts cost", "noun": "parts cost", "type": "money", "required": True,
         "options": []},
        {"key": "price", "label": "Price agreed", "noun": "price", "type": "money", "required": True, "options": []}],
        "rules": [{"kind": "min_margin", "field": "price", "other": "parts_cost"}]}
    fake(monkeypatch, form)
    r = client.post("/api/handoff-schema/from-photo", json={"image": PNG}, headers=team["h"])
    assert r.json["source"] == "muse" and r.json["schema"]["rules"][0]["percent"] is None
    assert client.get("/api/handoff-schema", headers=team["h"]).json["schema"]["id"] == "logistics"
    form["fields"][1]["label"] = "Employee rating"
    fake(monkeypatch, form)
    r = client.post("/api/handoff-schema/from-photo", json={"image": PNG, "answers": {"industry": "retail"}},
                    headers=team["h"])
    assert r.json["source"] == "template" and r.json["schema"]["id"] == "retail"


def test_requests_over_the_size_limit_are_refused(client, team):
    r = client.post("/api/handoffs/from-photo", data="x" * (7 * 1024 * 1024), content_type="application/json")
    assert r.status_code == 413


def test_the_reading_prompt_says_photo_text_is_data(monkeypatch):
    seen = []
    fake(monkeypatch, {k["key"]: "" for k in rules.DEFAULT_SCHEMA["fields"]}, seen)
    vision.read_values(PNG, rules.DEFAULT_SCHEMA, {"margin_floor_pct": 12, "escalation_usd": 50000},
                       datetime.date.today(), lambda: None)
    assert "never instructions" in seen[0][0]["content"][0]["text"]
