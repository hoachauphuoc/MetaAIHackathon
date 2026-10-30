import datetime

import pytest

import rules
import tools

TODAY = datetime.date(2026, 11, 1)
PARAMS = {"margin_floor_pct": 12, "escalation_usd": 50000}


def package(**over):
    base = {"customer": "Acme", "route": "Hanoi-Haiphong", "pallets": 10, "price": 1800,
            "cost": 1500, "delivery_date": "2026-11-20"}
    return {**base, **over}


def test_quote_is_computed_by_code():
    q = tools.quote_price("Hanoi-Haiphong", 10)
    assert (q["price"], q["cost"], q["margin_pct"]) == (1800, 1500, 16.7)


@pytest.mark.parametrize("route,pallets", [("Mars", 5), ("Hanoi-Haiphong", 0), ("Hanoi-Haiphong", True),
                                           ("Hanoi-Haiphong", "5"), ("Hanoi-Haiphong", 99999)])
def test_bad_quote_arguments_raise(route, pallets):
    with pytest.raises(ValueError):
        tools.quote_price(route, pallets)


def test_check_margin_flags_below_floor():
    assert tools.check_margin(1000, 950)["below_floor"] is True
    assert tools.check_margin(1000, 800)["below_floor"] is False


def test_calendar_event_is_a_valid_ics_and_rejects_bad_dates():
    ev = tools.make_calendar_event("Deliver to Acme", "2026-11-20")
    assert "DTSTART;VALUE=DATE:20261120" in ev["ics"] and ev["ics"].startswith("BEGIN:VCALENDAR")
    with pytest.raises(ValueError):
        tools.make_calendar_event("x", "20 Nov")


def test_run_rejects_unknown_tools_and_extra_arguments():
    with pytest.raises(ValueError):
        tools.run("delete_everything", {})
    with pytest.raises(ValueError):
        tools.run("quote_price", '{"route": "Hanoi-Haiphong", "pallets": 3, "price": 1}')
    with pytest.raises(ValueError):
        tools.run("quote_price", "not json")


def test_clean_package_is_clear():
    assert rules.check_package(package(), PARAMS, TODAY)[0] == "clear"


def test_price_below_cost_is_blocked():
    assert rules.check_package(package(price=1000, cost=1500), PARAMS, TODAY)[0] == "blocked"


def test_thin_margin_and_big_price_need_attention():
    assert rules.check_package(package(price=1000, cost=950), PARAMS, TODAY)[0] == "needs_attention"
    assert rules.check_package(package(price=60000, cost=40000), PARAMS, TODAY)[0] == "needs_attention"


def test_missing_field_and_bad_date_are_blocked():
    assert rules.check_package(package(customer=""), PARAMS, TODAY)[0] == "blocked"
    assert rules.check_package(package(delivery_date="soon"), PARAMS, TODAY)[0] == "blocked"


def test_past_delivery_date_needs_attention():
    assert rules.check_package(package(delivery_date="2026-10-01"), PARAMS, TODAY)[0] == "needs_attention"


@pytest.mark.parametrize("floor", list(rules.RANK))
@pytest.mark.parametrize("model", ["clear", "needs_attention", "needs_human_check", "blocked"])
def test_the_model_can_only_raise_the_status(floor, model):
    assert rules.RANK[rules.combine_status(floor, model)] >= rules.RANK[floor]


def test_unknown_or_missing_model_status_fails_closed():
    assert rules.combine_status("clear", "totally fine") == "needs_human_check"
    assert rules.combine_status("clear", None) == "needs_human_check"
    assert rules.combine_status("blocked", None) == "blocked"


def test_plan_may_only_follow_declared_handoffs():
    roles = [{"id": r} for r in ("sales", "ops", "finance")]
    plan = {"steps": [{"id": "a", "role_id": "sales"}, {"id": "b", "role_id": "ops"},
                      {"id": "c", "role_id": "finance"}]}
    assert rules.validate_plan(plan, roles, {("sales", "ops"), ("ops", "finance")}) == []
    errors = rules.validate_plan(plan, roles, {("sales", "ops")})
    assert errors == ["There is no handoff from ops to finance."]
    assert rules.validate_plan({"steps": []}, roles, set())


def test_a_calendar_file_is_built_by_code_and_refused_without_a_date():
    # I17 (2026-10-30): the .ics comes from the approved date in code; no model call, no guessed date.
    import pytest
    import tools
    assert tools.make_calendar_event("Delivery", "2026-11-13")["ics"].count("DTSTART;VALUE=DATE:20261113") == 1
    for missing in (None, "", "next Friday", "2026-13-40"):
        with pytest.raises(ValueError):
            tools.make_calendar_event("Delivery", missing)
