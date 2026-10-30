"""Walk the judges' path on the deployed link in a hidden browser and print what a stranger would see, with timings.

Usage: python scripts/live_check.py <url>      (needs requirements-dev.txt: Playwright and its Chromium)
Demo company -> chart -> accept -> Sales invite -> plan an order -> approve all three steps, then reads the Finance
step: which model answered and whether the order completed. Real models answer, so it spends a few cents of the
deployed app's credit; warm Private mode first (scripts/warm_glimmer.py) or the Finance step will say it is starting.
Exit code 1 when any step fails, the order does not complete, or no model answered the Finance step.
"""
import re
import sys
import time

from playwright.sync_api import sync_playwright


def main(url):
    base, failed = url.rstrip("/"), False
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.set_default_timeout(240_000)
        button = lambda name: page.get_by_role("button", name=name)  # noqa: E731
        t0 = time.time()

        def step(what, action):
            nonlocal failed
            start = time.time()
            try:
                action()
                print(f"ok    {time.time() - start:6.1f} s  {what}")
            except Exception as e:  # report and go on: the rest of the path still says something
                failed = True
                print(f"FAIL  {time.time() - start:6.1f} s  {what}: {type(e).__name__}")

        invite = {}

        def make_invite():
            card = page.locator(".card", has=page.get_by_role("heading", name="Sales")).first
            card.get_by_role("button", name="Create invite link").click()
            link = card.get_by_role("link", name="Open invite link")
            link.wait_for()
            invite["href"] = link.get_attribute("href")

        def approve_all():
            for i in range(3):
                b = button("Approve and hand over").nth(i)
                b.wait_for()
                b.click()
            page.locator("#order-done").wait_for()

        step("open the home page", lambda: page.goto(base))
        step("start the demo company", lambda: button("Try the demo company").click())
        step("Wonder designs the chart", lambda: (button("Design my org chart").click(),
                                                  button("Accept this chart").wait_for()))
        step("accept the chart", lambda: (button("Accept this chart").click(),
                                          button("Create invite link").first.wait_for()))
        step("create the Sales invite", make_invite)
        step("plan an order", lambda: (page.goto(base + invite["href"]), button("Plan this order").click(),
                                       button("Approve and hand over").first.wait_for()))
        step("approve the three steps (Finance runs in Private mode)", approve_all)
        finance = page.locator("li.step").last.inner_text() if page.locator("li.step").count() else ""
        model = re.search(r"Answered by (\S+)", finance)  # the badges share one line with the status
        answered = f"Answered by {model.group(1)}" if model else "no model answered"
        print(f"Finance: {answered}; order complete: {'The order is complete' in finance}")
        print(f"total {time.time() - t0:.1f} s")
        # The point of the path is the Private-mode answer: a Finance step no model answered is a failure here.
        failed = failed or "The order is complete" not in finance or model is None
        browser.close()
    return 1 if failed else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
