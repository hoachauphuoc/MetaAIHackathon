# Backlog, run 2026-10-27 (stage 5)

Ranked against the CLAUDE.md principles (a person approves every handoff; code decides structure, the model writes words; no per-person metrics; no stored chat), what the README already lists as built, the schedule (today 27 Oct, feature freeze 2 Nov, 1 to 2 hours a day of review and testing) and demo value for judges. Effort is calendar days of that budget. Items marked (own) are the critic's; the rest came from Muse Spark in `s3_ideas.json`.

| Rank | Idea | Evidence | Effort | Principle it could strain | Verdict |
|---|---|---|---|---|---|
| 1 | Phone-photo measurement set (own) | [b4-07] [b4-09] | 1 | No stored employee data: the photos must be synthetic sheets, not real staff paper | BUILD |
| 2 | Unreadable fields stay empty (own) | [b4-09] | 1 | Code decides structure: legibility must gate the field in code, not in model prose | BUILD |
| 3 | No-train trust mode, narrowed to source links on `/trust` | [b6-03] [b6-04] | 0.5 | None, if `/trust` still reads from running config | BUILD |
| 4 | Receipt snap to ledger with check | [b4-03] [b4-06] [b4-09] | 4 | Code decides numbers; a ledger is a new stored record and a new screen | DEFER |
| 5 | Role handbook builder | [b3-01] [b3-02] [b3-03] | 4 | Nothing kept about how a person works: handovers carry personal notes and names cannot be masked | DEFER |
| 6 | Sandbox cost meter on `/trust` (own) | [b6-03] | 0.5 | No per-person metrics: must be per sandbox only, never per role or person | DEFER |
| 7 | Paper notebook digitizer | [b4-01] [b4-02] [b4-10] | 3 | Code decides structure: many rows per page means the model splits records | CUT |
| 8 | Owner admin draft pack | [b1-01] [b1-04] | 3 | None | CUT |
| 9 | Weekly finance admin summarizer | [b1-02] [b1-03] | 3 | None, but its rationale mixes units | CUT |
| 10 | Approved starter seats to replace shadow AI | [b2-04] [b5-03] [b5-04] | 2 | Never monitor people: detecting shadow AI use would be monitoring | CUT |

## Notes per idea

1. **Phone-photo measurement set (own).** Add measured set 9: ten phone photos of printed job sheets filled in by hand with invented data, scored field by field. The README limit says photo reading was measured only on clean rendered sheets, and a vendor benchmark [b4-09] says handwriting is hard; the hospital OCR study [b4-07] is not small firms. Verdict BUILD: it turns the biggest open limit into a measured number, whatever it is, at low code risk.
2. **Unreadable fields stay empty (own).** Paper to form asks Spark for a per-field legibility flag; code leaves any field marked unreadable empty and highlighted with "A person must check this", instead of a guess. Genuinely new: today the rules re-check values, but a plausible misread passes the rules. Verdict BUILD: it is principle 3 (no silent substitution) applied to vision and pairs with item 1 in the demo.
3. **No-train trust mode.** Mostly built: Standard mode only, `-contributor` refused, `/trust` generated from config. "Approval logs" would list who approved what, which drifts toward per-person records, so drop that part. Genuinely new: `/trust` links Meta's own pages on Standard-mode data use, a vendor statement [b6-03] [b6-04], paraphrased, not quoted. Verdict BUILD: half a day, and judges can follow the link.
4. **Receipt snap to ledger.** Paper to form already photographs a sheet into the handoff form, and `reconcile_amounts` is in the skill catalog. A receipt form is a template; the ledger (stored list, totals, screen) is new. The evidence is old Australian vendor surveys [b4-03] and a 2015 vendor survey [b4-06]. Verdict DEFER: four days does not fit before the freeze.
5. **Role handbook builder.** Overlaps First three days (plan from the role kit) and Kind exit (handover to the team). New part: a role-level handbook compiled from the playbook and accepted documents, owner approved. Evidence is tech talent [b3-01] and vendor figures [b3-02] [b3-03], none about small firms. Verdict DEFER: real value, but personal notes in handovers make it a privacy design task, not a week-one feature.
6. **Sandbox cost meter (own).** The sandbox already counts calls and cost for the cap; show the running total on `/trust`, priced from Meta's list price, a vendor figure [b6-03]. Verdict DEFER: the README already shows per-call cost, so the demo gain is small.
7. **Paper notebook digitizer.** Duplicates Paper to form, including designing the form from a photo of today's paper. The new part, many entries per page, needs code to split rows. [b4-10] is about informal firms in Central America, not the target user. Verdict CUT: duplicate, and item 1 measures the real risk first.
8. **Owner admin draft pack.** The owner's assistant already drafts through `draft_message` and `summarize_document`, and the morning brief covers open documents. Both sources are vendor surveys [b1-01] [b1-04]. Verdict CUT: no new capability.
9. **Weekly finance admin summarizer.** Duplicates the morning brief (code sorts, Spark writes one line, read-only). Its rationale combines a weekly figure [b1-02] with a daily one [b1-03], which this run forbids. Verdict CUT: duplicate.
10. **Approved starter seats.** Invite links per role with seat limits and role-scoped assistants already exist. [b2-04] is a UK vendor survey and [b5-04] is a competitor's free tier. Verdict CUT: duplicate, and anything that finds shadow AI use is monitoring.

## Build order (before the 2 Nov freeze)

1. **Phone-photo measurement set.** Acceptance: `python scripts/measure.py set9` runs on at least ten phone photos of synthetic sheets (at least three hand-filled) stored under `data/`, prints fields correct out of total and median seconds, and writes them to `docs/MEASURED.md`; the README Limits line quotes the measured number; `scripts/check.ps1` passes with `FAKE_AI=1`; no photo shows a real person's data.
2. **Unreadable fields stay empty.** Acceptance: a new test in `tests/test_vision.py` feeds a fake vision answer marking one field unreadable with a value; the API returns that field empty and flagged, the UI shows "A person must check this" next to it, the package cannot be sent until the person fills it, and the rules re-check the filled value; `scripts/check.ps1` passes.
3. **No-train source links on `/trust`.** Acceptance: `/trust` shows a "Meta's own statement" block with links to the two Meta pages, rendered with `textContent`, only when the configured model ids are Standard mode; a test in `tests/test_trust.py` asserts the links appear and that a `-contributor` id is still refused; the CSP and `innerHTML` checks in `scripts/check.ps1` still pass.
