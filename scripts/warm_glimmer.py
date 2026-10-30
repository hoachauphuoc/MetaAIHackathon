"""Keep the Private-mode endpoint (Glimmer on Modal) warm for a window, then let it idle out.

A cold start took 166 s when timed (docs/MEASURED.md, set 10) and the app waits 35 s, so run this a few minutes before a demo or a
recording and leave it open. One tiny request every 8 minutes keeps the container inside Modal's
10-minute idle limit, so the GPU is billed for the window only. Needs the four PRIVATE_* variables
(see private_modal.py); prints timings and never the key.

    python scripts/warm_glimmer.py 45        # stay warm for 45 minutes
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import muse  # noqa: E402

EVERY_MINUTES = 8


WAKE_TRIES = 20  # each cold try waits out the app's own request timeout, so 20 tries cover a slow wake
WAKE_PAUSE_S = 5


def warm(minutes, ask, sleep=time.sleep, clock=time.time, say=print):
    """Ask until `minutes` have passed. While the model is still loading, ask again after a short pause and, at the
    first real answer, print how long the wake took: on an endpoint idle for over 10 minutes that is a cold start."""
    end = clock() + minutes * 60
    first, tries, woke = clock(), 0, False
    while True:
        start = clock()
        out = ask([{"role": "user", "content": "Reply with the word ready."}], max_tokens=5)
        say(f"{time.strftime('%H:%M:%S')} {'warm' if not out['demo_mode'] else 'not ready: ' + str(out['demo_reason'])}"
            f" ({clock() - start:.0f} s)")
        if not woke and not out["demo_mode"]:
            woke = True
            if tries:
                say(f"Woke after {clock() - first:.0f} s from the first try. If the endpoint had been idle for over "
                    "10 minutes, this is a cold start: record it in docs/MEASURED.md.")
        if not woke and tries < WAKE_TRIES:
            tries += 1
            sleep(WAKE_PAUSE_S)
            continue
        if clock() + EVERY_MINUTES * 60 >= end:
            return
        sleep(EVERY_MINUTES * 60)


if __name__ == "__main__":
    if not muse.private_config():
        raise SystemExit("Set the four PRIVATE_* variables first (see scripts/private_modal.py).")
    warm(float(sys.argv[1]) if len(sys.argv) > 1 else 45,
         lambda m, **kw: muse.complete(None, m, private=True, **kw))
