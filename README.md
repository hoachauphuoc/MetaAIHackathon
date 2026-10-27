# Role Assistants

A small company answers ten questions. Meta Muse Wonder designs its org chart, code rules check
the chart, and Muse Spark writes an AI assistant brief for every role. Employees open their own
link, chat with their role's assistant and run a team workflow in which one person approves every
handoff. Built for the Meta Global AI Developer Hackathon, Indie track, solo.

This is an agent pipeline, not a chatbot: survey, then Wonder (design), then rules (validate),
then Spark in parallel (assistants), then the assistants hand work to each other along the chart
with a person gating every step.

## For judges

- **Try it:** open the live URL (added to the submission), press **Try the demo company**, then
  **Design my org chart**. Nothing to sign up for.
- **Fast path (about 3 minutes):** accept the chart, wait for the four assistants, press
  **Create invite link** on Sales, open it, press **Plan this order**, approve the three steps.
  Finance shows `Private mode unavailable` and `A person must check this` when no open-weights
  provider is configured (see Limits).
- **See demo mode:** on the assistants page tick **Switch Muse off**. Every model answer is then
  labelled `Demo mode` and a person must check it. Nothing silently substitutes another answer.
- **Read the trust page:** `/trust` is generated from the running configuration.
- **Rerun the numbers:** `python scripts/measure.py` (needs a Meta key). Results: [docs/MEASURED.md](docs/MEASURED.md).

## Impact

Employees worry about AI at work, and companies leak data into it. The figures below are quoted
as published; the product answers each one with a design rule that has a test.

