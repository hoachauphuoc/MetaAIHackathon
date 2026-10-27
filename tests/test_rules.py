import rules


def role(id, reports_to=None, headcount=1, title=None):
    return {"id": id, "title": title or id.title(), "reports_to": reports_to, "headcount": headcount}


def fields(errors):
    return {(e["role_id"], e["field"]) for e in errors}


def test_valid_chart_has_no_errors():
    assert rules.validate_chart([role("md"), role("ops", "md", 3)], 10) == []


def test_cycle_is_rejected():
    chart = [role("md"), role("a", "b"), role("b", "a")]
    assert ("a", "reports_to") in fields(rules.validate_chart(chart, 10))


def test_orphan_reporting_line_is_rejected():
    assert ("ops", "reports_to") in fields(rules.validate_chart([role("md"), role("ops", "ghost")], 10))


def test_self_report_is_rejected():
    assert ("md", "reports_to") in fields(rules.validate_chart([role("md", "md")], 10))


def test_two_roots_or_none_is_rejected():
    assert (None, "reports_to") in fields(rules.validate_chart([role("a"), role("b")], 10))
    assert (None, "reports_to") in fields(rules.validate_chart([role("a", "b"), role("b", "a")], 10))


def test_more_headcount_than_the_company_has_is_rejected():
    errors = rules.validate_chart([role("md"), role("ops", "md", 9)], 5)
    assert "needs 10 people but the company has 5" in errors[0]["message"]


def test_headcount_must_be_a_real_int_not_bool():
    assert ("md", "headcount") in fields(rules.validate_chart([role("md", headcount=True)], 5))
    assert ("md", "headcount") in fields(rules.validate_chart([role("md", headcount=0)], 5))


def test_empty_title_and_duplicate_id_are_rejected():
    assert ("a", "title") in fields(rules.validate_chart([role("a", title=" ")], 5))
    assert ("a", "id") in fields(rules.validate_chart([role("a"), role("a", "a")], 5))


def test_role_still_held_cannot_disappear():
    errors = rules.validate_chart([role("md")], 5, {"ops": 2})
    assert "Move or offboard 2 people first" in errors[0]["message"]


def test_forbidden_and_unknown_skills_never_survive():
    kept, removed = rules.filter_skills(["draft_message", "evaluate_person", "rank_employees",
                                         "made_up", "hr_decision", "monitor_activity"])
    assert kept == ["draft_message"]
    assert set(removed) == {"evaluate_person", "rank_employees", "made_up", "hr_decision",
                            "monitor_activity"}
