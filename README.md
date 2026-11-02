# Role Assistant Foundry

An AI assistant for each role of a small company; 24-hour trial, sample data only; the order workflow covers Sales, Operations and Finance.

[Try it](https://role-assistants-662084666675.us-central1.run.app) · [Video](static/video/welcome.mp4)
<!-- The submitted video URL is for the owner to add here before submission. -->

It is an agent pipeline, not a chatbot: survey, then Wonder (design), then rules (validate), then Spark (one assistant brief per role), then the assistants hand work to each other along the chart with a person gating every step. Code checks every draft against the company's rules, and a person approves every handoff between roles. Finance defaults to Private mode when it is configured; the person can switch the step to Public. Every model call is listed in [Meta models used](#meta-models-used).

From ten survey answers to an assistant for every role took 31.9 s of app time on Meta Muse: app side only, one real-model run, five-role demo company, owner typing excluded ([docs/MEASURED.md](docs/MEASURED.md), "Setup time"). No real company has used it yet: every figure comes from synthetic data and the author's own test cases.

Architecture (request path, order workflow, levels, stored vs never stored): [docs/architecture.html](docs/architecture.html) (text version: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)).

Contents: [Stage One checklist](#stage-one-checklist) · [Try it](#try-it) · [Run it](#run-it) · [How it works](#how-it-works) · [Built today, and not built](#built-today-and-not-built)
Also: [What is measured](#what-is-measured) · [Meta models used](#meta-models-used) · [Privacy and safety design](#privacy-and-safety-design-each-line-has-a-test) · [Impact](#impact) · [What it costs](#what-it-costs-measured-per-call-usage-is-an-assumption)

## The problem, and what this makes possible

**The problem.** The author manages software teams and watches the same standoff every week: the company
wants AI but fears leaked client data, and employees fear AI the company can watch, so they paste work into
outside chatbots (the author's observation, not a survey). The nearest external figure: 48% of privacy and
security professionals entered non-public company information into GenAI tools ([Cisco 2024](https://newsroom.cisco.com/c/r/newsroom/en/us/a/y2024/m01/organizations-ban-use-of-generative-ai-over-data-privacy-security-cisco-study.html), n = 2,600).
More external figures are in [Impact](#impact).

**What was not possible before:** a ten-person company has no one to set up an assistant per role, and a
chat window cannot pass a quote from Sales to Operations to Finance under the company's own limits.

**What the code does that a chatbot cannot** (each is in code and tests):

- `validate_chart()` rejects cycles, dangling managers and more headcount than the company has (`tests/test_rules.py`).
- Work moves between roles only as tool calls whose numbers code computes from the signed order and quote;
  model-returned arguments that differ are recomputed from that source and flagged `needs_human_check` (`tests/test_workflow.py`).
- Each step unlocks only after a person presses Approve and the server issues an HMAC-protected receipt for
  the approved result (a server-issued receipt, not a personal signature); the next step requires it.
- Each invite approves only its own role's step; any other invite gets `409 wrong_role` (`app.py`, `tests/test_workflow.py`).
- The order passes to the next role's device as an order code (**Continue an order**), which the server re-checks.
- A rules floor sets the minimum status; the model can raise it, never lower it; a blocked step cannot be approved.
- Private mode never falls back silently to another model.
- Invite tokens stay out of URLs: API calls carry the token in the Authorization header, invite links use the
  URL fragment (`/join#token`), `?token=` on the API is refused with `400 token_in_url`, and the old path form
  is rewritten into the fragment by the browser, so an old `/join/<token>` link sends the token to the server once, in
  the request path, before the rewrite (`app.py`, `static/jointoken.js`, `tests/test_chat_and_privacy.py`).


## Stage One checklist

Legend: **Answer** is our claim, **Proof** is where to check it. What is built and what is not: [Built today, and not built](#built-today-and-not-built).

| Item | Answer | Proof |
|---|---|---|
| Problem statement | **Build for Your World.** Owners of small companies (around ten people) want AI but fear leaked client data, and employees fear AI the company can watch; this gives each role an assistant under the company's own rules. | [The problem](#the-problem-and-what-this-makes-possible), [Founder's story](#founders-story-why-role-assistant-foundry) |
| Meta models used | Muse Wonder (`muse-wonder-1.0`), Muse Spark (`muse-spark-1.3`), Muse Glimmer 30B on Modal (Private mode); experimental and not measured: Muse Voice Transcribe, SAM 3.1 | [Meta models used](#meta-models-used), `muse.py` |
| Live link | https://role-assistants-662084666675.us-central1.run.app | [docs/MEASURED.md](docs/MEASURED.md), set 16: one run on the deployed revision `role-assistants-00034-9z8`, 17 of 17 steps ok at desktop and 375 px width |
| Demo video | `static/video/welcome.mp4` in this repository (also played on the home page); the submitted video: see submission (URL to be added by the owner) | [static/video/welcome.mp4](static/video/welcome.mp4) |
| Public repository | https://github.com/hoachauphuoc/MetaAIHackathon, MIT | [LICENSE](LICENSE) |
| Built during the building period | First commit `04ef41b`, 27 Oct 2026 00:09 ET; from this first commit on (it holds the smoke script and the dev skills) | [Building period](#building-period-built-during-the-hackathon), `git log --reverse --format='%h %aI %s'` |
| Written before the building period | The idea and planning notes written on 26 Oct 2026 (planning, API study, feature research, design reviews) are **not** in this repository | [Building period](#building-period-built-during-the-hackathon) |

## What is measured

Every figure below has a set number in [docs/MEASURED.md](docs/MEASURED.md); all sets are small, synthetic and run by the author.

| Figure | What it is |
|---|---|
| 31 of 31 | End-to-end checks on real models in a hidden browser, desktop and 375 px phone (set 14, one run, local build, not the deployed link, no Private mode) |
| 9 of 10 vs 2 of 10 | Rule questions answered with the role playbook and company rules in the prompt vs a plain role prompt (set 4, author-written questions, string-match checks) |
| 10 of 10, 1 false alarm in 10 | Contradictions the rules cannot see (0 of 10) flagged by the Spark check, with 1 false alarm on 10 clean packages (set 11, author-written cases) |
| 39.5 s | The deployed link walked end to end on desktop, Finance answered by Muse-Glimmer-30B, Glimmer already awake (set 15, 2026-11-01, one run; the revision was not recorded) |
| 60.7 s | The deployed revision `role-assistants-00034-9z8` walked at desktop and 375 px width, 17 of 17 steps ok, Glimmer already awake (set 16, 2026-11-01, one run) |

Not measured: time and mental space freed. No hours saved are claimed; the hand-timed run is `scripts/timed_run.py` and has no by-hand time yet.

**Tests:** 327 Python test functions (790 cases with parametrization) and 39 JS tests, all passing, from `powershell -File scripts/check.ps1` (run 2026-11-02; it prints all three counts). The independent review's findings and their fixes are in [docs/evidence/solifan](docs/evidence/solifan/README.md).

## Founder's story: why Role Assistant Foundry

**The deadlock.** I manage software development and maintenance teams, and I watch the same standoff
every week. The company wants AI in the work, but fears leaked client data and uncontrolled cost. Banning
outside AI is unrealistic; forcing one rigid internal tool gets resisted. Employees want AI too, but they
fear AI the company can watch: that their workflows, domain know-how and the prompts they have refined will
be logged and one day used to replace them. So they walk around the company tool and paste work into outside
chatbots, which is exactly where client data leaks.

**The idea.** AI as an extension of the person, not their replacement, with governance and privacy kept in
different hands. My stance, which the design follows: *employees are not a fallback for failing automation;
they are the essential physical and intellectual interface.* That is why a person approves every handoff and
no model can remove that gate. The employee gets an assistant for their own role, and nothing in it reports
on how they work.

- **The company decides** the roles, which skills each role's assistant may use, the margin floors and
  approval limits, and who must approve each handoff. Code enforces these and the server refuses anything
  looser, naming the rule.
- **The employee keeps** the chat (held in their own browser, with a button to clear it; the server has no
  table of messages and its logs hold token counts, cost, model, timing and error type, never message text),
  and **My private rules** (item 14), readable only with their link and never by the owner.

**Why now.** Giving every role its own assistant, with permissions per level, used to mean consultants and
infrastructure. With Meta's models the owner answers ten questions and the app's side of the setup took
31.9 s in one run. I expect a first-time owner to need 5 to 10 minutes of clicking: an estimate, **not measured**.

**Rules this build follows.**

1. **One real problem, from my own desk.** The market I know is IT outsourcing and software-maintenance firms,
   where a client contract on data security meets staff who want AI's speed (the "Try the software studio
   demo" company is that case). No real company has used the app, so this is not dogfooding.
2. **AI proposes; code and a person decide.** Wonder and Spark propose and write; the rules, the skills
   catalogue, the approval chain and the call limits are code that a model answer cannot loosen. Nothing is
   sent, approved or exported without a person pressing the button. No tool runs, deploys or pushes. The demo runs on free Meta credit; Meta may use data from free-credit traffic (Meta's billing page says content may be used for product improvement while free credits are in use). Paid Standard use is excluded; `-contributor` ids are refused.
3. **Evidence over promises.** A figure appears here only if a run produced it (with the set number in
   [docs/MEASURED.md](docs/MEASURED.md)); anything else is labelled an estimate, not measured, or not built.
   A failed model call is shown as demo mode, never filled in. `/trust` states what the app stores and what it never does.
4. **Off the critical path.** The model plans at setup (the chart and a brief per role); at run time it only
   writes words and picks tool arguments. Every number and every permission is plain code, so a slow or failed
   model call can delay a note but cannot change a price, a limit or an approval.
5. **Privacy first, scoped honestly.** Masking happens in the browser before text goes to a model; what it
   covers and what it misses is in item 5. Nothing about how a person works is stored.

**Authority split: what the model may decide and what only code decides.**

| The model decides (words and proposals) | Code decides (structure, money, safety) |
|---|---|
| Wonder proposes the org chart; Spark writes each role's brief, chat replies, form drafts and notes | The chart stands only if it has no cycle, no orphan, one top role and no more people than the company has |
| Spark chooses the arguments of a tool call | Every number (price, cost, margin) is computed by the tool from the signed order and quote; only skills in `data/skills.json` reach an assistant; banned skills never do |
| The assistant's check adds notes to a step | The rules set the status and the model can only raise it, never lower it; a blocked step cannot be approved |
| Nothing | Approval limits, margin floors and the approver chain; the next step starts only with the server-issued HMAC receipt |
| Nothing | The per-sandbox model-call limit, Standard mode only (a `-contributor` model id is refused; the free-credit demo may be used by Meta, check the provider terms), no table of chat messages |

The tests behind these rows are in [Privacy and safety design](#privacy-and-safety-design-each-line-has-a-test).

## Try it

- **Open** https://role-assistants-662084666675.us-central1.run.app, press **Try the demo company**, then
  **Design my org chart**. Nothing to sign up for.
  *Limit: there is no login. An invite link is the whole credential (no passwords): anyone holding the link acts as that
  person, and the owner removes the person under People to revoke it. Sandboxes live in an
  in-memory SQLite database on the one Cloud Run instance, are removed after 24 hours and are lost on a restart.
  Staff must: keep personal names out of form fields, guard their invite link, and check the model's output.*
- **Fast path:**
  1. Accept the chart and wait for the assistants (one per role; four or five for the demo company, depending on the
     chart Wonder designs).
  2. Press **Create invite link** on Sales, Operations and Finance.
  3. Open Sales and press **Plan this order**.
  4. Approve the Sales step.
  5. Paste the order code under **Continue an order** on the Operations link, then on the Finance link.
  6. Approve each step there.

  App time from the home page to the first invite link was 15.3 s (local build, no Private mode; sum of set 14 steps 1 to 5; one real-model run, no typing).
- **Finance runs in Private mode on Glimmer.** Above the order form a line says whether Private mode is set up
  and whether Glimmer answered in the last ten minutes (probably warm) or not (may be asleep); the server only
  reports its last answer; the status check never probes the endpoint. Opening the order form does send one wake
  request (no order data, at most one per two minutes per server) so filling the form covers part of the start.
  *Limit: the endpoint sleeps when idle.*
  - Cold start: 166 s once, before the GPU snapshot, and 23 to 31 s in four runs after it
    ([docs/MEASURED.md](docs/MEASURED.md), set 10; not confirmed that the endpoint was asleep each of the four times).
  - The app waits 35 s a try, so a cold step shows `Private mode starting` and `A person must check this`, then retries
    on its own with a countdown (or press **Run this step again**); it never switches to another model.
  - When Private mode is not configured it shows `Private mode unavailable`.
- **Then the rules:** on the invite page, **My private rules** refuses a margin floor below the company's. In the
  Sales inbox, **Export approved (CSV)** downloads only handoffs every approver accepted (`tests/js/exchange.test.mjs`).
  **Try the software studio demo** shows another industry on the same engine.
- **See demo mode:** on the assistants page tick **Switch Muse off**. A banner confirms it, every model answer is
  then labelled `Demo mode` and a person must check it.
- **Read the trust page:** `/trust` is generated from the running configuration.
- **Rerun the numbers:** `python scripts/measure.py` (needs a Meta key) reruns the measured sets; set 14 (the
  hidden-browser run of the whole path) is reported, not rerunnable from this repo.

## How it works

### Core flow (items 1-8)

1. **Survey** (10 questions, prefilled for the demo company).
2. **Chart:** `muse-wonder-1.0` returns roles as JSON under a strict schema. `rules.validate_chart`
   rejects circles, missing bosses, two top roles and more headcount than the company has, and
   explains the problem in words. If Wonder fails or breaks a rule, a labelled **Template** chart
   is shown instead. The owner edits any role (live validation) and presses **Accept**.
3. **Assistants:** one `muse-spark-1.3` call per role; the browser starts them together. On the deployed link
   (set 15, one run) accepting the chart took 3.9 s and creating the Sales invite, which waits for every brief,
   0.6 s more; the 31.9 s setup figure was measured with the calls one after another. Skills must come from
   `data/skills.json`; anything else is removed and shown as removed. Handoffs may only point at roles that exist.
4. **Invite links:** one per person, tied to a role. A role with no free seat refuses. *Limit: the link is the
   only credential; there is no login.*
5. **Chat:** streamed from Spark; the browser keeps the history (IndexedDB) and sends it with each
   message. The server stores nothing. The assistant's prompt carries a hand-written playbook for
   the role (`data/playbooks.json`) and the company's real rules from `data/params.json` (margin
   floor, approval limit, rate card; cost only for roles that may see it): 9 of 10 rule-based questions
   answered correctly against 2 of 10 with the plain prompt (set 4). Before anything is sent the browser
   masks, with a preview: emails, phone numbers (US formats and numbers with a + country code), payment card
   numbers (checksum-verified), US Social Security numbers, IBANs, passwords, API keys, cloud keys, vendor tokens,
   private-key blocks, and the client names you list (`static/pii.js`, `tests/js/pii.test.mjs`).
   *Limit: masking is pattern-based. It does not find unlisted personal names, other national ID formats
   (passports, non-US ID numbers), phone numbers in a national format without a + country code (except US
   formats), or anything in photos. In the handoff form only the notes field is masked, so do not type personal
   names into other fields (also stated on `/trust`).* **Compare with generic AI** asks the same question of the
   role assistant and of a plain assistant, side by side.
6. **Team workflow (Sales, Operations, Finance):** each step lets the model choose a tool's arguments
   (`quote_price`, `make_calendar_event`, `check_margin`) by function calling; **code computes every number**
   (`tools.py`) as described above. A two-layer check follows: rules set a floor, then the model reads the
   package (customer notes are untrusted text inside a `<data>` block) and may only raise the status. A person
   presses Approve, the server issues the HMAC receipt and refuses step N+1 without a valid receipt for step N.
   The Finance step runs on Glimmer in Private mode: on a warm endpoint 10 of 10 function calls had the right
   arguments and 0 statuses fell below the rules floor (set 10).
   *Limit: Private mode runs on Glimmer 30B, not Muse Spark Open, which does not fit one GPU (its model card names it
   [816B with 42B active](https://huggingface.co/meta-models/Muse-Spark-Open-816B-A42B)). Glimmer's schema-forced JSON
   skips a visible reasoning phase, so it raises harmless points more often than Spark (3 of 10 clean packages vs 0
   of 10, set 10). The workflow, its three tools and the rate card are hand-written for the logistics form; other
   trades see the inbox and chat only.*
7. **Inbox and Today:** a person sends a quote package to another role along a declared handoff.
   Rules and Spark check it (the model can only raise the status). The receiving team sees it in a
   queue, one person takes it, then accepts or returns it with a reason; a blocked package cannot
   be accepted; a returned package goes back to the sender only, who edits it and sends it again,
   and the next reviewer sees why it came back and what changed; the sender can never decide on
   their own package. The queue is ordered by rules (waiting for me, overdue, worst status first); on a
   returned package **Suggest a fix** asks Spark for the smallest edit, the rules re-check it and the sender
   decides (median 3.2 s, 9 of 9 answered suggestions left no blocked package, set 3). Above USD 50,000 the
   top role must also approve after the receiver (a maker-checker step separate from the workflow's HMAC
   receipt). **Today** counts documents only. The owner can remove a person: their link answers 410 with
   `Clear-Site-Data`, their seat frees up, and work they held returns to the queue.
   *Limit: the model layer of the check was tested on author-written synthetic cases only (set 11, Spark: 10 of 10
   caught, 1 false alarm in 10; set 11p, Glimmer: 9 of 10 caught, 4 false alarms in 10).*
8. **Handoff form:** the document people pass between teams is data, not code. After the chart,
   the owner presses **Design the form for my company**; Spark is asked for 4 to 8 fields (the code accepts 3 to 10) and rules
   from a fixed vocabulary (not below, margin floor, approval limit, date not in the past),
   `rules.validate_handoff_schema` checks it (no field about people, known types, rules that point
   at real fields), and the owner edits the thresholds and accepts. Thresholds are the owner's or
   the company default, never the model's. If Spark fails, a labelled Template for the industry is
   shown. Every package keeps the form it was sent with. The model never writes interface code:
   the page draws inputs from the form definition and the CSP stays `script-src 'self'`.

### Extras (items 9-23)

The same rule (code decides, the model writes, a person approves) runs through a person's whole
time at the company:

9. **Paper to form:** a person photographs a paper job sheet and Spark vision fills the handoff
   form. Code checks the file (png, jpeg or webp by its first bytes, at most 4 MB), strips
   currency and separators from amounts, and the rules re-check every value before the person
   sends. The owner can also design the company's form from a photo of the paper form in use
   today. Photos are sent once and never stored. When the model cannot read a field it names it, and
   code empties that field and marks it "A person must check this" instead of keeping a guess.
   Measured: 60 of 60 fields on 10 rendered sheets (56 of 60 on the first run, before code stripped
   thousands separators from amounts, set 6); on 10 phone-degraded handwriting-style sheets
   53 of 56 legible fields, and 4 of 4 smudged fields left empty (set 9).
   *Limit: measured on rendered sheets only, not phone photos of real, creased or handwritten paper; expect
   misreads there. Photos are not masked for personal data (see item 20).*
10. **Morning brief:** the owner presses one button and sees the open documents in three short
   lists (needs the top role, stuck, moving today) with counts by role. Code puts each document
   in its list; Spark writes one line per document and never sees names or links; a line for an
   unknown document or naming a person is replaced by a line written by code. Read-only: approval
   still happens in the top role's inbox. Measured: 0 names or invented documents in 70 lines (set 7).
11. **First three days:** a new person opens their link and gets a three-day plan built from
   their role's assistant: what they send and to whom, which assistant skill helps. Only the
   kit's skills survive; a labelled template stands in without Muse. The plan and the ticks
   stay in that browser, so nobody, the owner included, sees how far they got.
   *Limit: run against the real model once ([docs/MEASURED.md](docs/MEASURED.md), "Day-One plan and handover draft").*
12. **Kind exit:** a person leaving drafts a handover from the documents they still hold or sent
   and their own notes. The draft is private until they send it; it goes to their own team, or
   to the top role when nobody shares the role, and they cannot accept it themselves. When the
   owner removes them, the handover stays with the team.
   *Limit: run against the real model once; the model words it from the person's own notes, which the person
   must read before sending.*
13. **The assistant reads your documents:** in chat, Spark can call three read-only tools (list
   my documents by group, read one document, count them). Code scopes every result to what that
   person sees in their inbox; no result names a person or carries a link; document text, notes
   included, goes back to the model as untrusted data. The assistant only reads: claiming,
   accepting, returning and sending stay with people. Measured: 11 of 11 questions on a seeded inbox,
   0 leaks, 0 followed injections; equal to pasting the inbox into the prompt on accuracy and slightly
   dearer at this size (set 8).
14. **My private rules:** on their own link a person sets a stricter margin floor or approval limit
   for their own assistant. The server refuses anything looser than the company's number and says
   which one; what is saved is readable only with that link, never by the owner or a unit.
15. **Plug into what you already run:** a handoff can be filled from a JSON or CSV file and the
   inbox exported as JSON or CSV. Import only fills the form (free-text notes are left out so they
   still pass the masking step), a person checks and sends it, and exported cells that start like
   a spreadsheet formula get a leading quote. **Export approved** holds only handoffs every approver
   accepted and that were not blocked, with the form's own columns, the approval chain and no free-text
   notes. No connector, key or outbound call is involved. An accepted, unblocked handoff also shows
   **Open email draft**: a `mailto:` draft with the form's fields and the approval chain (no notes, no
   model text); past about 1,800 characters there is no link, only **Copy the text** (`tests/js/exchange.test.mjs`).
16. **A second industry without training:** a clinic (an industry in the survey that says clinic, dental,
   medical or health; there is no demo button for it) gets its own chart template, a "Treatment plan quote"
   form (patient reference as a number, not a name; fee, cost, first visit) checked by the same code rules,
   and its own playbooks. Retail and services keep their forms; an industry with no form falls back to the
   services form and the chart says Template. Wonder on 5 synthetic clinics and 5 software companies passed
   the rules 10 of 10 (set 13, one run). *Limit: one referral path; transfers between clinics are not built,
   and the clinic form is not meant for real patient data.*
17. **A code helper for software companies:** a software studio ("Try the software studio demo", or any
   industry that says software, developer or devops) gets an Engineering Lead whose assistant holds the skill
   "Explain, review or draft code for a person to copy and run themselves". Code gives that skill to the
   engineering role only; a level can ban it like any other skill. The assistant has no tool that runs, deploys
   or pushes (a test lists every tool and fails on such a name), and its playbook says to label drafts
   "Untested draft". *Limit: not measured against the real model beyond one spot check.*
18. **What is stuck and where:** the sender's inbox lists what they sent that still waits for another
   team, with its age and whether someone took it (never who), and a reminder draft per row, built by
   code from the package's own fields and only copied; nothing is sent.
19. **Speak the job (experimental):** a push-to-talk button (up to 60 seconds) turns a spoken job note into
   text with Muse Voice Transcribe. The browser converts the recording to 16 kHz mono WAV, the server checks it
   by code (format, length) and sends it once; only the text comes back, into the customer-message box (item
   21), so the same masking, model reading and person checks apply. The recording is never stored.
   *Limit: **not measured.** Tested with fake audio and a stubbed model; the transcription endpoint has not been
   run against real audio, so no accuracy, word-error rate, example result or cost is claimed.*
20. **Cover before reading:** on a photo, the person names what to hide (for example `signature`),
   SAM 3.1 outlines it, and the browser paints those boxes black on its own copy before Spark reads the
   photo. Only boxes come back (code parses and clips them), the request sets `store: false`, and the
   screen says SAM can miss things: the person looks at the preview before sending.
   *Limit: **not measured.** Tested with stubbed replies and one hand check in a hidden browser against the real
   endpoint on a synthetic page (a red rectangle became black); SAM's accuracy on real documents has no number.*
21. **Customer message to form:** paste a customer's message and Spark fills the company's form.
   It is masked in the browser first (item 5), the message is treated as data, a field the model could
   not read is emptied by code, the rules check the result, and the person checks and sends. Nothing is stored.
22. **Start from a past quote:** a new draft from one of the sender's own handoffs. Dates are
   cleared, rate-card figures are recomputed by code, and every change is listed.
23. **Layered rules (Group and Subsidiary):** a company can split into units. A unit may only tighten its
   parent's margin floor and approval limit and must keep every skill its parent bans; the server refuses
   anything looser, naming the rule and the parent's value (`rules.py` `validate_child_rules`,
   `tests/test_levels.py`). A one-level company sees no difference. *Limit: only these two levels;
   departments, teams and individual levels are not built.*

## What each role stops doing by hand

This is the design intent, not a measured saving (no by-hand time has been recorded).

- **Sales** no longer retypes a quote: the form is filled from the order, and code computes the price and margin.
- **Operations** no longer copies an approved package into a sheet: the approved export and the calendar file are built by code from the steps covered by HMAC receipts.
- **Finance** no longer re-checks the margin with a calculator: code computes it, and the model only writes the note.

**Timed runs.** The landing page shows a "Timed runs" tile read from `data/timed_runs.json`: the same job timed by hand and in the app, who held the stopwatch, and the saving computed by code (`timed.py`, tested). A row is added only with `python scripts/timed_run.py`, never by a model. Today it holds one app-side time (setup, 31.9 s) and no by-hand time, and the tile says so.

## Built today, and not built

**The core, built for every company:** the org chart checked by code rules; a role assistant and a handoff
form per role, drafted by the model; code checks every draft; a person approves every step; the server issues an
HMAC-protected receipt for each approved step; Private mode on Glimmer, which never falls back silently.

**Built, hand-written:** the clinic and software-studio templates (chart, form and playbooks) and the logistics
workflow (Sales -> Operations -> Finance) with its three tools in `workflow.py`. A person wrote each of them; no
model assembled them.

**Experimental, not measured:** Voice input (item 19) and covering parts of a photo with SAM (item 20).

**Not built (the direction; none of it is claimed as working):**

- AI routing of the workflow itself: a model proposing which role does which step, from a fixed vocabulary of roles,
  tools and skills, checked by code (no loops, no orphan steps, no banned skill) before a person approves each step.
- Industry modules that plug into the core (no medical module is planned in this submission), and multilingual support.
- Divisions, departments, teams and individual levels (today: Group and Subsidiary).
- Admin-set spending caps (today: a per-sandbox call limit and a daily spend ceiling for the demo).
- Native desktop and phone apps; connectors to SAP, OCR, AWS, Google Cloud, Azure, HR and ERP systems.
- Free-text personal working styles (today a private rule is a number).
- Shadow/Assist/Primary modes, handoffs to a named person, manager assignment, parallel approval, org advisor.
- Web search: the `web_search` tool type is rejected (HTTP 400) in the form tried.

## Claim and proof

| Claim | Proof in the repository |
|---|---|
| Numbers come from code: from the signed order and quote; model-returned arguments that differ are recomputed and flagged `needs_human_check` | `test_bad_tool_arguments_are_retried_once_then_taken_from_the_package` and the Finance note filter in `workflow.py` |
| After a person presses Approve the server issues an HMAC-protected receipt; a forged step is refused | `test_a_receipt_for_another_result_or_another_run_is_refused` |
| An invite approves only its own role's step | `409 wrong_role` in `app.py`, `tests/test_workflow.py` |
| Names you list are masked in the browser; pattern masking alone does not find names | `tests/js/client_names.test.mjs`; [docs/MEASURED.md](docs/MEASURED.md), set 2 and "PII masking scope US and international" |
| The calendar file is built by code and refused without a date | `test_a_calendar_file_is_built_by_code_and_refused_without_a_date` |
| Every browser module parses before it reaches a browser | `test_every_browser_module_parses` |

## Meta models used

| Model | Used for | Measured |
|---|---|---|
| `muse-wonder-1.0` | Org chart under a strict JSON schema | 10 of 10 charts passed the rules first try; median 5.9 s; USD 0.0134 per chart (10-chart batch average, set 1; one UI run cost USD 0.038) |
| `muse-spark-1.3` | Role briefs (structured output), chat (streaming), tool calls (function calling), handoff checks (structured output), photo reading (vision), morning brief, first-days plan, handover draft | Brief about USD 0.005; chat answer USD 0.0015; fix suggestion median 3.2 s; photo reading 60 of 60 fields, median 3.3 s, USD 0.002 per sheet; contradictions 10 of 10, 1 false alarm in 10 (set 11) |
| Muse Glimmer 30B, id `meta-models/Muse-Glimmer-30B` (open weights, Private mode, served by the author on Modal with vLLM, `scripts/private_modal.py`; Baseten was used only for one comparison load test) | Finance-step tool call and check, through a configurable provider (`PRIVATE_PROVIDER`, `PRIVATE_BASE_URL`, `PRIVATE_MODEL`, `PRIVATE_API_KEY_FILE`; `/trust` shows the model in use) | 10 of 10 function calls with the right arguments; 12 of 12 seeded errors flagged by the final gate (a rules result, not the model's); 0 statuses below the rules floor; 3 of 10 clean packages raised needlessly (set 10, warm endpoint). Cold start: 166 s once before the GPU snapshot, 23 to 31 s in four runs after it (set 10) |
| `muse-voice-transcribe-1.0` | Speech to text for a spoken job note (item 19) | **Not measured**: not run against the real endpoint; USD 0.18 per audio hour is an assumed rate used only for the cost ceiling (`muse.py`), no cost is claimed |
| `sam-3.1` | Find what a short phrase names in a photo so it can be covered before reading (item 20); `sam.py` parses the returned boxes | **Not measured**: stubbed replies and one hand check on a synthetic page; price not published, so no cost is claimed |
| `muse-image-1.0` | Build time only: the illustration shown while Wonder designs the chart (`static/img/chart-wait.webp`), captioned as not the company's chart; the app never calls it | Not measured: one build-time generation, not reproducible from this repo (this repo records `muse-image-1.0` only for a different image, `flow_base.png`, in [scripts/demo_assets/README.md](scripts/demo_assets/README.md)); the file is 216,048 bytes; no cost is claimed |

Details and caveats: [docs/MEASURED.md](docs/MEASURED.md). Chat, charts and checks use the OpenAI SDK pointed at `https://api.meta.ai/v1`; Voice and SAM use plain HTTP calls to the same base URL. The `-contributor` refusal covers `complete()` and streaming; the Voice and SAM calls do not run it (experimental, not measured).

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
| LLM01 Prompt injection | Customer notes sit inside a `<data>` block marked untrusted; the model can only raise a status; measured on 8 injection cases (sets 2 and 10) |
| LLM02 Sensitive information disclosure | No message table, no message logging, Referrer-Policy `no-referrer`; invite tokens in the Authorization header and the URL fragment, never in a query string |
| LLM05 Improper output handling | Strict JSON schemas, rules validate every output, `textContent` only in the UI, CSP `script-src 'self'` |
| LLM06 Excessive agency | Models only choose arguments of three deterministic tools; every handoff needs a person; server-issued HMAC receipts after Approve |
| LLM10 Unbounded consumption | 80 model calls per sandbox, a daily cost ceiling, 24-hour sandboxes |

## Impact

The figures below are external, linked, not measured by us, and quoted as published. The right-hand column is a design response: what the product does about each finding, not a measured reduction in worry, leaks or time.

| Finding (external, linked, not measured by us) | Source | Design response (not measured impact) |
|---|---|---|
| 52% of US workers feel worried about future AI use in the workplace, 36% hopeful (n = 5,273 employed adults, published 25 Feb 2025) | [Pew Research Center](https://www.pewresearch.org/social-trends/2025/02/25/u-s-workers-are-more-worried-than-hopeful-about-future-ai-use-in-the-workplace) | Assistants help with documents; four skills that evaluate, rank, monitor or decide about people are never available (tested) |
| 81% of US adults say AI used to evaluate workers would make workers feel inappropriately watched (fielded 12-18 Dec 2022, n = 11,004 adults) | [Pew Research Center](https://www.pewresearch.org/internet/2023/04/20/ai-in-hiring-and-evaluating-workers-what-americans-think) | No performance or habit metrics exist in the data model; approvals keep a hash of the invite name only, to stop one person approving twice |
| 48% of respondents entered non-public company information and 45% entered employee information into GenAI tools (Cisco 2024 Data Privacy Benchmark, n = 2,600 privacy and security professionals) | [Cisco](https://newsroom.cisco.com/c/r/newsroom/en/us/a/y2024/m01/organizations-ban-use-of-generative-ai-over-data-privacy-security-cisco-study.html) | Chat is never stored on the server; Standard mode only; a Private mode path for open weights |
| 45% of US employees used AI at work at least a few times a year in Q3 2025, 10% daily (fielded 5-19 Aug 2025) | [Gallup](https://www.gallup.com/workplace/699689/ai-use-at-work-rises.aspx) | Role jobs make AI useful for the daily job without writing prompts (a design choice; no test enforces it) |
| 22.4% of owner time goes to administrative tasks plus legal and compliance (UENI's own survey, n = 837 US businesses with five or fewer employees, May 2024) | [UENI](https://ueni.com/en-us/small-business-research/how-microbusiness-owners-spend-their-time) | The morning brief lists open documents by role so the owner sees what waits on whom; the model writes words, code picks the documents |
| 11 hours a week on administrative or finance tasks (American Express SME Barometer, a company-run survey, n = 1,000 UK owners, July 2026) | [Retail Times](https://retailtimes.co.uk/amex-sme-barometer-small-business-owners-spend-nearly-twice-the-time-on-admin-than-growing-their-business/) | Handoffs carry a checked form instead of a chat thread. We measured accuracy, not hours saved |
| 66% of US adults agree AI-based worker evaluation would lead to the collected information being misused (Pew, 20 Apr 2023) | [Pew Research Center](https://www.pewresearch.org/internet/2023/04/20/americans-views-on-use-of-ai-to-monitor-and-evaluate-workers/) | Nothing is kept about how a person works, and the onboarding plan shows nobody, including the owner, how far a new hire got |
| 4.8 months average onboarding time for a new technical hire (Linux Foundation, 2024 State of Tech Talent, 418 records; tech roles, not small firms) | [Linux Foundation](https://www.linuxfoundation.org/blog/the-2024-state-of-tech-talent-report) | Day-One gives a new hire a first-three-days plan from their role's kit, and Kind exit lets a leaver hand over to their own team |
| 44% of informal microbusinesses keep systematic records, about three-quarters of those in notebooks (ILO survey, n = 1,400 firms in Guatemala, Honduras and El Salvador, working paper Oct 2025) | [Wharton School](https://accounting.wharton.upenn.edu/wp-content/uploads/2025/10/AguilarLindRamesh.pdf) | Paper to form turns a photo of the paper into a form a person checks. Measured on synthetic sheets only |

Some rows came from a research run (Claude Haiku, Sonnet and Opus helped as development tools; the
product itself runs on Muse only); the rest are cited from the linked page. Each figure was opened again at its source by a second pass. Two rows are a
company's own survey and say so. The method and what the figures do not show are in [docs/research](docs/research/README.md).

**Independent review.** On 2026-10-31 SOLIFAN (Japan) reviewed this repository once and reproduced abnormal cases locally. It found three high, one medium and one low issue; each is fixed, and the four code findings have regression tests. The Japanese original, an English translation and the finding-to-fix table are in [docs/evidence/solifan](docs/evidence/solifan/README.md). It is a limited technical review, not a quality certification, and it did not re-measure our figures.

## What it costs (measured per call; usage is an assumption)

The per-call prices are measured ([docs/MEASURED.md](docs/MEASURED.md)). The usage counts are
**assumptions** for a 10-person company with 5 roles and 22 working days a month, in three
scenarios anchored on published figures: an illustration of how the measured prices add up, not a claim about any
company's bill.

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

| | Light | Busy | All day |
|---|---|---|---|
| Setup, once (1 chart USD 0.038, one UI run; the 10-chart batch averaged USD 0.0134 (set 1); + 5 briefs USD 0.0047 each) | USD 0.06 | USD 0.06 | USD 0.06 |
| Chat answers, USD 0.0015 each | USD 1.32 | USD 7.92 | USD 26.40 |
| Workflow steps, 3 per order, under USD 0.01 each (upper bound used) | up to USD 3.30 | up to USD 13.20 | up to USD 33.00 |

Private mode (Glimmer on Modal) is billed per warm GPU hour, not per call, and is not in this table; its GPU cost is **not measured**. Photos (about
USD 0.002 per sheet, set 6) and morning briefs are left out; the cost of a fix suggestion is **not measured**. The
80-call cap and the daily cost ceiling protect the public demo; they are not a company's bill.

## Reasoning effort per call

Each call sets `reasoning_effort` itself; reasoning tokens are billed as output.

| Effort | Calls | Why |
|---|---|---|
| `minimal` | chat answers, workflow tool calls and the model check, fix suggestions, reading a paper document, the morning brief, reading the person's own documents | Short answers and checks; set 12 measures the model check only: there `high` was 3.6 times slower, 4.9 times dearer and flagged no more contradictions |
| `low` | the org chart (Wonder), role briefs, handoff forms, handover draft, first-days plan | `low` chosen for schema-bound output; **not measured** (set 12 tested `minimal` and `high` only) |

## Building period (built during the hackathon)

- The idea and planning notes (planning, API study, feature research, design reviews) were written on 26 Oct 2026, before the building period. They are
  **not** part of this repository.
- Every line of code, every test, the UI and the demo were built from **27 Oct 2026 00:09 ET**
  (first commit `04ef41b`, recorded as `2026-10-27T11:09:09+07:00`) to the submission on 4 Nov 2026. All times here are US Eastern (ET).
- `git log --reverse --format='%h %aI %s'` shows each commit's time; `git rev-list --count HEAD` gives the count.
- AI-assisted development: the code was written with Claude Code; the product itself runs on Meta Muse models.

## Run it

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
$env:META_API_KEY_FILE = "path\to\your\key.txt"
powershell -File scripts/run.ps1 -Real     # http://localhost:5000
powershell -File scripts/check.ps1         # tests, no model calls
python scripts/smoke.py                    # real API access check
python scripts/measure.py [set1 ... set13, set11p]  # the measured sets; set10 and set11p need Private mode; no argument skips set10 to set13 and set11p
python scripts/record_demo.py              # records the golden path as a captioned .webm
python scripts/warm_glimmer.py 45          # wakes the Private-mode endpoint, keeps it warm 45 minutes, prints the wake time
```

Today this is a demo only; real use means deploying it yourself. Deploy: `scripts/deploy.ps1 -Project <id>` (Cloud Run, one instance, secrets from Secret Manager). A push to `main` runs the same checks in GitHub Actions (`.github/workflows/deploy.yml`) and, when they pass and the `GCP_SA_KEY` secret is set, runs that script. The Private-mode endpoint scales to zero; the owner intends to run `GLIMMER_MIN_CONTAINERS=1 modal deploy scripts/private_modal.py` for the judging days only, which keeps one container awake (billed by the second), and a plain `modal deploy` turns it off. Opening the order form or starting a demo also wakes it (one request, no data, at most every two minutes): that shortens a cold start, it does not remove it.

## License

MIT, see [LICENSE](LICENSE).
