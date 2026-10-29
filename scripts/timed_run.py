"""Record one timed run (stopwatch, same job by hand and with the app) into data/timed_runs.json.

  python scripts/timed_run.py "Quote one clinic treatment plan" --app 48 --hand 540 --by owner --source "stopwatch, my laptop"
Leave out --hand if only the app was timed. Seconds, not minutes."""
import argparse
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import timed  # noqa: E402


def main(argv):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("task")
    p.add_argument("--app", type=float, required=True, help="seconds with the app")
    p.add_argument("--hand", type=float, help="seconds by hand")
    p.add_argument("--by", choices=timed.TIMERS, help="who held the stopwatch (needed with --hand)")
    p.add_argument("--source", required=True)
    p.add_argument("--note", default="")
    a = p.parse_args(argv)
    run = {"task": a.task, "app_seconds": a.app, "hand_seconds": a.hand, "timed_by": a.by, "source": a.source,
           "date": datetime.date.today().isoformat(), "note": a.note}
    if a.hand is None:
        del run["timed_by"]
    try:
        timed.add(run)
    except ValueError as e:
        print("REFUSED:", e)
        return 1
    print("added:", timed.with_saving(run))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
