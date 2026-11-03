# Independent review by SOLIFAN

Summary: the reviewer found 5 issues (3 high, 1 medium, 1 low); all 5 are fixed. The reviewer did not re-check the fixes, and this is not a certification.

A one-time technical review of this repository by SOLIFAN (reviewer: Mr. Okada Shinji), dated 2026-10-31 JST, performed on commit `1b7e7bde1c0e9f0d437f9c36fbb395e0b39f9a07`. The reviewer gave the owner permission to quote the report, the reviewer's name and the company name in the hackathon submission.

The reviewer is an acquaintance of the author from another hackathon and was not paid. This is not a quality certification. The report says its scope is limited: it re-ran the existing tests with no model calls, walked the public demo once, and reproduced abnormal cases locally with fictional data and stubbed model responses. It did **not** independently re-measure the author's past real-model figures (cost, latency, correct counts).

| File | What it is |
|---|---|
| `Role_Assistants_Independent_Review_JP_20261031.pdf` | The original report in Japanese, unmodified. It governs. |
| `Independent_Review_EN.md` | An unofficial English translation for readers. |

Original PDF SHA-256: `ba06cc2c25d1d0a78778b4b3afb5df2806d7fc7c118708dc3486781111ac1095`. Check with `Get-FileHash <file> -Algorithm SHA256` (PowerShell) or `sha256sum <file>`.

## What the review found and what was done about it

The review found three high findings, one medium and one low, and asked for wording changes. Each has a code change after the reviewed commit; H01, H02, H03 and M01 also have regression tests, L01 does not. All of this was done on 2026-10-31 after the report arrived.

| Finding | Summary | Fix commit | Regression test |
|---|---|---|---|
| H01 | A signed plan was not bound to a company | `4b39dbb` | `test_http_plan_from_another_sandbox_and_stale_plan_are_refused` |
| H02 | Valid-but-different tool arguments were calculated, signed and approved | `52a2863` | `test_valid_but_different_{quote,margin,calendar}_*_are_recomputed_and_flagged` (3 tests) |
| H03 | A banned skill still ran on the order path | `43e18a4` | `test_http_banned_tool_is_refused_at_plan_step_and_approve` |
| M01 | Status `clear` shown together with a contradicting finding | `3a913c8` | `test_clear_verdict_with_findings_needs_a_human_check` |
| L01 | Median was the upper median for even counts | `3a913c8` (code) and `e479854` (note) | none (`scripts/measure.py` now uses `statistics.median`) |
| Wording | "Signed approval" must say it is a server-issued HMAC receipt, not a personal signature; "every number is plain code" must name its source binding | `e479854` | README and `docs/MEASURED.md` text |

Tests are in `tests/test_workflow.py`. The full suite is run with `powershell -File scripts/check.ps1`.

## What is not done

- The review asked for a re-aggregation of the measured figures with the usual median. The figures in `docs/MEASURED.md` have **not** been re-run; the file now says so and says old and new figures must not be mixed.
- The review asked for per-case raw results of the main measurement sets to be kept with run time, code SHA, model ID and settings. That is not in the repository yet.
- The reviewer did not check that the fixes are correct. They were verified only by this repository's tests.
- The public demo was reviewed against the commit above; whether the live build equals a later commit is for the reader to check.
