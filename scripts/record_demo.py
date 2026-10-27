"""Record the demo video of the golden path as one .webm with English captions.

    python scripts/record_demo.py [--base http://localhost:5000] [--out demo_video]

Run the app with `scripts/run.ps1 -Real` first. With FAKE_AI the video would show the demo
label everywhere, so use it only to rehearse. One browser page is used for every role so the
recording stays a single file; the person switches by opening the invite links in turn.
"""
import argparse
import re

from playwright.sync_api import sync_playwright

CAPTION_JS = """
window.caption = (text) => {
  let box = document.getElementById('demo-caption');
  if (!box) {
    box = document.createElement('div');
    box.id = 'demo-caption';
    box.style.cssText = 'position:fixed;left:0;right:0;bottom:0;z-index:99999;padding:14px 24px;' +
      'background:rgba(20,24,31,.92);color:#fff;font:600 22px system-ui;text-align:center';
    document.body.append(box);
  }
  box.textContent = text;
};
"""


def run(base, out):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1280, "height": 720},
                                  record_video_dir=out, record_video_size={"width": 1280, "height": 720})
        page = ctx.new_page()
        page.set_default_timeout(150_000)

        def say(text, hold=3.0):
            page.evaluate(CAPTION_JS)
            page.evaluate("t => window.caption(t)", text)
            page.wait_for_timeout(int(hold * 1000))

        def link_for(role_word):
            card = page.locator(".card", has=page.locator("h3", has_text=re.compile(f"^{role_word}")))
            card.get_by_role("button", name="Create invite link").click()
            return card.locator("code").inner_text(timeout=30_000)

        page.goto(base)
        say("Role Assistants: an AI assistant for every role in a small company.")
        page.get_by_role("button", name="Try the demo company").click()
        say("Ten questions describe the company. Muse Wonder designs the org chart.")
        page.get_by_role("button", name="Design my org chart").click()
        page.get_by_role("button", name="Accept this chart").wait_for()
        say("Rules check the chart: one top role, no cycles, no more people than the company has.", 4)
        page.get_by_role("button", name="Accept this chart").click()
        page.get_by_role("button", name="Create invite link").first.wait_for()
        say("Muse Spark writes a role brief per role. Skills come only from an approved list.", 4)
        sales_url = link_for("Sales")
        ops_url = link_for("Operations")

        page.goto(sales_url)
        say("A salesperson opens their own link. Chat is stored only in this browser.", 3)
        page.fill("#send-price", "1000")
        say("Sales sends an order with the price below cost to the Operations team.", 3)
        page.get_by_role("button", name="Send handoff").click()
        say("Rules and the assistant check it first. The price is below the cost.", 4)

        page.goto(ops_url)
        page.get_by_role("button", name="Take it").first.wait_for()
        say("Operations sees it in the team queue and takes it.", 3)
        page.get_by_role("button", name="Take it").first.click()
        say("Accept is off: a blocked package can never be accepted. A person returns it.", 4)
        page.get_by_label("Reason for returning").fill("Price is below cost, please fix")
        page.get_by_role("button", name="Return", exact=True).click()
        page.wait_for_timeout(1500)

        page.goto(sales_url)
        page.get_by_text("Fix and resend").first.wait_for()
        say("The sender sees why it came back and fixes the price.", 3)
        page.locator('input[id^="fix-"][id$="-price"]').fill("1800")
        page.get_by_role("button", name="Check again and resend").click()
        say("Checked again: clear. It goes back to the Operations queue.", 3)

        page.goto(ops_url)
        page.get_by_text("Returned before").first.wait_for()
        say("The next reviewer sees what was wrong and what changed.", 3)
        page.get_by_role("button", name="Take it").first.click()
        page.get_by_role("button", name="Accept", exact=True).first.click()
        say("A different person than the sender decides. Nothing is tracked per person.", 4)

        page.goto(sales_url)
        say("A new order runs through Sales, Operations and Finance. You approve every step.", 3)
        page.get_by_role("button", name="Plan this order").click()
        for _ in range(3):
            page.get_by_role("button", name="Approve and hand over").last.wait_for()
            page.wait_for_timeout(2500)
            page.get_by_role("button", name="Approve and hand over").last.click()
        say("Finance runs in Private mode. Every status is computed by rules; the model can only raise it.", 5)

        page.goto(base.rstrip("/") + "/trust")
        say("What we store: documents and decisions. Never chats, never employee metrics.", 5)
        ctx.close()
        browser.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:5000")
    ap.add_argument("--out", default="demo_video")
    args = ap.parse_args()
    run(args.base, args.out)
