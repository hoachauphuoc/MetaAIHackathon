"""The research pipeline's gatekeeper: what may pass from one stage to the next is decided by code."""
import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("research", Path(__file__).parent.parent / "scripts" / "research.py")
research = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(research)

SOURCE = {"brief": "b1", "url": "https://example.org/report", "title": "Report", "publisher": "Example Org",
          "date": "2026-03", "reason": "A survey of small business owners"}
EVIDENCE = {"id": "b1-01", "brief": "b1", "url": "https://example.org/report", "publisher": "Example Org",
            "kind": "independent", "date": "2026-03", "figure": "52", "unit": "percent of owners",
            "sample_size": "n = 1,200", "quote": "Half of owners lose time to admin each week"}


def evidence(**changes):
    return {**EVIDENCE, **changes}


def test_a_good_source_and_a_good_evidence_record_pass():
    assert research.check_s1([SOURCE]) == []
    assert research.check_s2([EVIDENCE]) == []


@pytest.mark.parametrize("change,message", [
    ({"quote": " ".join(["word"] * 20)}, "quote has 20 words"),
    ({"date": ""}, "date must look like"),
    ({"date": "March 2026"}, "date must look like"),
    ({"sample_size": ""}, "sample_size is required"),
    ({"kind": "blog"}, "independent or vendor"),
    ({"url": "example.org/report"}, "url must start"),
    ({"brief": "b2"}, "brief must match"),
    ({"id": "report-1"}, "id must look like")])
def test_bad_evidence_is_rejected_with_a_reason(change, message):
    assert any(message in e for e in research.check_s2([evidence(**change)]))


def test_a_duplicated_evidence_id_is_rejected():
    assert any("used twice" in e for e in research.check_s2([EVIDENCE, EVIDENCE]))


def test_a_brief_cannot_have_more_than_twelve_sources():
    assert any("more than 12" in e for e in research.check_s1([SOURCE] * 13))


def test_every_figure_must_be_checked_and_a_mismatch_must_say_what_the_source_says():
    assert research.check_s4([{"id": "b1-01", "status": "verified", "checked_by": "sonnet"}], {"b1-01"}) == []
    assert any("never checked" in e for e in research.check_s4([], {"b1-01"}))
    assert any("what the source says" in e for e in research.check_s4(
        [{"id": "b1-01", "status": "mismatch", "checked_by": "opus"}], {"b1-01"}))
    assert any("status must be" in e for e in research.check_s4(
        [{"id": "b1-01", "status": "probably fine", "checked_by": "opus"}], {"b1-01"}))
    assert any("no such evidence" in e for e in research.check_s4(
        [{"id": "b9-09", "status": "verified", "checked_by": "opus"}], {"b1-01"}))


@pytest.fixture
def run(tmp_path):
    other = evidence(id="b1-02", kind="vendor", figure="33", unit="percent")
    third = evidence(id="b2-01", brief="b2", figure="9", unit="hours a week")
    (tmp_path / "s2_evidence.json").write_text(json.dumps([EVIDENCE, other, third]), encoding="utf-8")
    (tmp_path / "s4_verified.json").write_text(json.dumps([
        {"id": "b1-01", "status": "verified", "checked_by": "sonnet"},
        {"id": "b1-02", "status": "verified", "checked_by": "sonnet"},
        {"id": "b2-01", "status": "unreachable", "checked_by": "sonnet"}]), encoding="utf-8")
    return tmp_path


def test_impact_rows_only_for_verified_independent_figures(run):
    rows = research.impact_rows(run)
    assert len(rows) == 1 and "52" in rows[0] and "n = 1,200" in rows[0] and "https://example.org/report" in rows[0]
    assert "TO WRITE" in rows[0]  # the product answer is the author's, never generated


def test_findings_may_cite_only_verified_evidence(run):
    assert research.cites_problems("Owners lose time [b1-01] and more [b1-02].", run) == []
    problems = research.cites_problems("A claim [b2-01] and another [b7-07].", run)
    assert problems == ["b2-01 is cited but is not verified", "b7-07 is cited but is unknown"]


def test_merge_joins_per_brief_files_and_refuses_bad_ones(tmp_path):
    (tmp_path / "s1_b1.json").write_text(json.dumps([SOURCE]), encoding="utf-8")
    (tmp_path / "s1_b2.json").write_text(json.dumps([{**SOURCE, "brief": "b2"}]), encoding="utf-8")
    assert research.merge("s1", tmp_path) == []
    assert len(json.loads((tmp_path / "s1_sources.json").read_text(encoding="utf-8"))) == 2
    (tmp_path / "s1_b3.json").write_text(json.dumps([{**SOURCE, "url": "nope"}]), encoding="utf-8")
    assert research.merge("s1", tmp_path) != []


def test_muse_stage_without_a_model_is_labelled_and_makes_no_ideas(run):
    out = research.muse_ideas(run)
    assert out["demo_mode"] is True and out["ideas"] == []
    saved = json.loads((run / "s3_ideas.json").read_text(encoding="utf-8"))
    assert saved["demo_mode"] is True and "model" in saved


def test_muse_ideas_citing_unknown_evidence_are_dropped(run, monkeypatch):
    def reply(model, messages, **kw):
        assert "https://" not in json.dumps(messages)  # Muse sees figures and quotes, never URLs
        ideas = [{"title": "Good", "why": "Because", "evidence_ids": ["b1-01", "b9-99"], "effort_days": 2,
                  "principle_risk": "none"},
                 {"title": "Invented", "why": "No evidence", "evidence_ids": ["b9-99"], "effort_days": 1,
                  "principle_risk": "none"}]
        return {"model": model, "demo_mode": False, "demo_reason": None, "text": json.dumps({"ideas": ideas})}
    monkeypatch.setattr(research.muse, "complete", reply)
    out = research.muse_ideas(run)
    assert [i["title"] for i in out["ideas"]] == ["Good"] and out["ideas"][0]["evidence_ids"] == ["b1-01"]
    assert out["dropped_ideas"] == 1


def test_the_prompt_digest_never_carries_urls_or_publisher_pages():
    d = research.digest([EVIDENCE])
    assert set(d[0]) == {"id", "kind", "figure", "sample_size", "quote"}
