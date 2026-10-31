# Role Assistants: Independent Review (SOLIFAN, 2026-10-31), English translation

> **Unofficial English translation.** Prepared by the project owner's tooling so that readers who do not read Japanese can follow the report. The Japanese PDF next to this file, `Role_Assistants_Independent_Review_JP_20261031.pdf`, is the original and governs. Nothing was added, softened or removed; layout is simplified. Page markers follow the PDF (6 pages).

---

## Page 1 / 6: Summary and scope

SOLIFAN | INDEPENDENT REVIEW | 2026-10-31 JST | Role Assistants | source `1b7e7bde1c0e`

**Role Assistants: Independent Review Report**

Subject: Mr. Hoa Chau Phuoc, public project for the Meta Global AI Developer Hackathon.

**Verdict:** the main demo path works. There are three important fixes to the core safety claims.

Signed approval is implemented. However, binding to the company, binding to the source data, and execution control of banned skills are not sufficient.

As a concept, the aim of combining AI support that employees use with company rules is clear. The role-by-role flow, the display of the switch to a template, the design that does not switch to a standard model when Private fails, and the attitude of stating the limits of the measurements are all to be commended. On the other hand, "calculation is code" and "results are signed" alone cannot guarantee processing that rests on the right order and the right company's authority.

| Item checked | Result this time |
|---|---|
| Re-run of existing tests | Python 403 / 403 and JavaScript 33 / 33 passed. `FAKE_AI=1`, no external model calls. |
| End-to-end check of the public demo | Fictional logistics company → Wonder org chart → Spark assistants → Sales invitation → 3-step approval → order completed. A Glimmer response is displayed in Finance. |
| Independent abnormal-case verification | Reproduced locally: acceptance of another company's plan, calculation with valid arguments that differ from the order, execution of a banned skill, and continued approval of an old plan. |
| Check of measured values | The measurement code, case structure and explanations were cross-checked. Past real-model correct counts, costs and times were not independently re-measured. |

**Scope and conditions of verification.** The public code was pinned to the commit below. Verified on Linux / Python 3.12.14 / Node 24.22.1, using the versions of pytest, Flask and the OpenAI SDK specified by the repository. The execution environment differs from CI (Python 3.13 / Node 22). It is not confirmed whether the public demo is the same build as this commit.

Commit: `1b7e7bde1c0e9f0d437f9c36fbb395e0b39f9a07`
Demo: https://role-assistants-662084666675.us-central1.run.app

The additional verification is local verification using fictional data and stubbed model responses. No abnormal-case attempts against production, no input of real data, and no changes to source or settings were made. This is a technical review with a limited scope.

---

## Page 2 / 6: Claims and evidence

### Agreement between the description and the implementation / handling of measured values

| Claim | Result and reservation |
|---|---|
| AI does not lower the rules' verdict | `rules.combine_status` selects the maximum of the ranking. Even if the model says clear, a rules-side blocked or similar remains; existing tests also pass. |
| Tampered results and unapproved next steps are rejected | plan / ticket / receipt are verified with HMAC. There are tests that reject price tampering and reuse of a receipt from another run. However, binding to company and version: see H01. |
| Banned skills are removed from assistants | Removal from generated kits and keeping a child level's bans were confirmed. Bans are not re-checked when the fixed order workflow runs (H03). |
| Chat is not stored on the server | No DB table for messages. Existing tests confirm the DB and logs do not change. Business documents that were handed over are stored separately by design and are distinguished from chat non-storage. |
| Private does not silently fall back to a standard model | The code and stub tests have fallback prevention. This time, a Glimmer response was confirmed in the UI on the normal path. Failure and cold start were not re-tested in production. |
| The limits of the measurements are stated | Small scale, synthetic data, author-made scoring, unmeasured user effects, and set14 being impossible to re-run are stated in the README and MEASURED. |

### How far the measurement results were checked

The 20 cases of set11 were read from the code, and it was independently confirmed that with the rules alone all 20 come out clear. The test setup that treats contradiction detection as an evaluation of the model layer is therefore sound. However, figures such as "Spark 10/10" and "Glimmer 9/10" are the author's past measurement results, and this time's 403 stubbed tests do not demonstrate that accuracy.

In the public tree, the individual responses and raw run results of the main real-model measurement sets cannot be seen. A batch re-measurement using a real-model key and billing was not performed, so past cost, latency and correct counts cannot be treated as independently certified. The fact that set14 is report-only and cannot be re-run is already stated.

