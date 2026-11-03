Moved from the README; the README has the short version.

# Role Assistant Foundry: how it works

## Try it

- **Open** https://role-assistants-662084666675.us-central1.run.app, press **Try the demo company**, then
  **Design my org chart**. Nothing to sign up for.
  *Limit: there is no login. An invite link is the whole credential (no passwords): anyone holding the link acts as that
  person, and the owner removes the person under People to revoke it. Sandboxes live in an
  in-memory SQLite database on the one Cloud Run instance, are removed after 24 hours and are lost on a restart;
  a request for an unknown sandbox gets `410 sandbox_expired` ("This sandbox has ended. Start again."; `tests/test_app.py`).
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
    ([docs/MEASURED.md](MEASURED.md), set 10; not confirmed that the endpoint was asleep each of the four times).
  - The app waits 35 s a try, so a cold step shows `Private mode starting` and `A person must check this`, then retries
    on its own with a countdown (or press **Run this step again**); it never switches to another model.
    In the one end-to-end walk on a probably cold endpoint (set 17), the Finance step had not finished after 240 s
    and the order did not complete; the cause was not diagnosed. The owner intends to keep Glimmer awake during the
    judging days; that is an intention, not a guarantee.
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
   *Limit: run against the real model once ([docs/MEASURED.md](MEASURED.md), "Day-One plan and handover draft").*
12. **Kind exit:** a person leaving drafts a handover from the documents they still hold or sent
   and their own notes. The draft is private until they send it; it goes to their own team, or
   to the top role when nobody shares the role, and they cannot accept it themselves. When the
   owner removes them, the handover stays with the team.
   *Limit: run against the real model once; the model words it from the person's own notes, which the person
   must read before sending.*
13. **The assistant reads your documents:** in chat, Spark can call three read-only tools (list
   my documents by group, read one document, count them). Code scopes every result to what that
   person sees in their inbox; no result field names a person or carries a link (free-text notes come back as sent, pattern-masked, and may still hold a name someone typed); document text, notes
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

Three layers. Each item is labelled BUILT, NEXT or VISION. None of the NEXT or VISION items is claimed as working.

### Layer 1: BUILT and tested

- **BUILT** per-role approval: each invite approves only its own step, otherwise 409 `wrong_role` (`app.py`, `workflow.py`).
- **BUILT** code-checked org chart: cycles, orphans and excess headcount are rejected (`rules.py`).
- **BUILT** a role assistant and a handoff form per role, drafted by the model and checked by code (`assistants.py`, `handoffs.py`).
- **BUILT** Group and Subsidiary levels; a child can only tighten the parent's rules (`rules.py`).
- **BUILT** a server-issued HMAC receipt for each approved step (`workflow.py`, `app.py`).
- **BUILT** Private mode on an open-weights endpoint; it never falls back silently (`muse.py`).
- **BUILT** invite tokens kept out of server-visible URLs: Authorization header for API calls, the URL fragment (`/join#token`, never sent to the server) for the link (`app.py`).
- **BUILT, hand-written:** the clinic and software-studio templates and the logistics workflow (Sales -> Operations -> Finance), written by a person.
- **Experimental, not measured:** Voice input (item 19) and covering parts of a photo with SAM (item 20).

### Layer 2: NEXT STEP, planned, not built

- **NEXT** a library of role and skill templates per industry, prepared by hand and tested per industry; a company picks the roles it needs.
- **NEXT** a durable database in place of the in-memory store, so the 24-hour data limit goes away.
- **NEXT** accounts and login for employees (today only invite links).
- **NEXT** departments and teams under a subsidiary.

### Layer 3: VISION, not built and not scheduled

- **VISION** many companies on one platform.
- **VISION** many industries beyond the templates.
- **VISION** multiple languages (the product is English only today; masking and prompts are English).
- **VISION** connections between assistant folders across group, subsidiary, department and team levels, with the same rules flowing down.
- **VISION** other ideas, none built: AI routing of the workflow itself (checked by code before a person approves); admin-set spending caps; native desktop and phone apps; connectors to SAP, OCR, AWS, Google Cloud, Azure, HR and ERP systems; free-text personal working styles; Shadow/Assist/Primary modes and manager assignment; web search (the `web_search` tool type is rejected, HTTP 400, in the form tried).

Architecture: [docs/architecture.html](architecture.html).
