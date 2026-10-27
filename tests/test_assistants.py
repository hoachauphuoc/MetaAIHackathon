import json

import assistants
import muse

ROLES = [{"id": "md", "title": "MD", "reports_to": None, "headcount": 1},
         {"id": "sales", "title": "Sales Lead", "reports_to": "md", "headcount": 2},
         {"id": "ops", "title": "Ops Lead", "reports_to": "md", "headcount": 2},
         {"id": "finance", "title": "Finance Lead", "reports_to": "md", "headcount": 1}]


def spark_returns(monkeypatch, kit, demo=False):
    out = {"model": muse.SPARK, "demo_mode": demo, "demo_reason": "TimeoutError" if demo else None,
           "text": json.dumps(kit) if kit is not None else "", "cost_usd": 0.001}
    monkeypatch.setattr(muse, "complete", lambda *a, **k: out)


def kit(**over):
    base = {"goal": "g", "skills": ["draft_message"], "jobs": list("abcdefg"),
            "handoffs": [{"to_role": "ops", "what": "order"}], "limits": ["l"]}
    return {**base, **over}


def test_forbidden_skills_are_removed_and_reported(monkeypatch):
    spark_returns(monkeypatch, kit(skills=["draft_message", "evaluate_person", "rank_employees"]))
    out = assistants.build(ROLES[1], ROLES)
    assert out["skills"] == ["draft_message"]
    assert out["removed_skills"] == ["evaluate_person", "rank_employees"]
    assert out["demo_mode"] is False


def test_handoff_to_a_role_that_does_not_exist_is_dropped(monkeypatch):
    spark_returns(monkeypatch, kit(handoffs=[{"to_role": "ops", "what": "x"},
                                             {"to_role": "ghost", "what": "y"}]))
    assert [h["to_role"] for h in assistants.build(ROLES[1], ROLES)["handoffs"]] == ["ops"]


def test_jobs_are_cut_to_five(monkeypatch):
    spark_returns(monkeypatch, kit())
    assert len(assistants.build(ROLES[1], ROLES)["jobs"]) == 5


def test_muse_failure_gives_a_labelled_fallback_with_the_work_order(monkeypatch):
    spark_returns(monkeypatch, None, demo=True)
    out = assistants.build(ROLES[1], ROLES)
    assert out["demo_mode"] is True and out["demo_reason"] == "TimeoutError"
    assert out["handoffs"] == [{"to_role": "ops", "what": "The finished work for your review"}]
    assert assistants.fallback_kit(ROLES[3], ROLES)["handoffs"] == []


def test_cap_reached_never_calls_the_model(monkeypatch):
    monkeypatch.setattr(muse, "complete", lambda *a, **k: (_ for _ in ()).throw(AssertionError))
    out = assistants.build(ROLES[1], ROLES, lambda: "Demo limit reached")
    assert out["demo_reason"] == "Demo limit reached"


def test_fallback_never_contains_forbidden_skills():
    import rules
    for role in ROLES:
        kept, removed = rules.filter_skills(assistants.fallback_kit(role, ROLES)["skills"])
        assert removed == []
