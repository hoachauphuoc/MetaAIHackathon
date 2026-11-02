# Role Assistant Foundry: architecture

Role Assistant Foundry builds role-based AI assistants for small companies on Meta Muse models. Rules decide structure (org chart validity, skill lists, approval limits); the model only writes words and picks tool arguments. A visual version of these four views is in `docs/architecture.html`.

## (a) Request path

```mermaid
flowchart LR
  B["Browser<br/>index.html, join.html, trust.html<br/>masks PII, keeps chat history"]
  F["Flask on Cloud Run<br/>gunicorn 1 worker, 8 threads"]
  S[("In-memory SQLite<br/>sandboxes purged after 24 h")]
  M["muse.py<br/>the only door to a model"]
  subgraph API["Meta API: api.meta.ai/v1"]
    W["Wonder muse-wonder-1.0<br/>org chart"]
    SP["Spark muse-spark-1.3<br/>briefs, chat, tools, image input"]
    V["Voice muse-voice-transcribe-1.0"]
    SAM["SAM 3.1 sam-3.1<br/>photo regions"]
  end
  G["Glimmer on Modal<br/>Muse-Glimmer-30B, vLLM"]
  B -->|"HTTPS, invite token in Authorization header"| F
  F --> S
  F --> M
  M --> W
  M --> SP
  M --> V
  M --> SAM
  M -.->|"only when PRIVATE_* set"| G
```

Any model failure returns `demo_mode: true` with a label; `FAKE_AI=1` forces demo mode. Model ids ending in `-contributor` are refused. Private mode never falls back to the Meta API.

Source: `static/*.html`, `static/app.js`, `static/join.js`, `app.py`, `store.py`, `muse.py`, `chart.py`, `vision.py`, `voice.py`, `sam.py`, `scripts/private_modal.py`, `scripts/deploy.ps1`, `Dockerfile`.

## (b) Order workflow

```mermaid
flowchart LR
  P["/api/workflow/plan<br/>plan signed with HMAC-SHA256"]
  Q["Step 1: quote<br/>role sales, quote_price<br/>Spark"]
  O["Step 2: schedule<br/>role ops, make_calendar_event<br/>Spark"]
  Fi["Step 3: margin<br/>role finance, check_margin<br/>Glimmer, Private by default when configured;<br/>the person can switch the step to Public"]
  A1["Approve: sales invite"]
  A2["Approve: ops invite"]
  A3["Approve: finance invite"]
  R["Rules floor: rules.check_package<br/>model check can only be stricter"]
  P --> Q
  Q --> A1
  A1 -->|"HMAC receipt + order code"| O
  O --> A2
  A2 -->|"HMAC receipt + order code"| Fi
  Fi --> A3
  R -.-> Q
  R -.-> O
  R -.-> Fi
```

The model picks tool arguments, code computes the numbers (`tools.py`). `/api/workflow/step` runs a step only if every earlier step has a valid receipt. An invite approves only its own role's step (409 `wrong_role`, reason `other_role`), and one named person cannot approve two steps of the same order (409 `wrong_role`, reason `same_person`). The order code (plan, signature, roles, receipts) is copied by the approver and pasted by the next role; pasting grants nothing the signatures do not. Orders and tool results stay in the browser.

Source: `workflow.py`, `app.py`, `rules.py`, `tools.py`, `store.py` (`record_approval`), `static/join.js`.

## (c) Hierarchy

```mermaid
flowchart TB
  G["Group<br/>margin floor, approval limit, banned skills"]
  SU["Subsidiary<br/>may only tighten"]
  C["Company rules<br/>validated against levels above"]
  D["Department<br/>not built"]
  T["Team<br/>not built"]
  G -->|"strictest value wins"| SU
  SU -->|"strictest value wins"| C
  C -.-> D
  D -.-> T
  classDef built stroke-width:2px;
  classDef notbuilt stroke-dasharray: 5 5,stroke-width:2px;
  class G,SU,C built;
  class D,T notbuilt;
```

A child may keep or raise `margin_floor_pct`, keep or lower `escalation_usd`, and must keep every parent ban in `banned_skills` (it may add more). `validate_child_rules` rejects a looser child; `bind_levels` applies the strictest value.

Source: `rules.py` (`LEVEL_IDS`, `validate_child_rules`, `bind_levels`), `app.py` (`/api/levels`, `/api/levels/enable`, `PUT /api/levels/<unit_id>`).

## (d) Data: stored vs never stored

```mermaid
flowchart LR
  subgraph ST["Stored (8 tables deleted with the sandbox after 24 h; daily_cost is kept)"]
    s1["sandboxes, companies, assistants"]
    s2["people: invite token, display name, role"]
    s3["personal_rules: readable only with that person's invite"]
    s4["packages: handed-off business documents"]
    s5["decisions: accept or return"]
    s6["approvals: hash of the invite name per step, only to stop one person approving twice; no performance or habit metrics"]
    s7["daily_cost: service-wide USD per day, no who or what; not deleted with a sandbox"]
  end
  subgraph NV["Never stored"]
    n1["chat messages and history"]
    n2["workflow orders and tool results"]
    n3["suggested fixes, morning brief, onboarding ticks, handover draft"]
    n4["photos, voice recordings, pasted customer messages"]
    n5["habits, speed, experience, per-person statistics"]
    n6["Training: paid Standard use is excluded and -contributor ids are refused; the free-credit demo may be used by Meta (Meta's billing page says content may be used for product improvement while free credits are in use)"]
  end
```

Source: `trust.py` (`STORED`, `NEVER_STORED`), `store.py` (tables).
