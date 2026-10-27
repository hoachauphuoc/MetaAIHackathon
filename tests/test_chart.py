import json

import pytest

import chart
import muse
import rules

ANSWERS = {"company_name": "Acme", "industry": "logistics", "headcount": 14}


def wonder_returns(monkeypatch, text, demo=False):
    out = {"model": muse.WONDER, "demo_mode": demo, "demo_reason": "TimeoutError" if demo else None,
           "text": text, "cost_usd": 0.01, "latency_ms": 5}
    monkeypatch.setattr(muse, "complete", lambda *a, **k: out)


def good_chart():
    return {"roles": [
        {"id": "md", "title": "MD", "reports_to": None, "headcount": 1, "reason": "x", "source": "answers"},
        {"id": "ops", "title": "Ops", "reports_to": "md", "headcount": 5, "reason": "x", "source": "ai"}]}


@pytest.mark.parametrize("industry", ["logistics", "retail", "services", "unknown"])
@pytest.mark.parametrize("size", [1, 3, 5, 14, 80])
def test_every_template_passes_the_rules(industry, size):
    roles = chart.template_chart(industry, size)
    assert rules.validate_chart(roles, size) == []
    assert sum(r["headcount"] for r in roles) <= size


def test_valid_wonder_chart_is_used(monkeypatch):
    wonder_returns(monkeypatch, json.dumps(good_chart()))
    out = chart.generate(ANSWERS)
    assert out["source"] == "wonder" and out["demo_mode"] is False and out["errors"] == []


def test_wonder_chart_that_breaks_a_rule_falls_back_to_a_labelled_template(monkeypatch):
    bad = good_chart()
    bad["roles"][1]["headcount"] = 99
    wonder_returns(monkeypatch, json.dumps(bad))
    out = chart.generate(ANSWERS)
    assert out["source"] == "template" and out["demo_mode"] is True and out["errors"] == []


def test_unreadable_output_falls_back(monkeypatch):
    wonder_returns(monkeypatch, "not json")
    assert chart.generate(ANSWERS)["source"] == "template"


def test_muse_failure_is_demo_mode(monkeypatch):
    wonder_returns(monkeypatch, "", demo=True)
    out = chart.generate(ANSWERS)
    assert out["demo_mode"] is True and out["demo_reason"] == "TimeoutError"


def test_cap_reached_never_calls_the_model(monkeypatch):
    monkeypatch.setattr(muse, "complete", lambda *a, **k: pytest.fail("model was called"))
    out = chart.generate(ANSWERS, lambda: "Demo limit reached")
    assert out["demo_reason"] == "Demo limit reached" and out["demo_mode"] is True


def test_bad_headcount_is_refused():
    with pytest.raises(ValueError):
        chart.generate({"headcount": "many"})


def test_invisible_characters_are_stripped_from_answers():
    assert chart.clean_answers({"headcount": 3, "tools": "a​b‮c"})["tools"] == "abc"
