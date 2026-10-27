"""Rules decide structure; the model only writes words (principle 1). Pure functions, no I/O."""
import datetime
import json
import re
from pathlib import Path

DATA = Path(__file__).parent / "data"
SKILLS = json.loads((DATA / "skills.json").read_text(encoding="utf-8"))
ALLOWED_SKILLS = {s["id"] for s in SKILLS["allowed"]}
FORBIDDEN_SKILLS = set(SKILLS["forbidden"])


def validate_chart(roles, company_size, people_by_role=None):
    """Return [{role_id, field, message}]; role_id is None for chart-wide errors."""
    errors = []

    def err(role_id, field, message):
        errors.append({"role_id": role_id, "field": field, "message": message})

    ids = [r.get("id") for r in roles]
    known = set(ids)
    seen = set()
    for r in roles:
        rid = r.get("id")
        if not rid or rid in seen:
            err(rid, "id", "Every role needs a unique id.")
        seen.add(rid)
        if not str(r.get("title") or "").strip():
            err(rid, "title", "Give this role a title.")
        h = r.get("headcount")
        if isinstance(h, bool) or not isinstance(h, int) or h < 1:
            err(rid, "headcount", "Headcount must be a whole number, at least 1.")
        boss = r.get("reports_to")
        if boss is not None and boss not in known:
            err(rid, "reports_to", "This role reports to a role that does not exist.")
        elif boss == rid:
            err(rid, "reports_to", "A role cannot report to itself.")

    roots = [r for r in roles if r.get("reports_to") is None]
    if len(roots) != 1:
        err(None, "reports_to", f"The chart needs exactly one top role; it has {len(roots)}.")

    parent = {r.get("id"): r.get("reports_to") for r in roles}
    for rid in parent:
        node, steps = rid, 0
        while node is not None and node in parent and steps <= len(parent):
            node, steps = parent[node], steps + 1
        if steps > len(parent):
            err(rid, "reports_to", "Reporting lines go in a circle through this role.")

    total = sum(r["headcount"] for r in roles
                if isinstance(r.get("headcount"), int) and not isinstance(r["headcount"], bool))
    if total > company_size:
        err(None, "headcount", f"The chart needs {total} people but the company has {company_size}.")

    for rid, held in (people_by_role or {}).items():
        if held and rid not in known:
            err(rid, "id", f"Move or offboard {held} people first.")
    return errors


def filter_skills(requested):
    """Return (kept, removed). Unknown or forbidden ids never reach an assistant."""
    kept, removed = [], []
    for skill in requested:
        (kept if skill in ALLOWED_SKILLS and skill not in FORBIDDEN_SKILLS else removed).append(skill)
    return kept, removed


# --- Handoff checks ---------------------------------------------------------------------
# Status rank: clear < needs_attention < needs_human_check < blocked. The model may only raise.
RANK = {"clear": 0, "needs_attention": 1, "needs_human_check": 2, "blocked": 3}


def combine_status(rules_floor, model_status):
    """An unknown or missing model status fails closed to needs_human_check."""
    model = model_status if model_status in RANK else "needs_human_check"
    return max(rules_floor, model, key=RANK.__getitem__)


def validate_plan(plan, roles, edges):
    """A workflow may only move along handoffs the assistants declared. Returns [message]."""
    errors, steps = [], plan.get("steps", [])
    known = {r["id"] for r in roles}
    if not 1 <= len(steps) <= 6:
        errors.append("A workflow has between 1 and 6 steps.")
    if len({s["id"] for s in steps}) != len(steps):
        errors.append("Every step needs a unique id.")
    for step in steps:
        if step["role_id"] not in known:
            errors.append(f"Step {step['id']} is for a role that does not exist.")
    for before, after in zip(steps, steps[1:]):
        if before["role_id"] != after["role_id"] and (before["role_id"], after["role_id"]) not in edges:
            errors.append(f"There is no handoff from {before['role_id']} to {after['role_id']}.")
    return errors


# --- Handoff form schema ----------------------------------------------------------------
# The form is data: a model may propose one, but only this vocabulary exists and only code
# validates and applies it. Thresholds come from the owner or params, never from the model.
SCHEMAS = json.loads((DATA / "handoff_schemas.json").read_text(encoding="utf-8"))
DEFAULT_SCHEMA = SCHEMAS["logistics"]
# Sent by a person leaving a role to their own team; not a company form, so canonical() cannot claim it.
HANDOVER_SCHEMA = json.loads((DATA / "handover_form.json").read_text(encoding="utf-8"))
FIELD_TYPES = ("text", "longtext", "integer", "number", "money", "date", "choice")
RULE_KINDS = ("not_below", "min_margin", "escalate_over", "date_not_past")
NUMERIC = ("integer", "number", "money")
KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,24}$")
FORBIDDEN_FIELD_WORDS = ("employee", "staff", "worker", "performance", "rating", "score", "rank",
                         "productivity", "monitor", "evaluat", "appraisal", "attendance", "hr_")


def _short_text(value, limit):
    return (isinstance(value, str) and 0 < len(value.strip()) <= limit
            and all(c.isprintable() for c in value))