### L01 / Minor: unify the definition of median

Several places in `measure.py` use `sorted(values)[len(values)//2]`. For an even count this is the upper median, not the usual median (the average of the two middle values). Example: for 1 to 10 it gives 6, and the usual median is 5.5. Either unify on `statistics.median` or state "upper median" explicitly, and re-aggregate from the raw data.

Evidence: `scripts/measure.py` L107; `docs/MEASURED.md`; `tests/test_workflow.py`

---

## Page 3 / 6: H01, context binding

### H01: a signed plan is not bound to a company

Priority: high / reproduced locally over HTTP.

When company A's plan, which carries a genuine signature, is run by a user of company B, it is processed under B's looser rules. Approval of a result issued in A also succeeded with a user of B.

**Reproduction results**

Condition: A's margin floor is 30%, B's is 12%. The same signed plan from A and the same order are used.

| Action | Actual response |
|---|---|
| `/api/workflow/step` by a user of A | HTTP 200 / needs_attention |
| Run the same A plan with a user of B | HTTP 200 / clear |
| B calls `/api/workflow/approve` with A's ticket | HTTP 200 / receipt issued |

Related: an old plan after the org chart is replaced. After an old role was removed from the org chart, approval of the old ticket was still HTTP 200.

**Cause:** what is signed is kind, run_id, step_id and payload; the plan contains no company ID, no company / policy version, and no acting principal. `step` takes the rules from the company of the user attached to the request, and `approve`, after confirming that the user is valid, does not use that company or role.

**Scope of impact:** this presupposes that one already holds A's signed plan / ticket. It was not confirmed that unknown orders of other companies can be listed, that tokens can be guessed, or that the signature can be cryptographically forged. The signature itself was not broken; the problem is that the permitted use of a genuine signature is not bound.

**Fix and acceptance condition**

Bind the same company ID, company / policy version and expiry to the plan, ticket and receipt, and check them against the current user at every endpoint. Where needed, also bind the acting principal to an opaque ID, and state in the specification whether approval is by individual staff or a single-user demo approval.

Acceptance condition: reject every route that uses A's plan, result or receipt at B, and either invalidate an old plan after a company or rules change or re-evaluate it under the current authority and rules. Confirm that the normal sequence of approvals within the same company still succeeds.

Evidence: `app.py` L333; `workflow.py` L57

---

## Page 4 / 6: H02, source-argument integrity

### H02: calculation arguments do not match the original order

Priority: high / reproduced with a model stub.

The formulas are code, but if the AI chooses wrong arguments of a valid type and range, they can be calculated, signed and approved as they are. The match between the original order and the calculation input is not guaranteed by code.

| Verification example | Expected / actual |
|---|---|
| Signed order of 10 pallets, AI chooses the valid argument `pallets=1` | Expected: 10 × rate → price 1,800 / cost 1,500. Actual: price 180 / cost 150. clear, `demo_mode=false`, and an approval receipt is also issued. |
| Finance chooses `price=10000, cost=1` | The signed quote is 1,800 / 1,500, yet the Finance result is 10,000 / 1, margin 100.0%, and clear. |

**Cause:** `call_tool` checks the expected tool name and the type and range of the arguments, but does not match each argument against the signed task / the previous-step receipt. A different quantity or amount that is valid as input does not become an error, and neither a retry nor a switch to the original data happens. If the later model check misses it, it becomes clear.

**What this confirms:** this is not a measurement that a real model errs at this frequency. It is a test showing that, if the model returns wrong but valid arguments, the code's safety boundary cannot prevent it. The price, cost and margin of the one production order this time were calculated correctly.

**Fix and acceptance condition**

Match `quote_price` route / pallets to the signed order, `check_margin` price / cost to the signed quote, and the calendar date to the signed order. Where the business permits a change, show the difference as a change proposal, have a person approve the revision of the original order, and then re-plan.

On a mismatch, do not execute that result or treat it as clear: normalize the arguments and re-check, or move it to an explicit error / needs-check. The tests should include not only "invalid arguments" but also "valid arguments that differ from the order".

**Sign after binding the data.** A signature detects tampering with results the server produced. It does not guarantee the correctness of results the server itself produced from wrong input. The README statement "every number is plain code" should state alongside it whether source-data binding exists.

