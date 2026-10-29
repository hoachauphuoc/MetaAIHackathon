"""The code helper skill for a software company: explain, review and draft, never run, and only on the engineering role."""
import json
import re

import assistants
import chart
import chat
import muse
import rules
import tools
import workspace

ROLES = [{"id": "md", "title": "Managing Director", "reports_to": None, "headcount": 1},
         {"id": "engineering", "title": "Engineering Lead", "reports_to": "md", "headcount": 4},
         {"id": "sales", "title": "Account Manager", "reports_to": "md", "headcount": 2}]


def spark_returns(monkeypatch, skills):
    kit = {"goal": "g", "skills": skills, "jobs": list("abcde"), "handoffs": [], "limits": ["l"]}
    out = {"model": muse.SPARK, "demo_mode": False, "demo_reason": None, "text": json.dumps(kit), "cost_usd": 0.0}
    monkeypatch.setattr(muse, "complete", lambda *a, **k: out)


def test_the_skill_is_in_the_catalog_so_levels_can_ban_it():
    assert "help_with_code" in rules.ALLOWED_SKILLS
    assert rules.filter_skills(["draft_message", "help_with_code"], banned=["help_with_code"])[0] == ["draft_message"]


def test_only_the_engineering_role_holds_it_and_it_always_does(monkeypatch):
    spark_returns(monkeypatch, ["draft_message", "help_with_code"])  # the model hands it to sales too
    assert "help_with_code" not in assistants.build(ROLES[2], ROLES)["skills"]
    spark_returns(monkeypatch, ["draft_message"])  # and forgets it for engineering
    assert "help_with_code" in assistants.build(ROLES[1], ROLES)["skills"]


def test_the_labelled_fallback_kit_also_gets_it_for_engineering(monkeypatch):
    spark_returns(monkeypatch, [])
    monkeypatch.setattr(muse, "complete", lambda *a, **k: {"model": muse.SPARK, "demo_mode": True,
                                                            "demo_reason": "TimeoutError", "text": "", "cost_usd": 0.0})
    kit = assistants.build(ROLES[1], ROLES)
    assert kit["demo_mode"] is True and "help_with_code" in kit["skills"]


def test_an_engineering_lead_gets_the_engineering_playbook_not_management():
    book = chat.playbook_for({"role_id": "engineering", "role_title": "Engineering Lead"})
    assert "Untested draft" in " ".join(book["method"])
    assert any("Never run, deploy, push or merge" in n for n in book["never"])


def test_the_system_prompt_of_a_code_role_forbids_running_and_pasted_secrets():
    prompt = chat.system_prompt(None, {"role_id": "engineering", "role_title": "Engineering Lead", "goal": "g",
                                       "jobs": ["Review a change"], "limits": ["l"]})
    assert "Never run, deploy, push or merge" in prompt and "rotate it" in prompt


def test_no_tool_the_product_offers_can_run_code_or_touch_a_repository():
    names = set(tools.TOOLS) | {d["function"]["name"] if "function" in d else d["name"] for d in workspace.definitions()}
    assert not any(re.search(r"exec|run|shell|deploy|push|commit|merge|eval", n) for n in names)


def test_a_software_company_gets_its_own_chart_with_an_engineering_lead():
    assert rules.industry_key("Software studio") == "software"
    roles = chart.template_chart("custom software studio", 12)
    assert [r["title"] for r in roles][:2] == ["Managing Director", "Engineering Lead"]
    assert rules.validate_chart(roles, 12) == []
    assert rules.industry_key("tea shop") is None
