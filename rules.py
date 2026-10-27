"""Rules decide structure; the model only writes words (principle 1). Pure functions, no I/O."""
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