Evidence: `workflow.py` L113; `workflow.py` L214; `tools.py`

---

## Page 5 / 6: H03, tool authorization

### H03: a banned skill runs on the order path

Priority: high / reproduced locally over HTTP.

When `quote_price` is banned at the Group, it is removed from Sales' kit. However, even for an order plan newly created after the ban, `quote_price` is executed.

| Action / check | Result |
|---|---|
| Save `banned_skills=[quote_price]` at the Group | HTTP 200 |
| Fetch the Sales kit's skills | `quote_price` is not included. The removal itself succeeded. |
| After the ban, create a new plan and run the quote | HTTP 200 / tool=`quote_price` / price=1800 |

**Cause:** the fixed STEPS and handoff edges are validated, but the current company's ban list and the role's allowed skills are not checked before tool execution. This is not a problem of old plans only; it also reproduces with new plans after the ban.

**Fix and acceptance condition**

Immediately before each tool call, check on the server the role's allowed list and the ban lists of all levels. If banned, do not call the model, do not execute the tool, and return a reason for refusal. Check the same constraint at plan issue and at approval, so that a ban changed midway cannot slip through.

Acceptance condition: refuse the banned tool on every route (new plans, existing plans, and direct API). Legitimate tools that are not banned keep working, and the existing test that a child level cannot lift a parent's ban is kept.

Evidence: `app.py` L503; `workflow.py` L18; `workflow.py` L214; `rules.py` L99

### Precision of the phrase "signed approval"

The implementation is not an electronic signature with the person's own private key. It is a method in which the server that received the Approve action issues an HMAC-protected receipt. In the 3-step logistics demo, the same invited user approves every step. Please explain it as a path separate from the Inbox maker-checker and role-by-role decisions. It cannot be said that there is non-repudiation by the individual, or an audit record signed individually by each person in charge.

Suggested wording: "After a person clicks Approve, the server issues an HMAC-protected receipt for the approved result."

After the fix, explain that the receipt is also bound to company, version and acting principal.

---

## Page 6 / 6: Live result and acceptance

### Notes for production and items to confirm after the fixes

**M01 / Medium: Clear together with a contradicting finding observed in production**

This time's Finance step correctly displayed price 2,160 / cost 1,800 / margin 16.7%. However, while the status was Clear, the explanation and the Assistant's notes displayed "the margin does not match the price and cost". Final approval and order completion nevertheless succeeded as they were. The model response was measured once, and the occurrence rate is unmeasured.

When the status and the explanation disagree, do not show it as Clear: provide conservative consistency handling, for example by stating the contradiction explicitly and moving to needs-check. Add a stub response in which the model returns clear and an inconsistent finding at the same time, and verify that the screen and the final state agree.

| Priority | What must be confirmed after the fix |
|---|---|
| 1 / H01 | Reject another company's plan, ticket and receipt. Fix how an old plan is treated after a company / rules version change. |
| 2 / H02 | Detect valid quantities, amounts and dates that differ from the original order, and do not sign or approve with the wrong input as it is. |
| 3 / H03 | A banned skill does not run on any route (new and old plans, direct API) and stops before the model call. |
| 4 / M01 | Do not show Clear together with a contradicting finding. Make status, explanation and confirmation action agree. |
| 5 / L01 | Unify the median on the usual definition, keep each measurement output and its version, and re-aggregate. |

**Regression check.** Add boundary tests to the existing 403 tests and 33 JS tests. Finally, run one order through the public demo and re-check the screen and the README.

### Minimum set to make the measurement materials more verifiable

For the main sets, keep together anonymized individual JSON files, run times, code SHA, model IDs, settings and the aggregation script. Include not only success counts but also failures, timeouts and no-answers, and do not mix past one-off values such as 31.9 seconds with future re-measurements in the same notation. There is no need to publish personal information or keys.

### Final findings

The intent of the concept and the normal demo hold up. There is also a strength in the honesty of the explanations. The center of the improvement is not adding features, but consistently binding the source data, the company and the permissions to the signed result. Until the three points above are fixed, the evaluation "a finished product that guarantees the company's authority and constraints through to execution" is withheld.

The reproduction results in this report were obtained in a local environment at the specified commit. In production, only the normal path and the display were checked. Voice, photos, all industries, concurrency, load tolerance, and re-verification of third-party research sources are outside the scope of this review.

Evidence: `README.md`; `static/join.js` L283