def validate_handoff_schema(schema):
    """Return [message]; empty means the form can be used."""
    errors = []
    if not isinstance(schema, dict):
        return ["The form must be an object."]
    fields = schema.get("fields")
    if not isinstance(fields, list) or not 3 <= len(fields) <= 10:
        return ["A handoff form has between 3 and 10 fields."]
    by_key = {}
    for f in fields:
        key = f.get("key") if isinstance(f, dict) else None
        if not isinstance(key, str) or not KEY_PATTERN.match(key) or key in ("notes", "id"):
            errors.append(f"Field key {key!r} is not allowed.")
            continue
        if key in by_key:
            errors.append(f"Field key {key} is used twice.")
        by_key[key] = f
        if f.get("type") not in FIELD_TYPES:
            errors.append(f"Field {key} has an unknown type.")
        if not _short_text(f.get("label"), 60) or not _short_text(f.get("noun"), 24):
            errors.append(f"Field {key} needs a short label and noun.")
        if not isinstance(f.get("required"), bool):
            errors.append(f"Field {key} must say whether it is required.")
        options = f.get("options") or []
        if f.get("type") == "choice":
            if not 2 <= len(options) <= 12 or not all(_short_text(o, 40) for o in options) \
                    or len(set(options)) != len(options):
                errors.append(f"Field {key} needs 2 to 12 different short options.")
        elif options:
            errors.append(f"Field {key} cannot have options.")
        text = f"{key} {f.get('label', '')} {f.get('noun', '')}".lower()
        if any(word in text for word in FORBIDDEN_FIELD_WORDS):
            errors.append(f"Field {key} is about people; forms describe documents only.")
    if by_key.get(schema.get("title_field"), {}).get("type") != "text":
        errors.append("The title field must be a text field of the form.")
    rules_ = schema.get("rules")
    if not isinstance(rules_, list) or len(rules_) > 8:
        return errors + ["A form has at most 8 rules."]
    for r in rules_:
        kind = r.get("kind") if isinstance(r, dict) else None
        if kind not in RULE_KINDS:
            errors.append(f"Rule {kind!r} does not exist.")
            continue
        names = [r.get("field")] + ([r.get("other")] if kind in ("not_below", "min_margin") else [])
        if any(n not in by_key for n in names):
            errors.append(f"Rule {kind} points at a field that does not exist.")
            continue
        wanted = "date" if kind == "date_not_past" else None
        for n in names:
            kind_ok = by_key[n]["type"] == wanted if wanted else by_key[n]["type"] in NUMERIC
            if not kind_ok:
                errors.append(f"Rule {kind} cannot use field {n}: wrong type.")
        pct, usd = r.get("percent"), r.get("usd")
        if kind == "min_margin" and pct is not None and not (
                isinstance(pct, (int, float)) and not isinstance(pct, bool) and 1 <= pct <= 50):
            errors.append("The margin floor must be between 1 and 50 percent.")
        if kind == "escalate_over" and usd is not None and not (
                isinstance(usd, (int, float)) and not isinstance(usd, bool) and 1 <= usd <= 10_000_000):
            errors.append("The approval limit must be between 1 and 10,000,000.")
    return errors


def rule_threshold(schema, kind, params):
    """The owner's number for a rule if set, else the company default from params."""
    rule = next((r for r in schema["rules"] if r["kind"] == kind), None)
    if rule is None:
        return None
    mine = rule.get("percent") if kind == "min_margin" else rule.get("usd")
    return mine if mine is not None else (
        params["margin_floor_pct"] if kind == "min_margin" else params["escalation_usd"])


def check_package(values, params, today, schema=None):
    """Hard checks on a handoff package. Returns (status, findings); findings carry source=rules."""
    schema = schema or DEFAULT_SCHEMA
    findings = []
    nouns = {f["key"]: f["noun"] for f in schema["fields"]}

    def add(status, message):
        findings.append({"status": status, "message": message, "source": "rules"})

    for f in schema["fields"]:
        value = values.get(f["key"])
        if f["required"] and value in (None, ""):
            add("blocked", f"Missing: {f['key']}.")
        elif f["type"] == "choice" and value not in (None, "") and value not in f["options"]:
            add("blocked", f"The {f['noun']} is not one of the choices.")
        elif f["type"] == "date" and value:
            try:
                datetime.date.fromisoformat(value)
            except (TypeError, ValueError):
                add("blocked", f"The {f['noun']} is not a valid date.")

    def number(key):
        v = values.get(key)
        return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None

    below = set()
    for r in schema["rules"]:
        kind, field, other = r["kind"], r["field"], r.get("other")
        a, b = number(field), number(other) if other else None
        if kind == "not_below" and a is not None and b is not None and a > 0 and a < b:
            below.add(field)
            add("blocked", f"The {nouns[field]} is below the {nouns[other]}.")
        elif kind == "min_margin" and a is not None and b is not None and a > 0 and field not in below:
            floor = rule_threshold(schema, kind, params)
            if (a - b) / a * 100 < floor:
                add("needs_attention", f"The margin is under the {floor:g}% floor.")
        elif kind == "escalate_over" and a is not None and a > 0:
            limit = rule_threshold(schema, kind, params)
            if a > limit:
                add("needs_attention", f"The {nouns[field]} is above USD {limit:,.0f}: the "
                                       "top role must approve.")
        elif kind == "date_not_past" and values.get(field):
            try:
                if datetime.date.fromisoformat(values[field]) < today:
                    add("needs_attention", f"The {nouns[field]} is in the past.")
            except (TypeError, ValueError):
                pass  # reported above as not a valid date
    status = max((f["status"] for f in findings), key=RANK.__getitem__, default="clear")
    return status, findings
