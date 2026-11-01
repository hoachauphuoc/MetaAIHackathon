"""Record the demo video of the golden path as one .webm with English captions.

    python scripts/record_demo.py [--base http://localhost:5000] [--out demo_video]

Run the app with `scripts/run.ps1 -Real` first. With FAKE_AI the video would show the demo
label everywhere, so use it only to rehearse. One browser page is used for every role so the
recording stays a single file; the person switches by opening the invite links in turn.
Warm the Private-mode endpoint first (`modal run scripts/private_modal.py`, a few minutes before):
a cold Glimmer took 166 s to wake before the GPU snapshot and 23 to 31 s after it, the app waits 35 s a try, and a
slow wake would put "Private mode starting" in the take.
"""
import argparse
import re

from playwright.sync_api import sync_playwright

# The bar sits over the bottom of the page, so the body gets room to scroll content above it.
CAPTION_JS = """
window.caption = (text) => {
  let box = document.getElementById('demo-caption');
  if (!box) {
    box = document.createElement('div');
    box.id = 'demo-caption';
    box.style.cssText = 'position:fixed;left:0;right:0;bottom:0;z-index:99999;padding:14px 24px;' +
      'background:rgba(20,24,31,.92);color:#fff;font:600 22px system-ui;text-align:center';
    document.body.append(box);
    document.body.style.paddingBottom = '140px';
  }
  box.textContent = text;
};
"""


# A title card is the first frame so the recording never opens on an empty page; the hook is a measured number.
CARD = """<body style="margin:0;height:100vh;display:flex;flex-direction:column;align-items:center;
justify-content:center;background:#14181f;color:#fff;font-family:system-ui;text-align:center;padding:0 80px">
<div style="font-size:{big}px;font-weight:800;line-height:1.1">{head}</div>
<div style="font-size:30px;margin-top:28px;max-width:1000px;line-height:1.35">{body}</div>
<div style="font-size:20px;margin-top:36px;opacity:.7">{foot}</div></body>"""

LIVE_URL = "https://role-assistants-662084666675.us-central1.run.app"


