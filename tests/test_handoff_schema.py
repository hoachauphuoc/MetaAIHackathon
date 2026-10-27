import copy
import datetime

import pytest

import handoffs
import rules

TODAY = datetime.date(2026, 11, 1)
PARAMS = {"margin_floor_pct": 12, "escalation_usd": 50000}


def schema(name="services"):
    return copy.deepcopy(rules.SCHEMAS[name])


@pytest.mark.parametrize("name", list(rules.SCHEMAS))
def test_shipped_forms_are_valid(name):
    assert rules.validate_handoff_schema(rules.SCHEMAS[name]) == []


def bad(mutate):
    s = schema()
    mutate(s)
    return rules.validate_handoff_schema(s)


def test_validator_rejects_each_kind_of_bad_form():
    assert bad(lambda s: s["fields"].__delitem__(slice(2, None)))  # too few fields
    assert bad(lambda s: s["fields"].extend([dict(s["fields"][0], key=f"extra{i}") for i in range(8)]))
    assert bad(lambda s: s["fields"][0].update(key="Bad Key"))
    assert bad(lambda s: s["fields"][0].update(key="notes"))
    assert bad(lambda s: s["fields"][1].update(key="client"))  # duplicate key
    assert bad(lambda s: s["fields"][1].update(type="html"))
    assert bad(lambda s: s["fields"][1].update(type="choice", options=["only one"]))
    assert bad(lambda s: s["fields"][1].update(options=["x", "y"]))  # options on a text field
    assert bad(lambda s: s.update(title_field="hours"))
    assert bad(lambda s: s["rules"].append({"kind": "run_script", "field": "price"}))
    assert bad(lambda s: s["rules"][0].update(field="nope"))
    assert bad(lambda s: s["rules"][0].update(field="client"))  # not a number
    assert bad(lambda s: s["rules"][3].update(field="price"))  # not a date
    assert bad(lambda s: s["rules"][1].update(percent=90))
    assert bad(lambda s: s["rules"][2].update(usd=-5))
    assert bad(lambda s: s["fields"][0].update(label="x" * 80))


@pytest.mark.parametrize("word", ["Employee performance score", "Staff rating", "Rank of the worker",
                                  "Productivity", "Monitor activity"])
def test_forms_cannot_describe_people(word):
    errors = bad(lambda s: s["fields"][1].update(label=word, noun="note"))
    assert any("about people" in e for e in errors)


def test_logistics_wording_is_unchanged():
    values = {"customer": "A", "route": "Hanoi-Haiphong", "pallets": 1, "price": 1000.0, "cost": 1500.0,
              "delivery_date": "2026-10-01"}
    status, findings = rules.check_package(values, PARAMS, TODAY)
    messages = [f["message"] for f in findings]
    assert status == "blocked" and "The price is below the cost." in messages
    assert "The delivery date is in the past." in messages


def test_a_services_form_is_checked_with_its_own_words_and_the_owners_thresholds():
    s = schema()
    values = {"client": "Dental Co", "service": "Audit", "hours": 8, "price": 1050.0, "cost": 1000.0,
              "start_date": "2026-12-01"}
    assert rules.check_package(values, PARAMS, TODAY, s)[1][0]["message"] == "The margin is under the 12% floor."
    s["rules"][1]["percent"] = 3
    assert rules.check_package(values, PARAMS, TODAY, s)[0] == "clear"
    s["rules"][2]["usd"] = 1000
    status, findings = rules.check_package(values, PARAMS, TODAY, s)
    assert status == "needs_attention" and "USD 1,000" in findings[0]["message"]
    status, findings = rules.check_package({**values, "start_date": "soon"}, PARAMS, TODAY, s)
    assert status == "blocked" and "start date is not a valid date" in findings[0]["message"]
    assert rules.check_package({**values, "client": ""}, PARAMS, TODAY, s)[0] == "blocked"


def test_a_choice_outside_its_options_is_blocked():
    values = {"customer": "A", "route": "Hanoi-Haipong", "pallets": 1, "price": 2000.0, "cost": 1500.0,
              "delivery_date": "2026-12-01"}
    status, findings = rules.check_package(values, PARAMS, TODAY)
    assert status == "blocked" and "route is not one of the choices" in findings[0]["message"]


def test_clean_values_types_every_field_by_the_form():
    s = schema()
    got = handoffs.clean_values({"client": " Acme ", "service": "x", "hours": "7.9", "price": "100.5",
                                 "cost": "abc", "start_date": "2026-12-01", "route": "ignored",
                                 "notes": "n"}, s)
    assert got == {"client": "Acme", "service": "x", "hours": 7, "price": 100.5, "cost": None,
                   "start_date": "2026-12-01", "notes": "n"}


def test_the_approval_chain_uses_the_forms_own_limit():
    s = schema()
    roles = [{"id": "md", "reports_to": None}, {"id": "ops", "reports_to": "md"}]
    assert handoffs.approval_chain("ops", {"price": 2000}, PARAMS, roles, s) == ["ops"]
    s["rules"][2]["usd"] = 1500
    assert handoffs.approval_chain("ops", {"price": 2000}, PARAMS, roles, s) == ["ops", "md"]
