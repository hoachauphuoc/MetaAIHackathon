"""The warm loop must keep asking inside the idle limit and stop at the end of the window."""
import importlib.util
from pathlib import Path


def load():
    spec = importlib.util.spec_from_file_location("warm_glimmer", Path(__file__).parent.parent / "scripts" / "warm_glimmer.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_it_asks_every_eight_minutes_and_stops_at_the_end_of_the_window():
    warm = load()
    now = [0.0]
    asked, lines = [], []

    def ask(messages, **kw):
        asked.append(now[0])
        return {"demo_mode": False, "demo_reason": None}

    warm.warm(45, ask, sleep=lambda s: now.__setitem__(0, now[0] + s), clock=lambda: now[0], say=lines.append)
    assert asked == [0, 480, 960, 1440, 1920, 2400]
    assert all(b - a <= 600 for a, b in zip(asked, asked[1:]))  # inside Modal's 10-minute idle limit
    assert len(lines) == len(asked) and "warm" in lines[0]


def test_a_cold_answer_is_reported_not_hidden():
    warm = load()
    lines = []
    warm.warm(1, lambda m, **kw: {"demo_mode": True, "demo_reason": "Private mode starting"},
              sleep=lambda s: None, clock=lambda: 0.0, say=lines.append)
    assert "not ready: Private mode starting" in lines[0]
