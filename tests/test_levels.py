"""Layered rules in one sandbox: a unit may only tighten its parent's numbers."""
import pytest

import app as app_module
import chat
import rules

ROLES = [{"id": "md", "title": "MD", "reports_to": None, "headcount": 1},
         {"id": "ops", "title": "Ops", "reports_to": "md", "headcount": 3}]
PARAMS = {"margin_floor_pct": 12, "escalation_usd": 50000}
GROUP = {"margin_floor_pct": 20, "escalation_usd": 40000}


@pytest.fixture
def client():
    return app_module.create_app().test_client()


def company(client):
    h = {"X-Sandbox": client.post("/api/sandbox").json["sandbox"]}
    client.post("/api/company", json={"company": "Pixel", "roles": ROLES, "size": 20}, headers=h)
    return h


def leveled(client):
    h = company(client)
    client.post("/api/levels/enable", headers=h)
    assert client.put("/api/levels/group", json=GROUP, headers=h).status_code == 200
    return h


LOOSER = [({**GROUP, "margin_floor_pct": 19}, "margin_floor_pct", 20),
          ({**GROUP, "escalation_usd": 40001}, "escalation_usd", 40000)]


@pytest.mark.parametrize("child,rule,parent_value", LOOSER)
def test_every_loosening_is_refused_with_the_rule_and_the_parents_value(client, child, rule, parent_value):
    h = leveled(client)
    got = client.put("/api/levels/subsidiary", json=child, headers=h)
    assert got.status_code == 422
    error = got.json["errors"][0]
    assert error["rule"] == rule and error["parent_value"] == parent_value and "Group" in error["message"]


def test_generated_widenings_never_pass_and_equal_or_tighter_values_do():
    for rule, spec in rules.LEVEL_RULES.items():
        up = spec["stricter"] == "up"
        for step in (1, 5, 100):
            looser = {**GROUP, rule: GROUP[rule] - step if up else GROUP[rule] + step}
            assert [e["rule"] for e in rules.validate_child_rules(GROUP, looser)] == [rule]
            tighter = {**GROUP, rule: GROUP[rule] + step if up else GROUP[rule] - step}
            assert rules.validate_child_rules(GROUP, tighter) == []
        assert rules.validate_child_rules(GROUP, GROUP) == []


def test_a_tighter_subsidiary_is_stored_and_the_checks_and_chat_use_it(client):
    h = leveled(client)
    assert client.put("/api/levels/subsidiary", json={**GROUP, "escalation_usd": 30000}, headers=h).status_code == 200
    schema = client.get("/api/handoff-schema", headers=h).json["schema"]
    assert rules.rule_threshold(schema, "escalate_over", PARAMS) == 30000
    assert rules.rule_threshold(schema, "min_margin", PARAMS) == 20
    text = chat.company_rules({"shows_cost": False}, rules.bind_levels(
        [{**GROUP, "id": "group"}, {**GROUP, "escalation_usd": 30000, "id": "subsidiary"}], PARAMS,
        rules.DEFAULT_SCHEMA)[1])
    assert "margin floor is 20%" in text and "USD 30,000" in text


def test_a_parent_that_tightens_later_still_wins(client):
    h = leveled(client)
    client.put("/api/levels/subsidiary", json=GROUP, headers=h)
    client.put("/api/levels/group", json={**GROUP, "margin_floor_pct": 25}, headers=h)
    schema = client.get("/api/handoff-schema", headers=h).json["schema"]
    assert rules.rule_threshold(schema, "min_margin", PARAMS) == 25


def test_the_form_route_cannot_loosen_what_a_level_set(client):
    h = leveled(client)
    loose = {**rules.SCHEMAS["logistics"]}
    loose["rules"] = [{**r, "usd": 80000} if r["kind"] == "escalate_over" else r for r in loose["rules"]]
    got = client.post("/api/handoff-schema", json={"schema": loose}, headers=h)
    assert got.status_code == 422 and got.json["errors"][0]["rule"] == "escalation_usd"


def test_values_out_of_range_or_not_numbers_are_refused(client):
    h = leveled(client)
    for bad in ({"margin_floor_pct": "a", "escalation_usd": 1}, {"margin_floor_pct": 60, "escalation_usd": 1},
                {"margin_floor_pct": True, "escalation_usd": 1}, {}):
        assert client.put("/api/levels/group", json=bad, headers=h).status_code == 422


