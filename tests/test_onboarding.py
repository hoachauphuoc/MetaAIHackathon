"""Day-One: the plan is built from the role's kit, only the kit's skills survive, nothing is stored."""
import json

import pytest

import app as app_module
import muse
import onboarding

ROLES = [{"id": "md", "title": "MD", "reports_to": None, "headcount": 1},
         {"id": "sales", "title": "Sales Lead", "reports_to": "md", "headcount": 2},
         {"id": "ops", "title": "Ops Lead", "reports_to": "md", "headcount": 2}]


@pytest.fixture
def client():
    return app_module.create_app().test_client()


@pytest.fixture
def person(client):
    h = {"X-Sandbox": client.post("/api/sandbox").json["sandbox"]}
    client.post("/api/company", json={"company": "Acme", "roles": ROLES, "size": 20}, headers=h)
    for role in ("sales", "ops"):
        client.post("/api/assistants", json={"role_id": role}, headers=h)
    return client.post("/api/invites", json={"role_id": "sales"}, headers=h).json["token"]


def fake(monkeypatch, days, seen=None):
    def complete(model, messages, **kw):
        if seen is not None:
            seen.append(json.dumps(messages))
        return {"model": model, "latency_ms": 1, "demo_mode": False, "demo_reason": None,
                "text": json.dumps({"days": days}), "cost_usd": 0.001}
    monkeypatch.setattr(muse, "complete", complete)


def task(title, skill=None):
    return {"title": title, "why": "Because.", "skill": skill}


def test_without_muse_the_plan_is_a_labelled_template_from_the_kit(client, person):
    r = client.post("/api/onboarding", json={"token": person}).json
    titles = [t["title"] for day in r["days"] for t in day]
    assert r["demo_mode"] is True and r["source"] == "template" and len(r["days"]) == 3
    assert "Ask the Ops Lead team what they need from you" in titles
    assert all(t["skill"] in (None, "prepare_handoff") for day in r["days"] for t in day)


def test_unknown_and_forbidden_skills_never_reach_the_plan(client, person, monkeypatch):
    fake(monkeypatch, [{"tasks": [task("Draft a hello to a customer", "draft_message"),
                                  task("Score your teammates", "rank_employees"),
                                  task("Use a made-up tool", "teleport")]},
                       {"tasks": [task("Meet the Ops Lead team")]}, {"tasks": [task("Send a first handoff")]}])
    r = client.post("/api/onboarding", json={"token": person}).json
    skills = [t["skill"] for day in r["days"] for t in day]
    assert r["source"] == "muse" and set(r["removed_skills"]) == {"rank_employees", "teleport"}
    assert skills == ["draft_message", None, None, None, None]


def test_the_plan_is_capped_to_three_days_of_five_tasks(client, person, monkeypatch):
    fake(monkeypatch, [{"tasks": [task(f"Task {n}") for n in range(9)]}] * 5)
    r = client.post("/api/onboarding", json={"token": person}).json
    assert len(r["days"]) == onboarding.DAYS and all(len(d) == onboarding.TASKS_PER_DAY for d in r["days"])


def test_an_empty_or_broken_answer_falls_back_to_the_template(client, person, monkeypatch):
    fake(monkeypatch, [{"tasks": [task("   ")]}])
    assert client.post("/api/onboarding", json={"token": person}).json["source"] == "template"
    monkeypatch.setattr(muse, "complete", lambda model, messages, **kw: {
        "model": model, "latency_ms": 1, "demo_mode": False, "demo_reason": None, "text": "{", "cost_usd": 0})
    assert client.post("/api/onboarding", json={"token": person}).json["demo_mode"] is True


def test_the_plan_is_not_stored_and_the_model_sees_the_role_not_the_person(client, person, monkeypatch):
    seen = []
    fake(monkeypatch, [{"tasks": [task("Meet the Ops Lead team")]}], seen)
    db = client.application.config["STORE"]
    before = {t: db.db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in db.table_names()}
    client.post("/api/onboarding", json={"token": person})
    after = {t: db.db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in db.table_names()}
    assert after == before and person not in seen[0] and "Sales Lead" in seen[0] and "Ops Lead" in seen[0]


def test_a_bad_link_gets_no_plan(client):
    assert client.post("/api/onboarding", json={"token": "nope"}).status_code in (404, 410)
