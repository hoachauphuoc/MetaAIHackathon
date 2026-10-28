"""Keep the Private-mode endpoint (Glimmer on Modal) warm for a window, then let it idle out.

A cold start takes about 200 s and the app waits 60 s, so run this a few minutes before a demo or a
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


def warm(minutes, ask, sleep=time.sleep, clock=time.time, say=print):
    """Ask until `minutes` have passed; the first ask can take about 200 s while the model loads."""
    end = clock() + minutes * 60
    while True:
        start = clock()
        out = ask([{"role": "user", "content": "Reply with the word ready."}], max_tokens=5)
        say(f"{time.strftime('%H:%M:%S')} {'warm' if not out['demo_mode'] else 'not ready: ' + str(out['demo_reason'])}"
            f" ({clock() - start:.0f} s)")
        if clock() + EVERY_MINUTES * 60 >= end:
            return
        sleep(EVERY_MINUTES * 60)


if __name__ == "__main__":
    if not muse.private_config():
        raise SystemExit("Set the four PRIVATE_* variables first (see scripts/private_modal.py).")
    warm(float(sys.argv[1]) if len(sys.argv) > 1 else 45,
         lambda m, **kw: muse.complete(None, m, private=True, **kw))