def test_a_one_level_company_is_unchanged(client):
    h = company(client)
    assert client.get("/api/levels", headers=h).json["levels"] is None
    assert client.get("/api/handoff-schema", headers=h).json["schema"] == rules.DEFAULT_SCHEMA
    assert rules.bind_levels(None, PARAMS, rules.DEFAULT_SCHEMA) == (PARAMS, rules.DEFAULT_SCHEMA)


def test_a_unit_of_another_sandbox_is_not_reachable(client):
    h1, h2 = leveled(client), company(client)
    assert client.put("/api/levels/group", json=GROUP, headers=h2).status_code == 404
    assert client.get("/api/levels", headers=h2).json["levels"] is None
    client.put("/api/levels/group", json={**GROUP, "margin_floor_pct": 30}, headers=h1)
    assert client.get("/api/levels", headers=h2).json["levels"] is None


CANARY = 31337.5


def with_person(client, h, role="ops"):
    return client.post("/api/invites", json={"role_id": role, "display_name": "Lan"}, headers=h).json["token"]


def test_a_person_may_tighten_but_not_loosen_the_company_and_chat_uses_it(client, monkeypatch):
    h = leveled(client)
    token = with_person(client, h)
    refused = client.put("/api/personal-rules", json={"token": token, "margin_floor_pct": 19,
                                                      "escalation_usd": 40000})
    assert refused.status_code == 422 and refused.json["errors"][0]["rule"] == "margin_floor_pct"
    ok = client.put("/api/personal-rules", json={"token": token, "margin_floor_pct": 25, "escalation_usd": 10000})
    assert ok.status_code == 200
    assert client.get(f"/api/personal-rules?token={token}").json["rules"]["escalation_usd"] == 10000
    schema = rules.bind_levels([{"margin_floor_pct": 25, "escalation_usd": 10000}], {**PARAMS, **GROUP},
                               rules.DEFAULT_SCHEMA)[1]
    assert "USD 10,000" in chat.company_rules({"shows_cost": False}, schema)


def test_the_canary_in_a_personal_rule_never_reaches_the_owner_or_another_sandbox(client):
    h = leveled(client)
    token = with_person(client, h)
    other = leveled(client)
    other_token = with_person(client, other)
    assert client.put("/api/personal-rules", json={"token": token, "margin_floor_pct": 25,
                                                   "escalation_usd": CANARY}).status_code == 200
    seen = []
    for rule in client.application.url_map.iter_rules():
        if "GET" in rule.methods and not rule.arguments and rule.rule.startswith("/api/") \
                and rule.rule != "/api/personal-rules":
            for headers in (h, other):
                got = client.get(rule.rule, headers=headers)
                seen.append(got.get_data(as_text=True))
    assert seen and not any("31337" in text for text in seen)
    assert client.get(f"/api/personal-rules?token={other_token}").json["rules"] is None


def test_a_person_who_leaves_takes_their_private_rules_with_them(client):
    h = leveled(client)
    token = with_person(client, h)
    client.put("/api/personal-rules", json={"token": token, "margin_floor_pct": 25, "escalation_usd": 10000})
    pid = client.get("/api/people", headers=h).json["people"][0]["id"]
    assert client.post(f"/api/people/{pid}/offboard", headers=h).status_code == 200
    assert client.application.config["STORE"].get_personal_rules(token) is None


def test_the_owner_sees_which_unit_set_each_number_and_no_person(client):
    h = leveled(client)
    client.put("/api/levels/subsidiary", json={**GROUP, "escalation_usd": 30000}, headers=h)
    got = client.get("/api/levels", headers=h).json["effective"]
    assert got == {"margin_floor_pct": {"value": 20, "set_by": "Group"},
                   "escalation_usd": {"value": 30000, "set_by": "Subsidiary"}}
    client.put("/api/levels/group", json={**GROUP, "escalation_usd": 20000}, headers=h)
    assert client.get("/api/levels", headers=h).json["effective"]["escalation_usd"]["set_by"] == "Group"
    assert set(client.get("/api/levels", headers=h).json) == {"levels", "rules", "effective"}


def test_a_one_level_company_has_no_provenance(client):
    assert client.get("/api/levels", headers=company(client)).json["effective"] is None
