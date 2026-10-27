---
name: submit-kit
description: Prepare the Meta hackathon submission for the MetaAIHackathon app - README, project write-up, video captions and the submission checklist - from measured numbers only. Use when the user types /submit-kit or asks to prepare the README, write-up, video or submission.
---

# /submit-kit: submission material from evidence

Reply to the user in Vietnamese; every produced file is English.

## Inputs

`C:/Users/phuochoa/MetaAI_design_pre_event/PLAN.md` (pitch, four strengths, video outline), `C:/Users/phuochoa/MetaAI_design_pre_event/MEASURED.md` (from `scripts/measure.py`), `C:/Users/phuochoa/MetaAI_design_pre_event/PROGRESS.md`, the live URL if deployed.

## Outputs

1. `README.md`: one-line pitch; live URL and "Try the demo company"; the four strengths; how each Meta model is used (`muse-wonder-1.0`, `muse-spark-1.3`, others only if really used); privacy design with honest limits (Standard mode is not used for training; Meta's ZDR is not enabled, so do not claim nobody stores anything); measured numbers with sample sizes; run locally; run tests; licence MIT.
2. `C:/Users/phuochoa/MetaAI_design_pre_event/SUBMISSION.md`: problem, who it is for, how Meta's models are used (beyond a basic integration), what was built during Oct 26 - Nov 4 (cite `git log --oneline`), what is next. Frame Meta positively; never mention Meta's past privacy cases.
3. `C:/Users/phuochoa/MetaAI_design_pre_event/VIDEO_CAPTIONS.md`: one caption per scene of the video outline, ≤ 12 words each, timed to `scripts/record_demo.py` steps.
4. A submission checklist in the reply: fields to fill, links to paste, deadline 2026-11-04 9:00 PM ET (2026-11-05 9:00 AM Vietnam).

## Hackathon requirements (Participant Guide, 2026-10-26)

- Public repository; a **3-minute** demo video that shows only what was built during the hackathon; every contributor listed; submit on the Cerebral Valley platform by 2026-11-04 9:00 PM EST.
- **New work only (Indie may not build on existing code):** the Participant Guide gives the building period as Oct 27 – Nov 4, 2026 (kickoff Oct 26, 12:00 PM ET). Use the window recorded in `C:/Users/phuochoa/MetaAI_design_pre_event/PROGRESS.md` Decisions, and disclose anything built before it. README needs a "Built during the hackathon" section with that window, citing `git log --reverse --format="%h %ad %s" --date=short`, and a short "Not built during the hackathon" list: development tooling copied from earlier projects (`.claude/skills_archive/`), the libraries in `requirements.txt`. Failing to separate these risks disqualification.
- Avoid the anti-project framing: describe the agent pipeline (survey → Wonder org design → rule check → parallel Spark assistant builds → private open-weights mode), never "a chatbot" or "RAG".
- Bonus prizes to flag in the submission: Best Build on Meta Open Weight Models (Private mode on Muse Spark Open / Glimmer, name the provider), Best Agentic Use-Case, Most Viral (X post link; produce a ≤ 280-character post text plus the 45-second clip plan), Community Vote.

## Rules

- Every number must come from `C:/Users/phuochoa/MetaAI_design_pre_event/MEASURED.md` or a test count from `scripts/check.ps1`; if missing, write "not measured" rather than a guess.
- Keep the README under ~150 lines.
- List in the reply the 3 sentences the user should reread before submitting (any claim about privacy, any number, any comparison).
