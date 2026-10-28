"""Set 11's cases must be ones the rules pass, or the measure would credit the model for the rules' work."""
import datetime
import importlib.util
from pathlib import Path

import rules
import tools


def load_measure():
    spec = importlib.util.spec_from_file_location("measure", Path(__file__).parent.parent / "scripts" / "measure.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_set11_case_passes_the_rules_so_only_the_model_can_catch_a_contradiction():
    measure = load_measure()
    cases = measure.contradiction_cases()
    assert [k for k, _ in cases].count("contradiction") == 10 and [k for k, _ in cases].count("consistent") == 10
    for kind, values in cases:
        status, _ = rules.check_package(values, tools.PARAMS, datetime.date(2026, 11, 1))
        assert status == "clear", (kind, values["notes"])


def test_the_contradiction_notes_are_distinct_and_both_arms_are_registered():
    measure = load_measure()
    notes = [v["notes"] for _, v in measure.contradiction_cases()]
    assert len(set(notes)) == 20
    assert {"set11", "set11p", "set12"} <= set(measure.SETS)
