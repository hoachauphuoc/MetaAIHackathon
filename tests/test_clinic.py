"""The second industry: a clinic gets its own chart, form, rules and playbooks without any training."""
import datetime

import pytest

import app as app_module
import chart
import chat
import handoff_schema
import rules

TODAY = datetime.date(2026, 11, 1)
PARAMS = {"margin_floor_pct": 12, "escalation_usd": 50000}
GOOD = {"patient_ref": "P-1042", "treatment": "Two fillings", "sessions": 2, "fee": 400, "cost": 300,
        "start_date": "2026-11-10"}


@pytest.mark.parametrize("typed,key", [("clinic", "clinic"), ("Dental Clinic", "clinic"), ("physiotherapy", "clinic"),
                                       ("logistics", "logistics"), ("tea shop", None), ("", None), (None, None)])
def test_an_owner_typed_industry_maps_to_a_shipped_key(typed, key):
    assert rules.industry_key(typed) == key


@pytest.mark.parametrize("size", [1, 3, 9, 40])
def test_the_clinic_chart_passes_the_rules_and_is_not_the_services_fallback(size):
    roles = chart.template_chart("dental clinic", size)
    assert rules.validate_chart(roles, size) == []
    assert roles[0]["title"] == "Clinic Director"


def test_an_unknown_industry_still_falls_back_to_services():
    assert chart.template_chart("tea shop", 5)[0]["title"] == "Director"
    assert handoff_schema.template_for("tea shop")["id"] == "services"


def test_the_clinic_form_checks_fee_margin_and_date_with_the_shared_rules():
    schema = rules.SCHEMAS["clinic"]
    assert rules.check_package(GOOD, PARAMS, TODAY, schema)[0] == "clear"
    assert rules.check_package({**GOOD, "fee": 250}, PARAMS, TODAY, schema)[0] == "blocked"
    assert rules.check_package({**GOOD, "fee": 310}, PARAMS, TODAY, schema)[0] == "needs_attention"
    assert rules.check_package({**GOOD, "start_date": "2026-10-01"}, PARAMS, TODAY, schema)[0] == "needs_attention"
    assert rules.check_package({**GOOD, "patient_ref": ""}, PARAMS, TODAY, schema)[0] == "blocked"


def test_the_patient_field_asks_for_a_number_not_a_name():
    assert "not a name" in rules.SCHEMAS["clinic"]["fields"][0]["label"]


def kit(title):
    return {"role_id": "x", "role_title": title}


def test_freight_playbooks_stay_on_the_freight_form_and_other_forms_get_neutral_ones():
    sales = kit("Patient Account Coordinator")
    freight = " ".join(chat.playbook_for(sales, rules.SCHEMAS["logistics"])["method"])
    other = " ".join(chat.playbook_for(sales, rules.SCHEMAS["clinic"])["method"])
    assert "pallets" in freight and "pallets" not in other and "route" not in other
    ops = " ".join(chat.playbook_for(kit("Clinic Operations Lead"), rules.SCHEMAS["clinic"])["method"])
    assert "pallets" not in ops and "route" not in ops


def test_the_default_playbook_is_unchanged_for_the_freight_company():
    assert "pallets" in " ".join(chat.playbook_for(kit("Sales Lead"))["method"])


def test_the_clinic_demo_survey_is_served_and_the_default_is_unchanged():
    client = app_module.create_app().test_client()
    assert client.get("/api/survey/demo?industry=clinic").json["answers"]["industry"] == "clinic"
    assert client.get("/api/survey/demo").json["answers"]["industry"] == "logistics"
