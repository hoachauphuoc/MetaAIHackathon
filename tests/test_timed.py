"""The timed-runs tile: only stopwatch rows with the right fields are shown, and the saving is computed by code."""
import json

import pytest

import app as app_module
import timed

GOOD = {"task": "Quote one order", "app_seconds": 40, "hand_seconds": 600, "timed_by": "owner",
        "source": "stopwatch", "date": "2026-10-30", "note": ""}


@pytest.fixture
def client():
    return app_module.create_app().test_client()


def test_a_complete_row_gets_its_saving_computed_by_code():
    row = timed.with_saving(GOOD)
    assert row["saved_seconds"] == 560 and row["saved_percent"] == 93


def test_a_row_without_a_by_hand_time_shows_no_saving():
    row = timed.with_saving({**GOOD, "hand_seconds": None, "timed_by": None})
    assert row["saved_seconds"] is None and row["saved_percent"] is None


@pytest.mark.parametrize("change", [{"app_seconds": 0}, {"app_seconds": True}, {"hand_seconds": -5}, {"source": " "},
                                    {"date": ""}, {"timed_by": "claude"}, {"timed_by": None}])
def test_a_row_that_breaks_a_rule_is_refused(change):
    assert timed.problems({**GOOD, **change})


def test_a_broken_row_in_the_file_is_left_out_not_repaired(tmp_path):
    path = tmp_path / "t.json"
    path.write_text(json.dumps({"runs": [GOOD, {**GOOD, "app_seconds": 0}]}), encoding="utf-8")
    assert len(timed.load(path)) == 1


def test_add_refuses_a_bad_row_and_keeps_the_file(tmp_path):
    path = tmp_path / "t.json"
    path.write_text(json.dumps({"runs": []}), encoding="utf-8")
    with pytest.raises(ValueError):
        timed.add({**GOOD, "timed_by": "model"}, path)
    assert json.loads(path.read_text(encoding="utf-8"))["runs"] == []
    timed.add(GOOD, path)
    assert len(timed.load(path)) == 1


def test_the_shipped_file_is_valid_and_has_no_invented_hand_time():
    runs = json.loads(timed.PATH.read_text(encoding="utf-8"))["runs"]
    assert runs and all(not timed.problems(r) for r in runs)


def test_the_route_serves_the_valid_rows(client):
    assert client.get("/api/timed-runs").json["runs"][0]["app_seconds"] > 0