| Finding | Source | Product answer |
|---|---|---|
| 52% of US workers feel worried about future AI use in the workplace, 36% hopeful (n = 5,273 employed adults, published 25 Feb 2025) | [Pew Research Center](https://www.pewresearch.org/social-trends/2025/02/25/u-s-workers-are-more-worried-than-hopeful-about-future-ai-use-in-the-workplace) | Assistants help with documents; four skills that evaluate, rank, monitor or decide about people are never available |
| 81% of US adults say AI used to evaluate workers would make workers feel inappropriately watched (fielded 12-18 Dec 2022, n = 11,004 adults) | [Pew Research Center](https://www.pewresearch.org/internet/2023/04/20/ai-in-hiring-and-evaluating-workers-what-americans-think) | No per-person metrics exist anywhere in the data model |
| 48% of respondents entered non-public company information and 45% entered employee information into GenAI tools (Cisco 2024 Data Privacy Benchmark, n = 2,600 privacy and security professionals) | [Cisco](https://newsroom.cisco.com/c/r/newsroom/en/us/a/y2024/m01/organizations-ban-use-of-generative-ai-over-data-privacy-security-cisco-study.html) | Chat is never stored on the server; Standard mode only; a Private mode path for open weights |
| 45% of US employees used AI at work at least a few times a year in Q3 2025, 10% daily (fielded 5-19 Aug 2025) | [Gallup](https://www.gallup.com/workplace/699689/ai-use-at-work-rises.aspx) | Role jobs make AI useful for the daily job without writing prompts |

The strongest evidence is our own measured set, which you can rerun: [docs/MEASURED.md](docs/MEASURED.md).

## How it works

1. **Survey** (10 questions, prefilled for the demo company).
2. **Chart:** `muse-wonder-1.0` returns roles as JSON under a strict schema. `rules.validate_chart`
   rejects circles, missing bosses, two top roles and more headcount than the company has, and
   explains the problem in words. If Wonder fails or breaks a rule, a labelled **Template** chart
   is shown instead. The owner edits any role (live validation) and presses **Accept**.
3. **Assistants:** one `muse-spark-1.3` call per role, in parallel. Skills must come from
   `data/skills.json`; anything else is removed and shown as removed. Handoffs may only point at
   roles that exist.
4. **Invite links:** one per person, tied to a role. A role with no free seat refuses.
5. **Chat:** streamed from Spark; the browser keeps the history (IndexedDB) and sends it with each
   message. The server stores nothing. The assistant's prompt carries a hand-written playbook for
   the role (`data/playbooks.json`) and the company's real rules from `data/params.json` (margin
   floor, approval limit, rate card; cost only for roles that may see it). Measured: 9 of 10
   rule-based questions answered correctly against 2 of 10 with the plain prompt. Before anything is sent, emails, phone numbers, card
   numbers, ID numbers and IBANs are masked in the browser, with a preview. **Compare with generic
   AI** asks the same question of the role assistant and of a plain assistant, side by side.
6. **Team workflow (Sales, Operations, Finance):** each step lets the model choose a tool's
   arguments by function calling; **code computes every number** (`tools.py`). A two-layer check
   follows: rules set a floor, then the model reads the package (customer notes are untrusted
   text) and may only raise the status. A person presses Approve; the server signs each result and
   refuses step N+1 without a valid receipt for step N. A blocked step cannot be approved.

7. **Inbox and Today:** a person sends a quote package to another role along a declared handoff.
   Rules and Spark check it (the model can only raise the status). The receiving team sees it in a
   queue, one person takes it, then accepts or returns it with a reason; a blocked package cannot
   be accepted; a returned package goes back to the sender only, who edits it and sends it again,
   and the next reviewer sees why it came back and what changed; the sender can never decide on
   their own package; the card carries the assistant's two-sentence summary and the queue is
   ordered by rules (waiting for me, overdue, worst status first); on a returned package **Suggest a
   fix** asks Spark for the smallest edit, the rules re-check it and the sender decides; above USD 50,000 the top role
   signs after the receiver; overdue is a property of the package. **Today** counts documents
   only. The owner can remove a person: their link answers 410 with `Clear-Site-Data`, their seat
   frees up, and work they held returns to the queue.

8. **Handoff form:** the document people pass between teams is data, not code. After the chart,
   the owner presses **Design the form for my company**; Spark proposes 4 to 8 fields and rules
   from a fixed vocabulary (not below, margin floor, approval limit, date not in the past),
   `rules.validate_handoff_schema` checks it (no field about people, known types, rules that point
   at real fields), and the owner edits the thresholds and accepts. Thresholds are the owner's or
   the company default, never the model's. If Spark fails, a labelled Template for the industry is
   shown. Every package keeps the form it was sent with. The model never writes interface code:
   the page draws inputs from the form definition and the CSP stays `script-src 'self'`.

The same rule (code decides, the model writes, a person approves) runs through a person's whole
time at the company:

9. **Paper to form:** a person photographs a paper job sheet and Spark vision fills the handoff
   form. Code checks the file (png, jpeg or webp by its first bytes, at most 4 MB), strips
   currency and separators from amounts, and the rules re-check every value before the person
   sends. The owner can also design the company's form from a photo of the paper form in use
   today. Photos are sent once and never stored. Measured: 60 of 60 fields on 10 rendered sheets.
10. **Morning brief:** the owner presses one button and sees the open documents in three short
   lists (needs the top role, stuck, moving today) with counts by role. Code puts each document
   in its list; Spark writes one line per document and never sees names or links; a line for an
   unknown document or naming a person is replaced by a line written by code. Read-only: signing
   still happens in the top role's inbox.
11. **First three days:** a new person opens their link and gets a three-day plan built from
   their role's assistant: what they send and to whom, which assistant skill helps. Only the
   kit's skills survive; a labelled template stands in without Muse. The plan and the ticks
   stay in that browser, so nobody, the owner included, sees how far they got.
12. **Kind exit:** a person leaving drafts a handover from the documents they still hold or sent
   and their own notes. The draft is private until they send it; it goes to their own team, or
   to the top role when nobody shares the role, and they cannot accept it themselves. When the
   owner removes them, the handover stays with the team.

## Meta models used

| Model | Used for | Measured |
|---|---|---|
| `muse-wonder-1.0` | Org chart under a strict JSON schema | 10 of 10 charts passed the rules first try; median 5.9 s; USD 0.0134 per chart |
| `muse-spark-1.3` | Role briefs (structured output), chat (streaming), tool calls (function calling), handoff checks (structured output), photo reading (vision), morning brief, first-days plan, handover draft | Brief about USD 0.005; chat answer USD 0.0015; fix suggestion median 3.2 s, 9 of 9 answered suggestions left no blocked package; photo reading 60 of 60 fields, median 3.3 s, USD 0.002 per sheet; morning brief 0 names or invented documents in 70 lines |
| Open-weights Muse Spark Open (Private mode) | Finance-step tool call and check, through a configurable provider | **Not enabled in this build**, see Limits |

Details and caveats: [docs/MEASURED.md](docs/MEASURED.md).

## Privacy and safety design (each line has a test)

| Rule | Test |
|---|---|
| Rules decide structure, the model writes words | `tests/test_rules.py`, `tests/test_chart.py` |
| Only skills from the catalog; forbidden skills never reach an assistant | `tests/test_rules.py`, `tests/test_assistants.py` |
| No silent substitution: a failed model call is labelled `demo_mode` | `tests/test_muse.py`, `tests/test_workflow.py` |
| No chat storage: table contents and logs unchanged after chat | `tests/test_chat_and_privacy.py`, `tests/test_trust.py` |
| No training on employee data: `-contributor` model ids refused | `tests/test_muse.py`, `tests/test_trust.py` |
| One sandbox cannot read another | `tests/test_store.py`, `tests/test_app.py` |
| A person approves every handoff; the model cannot lower a rules status | `tests/test_workflow.py`, `tests/test_tools_and_gate.py` |
| Private never falls back to the standard API | `tests/test_workflow.py`, `tests/test_trust.py` |
| Handoffs: maker-checker, claim, blocked cannot be accepted, leaver gets 410 | `tests/test_handoffs.py` |
| Photos: type checked by bytes, never stored, values re-checked by rules | `tests/test_vision.py` |
| Morning brief: lists by rules, no names, no invented documents, owner only | `tests/test_brief.py` |
| First-days plan: kit skills only, nothing stored | `tests/test_onboarding.py` |
| Handover: private draft, own team, leaver cannot accept | `tests/test_handover.py` |
| Personal data masked in the browser | `tests/js/pii.test.mjs` |
| Model text never becomes HTML | `scripts/check.ps1` fails on `innerHTML` and similar |

OWASP Top 10 for LLM applications, as applied here:

| Risk | What the code does |
|---|---|
| LLM01 Prompt injection | Customer notes sit inside a `<data>` block marked untrusted; the model can only raise a status; measured on 8 injection cases |
| LLM02 Sensitive information disclosure | No message table, no message logging, Referrer-Policy `no-referrer` because the invite token sits in the URL |
| LLM05 Improper output handling | Strict JSON schemas, rules validate every output, `textContent` only in the UI, CSP `script-src 'self'` |
| LLM06 Excessive agency | Models only choose arguments of three deterministic tools; every handoff needs a person; signed receipts |
| LLM10 Unbounded consumption | 80 model calls per sandbox, a daily cost ceiling, 24-hour sandboxes |

## Built during the hackathon

- Repository history starts on **2026-10-27 11:09 (UTC+7)**, inside the Oct 27 to Nov 4 building
  period. All code, tests and data in this repository were written from that point.
- Design notes and a throw-away interface prototype were drafted on 2026-10-26 before the kickoff.
  They are **not** in this repository and no code from them was copied; the interface was rewritten
  from scratch. Only the general visual direction was reused.
- AI-assisted development: the code was written with Claude Code; the product itself runs on Meta
  Muse models.

## Limits (honest)

- **Private mode is built but not enabled in this build.** The open-weights path (`muse.py`,
  `PRIVATE_PROVIDER`, `PRIVATE_BASE_URL`, `PRIVATE_MODEL`, `PRIVATE_API_KEY_FILE`) is tested with
  stubs only; no open-weights provider was connected when this was written. When it is not
  configured the Finance step says `Private mode unavailable` and asks a person to check. It
  never uses the standard API instead. When enabled, the interface says "hosted by <provider>" and
  `/trust` shows "Built with Muse Spark Open".
- Demo scope: an invite link is the whole credential (no passwords). Sandboxes live in memory for
  24 hours and are lost on restart.
- Photo reading was measured on clean rendered sheets, not phone photos of real, creased or
  handwritten paper; expect misreads there. Photos are not masked for personal data. Voice and
  web search are not used: the `web_search` tool type is rejected (HTTP 400) in the form I tried,
  and voice was not tried.
- The morning brief, first-days plan and handover draft were each run against the real model
  only a few times (see MEASURED); the handover is worded by the model from the person's own
  notes, which the person must read before sending.
- Measured sets are synthetic and small; the model layer of the gate was not tested for
  contradictions the rules cannot see.
- The handoff form is generic; the fixed Sales, Operations, Finance order demo and its rate card
  exist only for the logistics form, so other trades see the inbox and chat only. Only the notes
  field is masked for personal data in the browser; the other text fields are not, so do not type
  personal names into them (also stated on `/trust`).
- Not built: Shadow/Assist/Primary modes, handoffs to a named person, manager assignment, parallel
  approval, CSV import, export, voice, org advisor.
- PII masking is pattern-based and cannot detect names (shown to the user and on `/trust`).

## Run it

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
$env:META_API_KEY_FILE = "path\to\your\key.txt"
powershell -File scripts/run.ps1 -Real     # http://localhost:5000
powershell -File scripts/check.ps1         # tests, no model calls
python scripts/smoke.py                    # real API access check
python scripts/measure.py [set1 ... set7]  # the measured sets (all, or the named ones)
python scripts/record_demo.py              # records the golden path as a captioned .webm
```

Deploy: `scripts/deploy.ps1 -Project <id>` (Cloud Run, one instance, secrets from Secret Manager).

Models are called through the OpenAI SDK pointed at `https://api.meta.ai/v1`.
