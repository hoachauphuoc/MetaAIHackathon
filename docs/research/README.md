# Research pipeline (development tool, not part of the product)

The product runs on Muse only. This pipeline helped decide what to build next and which figures the README may quote. It used Claude models through Claude Code subagents and Muse Spark for one stage. None of it ships in the app, `/trust` or the Models table.

## Stages

| # | Stage | Model | Output |
|---|---|---|---|
| 1 | Collect candidate sources per brief | Claude Haiku | `s1_sources.json` |
| 2 | Extract one figure per source with a short quote | Claude Sonnet | `s2_evidence.json` |
| 3 | Propose upgrades from the evidence digest | Muse Spark | `s3_ideas.json` |
| 4 | Re-open each source and check the figure; Opus settles mismatches | Claude Sonnet, then Opus | `s4_verified.json` |
| 5 | Critique and rank against the product rules and the schedule | Claude Opus | `FINDINGS.md`, `s5_backlog.md` |

The six briefs are in `briefs.json`. Outputs of each run are in `runs/<date>/`.

## What code decides (`scripts/research.py`, tested in `tests/test_research.py`)

- A stage file that breaks its contract (missing date or sample size, quote over 15 words, duplicate id, a figure never checked) is rejected, never repaired by a model.
- Stage 4 sees only the URL, figure and unit, not the stage 2 reasoning, so the check is independent.
- Muse sees figures and short quotes, never URLs. Ideas that cite evidence ids not in the data are dropped. If Muse fails the file says `demo_mode: true`.
- `FINDINGS.md` and the backlog may cite only `verified` ids (`research.py cites`).
- The impact rows in docs/IMPACT_AND_COSTS.md come from `research.py impact-rows` or are cited directly from the linked page; company-run surveys are labelled as such. The product answer in each row is written by the author.

## Run

`/survey` in Claude Code runs all six briefs; `/survey b1` runs one. The pipeline was run from Claude Code with a local skill that is not part of this repository; `scripts/research.py` and its tests are.