def run(base, out):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1280, "height": 720},
                                  record_video_dir=out, record_video_size={"width": 1280, "height": 720})
        page = ctx.new_page()
        page.set_default_timeout(150_000)
        shown = ""

        def card(head, body, foot, hold, big=120):
            # The app's CSP blocks inline styles, so a card must not be set on one of its pages.
            page.goto("about:blank")
            page.set_content(CARD.format(head=head, body=body, foot=foot, big=big))
            page.wait_for_timeout(int(hold * 1000))

        def caption(text):
            nonlocal shown
            shown = text
            page.evaluate(CAPTION_JS)
            page.evaluate("t => window.caption(t)", text)

        def say(text, hold):
            caption(text)
            page.wait_for_timeout(int(hold * 1000))

        def go(url):
            # A new page starts without the bar; put the last caption back at once.
            page.goto(url)
            if shown:
                caption(shown)

        def look(locator):
            locator.first.evaluate("e => e.scrollIntoView({block: 'center'})")
            page.wait_for_timeout(400)

        def link_for(role_word):
            card = page.locator(".card", has=page.locator("h3", has_text=re.compile(f"^{role_word}")))
            card.get_by_role("button", name="Create invite link").click()
            return card.locator("code").inner_text(timeout=30_000)

        card("31.9 s", "From ten answers to an AI assistant for every role, on Meta Muse. "
             "Nothing moves between roles until a person approves.",
             "App side only, one real-model run, owner typing excluded (docs/MEASURED.md)", 6)
        go(base)
        say("Role Assistants: an AI assistant for every role in a small company.", 4)
        page.get_by_role("button", name="Try the demo company").click()
        say("Ten questions describe the company. Muse Wonder designs the org chart.", 4)
        page.get_by_role("button", name="Design my org chart").click()
        caption("Muse Wonder is designing the chart...")
        page.get_by_role("button", name="Accept this chart").wait_for()
        say("Rules check the chart: one top role, no cycles, no more people than the company has.", 6)
        page.get_by_role("button", name="Accept this chart").click()
        caption("Muse Spark writes a role brief per role. Skills come only from an approved list.")
        page.get_by_role("button", name="Create invite link").first.wait_for()
        page.wait_for_timeout(5000)
        sales_url = link_for("Sales")
        ops_url = link_for("Operations")

        go(sales_url)
        look(page.get_by_text("Your messages are not stored on the server"))
        say("A salesperson opens their own link. Chat is stored only in this browser.", 5)
        look(page.locator("#send-price"))
        # The kit is model-written, so the first option is not always Operations.
        page.select_option("#to-role", "ops")
        page.fill("#send-price", "1000")
        say("Sales sends an order with the price below cost to the Operations team.", 5)
        page.get_by_role("button", name="Send handoff").click()
        caption("Rules check it first. The price is below the cost.")
        page.get_by_text("Waiting for Operations").first.wait_for()
        look(page.get_by_text("Waiting for Operations"))
        say("Rules check it first. The price is below the cost.", 5)

        go(ops_url)
        page.get_by_role("button", name="Take it").first.wait_for()
        look(page.get_by_role("button", name="Take it"))
        say("Operations sees it in the team queue and takes it.", 4)
        page.get_by_role("button", name="Take it").first.click()
        look(page.get_by_label("Reason for returning"))
        say("Accept is off: a blocked package can never be accepted. A person returns it.", 5)
        page.get_by_label("Reason for returning").fill("Price is below cost, please fix")
        page.wait_for_timeout(1000)
        page.get_by_role("button", name="Return", exact=True).click()
        page.wait_for_timeout(1500)

        go(sales_url)
        page.get_by_text("Fix and resend").first.wait_for()
        look(page.get_by_text("Returned: Price is below cost"))
        say("The sender sees why it came back.", 4)
        price = page.locator('input[id^="fix-"][id$="-price"]')
        look(price)
        price.fill("1800")
        say("They fix the price, then check again and resend.", 4)
        page.get_by_role("button", name="Check again and resend").click()
        page.get_by_text("Returned to the sender").first.wait_for(state="hidden")
        look(page.get_by_text("Waiting for Operations"))
        say("Checked again: clear. It goes back to the Operations queue.", 4.5)

        go(ops_url)
        page.get_by_text("Returned before").first.wait_for()
        look(page.get_by_text("Returned before"))
        say("The next reviewer sees what was wrong and what changed.", 6)
        page.get_by_role("button", name="Take it").first.click()
        page.get_by_role("button", name="Accept", exact=True).first.click()
        look(page.get_by_text("Accepted"))
        say("A different person than the sender decides. Nothing is tracked per person.", 5)

        go(sales_url)
        look(page.get_by_role("button", name="Plan this order"))
        say("A new order runs through Sales, Operations and Finance. You approve every step.", 5)
        page.get_by_role("button", name="Plan this order").click()
        # Earlier steps keep a disabled Approve button, so wait for the one that is still enabled.
        approve = page.locator("button:not([disabled])", has_text="Approve and hand over")
        lines = ["Sales quotes the order. The margin is computed by code, not by the model.",
                 "Operations schedules the delivery. Nothing moves until you approve.",
                 "Finance: open-weights Muse Glimmer 30B on Modal, Private mode. No silent fallback."]
        for line in lines:
            approve.last.wait_for()
            look(approve.last)
            say(line, 8 if line is lines[-1] else 5)
            approve.last.click()
        page.wait_for_timeout(1000)

        go(base.rstrip("/") + "/trust")
        say("What we store: documents and decisions. Never chats, never employee metrics.", 5)
        card("31 of 31", "end-to-end checks on real models, desktop and phone (set 14, local build). "
             "778 tests with no model calls. A limited independent review by SOLIFAN: 5 findings, 5 fixed in code.",
             LIVE_URL, 7, big=110)
        ctx.close()
        browser.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:5000")
    ap.add_argument("--out", default="demo_video")
    args = ap.parse_args()
    run(args.base, args.out)
