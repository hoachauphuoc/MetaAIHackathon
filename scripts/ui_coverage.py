"""Measure how much of the browser code the judges' path runs: byte coverage of static/*.js in Chromium.

Usage: python scripts/ui_coverage.py            (FAKE_AI, no model calls; needs Playwright's Chromium)
Starts the app locally, walks the same path as scripts/live_check.py, collects Chromium's precise coverage
(Profiler domain over the DevTools protocol, so no new dependency), and prints the share of each module's bytes
that ran. A byte counts as run when its innermost range has a count above zero.
"""
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PORT = 5011


def wait_for_port(port, seconds=30):
    deadline = time.time() + seconds
    while time.time() < deadline:
        with socket.socket() as s:
            s.settimeout(0.5)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.5)
    return False


def covered_bytes(ranges, size):
    """Bytes covered by Chromium's nested ranges: a byte is covered when its innermost range has count > 0."""
    hit = [0] * size
    for fn in ranges:
        for r in sorted(fn["ranges"], key=lambda r: (r["startOffset"], -(r["endOffset"] - r["startOffset"]))):
            for i in range(max(r["startOffset"], 0), min(r["endOffset"], size)):
                hit[i] = 1 if r["count"] > 0 else 0  # later, more nested ranges overwrite the outer ones
    return sum(hit)


def main():
    env = {**os.environ, "FAKE_AI": "1"}
    server = subprocess.Popen([sys.executable, "-m", "flask", "--app", "app", "run", "--port", str(PORT)],
                              cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        if not wait_for_port(PORT):
            raise SystemExit("the app did not start")
        base = f"http://127.0.0.1:{PORT}"
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.set_default_timeout(60_000)
            cdp = page.context.new_cdp_session(page)
            cdp.send("Profiler.enable")
            cdp.send("Profiler.startPreciseCoverage", {"callCount": True, "detailed": True})
            button = lambda name: page.get_by_role("button", name=name)  # noqa: E731
            page.goto(base)
            button("Try the demo company").click()
            button("Design my org chart").click()
            button("Accept this chart").wait_for()
            button("Accept this chart").click()
            button("Create invite link").first.wait_for()
            card = page.locator(".card", has=page.get_by_role("heading", name="Sales")).first
            card.get_by_role("button", name="Create invite link").click()
            link = card.get_by_role("link", name="Open invite link")
            link.wait_for()
            page.goto(base + link.get_attribute("href"))
            button("Plan this order").click()
            for i in range(3):
                b = button("Approve and hand over").nth(i)
                b.wait_for()
                b.click()
            page.locator("#order-done").wait_for()
            scripts = cdp.send("Profiler.takePreciseCoverage")["result"]
            browser.close()
    finally:
        server.terminate()

    by_url = {}
    for entry in scripts:
        if "/static/" in entry["url"] and entry["url"].endswith(".js"):
            by_url.setdefault(entry["url"].rsplit("/", 1)[-1], []).append(entry)
    rows, total, hit_total = [], 0, 0
    for name in sorted(p.name for p in (ROOT / "static").glob("*.js")):
        source = (ROOT / "static" / name).read_bytes()
        entries = by_url.get(name, [])
        # A module can load more than once (a reload, a second page): a byte counts once if any load ran it.
        hit = max((covered_bytes(e["functions"], len(source)) for e in entries), default=0)
        pct = 100 * hit / len(source) if source else 100
        rows.append((name, pct))
        total += len(source)
        hit_total += hit
    for name, pct in rows:
        print(f"{name:14} {pct:6.1f}%")
    print(f"{'all static js':14} {100 * hit_total / total:6.1f}%")
    print("note: app.js is not in Chromium's coverage report for this path, so its 0.0 is a measurement gap, not a finding")
    print(json.dumps({"modules": {n: round(p, 1) for n, p in rows}}))


if __name__ == "__main__":
    main()
