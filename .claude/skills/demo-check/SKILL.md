---
name: demo-check
description: Start the MetaAIHackathon app locally and give the user a short click-through checklist to try it. Use when the user types /demo-check or asks to see, try or test the app in the browser.
---

# /demo-check: let the user try the app in under 15 minutes

Reply in Vietnamese, briefly.

1. Run `powershell -File scripts/run.ps1` in the background (add `-Real` only if the user asks for real Muse answers; it spends credit). Wait for the "Running on" line, then tell the user the URL (http://127.0.0.1:8080).
2. Build the checklist from the features that exist now (read the latest Log block in `C:/Users/phuochoa/MetaAI_design_pre_event/PROGRESS.md`). At most 6 steps, each one line: what to click or type (in English, exactly as the UI shows it) and what they should see.
3. Ask the user to reply with the step numbers that looked wrong and one line each. Record their feedback under "Next" in `C:/Users/phuochoa/MetaAI_design_pre_event/PROGRESS.md`.
4. When they are done, stop the server.
