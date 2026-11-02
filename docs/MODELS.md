Moved from the README; the README has the short version.

# Role Assistant Foundry: models

## Meta models used

| Model | Used for | Measured |
|---|---|---|
| `muse-wonder-1.0` | Org chart under a strict JSON schema | 10 of 10 charts passed the rules first try; median 5.9 s; USD 0.0134 per chart (10-chart batch average, set 1; one UI run cost USD 0.038) |
| `muse-spark-1.3` | Role briefs (structured output), chat (streaming), tool calls (function calling), handoff checks (structured output), photo reading (vision), morning brief, first-days plan, handover draft | Brief about USD 0.005; chat answer USD 0.0015; fix suggestion median 3.2 s; photo reading 60 of 60 fields, median 3.3 s, USD 0.002 per sheet; contradictions 10 of 10, 1 false alarm in 10 (set 11) |
| Muse Glimmer 30B, id `meta-models/Muse-Glimmer-30B` (open weights, Private mode, served by the author on Modal with vLLM, `scripts/private_modal.py`; Baseten was used only for one comparison load test) | Finance-step tool call and check, through a configurable provider (`PRIVATE_PROVIDER`, `PRIVATE_BASE_URL`, `PRIVATE_MODEL`, `PRIVATE_API_KEY_FILE`; `/trust` shows the model in use) | 10 of 10 function calls with the right arguments; 12 of 12 seeded errors flagged by the final gate (a rules result, not the model's); 0 statuses below the rules floor; 3 of 10 clean packages raised needlessly (set 10, warm endpoint). Cold start: 166 s once before the GPU snapshot, 23 to 31 s in four runs after it (set 10) |
| `muse-voice-transcribe-1.0` | Speech to text for a spoken job note (item 19) | Experimental, unmeasured: not run against the real endpoint; USD 0.18 per audio hour is an assumed rate used only for the cost ceiling (`muse.py`), no cost is claimed |
| `sam-3.1` | Find what a short phrase names in a photo so it can be covered before reading (item 20); `sam.py` parses the returned boxes | Experimental, unmeasured: stubbed replies and one hand check on a synthetic page; price not published, so no cost is claimed |
| `muse-image-1.0` | Build time only: the illustration shown while Wonder designs the chart (`static/img/chart-wait.webp`), captioned as not the company's chart; the app never calls it | Not measured: one build-time generation, not reproducible from this repo (this repo records `muse-image-1.0` only for a different image, `flow_base.png`, in [scripts/demo_assets/README.md](../scripts/demo_assets/README.md)); the file is 216,048 bytes; no cost is claimed |

Details and caveats: [docs/MEASURED.md](MEASURED.md). Chat, charts and checks use the OpenAI SDK pointed at `https://api.meta.ai/v1`; Voice and SAM use plain HTTP calls to the same base URL. The `-contributor` refusal covers `complete()` and streaming; the Voice and SAM calls do not run it (experimental, not measured).

## Reasoning effort per call

Each call sets `reasoning_effort` itself; reasoning tokens are billed as output.

| Effort | Calls | Why |
|---|---|---|
| `minimal` | chat answers, workflow tool calls and the model check, fix suggestions, reading a paper document, the morning brief, reading the person's own documents | Short answers and checks; set 12 measures the model check only: there `high` was 3.6 times slower, 4.9 times dearer and flagged no more contradictions |
| `low` | the org chart (Wonder), role briefs, handoff forms, handover draft, first-days plan | `low` chosen for schema-bound output; **not measured** (set 12 tested `minimal` and `high` only) |
