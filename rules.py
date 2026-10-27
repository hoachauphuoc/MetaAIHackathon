"""Rules decide structure; the model only writes words (principle 1). Pure functions, no I/O."""
import datetime
import json
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


def check_package(values, params, today):
    """Hard checks on a quote package. Returns (status, findings); findings carry source=rules."""
    findings = []

    def add(status, message):
        findings.append({"status": status, "message": message, "source": "rules"})

    for field in ("customer", "route", "pallets", "price", "cost", "delivery_date"):
        if values.get(field) in (None, ""):
            add("blocked", f"Missing: {field}.")
    price, cost = values.get("price"), values.get("cost")
    if isinstance(price, (int, float)) and isinstance(cost, (int, float)) and price > 0:
        if price < cost:
            add("blocked", "The price is below the cost.")
        elif (price - cost) / price * 100 < params["margin_floor_pct"]:
            add("needs_attention", f"The margin is under the {params['margin_floor_pct']}% floor.")
        if price > params["escalation_usd"]:
            add("needs_attention", f"The price is above USD {params['escalation_usd']:,}: the "
                                   "Managing Director must approve.")
    date = values.get("delivery_date")
    if date:
        try:
            if datetime.date.fromisoformat(date) < today:
                add("needs_attention", "The delivery date is in the past.")
        except (TypeError, ValueError):
            add("blocked", "The delivery date is not a valid date.")
    status = max((f["status"] for f in findings), key=RANK.__getitem__, default="clear")
    return status, findings
