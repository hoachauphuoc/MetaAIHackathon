---
name: day
description: Run one daily build session for the MetaAIHackathon app. Use when the user types /day, says "làm tiếp", "continue", or asks what to do today. Reads the plan and progress, builds the next item, checks, logs progress (no git commits), and ends with the user's short task list.
---

# /day: one build session, user time ≤ 15 minutes

The user has 1-2 hours a day and is not watching the work. Reply in Vietnamese, briefly. Product text stays English.

## Steps

1. **Read state (cheap):** `C:/Users/phuochoa/MetaAI_design_pre_event/PROGRESS.md` (Next, Decisions, last Log block), then the matching session row and scope in `C:/Users/phuochoa/MetaAI_design_pre_event/PLAN.md`. Do not reread files already in context.
2. **Pick work:** the first unfinished item under "Next". If it needs a user decision (a choice between options, a key, a deploy), ask it in ONE `AskUserQuestion` call up front, then continue with what does not depend on it.
3. **Build** the smallest complete slice: code + its tests (principles in `CLAUDE.md`; each principle has a test). Tests use `FAKE_AI=1` and never spend credit. Call the real model only through `scripts/smoke.py` or when a prompt changed, and add its cost to "Credit used".
4. **Check:** `powershell -File scripts/check.ps1`. On FAIL, fix and rerun (at most 3 rounds), then stop and report the failing line.
5. **Log:** add a block at the top of "Log" in `C:/Users/phuochoa/MetaAI_design_pre_event/PROGRESS.md` (date, `Day N`, 2-4 bullets of what changed, measured numbers only) and rewrite "Next".
6. **No git:** never `git init`, commit or push. Git starts only when the user explicitly orders it in a message.
7. **Reply** in exactly this shape:
   ```
   Day N — <one-line result>
   - Done: ...
   - Check: PASS <counts>   (or FAIL <first line>)
   - Credit: $x.xx of $150
   - Next session: ...
   Việc của bạn (≤15 phút):
   1. ...
   ```
   If nothing needs the user, write "Việc của bạn: không có".

## Guardrails

- If the session falls behind the schedule in `C:/Users/phuochoa/MetaAI_design_pre_event/PLAN.md`, say so in the reply and suggest `/cut`.
- Never read or print the Meta key; never run `gcloud`.
- Do not widen scope beyond `C:/Users/phuochoa/MetaAI_design_pre_event/PLAN.md` (stretch items only when the MVP row for the day is done).
