"""Timed runs: the same job done by hand and with the app, shown as a tile on the landing page.

The file data/timed_runs.json is written by a person with a stopwatch (scripts/timed_run.py), never by a model.
Code decides what may be shown: a row needs an app time, a source and a date; a by-hand time needs to say who
timed it; the saving is computed here, so no page or model can state a number the file does not hold."""
import json
from pathlib import Path

PATH = Path(__file__).parent / "data" / "timed_runs.json"
TIMERS = ("owner", "author", "outside")  # "outside" = a person who is not the author


def problems(run):
    errors = []
    for key in ("task", "source", "date"):
        if not (isinstance(run.get(key), str) and run[key].strip()):
            errors.append(f"{key} is required")
    app = run.get("app_seconds")
    if isinstance(app, bool) or not isinstance(app, (int, float)) or app <= 0:
        errors.append("app_seconds must be a number above 0")
    hand = run.get("hand_seconds")
    if hand is not None:
        if isinstance(hand, bool) or not isinstance(hand, (int, float)) or hand <= 0:
            errors.append("hand_seconds must be a number above 0, or null when it was not timed")
        if run.get("timed_by") not in TIMERS:
            errors.append(f"timed_by must be one of {', '.join(TIMERS)} when hand_seconds is set")
    return errors


def with_saving(run):
    hand, app = run.get("hand_seconds"), run["app_seconds"]
    if hand is None:
        return {**run, "saved_seconds": None, "saved_percent": None}
    return {**run, "saved_seconds": round(hand - app, 1), "saved_percent": round(100 * (hand - app) / hand)}


def load(path=PATH):
    """Valid rows only; a broken row is left out, never repaired."""
    runs = json.loads(Path(path).read_text(encoding="utf-8")).get("runs", [])
    return [with_saving(r) for r in runs if not problems(r)]


def add(run, path=PATH):
    errors = problems(run)
    if errors:
        raise ValueError("; ".join(errors))
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    data["runs"].append(run)
    Path(path).write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
