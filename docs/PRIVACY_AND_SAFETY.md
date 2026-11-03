Moved from the README; the README has the short version.

# Role Assistant Foundry: privacy and safety

## Claim and proof

| Claim | Proof in the repository |
|---|---|
| Numbers come from code: from the signed order and quote; model-returned arguments that differ are recomputed and flagged `needs_human_check` | `test_bad_tool_arguments_are_retried_once_then_taken_from_the_package` and the Finance note filter in `workflow.py` |
| After a person presses Approve the server issues an HMAC-protected receipt; a forged step is refused | `test_a_receipt_for_another_result_or_another_run_is_refused` |
| An invite approves only its own role's step | `409 wrong_role` in `app.py`, `tests/test_workflow.py` |
| Names you list are masked in the browser; pattern masking alone does not find names | `tests/js/client_names.test.mjs`; [docs/MEASURED.md](MEASURED.md), "PII masking scope US and international" (names: 0 of 4 found by patterns, by design) |
| The calendar file is built by code and refused without a date | `test_a_calendar_file_is_built_by_code_and_refused_without_a_date` |
| Every browser module parses before it reaches a browser | `test_every_browser_module_parses` |

## Privacy and safety design (each line has a test)

| Rule | Test |
|---|---|
| Rules decide structure, the model writes words | `tests/test_rules.py`, `tests/test_chart.py` |
| Only skills from the catalog; forbidden skills never reach an assistant | `tests/test_rules.py`, `tests/test_assistants.py` |
| No silent substitution: a failed model call is labelled `demo_mode` | `tests/test_muse.py`, `tests/test_workflow.py` |
| No chat storage: table contents and logs unchanged after chat | `tests/test_chat_and_privacy.py`, `tests/test_trust.py` |
| No training on employee data in the product (paid Standard mode; `-contributor` model ids refused). The public demo runs on free hackathon credits, which Meta says may use content for product improvement, so it is for sample data only | `tests/test_muse.py`, `tests/test_trust.py` |
| One sandbox cannot read another | `tests/test_store.py`, `tests/test_app.py` |
| A person approves every handoff; the model cannot lower a rules status | `tests/test_workflow.py`, `tests/test_tools_and_gate.py` |
| Private never falls back to the standard API | `tests/test_workflow.py`, `tests/test_trust.py` |
| Handoffs: maker-checker, claim, blocked cannot be accepted, leaver gets 410 | `tests/test_handoffs.py` |
| Handoff check: an empty or unreadable answer is retried once with more room; a second failure goes to a person, and the rules floor still decides | `tests/test_handoffs.py` |
| Units may only tighten their parent's rules | `tests/test_levels.py` |
| Sales inbox **Export approved**: only handoffs every approver accepted and that were not blocked, no notes | `tests/js/exchange.test.mjs` |
| The org chart says who drew it: "Designed by Muse Wonder", or "Template" when Wonder failed | `tests/js/chart_label.test.mjs` |
| Photos: type checked by bytes, never stored, values re-checked by rules, unreadable fields emptied by code | `tests/test_vision.py` |
| Morning brief: lists by rules, no names, no invented documents, owner only | `tests/test_brief.py` |
| First-days plan: kit skills only, nothing stored | `tests/test_onboarding.py` |
| Handover: private draft, own team, leaver cannot accept | `tests/test_handover.py` |
| Chat tools: read-only, scoped to the person, no tokens or names, notes are data | `tests/test_workspace.py` |
| Browser masking of the list in item 5 | `tests/js/pii.test.mjs` |
| Invite tokens never in a query string (`?token=` refused) | `tests/test_chat_and_privacy.py` |
| Model text never becomes HTML | `scripts/check.ps1` fails on `innerHTML` and similar |

OWASP Top 10 for LLM applications, as applied here:

| Risk | What the code does |
|---|---|
| LLM01 Prompt injection | Customer notes sit inside a `<data>` block marked untrusted; the model can only raise a status; measured on 8 injection cases in each of sets 2 (Spark) and 10 (Glimmer) |
| LLM02 Sensitive information disclosure | No message table, no message logging, Referrer-Policy `no-referrer`; invite tokens in the Authorization header and the URL fragment, never in a query string |
| LLM05 Improper output handling | Strict JSON schemas, rules validate every output, `textContent` only in the UI, CSP `script-src 'self'` |
| LLM06 Excessive agency | Models only choose arguments of three deterministic tools; every handoff needs a person; server-issued HMAC receipts after Approve |
| LLM10 Unbounded consumption | 80 model calls per sandbox, a daily cost ceiling, 24-hour sandboxes |
