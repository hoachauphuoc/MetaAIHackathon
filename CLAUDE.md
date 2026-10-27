# CLAUDE.md

Role-based AI assistants for small companies, built on Meta Muse models, for the Meta Global AI Developer Hackathon (Indie track, solo). Submission due 2026-11-04 9:00 PM ET (2026-11-05 9:00 AM Vietnam).

- Plan: `C:/Users/phuochoa/MetaAI_design_pre_event/PLAN.md` (scope, principles, schedule). Progress between sessions: `C:/Users/phuochoa/MetaAI_design_pre_event/PROGRESS.md`.
- Tooling plan: `C:/Users/phuochoa/MetaAI_design_pre_event/TOOLING_PLAN.md`. Full original plan (reference only): `C:/Users/phuochoa/MetaAI_design_pre_event/PLAN_full.md`.

## Working rules

- The user has 1-2 hours a day. Do the work; end every session with a 5-line summary and "Your tasks (≤15 min)".
- Reply to the user in Vietnamese, briefly. Everything in the product (UI, prompts, data, README, video) is English.
- No git: do not run `git init`, commit, push or add a remote until the user explicitly orders it in that message. Choosing a commit option in an earlier question does not count.
- Never read, print or commit API keys. The Meta key is read at runtime from `META_API_KEY` or the file named by `META_API_KEY_FILE`.
- Never run `gcloud` deploy commands; the user runs `scripts/deploy.ps1`.

## Product principles (each has a test)

1. Rules decide structure, the model writes words: `validate_chart()` rejects cycles, orphans, more headcount than the company has.
2. The model may only use skills from `data/skills.json`; forbidden skills (`evaluate_person`, `rank_employees`, `hr_decision`, `monitor_activity`) never reach an assistant.
3. No silent substitution: when Muse fails, the response carries `demo_mode: true` and the UI shows the label.
4. No chat logging: chat goes through a stateless proxy; no table holds messages; logs hold token counts and cost only. Handed-off business documents and decisions ARE stored (company records); employee habits, experience or per-person metrics never are.
5. No training on employee data: Standard mode only; any model id ending in `-contributor` is refused.
6. Sandboxes are isolated: one sandbox can never read another's data.

## Code

- Python 3.13, Flask, stdlib `sqlite3`, OpenAI SDK pointed at `https://api.meta.ai/v1`. Plain HTML/CSS/JS, no build step.
- Tests run with `FAKE_AI=1` and never call a model. One command: `powershell -File scripts/check.ps1`.
- Comments say why, not what. No dead code, no speculative helpers, no new dependency without a reason.
