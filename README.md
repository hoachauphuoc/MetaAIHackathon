# Role Assistant Foundry

Small companies want an AI assistant for each role, but nobody wants AI deciding money or approvals alone. Role Assistant Foundry gives each role in a ten-person company an assistant that works under the company's own rules, for owners and their staff.

- **The model drafts** the org chart, each role's assistant and its handoff form (Meta Muse).
- **Code checks** every draft against the company's rules; groups can only tighten them.
- **A person approves** each step, and the server issues an HMAC receipt per approval; each invite link approves one role only.
- **Private mode** never switches to another model silently.

**Live now:** each demo sandbox is deleted after 24 hours; sample data only, no real users yet. Link: https://role-assistants-662084666675.us-central1.run.app

[Try it](https://role-assistants-662084666675.us-central1.run.app) · [Demo video, 178 s](https://youtu.be/n30I40GJSMQ) · [127 s home-page cut in this repository](static/video/welcome.mp4) · [Evidence and full examples](docs/PROJECT_DETAILS.md)

Contents: [Stage One checklist](#stage-one-checklist) · [What is measured](#what-is-measured) · [Try it](#try-it) · [How it works](#how-it-works) · [Built today](#built-today-and-not-built) · [Models](#meta-models-used) · [Privacy](#privacy-and-safety-design-each-line-has-a-test) · [Run it](#run-it) · Docs: [How it works](docs/HOW_IT_WORKS.md) · [Models](docs/MODELS.md) · [Privacy](docs/PRIVACY_AND_SAFETY.md) · [Impact and costs](docs/IMPACT_AND_COSTS.md) · [Details](docs/PROJECT_DETAILS.md)

## Stage One checklist

Legend: **Answer** is the claim, **Proof** is where to check it. What is built and what is not: [Built today, and not built](#built-today-and-not-built).

| Item | Answer | Proof |
|---|---|---|
| Track | **Indie developer**, built solo by PhuocHoa | This README, [LICENSE](LICENSE), `git log` |
| Problem statement | **Build for Your World.** Owners of small companies (around ten people) want AI but fear leaked client data, and employees fear AI the company can watch; this gives each role an assistant under the company's own rules. | [The problem](docs/PROJECT_DETAILS.md#the-problem-and-what-this-makes-possible), [Founder's story](#founders-story-why-role-assistant-foundry) |
| Meta models used | Muse Wonder (`muse-wonder-1.0`), Muse Spark (`muse-spark-1.3`), Muse Glimmer 30B on Modal (Private mode); Muse Voice Transcribe and SAM 3.1 are experimental, unmeasured | [Meta models used](#meta-models-used), `muse.py` |
| Live link | https://role-assistants-662084666675.us-central1.run.app | [docs/MEASURED.md](docs/MEASURED.md), set 16: one run on the deployed revision `role-assistants-00034-9z8`, 17 of 17 steps ok at desktop and 375 px width |
| Demo video | Submitted video: https://youtu.be/n30I40GJSMQ (178 s). The home page plays a 127 s cut of the same recording, in this repository as `static/video/welcome.mp4`. | [YouTube](https://youtu.be/n30I40GJSMQ), [static/video/welcome.mp4](static/video/welcome.mp4) |
| Public repository | https://github.com/hoachauphuoc/MetaAIHackathon, MIT | [LICENSE](LICENSE) |
| Built during the building period | First commit `04ef41b`, 27 Oct 2026 00:09 ET; every commit in this repository is from the building period | [Building period](#building-period-built-during-the-hackathon), `git log --reverse --format='%h %aI %s'` |
| Written before the building period | The idea and planning notes written on 26 Oct 2026 (planning, API study, feature research, design reviews) are **not** in this repository | [Building period](#building-period-built-during-the-hackathon) |

## What is measured

Every figure below has a set number in [docs/MEASURED.md](docs/MEASURED.md); all sets are small, synthetic and run by the author.

- **Strongest proof:** contradictions the rules cannot see, 10 of 10 flagged by Spark with 1 false alarm in 10 (set 11); 31 of 31 end-to-end checks on real models (set 14).

| Figure | What it is |
|---|---|
| 31 of 31 | End-to-end checks on real models in a hidden browser, desktop and 375 px phone (set 14, one run, local build, not the deployed link, no Private mode) |
| 9 of 10 vs 2 of 10 | Rule questions answered with the role playbook and company rules in the prompt vs a plain role prompt (set 4, author-written questions, string-match checks) |
| 10 of 10, 1 false alarm in 10 | Contradictions the rules cannot see (0 of 10) flagged by the Spark check, with 1 false alarm on 10 clean packages (set 11, author-written cases) |
| 39.5 s | The deployed link walked end to end on desktop, Finance answered by Muse-Glimmer-30B, Glimmer already awake (set 15, 2026-11-01, one run; the revision was not recorded) |
| 60.7 s | The deployed revision `role-assistants-00034-9z8` walked at desktop and 375 px width, 17 of 17 steps ok, Glimmer already awake (set 16, 2026-11-01, one run) |
| Failed, 240 s | The deployed link walked after about 12.5 minutes idle (Glimmer probably asleep): the Finance step timed out at 240 s and the order did not complete; cause not diagnosed (set 17, 2026-11-02, one run) |

Not measured: time and mental space freed. No hours saved are claimed; the hand-timed run is `scripts/timed_run.py` and has no by-hand time yet.

**Tests:** 327 Python test functions (790 cases with parametrization) and 39 JS tests, all passing, from `powershell -File scripts/check.ps1` (run 2026-11-02; it prints all three counts). The independent review's findings and their fixes are in [docs/evidence/solifan](docs/evidence/solifan/README.md).

## Try it

- **Open** https://role-assistants-662084666675.us-central1.run.app, press **Try the demo company**, then **Design my org chart**. Nothing to sign up for.
- **Fast path:** accept the chart and wait for the assistants; press **Create invite link** on Sales, Operations and Finance; open Sales, press **Plan this order** and approve; paste the order code under **Continue an order** on the Operations link, then the Finance link, and approve each step.
- *Limit: there is no login and an invite link is the whole credential. Sandboxes live in memory, are removed after 24 hours, and an unknown sandbox gets `410 sandbox_expired`. If the Finance step shows `Private mode starting`, the open-weights endpoint is waking: wait for the countdown or press **Run this step again**; it never switches model on its own (one cold walk did not finish within 240 s, set 17).*
- Full walkthrough, Private mode timing and demo mode: [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md#try-it)

## How it works

A survey of 10 questions goes to Muse Wonder, which draws the org chart as JSON; rules validate it (no cycle, no orphan, no more people than the company has). Muse Spark then writes one brief per role, and the assistants hand work to each other along the chart. Code computes every number; a person approves each step and the server issues an HMAC receipt. All 23 items are in [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md); the design is in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/architecture.html](docs/architecture.html).

## Built today, and not built

| Layer | Items |
|---|---|
| BUILT and tested | Per-role approval, code-checked org chart, role assistants and handoff forms, Group and Subsidiary levels, HMAC receipts, Private mode without silent fallback, invite tokens out of server-visible URLs; hand-written clinic and software-studio templates and the logistics workflow |
| NEXT, planned, not built | Role and skill template library per industry, a durable database, accounts and login, departments and teams |
| VISION, not built, not scheduled | Many companies and industries on one platform, multiple languages, connections between folders across levels, connectors, native apps, other ideas |

Experimental, not measured: Voice input and SAM photo covering. None of the NEXT or VISION items is claimed as working. Full lists: [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md#built-today-and-not-built).

## Meta models used

- `muse-wonder-1.0`: org chart under a strict JSON schema; 10 of 10 charts passed the rules first try (set 1).
- `muse-spark-1.3`: role briefs, chat, tool calls, handoff checks, photo reading; contradictions 10 of 10, 1 false alarm in 10 (set 11).
- `meta-models/Muse-Glimmer-30B`: Private mode, Finance step; 10 of 10 function calls with the right arguments (set 10, warm endpoint).
- `muse-voice-transcribe-1.0`: speech to text; experimental, unmeasured.
- `sam-3.1`: cover part of a photo before reading; experimental, unmeasured.
- `muse-image-1.0`: build time only, one illustration; not measured.

Full table and caveats: [docs/MODELS.md](docs/MODELS.md) and [docs/MEASURED.md](docs/MEASURED.md).

## Privacy and safety design (each line has a test)

- **Chat history is kept in the employee's browser**; the server passes each message to the model and stores none; no per-person metrics are kept.
- **Masking first:** emails, phone numbers, card numbers, keys and listed client names are masked in the browser before a chat message, a handoff's notes, a handover or a pasted customer message reaches a model. Other form fields, unlisted personal names and photos are not masked (stated on `/trust`).
- **Standard mode only:** chat, chart and check calls refuse any `-contributor` model id; Voice and SAM use fixed Standard ids. The public demo runs on free hackathon credits that Meta may use for product improvement, so it is for sample data only.
- **Isolated sandboxes:** one sandbox cannot read another.
- **Blocked stays blocked:** a handoff priced below cost stays blocked even when its note says to mark it clear.
- **Model text never becomes HTML:** the UI uses `textContent` only and the check script fails on `innerHTML`.

`/trust` states what the app stores and which chart and chat models it uses, generated from the running configuration; Voice and SAM, both experimental, are listed in [docs/MODELS.md](docs/MODELS.md). The full table of tests, the OWASP mapping, and claim and proof are in [docs/PRIVACY_AND_SAFETY.md](docs/PRIVACY_AND_SAFETY.md).

## Founder's story: why Role Assistant Foundry

The deadlock: companies want AI but fear leaked client data, and employees fear AI the company can watch, so they paste work into outside chatbots. This build gives each role an assistant, keeps governance with the company and the chat with the employee. Full story: [docs/PROJECT_DETAILS.md](docs/PROJECT_DETAILS.md#founders-story-why-role-assistant-foundry).

## Impact and costs

External figures on worker worry and small-business admin time, the independent SOLIFAN review, and three cost scenarios built on measured per-call prices are in [docs/IMPACT_AND_COSTS.md](docs/IMPACT_AND_COSTS.md).
Nothing there is a measured saving.

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

Today this is a demo only; real use means deploying it yourself. Deploy: `scripts/deploy.ps1 -Project <id>` (Cloud Run, one instance, secrets from Secret Manager). A push to `main` runs the same checks in GitHub Actions (`.github/workflows/deploy.yml`) and, when they pass and the `GCP_SA_KEY` secret is set, runs that script. The Private-mode endpoint scales to zero; the owner intends to run `$env:GLIMMER_MIN_CONTAINERS = 1; modal deploy scripts/private_modal.py` for the judging days only, which keeps one container awake (billed by the second); `modal deploy scripts/private_modal.py` from a new shell (without the variable) turns it off. That is an intention, not a guarantee: a visitor may still meet a cold endpoint (set 17). Opening the order form or starting a demo also wakes it (one fixed one-word request, no order data, at most every two minutes): that shortens a cold start, it does not remove it.

## License

MIT, see [LICENSE](LICENSE).
