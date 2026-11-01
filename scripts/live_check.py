"""Walk the judges' path on the deployed link in a hidden browser and print what a stranger would see, with timings.

Usage: python scripts/live_check.py <url>      (needs requirements-dev.txt: Playwright and its Chromium)
Demo company -> chart -> accept -> three role invites -> plan an order -> approve the three steps on one invite per role, then reads the Finance
step: which model answered and whether the order completed, and clicks Export approved (CSV) in the Sales inbox.
A second pass at phone width (375 px) runs chart, accept and invite creation again. Real models answer, so it spends
a few cents of the deployed app's credit; warm Private mode first (scripts/warm_glimmer.py) or the Finance step will
say it is starting.
Exit code 1 when any step fails, the order does not complete, no model answered the Finance step, the chart carries
no provenance label, the export does not download, or a Demo mode label (template brief, Private mode starting) is
visible on the invite page or the finished order.
"""
import re
import sys
import time

from playwright.sync_api import sync_playwright

CHART_LABELS = ("Designed by Muse Wonder", "Template")
EXPORT_TIMEOUT_MS = 30_000


def main(url):
    base, failed = url.rstrip("/"), False
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        t0 = time.time()

        def step(what, action):
            nonlocal failed
            start = time.time()
            try:
                action()
                print(f"ok    {time.time() - start:6.1f} s  {what}")
            except Exception as e:  # report and go on: the rest of the path still says something
                failed = True
                print(f"FAIL  {time.time() - start:6.1f} s  {what}: {type(e).__name__}: {str(e)[:200]}")

        def owner_path(page, invite, width):
            button = lambda name: page.get_by_role("button", name=name)  # noqa: E731

            def chart_label():
                origin = page.locator(".chart-origin .badge").first.inner_text()
                if origin not in CHART_LABELS:
                    raise RuntimeError(f"the chart says {origin!r}, not one of {CHART_LABELS}")
                print(f"      chart label: {origin}")

            def make_invites():
                for role in ("Sales", "Operations", "Finance"):
                    card = page.locator(".card", has=page.get_by_role("heading", name=role)).first
                    card.get_by_role("button", name="Create invite link").click()
                    link = card.get_by_role("link", name="Open invite link")
                    link.wait_for()
                    invite[role] = link.get_attribute("href")

            step(f"open the home page ({width} px)", lambda: page.goto(base))
            step("start the demo company", lambda: button("Try the demo company").click())
            step("Wonder designs the chart", lambda: (button("Design my org chart").click(),
                                                      button("Accept this chart").wait_for()))
            step("the chart says who drew it", chart_label)
            step("accept the chart", lambda: (button("Accept this chart").click(),
                                              button("Create invite link").first.wait_for()))
            step("create the Sales, Operations and Finance invites", make_invites)

        page = browser.new_page(viewport={"width": 1280, "height": 900}, accept_downloads=True)
        page.set_default_timeout(240_000)
        button = lambda name: page.get_by_role("button", name=name)  # noqa: E731
        invite = {}

        def approve_all():
            # Each role approves its own step on its own invite; the order travels between them as a code.
            for i, role in enumerate(("Sales", "Operations", "Finance")):
                if i:
                    page.goto(base + invite[role])
                    page.fill("#order-code", code)
                    button("Continue this order").click()
                b = button("Approve and hand over").first
                b.wait_for()
                page.wait_for_function("b => !b.disabled", arg=b.element_handle())
                if i < 2:
                    code = page.get_by_label("Order code", exact=True).input_value()
                b.click()
            page.locator("#order-done").wait_for()

        def no_demo_label(where):
            # A finished path can still be the labelled fallback (template brief, Private mode starting):
            # the judges read that as "not on real models", so a visible label fails the check.
            notes = [n.inner_text() for n in page.locator(".demo-note").all() if n.is_visible()]
            if notes:
                raise RuntimeError(f"{where} shows {notes[0]!r}")

        def export_approved():
            # The download is built in the page from /api/inbox; an empty export still has the header line.
            with page.expect_download(timeout=EXPORT_TIMEOUT_MS) as got:
                button("Export approved (CSV)").click(timeout=EXPORT_TIMEOUT_MS)
            download = got.value
            if download.failure():
                raise RuntimeError(f"the download failed: {download.failure()}")
            with open(download.path(), encoding="utf-8") as f:
                lines = f.read().splitlines()
            if download.suggested_filename != "approved-handoffs.csv" or not lines:
                raise RuntimeError(f"got {download.suggested_filename!r} with {len(lines)} lines")
            print(f"      {download.suggested_filename}: {len(lines) - 1} approved handoffs")

        owner_path(page, invite, 1280)
        step("plan an order", lambda: (page.goto(base + invite["Sales"]), button("Plan this order").click(),
                                       button("Approve and hand over").first.wait_for()))
        step("no Demo mode label on the invite page or the plan", lambda: no_demo_label("the invite page"))
        step("approve the three steps (Finance runs in Private mode)", approve_all)
        step("no Demo mode or Private mode starting label at the end", lambda: no_demo_label("the finished order"))
        finance = page.locator("li.step").last.inner_text() if page.locator("li.step").count() else ""
        model = re.search(r"Answered by (\S+)", finance)  # the badges share one line with the status
        answered = f"Answered by {model.group(1)}" if model else "no model answered"
        print(f"Finance: {answered}; order complete: {'The order is complete' in finance}")
        step("Export approved (CSV) in the Sales inbox downloads a file", export_approved)
        # The point of the path is the Private-mode answer: a Finance step no model answered is a failure here.
        failed = failed or "The order is complete" not in finance or model is None

        phone = browser.new_page(viewport={"width": 375, "height": 812}, is_mobile=True, has_touch=True)
        phone.set_default_timeout(240_000)
        owner_path(phone, {}, 375)
        print(f"total {time.time() - t0:.1f} s")
        browser.close()
    return 1 if failed else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
