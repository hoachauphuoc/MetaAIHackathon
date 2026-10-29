# Role Assistants

A small company answers ten questions. Meta Muse Wonder designs its org chart, code rules check
the chart, and Muse Spark writes an AI assistant brief for every role. Employees open their own
link, chat with their role's assistant and run a team workflow in which one person approves every
handoff. Built for the Meta Global AI Developer Hackathon, Indie track, solo, for the problem
statement **Build for Your World**: the domain is the small company the author knows firsthand, and
the time freed is the owner's and each employee's.

**Models:** Muse Wonder (org chart), Muse Spark (assistants, chat, forms), Muse Glimmer 30B on Modal
(Private mode). **Layered rules:** a company can split into units (Group, Subsidiary); a unit may
only tighten its parent's margin floor and approval limit and must keep every skill its parent bans, and the server
refuses anything looser, naming the rule and the parent's value. A one-level company sees no difference. **Catches what rules
cannot:** a package whose notes contradict its fields passes every rule, and the model layer flags it
(set 11, Spark leg: 10 of 10 caught, 1 false alarm in 10 clean ones; the author wrote the cases).

**Measured, rerunnable:** with the role playbook and company rules in the prompt the assistant passed
9 of 10 rule questions, against 2 of 10 with a plain role prompt (set 4, string-match checks written by
the author; [docs/MEASURED.md](docs/MEASURED.md)). What is and is never stored: `/trust` and the
[privacy table](#privacy-and-safety-design-each-line-has-a-test).

**Live:** https://role-assistants-662084666675.us-central1.run.app

This is an agent pipeline, not a chatbot: survey, then Wonder (design), then rules (validate),
then Spark in parallel (assistants), then the assistants hand work to each other along the chart
with a person gating every step.

## For judges

- **Try it:** open https://role-assistants-662084666675.us-central1.run.app, press **Try the demo company**, then
  **Design my org chart**. Nothing to sign up for.
- **Fast path (a short click path; the app's own setup took 31.9 s in one measured run, the rest is your clicking):** accept the chart, wait for the assistants (one per role; four or five for the demo company, depending on the chart Wonder designs), press
  **Create invite link** on Sales, open it, press **Plan this order**, approve the three steps.
  Finance runs on the open-weights model in Private mode; if no provider is reachable it shows
  `Private mode starting` (or `unavailable`) and `A person must check this` (see Limits).
- **See demo mode:** on the assistants page tick **Switch Muse off**. A banner confirms it, and every
  model answer is then labelled `Demo mode` and a person must check it. Nothing silently substitutes another answer.
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
| 22.4% of owner time goes to administrative tasks plus legal and compliance (UENI's own survey, n = 837 US businesses with five or fewer employees, May 2024) | [UENI](https://ueni.com/en-us/small-business-research/how-microbusiness-owners-spend-their-time) | The morning brief lists open documents by role so the owner sees what waits on whom; the model writes words, code picks the documents |
| 11 hours a week on administrative or finance tasks (American Express SME Barometer, a company-run survey, n = 1,000 UK owners, July 2026) | [Retail Times](https://retailtimes.co.uk/amex-sme-barometer-small-business-owners-spend-nearly-twice-the-time-on-admin-than-growing-their-business/) | Handoffs carry a checked form instead of a chat thread, and the chat assistant reads the person's own documents. We measured accuracy, not hours saved |
| 66% of US adults agree AI-based worker evaluation would lead to the collected information being misused (Pew, 20 Apr 2023) | [Pew Research Center](https://www.pewresearch.org/internet/2023/04/20/americans-views-on-use-of-ai-to-monitor-and-evaluate-workers/) | Nothing is kept about how a person works, and the onboarding plan shows nobody, including the owner, how far a new hire got |
| 4.8 months average onboarding time for a new technical hire (Linux Foundation, 2024 State of Tech Talent, 418 records; tech roles, not small firms) | [Linux Foundation](https://www.linuxfoundation.org/blog/the-2024-state-of-tech-talent-report) | Day-One gives a new hire a first-three-days plan from their role's kit, and Kind exit lets a leaver hand over to their own team |
| 44% of informal microbusinesses keep systematic records, about three-quarters of those in notebooks (ILO survey, n = 1,400 firms in Guatemala, Honduras and El Salvador, working paper Oct 2025) | [Wharton School](https://accounting.wharton.upenn.edu/wp-content/uploads/2025/10/AguilarLindRamesh.pdf) | Paper to form turns a photo of the paper into a form a person checks. Measured on synthetic sheets only |

The five rows added in October 2026 were found by a chained research run (Claude Haiku, Sonnet and
Opus helped as development tools; the product itself runs on Muse only) and each figure was opened
again at its source by a second pass. Two rows are a company's own survey and say so. The method,
the 39 checked figures and what they do not show are in [docs/research](docs/research/README.md).
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
   today. Photos are sent once and never stored. When the model cannot read a field it names it, and
   code empties that field and marks it "A person must check this" instead of keeping a guess.
   Measured: 60 of 60 fields on 10 rendered sheets (56 of 60 on the first run, before code stripped
   thousands separators from amounts); on 10 phone-degraded handwriting-style sheets
   53 of 56 legible fields, and 4 of 4 smudged fields left empty.
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
13. **The assistant reads your documents:** in chat, Spark can call three read-only tools (list
   my documents by group, read one document, count them). Code scopes every result to what that
   person sees in their inbox; no result names a person or carries a link; document text, notes
   included, goes back to the model as untrusted data. The assistant only reads: claiming,
   accepting, returning and sending stay with people. The answer says what it looked at, and
   nothing is stored. Measured: 11 of 11 questions on a seeded inbox, 0 leaks, 0 followed
   injections; equal to pasting the inbox into the prompt on accuracy and slightly dearer at this
   size (MEASURED.md, set 8).
14. **My private rules:** on their own link a person sets a stricter margin floor or approval limit
   for their own assistant. The server refuses anything looser than the company's number and says
   which one; what is saved is readable only with that link, never by the owner or a unit. The
   numbers come from code, the model only uses them in that person's chat.
15. **Plug into what you already run:** a handoff can be filled from a JSON or CSV file and the
   inbox exported as JSON or CSV. Import only fills the form (free-text notes are left out so they
   still pass the masking step), a person checks and sends it, and exported cells that start like
   a spreadsheet formula get a leading quote. **Export approved** adds a second export that holds only handoffs every approver accepted and that were not blocked, with the form's own columns in the form's order, the approval chain and no free-text notes, ready for a sheet or another system to read. No connector, key or outbound call is involved: the person downloads the file.
15b. **A second industry without training:** a clinic ("Try the clinic demo", or any industry that says clinic, dental, medical or health) gets its own chart template, a "Treatment plan quote" form (patient reference as a number, not a name; fee, cost, first visit) checked by the same code rules (fee not below cost, margin floor, approval limit, date not in the past), and playbooks that no longer talk about routes and pallets. Retail and services keep their forms; an industry we have no form for still falls back to the services form and the chart says Template. Nothing is trained: the structure is a shipped template, the rules are code, and Muse only writes words. Not measured: Wonder on clinic surveys, and the clinic form is not meant for real patient data.

15c. **A code helper for software companies:** a software studio ("Try the software studio demo", or any industry that says software, developer or devops) gets a chart with an Engineering Lead whose assistant holds the skill "Explain, review or draft code for a person to copy and run themselves". Code, not the model, gives that skill to the engineering role only; a level can ban it like any other skill. The assistant has no tool that runs, deploys or pushes (a test lists every tool and fails on such a name), its playbook says to label drafts "Untested draft" and never to repeat a secret, and passwords, cloud keys, vendor tokens and private-key blocks in a pasted message are masked in the browser like personal data. Not measured against the real model beyond one spot check; image generation was cut from this build.
16. **What is stuck and where:** the sender's inbox lists what they sent that still waits for another
   team, with its age and whether someone took it (never who), and a reminder draft per row. The
   draft is built by code from the package's own fields and is only copied; nothing is sent.
17. **Customer message to form:** paste a customer's message and Spark fills the company's form.
   Emails and phone numbers are masked in the browser first, the message is treated as data, a
   field the model could not read is emptied by code, the rules check the result, and the person
   checks and sends. Nothing is stored.
18. **Start from a past quote:** a new draft from one of the sender's own handoffs. Dates are
   cleared, rate-card figures are recomputed by code, and every change is listed.
19. **Speak the job:** a push-to-talk button (up to 60 seconds) turns a spoken job note into text with
   Muse Voice Transcribe. The browser converts the recording to 16 kHz mono WAV, the server checks it
   by code (format, length) and sends it once; only the text comes back, into the message box of
   item 17, so the same masking, the same model reading and the same person checks apply. The
   recording is never stored. Measured once with a real microphone (a Vietnamese sentence came out
   right); not yet measured on noisy speech or on a full order (see Limits).
20. **Cover before reading:** on a photo, the person names what to hide (for example `signature`),
   SAM 3.1 outlines it, and the browser paints those boxes black on its own copy before Spark reads the
   photo. Only boxes come back (code parses and clips them), the request sets `store: false`, and the
   screen says SAM can miss things: the person looks at the preview before sending. Checked in a hidden
   browser against the real endpoint on a synthetic page (a red rectangle became black); not measured
   on real documents.

## Meta models used

| Model | Used for | Measured |
|---|---|---|
| `muse-wonder-1.0` | Org chart under a strict JSON schema | 10 of 10 charts passed the rules first try; median 5.9 s; USD 0.0134 per chart |
| `muse-spark-1.3` | Role briefs (structured output), chat (streaming), tool calls (function calling), handoff checks (structured output), photo reading (vision), morning brief, first-days plan, handover draft | Brief about USD 0.005; chat answer USD 0.0015; fix suggestion median 3.2 s, 9 of 9 answered suggestions left no blocked package; photo reading 60 of 60 fields after the amount-cleaning fix (56 of 60 on the first run), median 3.3 s, USD 0.002 per sheet; morning brief 0 names or invented documents in 70 lines; model layer of the handoff check flagged 10 of 10 contradictions the rules cannot see, 1 false alarm in 10 (set 11, Spark only) |
| `muse-voice-transcribe-1.0` | Speech to text for a spoken job note (item 19), one short WAV per request | Not yet run against the real endpoint; list price USD 0.18 per audio hour, so a 30 second note is about USD 0.0015 |
| `sam-3.1` | Outline what a short phrase names in a photo so it can be covered before reading (item 20) | One real call on a synthetic page returned the exact box; price not published on the docs page, so no cost is claimed |
| `meta-models/Muse-Glimmer-30B` (open weights, Private mode, served by me on Modal with vLLM) | Finance-step tool call and check, through a configurable provider | 10 of 10 function calls with the right arguments; 12 of 12 seeded errors flagged, 0 statuses below the rules floor; 3 of 10 clean packages raised needlessly (Spark: 0); set 10 |

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
| Photos: type checked by bytes, never stored, values re-checked by rules, unreadable fields emptied by code | `tests/test_vision.py` |
| Morning brief: lists by rules, no names, no invented documents, owner only | `tests/test_brief.py` |
| First-days plan: kit skills only, nothing stored | `tests/test_onboarding.py` |
| Handover: private draft, own team, leaver cannot accept | `tests/test_handover.py` |
| Chat tools: read-only, scoped to the person, no tokens or names, notes are data | `tests/test_workspace.py` |
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

## Building period (built during the hackathon)

- Repository history starts on **2026-10-27 11:09 (UTC+7)**, inside the Oct 27 to Nov 4 building
  period. All code, tests and data in this repository were written from that point.
- Design notes and a throw-away interface prototype were drafted on 2026-10-26 before the kickoff.
  They are **not** in this repository and no code from them was copied; the interface was rewritten
  from scratch. Only the general visual direction was reused.
- AI-assisted development: the code was written with Claude Code; the product itself runs on Meta
  Muse models.

## What it costs a company per month (assumptions labelled)

The per-call prices are measured ([docs/MEASURED.md](docs/MEASURED.md)). The usage counts are
**assumptions** for a 10-person company with 5 roles and 22 working days a month, in three
scenarios anchored on published figures. **The busy one is our headline: about USD 21 a month for a
10-person company under these assumed counts. It is an estimate, not measured usage.**

- **Light:** 4 chat answers per person per day. ChatGPT's 18 billion messages a week from 700
  million weekly users is about 3.7 a day per user, most of it not about work ([NBER paper by OpenAI, 2025](https://cdn.openai.com/pdf/a253471f-8260-40c6-a2cc-aa93fe9f142e/economic-research-chatgpt-usage-paper.pdf)).
  5 orders a day through the team workflow.
- **Busy:** 24 chat answers per person per day, 6 times the light figure: OpenAI reports its heaviest
  workers send 6 times the median ([State of Enterprise AI, Dec 2025](https://cdn.openai.com/pdf/7ef17d82-96bf-4dd1-9df2-228f7f377a29/the-state-of-enterprise-ai_2025-report.pdf)).
  20 orders a day.
- **All day:** 80 answers per person per day, one every 6 minutes over an 8-hour day (our assumption, no
  published figure). 50 orders a day: suppliers put a manual purchase order at 8 to 12 minutes
  ([Hobson & Company, via TradeCentric](https://tradecentric.com/blog/manual-order-processing-cost)), so
  50 is about 8 hours of handling for the team.

Setup time, measured on 2026-10-28 with the real models in a hidden browser run of the demo company
(5 roles): the chart took 6.0 s and the five assistant briefs 4.7 to 6.3 s each, one after another, 31.9 s
in all. That is the app's side only: typing the ten answers and reading the result are not counted, and
the same job by hand was not timed. Details in [docs/MEASURED.md](docs/MEASURED.md) (setup time).

| | Light | Busy | All day |
|---|---|---|---|
| Setup, once (1 chart USD 0.038 + 5 briefs USD 0.0047 each) | USD 0.06 | USD 0.06 | USD 0.06 |
| Chat answers, USD 0.0015 each | USD 1.32 | USD 7.92 | USD 26.40 |
| Workflow steps, 3 per order, under USD 0.01 each (upper bound used) | up to USD 3.30 | up to USD 13.20 | up to USD 33.00 |
| **Total per month (Muse Wonder and Spark)** | **about USD 5** | **about USD 21** | **about USD 59, at most** |

Private mode (Glimmer on Modal) is billed per warm GPU hour, not per call, and is not in this
table. Photos, morning briefs and fix suggestions cost about USD 0.002 to 0.02 each and are left out.
The 80-call cap and the daily cost ceiling protect the public demo; they are not a company's bill.

## Reasoning effort per call

Each call sets `reasoning_effort` itself; reasoning tokens are billed as output.

| Effort | Calls | Why |
|---|---|---|
| `minimal` | chat answers, workflow tool calls and the model check, fix suggestions, reading a paper document, the morning brief, reading the person's own documents | Short answers and checks; measured in set 12: `high` was 3.6 times slower, 4.9 times dearer and flagged no more contradictions |
| `low` | the org chart (Wonder), role briefs, handoff forms, handover draft, first-days plan | Structured output that must follow a schema; a little reasoning helps and the cost stays small |

## Limits (honest)

- **Private mode runs on Muse Glimmer 30B, not Muse Spark Open.** Spark Open (816B) does not fit one
  GPU, so the Finance step uses Glimmer (open weights) served by me on Modal
  (`scripts/private_modal.py`). It is configured by `PRIVATE_PROVIDER`, `PRIVATE_BASE_URL`,
  `PRIVATE_MODEL`, `PRIVATE_API_KEY_FILE`; `/trust` shows the model in use. Measured in set 10 on a
  warm endpoint. A cold start takes about 200 s and the app waits 35 s a try, so when the endpoint is
  idle the step says `Private mode starting` (once per request, inside the 120 s request limit) and asks a
  person to press retry; when Private mode is not configured it says `Private mode unavailable`. It never
  uses the standard API instead. Its schema-forced JSON skips a visible reasoning phase, so it raises harmless points
  more often than Spark.
- Demo scope: an invite link is the whole credential (no passwords). Sandboxes live in memory for
  24 hours and are lost on restart.
- Photo reading was measured on rendered sheets, including phone-degraded ones in handwriting-style
  fonts (set 9), not phone photos of real, creased or handwritten paper; expect misreads there. Photos are not masked for personal data. Web search
  is not used: the `web_search` tool type is rejected (HTTP 400) in the form I tried. Voice input
  (item 19) is built and tested with fake recordings and a stubbed model; a real-model
  word-error rate on noisy speech has not been measured.
- The morning brief, first-days plan and handover draft were each run against the real model
  only a few times (see MEASURED); the handover is worded by the model from the person's own
  notes, which the person must read before sending.
- Measured sets are synthetic and small. The model layer of the gate was tested for contradictions the
  rules cannot see in set 11 (Spark leg only: 10 of 10 caught, 1 false alarm in 10 consistent
  packages, written by the author); the Glimmer leg (`set11p`) has not been run.
- The handoff form is generic; the fixed Sales, Operations, Finance order demo and its rate card
  exist only for the logistics form, so other trades see the inbox and chat only. Only the notes
  field is masked for personal data in the browser; the other text fields are not, so do not type
  personal names into them (also stated on `/trust`).
- Not built: Shadow/Assist/Primary modes, handoffs to a named person, manager assignment, parallel
  approval, org advisor. (Handoff JSON/CSV import and export are built; see "How it works".)
- PII masking is pattern-based and cannot detect names (shown to the user and on `/trust`).

## Run it

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
$env:META_API_KEY_FILE = "path\to\your\key.txt"
powershell -File scripts/run.ps1 -Real     # http://localhost:5000
powershell -File scripts/check.ps1         # tests, no model calls
python scripts/smoke.py                    # real API access check
python scripts/measure.py [set1 ... set10]  # the measured sets (no argument runs sets 1 to 9; set10 needs Private mode)
python scripts/record_demo.py              # records the golden path as a captioned .webm
```

Deploy: `scripts/deploy.ps1 -Project <id>` (Cloud Run, one instance, secrets from Secret Manager).

Models are called through the OpenAI SDK pointed at `https://api.meta.ai/v1`.

## License

MIT, see [LICENSE](LICENSE).
