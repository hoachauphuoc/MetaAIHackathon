"""Handoff inbox: documents move between roles along declared edges, with a person deciding.

State belongs to the document, never to a person: there is no count, speed or history per
person. The sender and holder are stored only so the sender cannot approve their own package
(maker-checker) and so a held package is not claimed twice.
"""
import datetime
import secrets

import rules
import workflow

FIELDS = ("customer", "route", "pallets", "price", "cost", "delivery_date")


class Refused(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status, self.message = status, message


def clean_values(raw):
    def text(key, limit):
        value = str(raw.get(key) or "")[:limit]
        return "".join(c for c in value if c.isprintable() or c == "\n").strip()

    def number(key):
        try:
            return float(raw[key]) if raw.get(key) not in (None, "") else None
        except (TypeError, ValueError):
            return None

    pallets = number("pallets")
    return {"customer": text("customer", 120), "route": text("route", 60),
            "pallets": int(pallets) if pallets is not None else None, "price": number("price"),
            "cost": number("cost"), "delivery_date": text("delivery_date", 10),
            "notes": text("notes", 1000)}


def edges(kits):
    return {(role_id, h["to_role"]) for role_id, kit in kits.items() for h in kit["handoffs"]}


def top_role(roles):
    return next((r["id"] for r in roles if r["reports_to"] is None), None)


def approval_chain(to_role, values, params, roles):
    """The receiver first; above the company's limit the top role signs after them."""
    chain = [to_role]
    top = top_role(roles)
    price = values.get("price")
    if isinstance(price, (int, float)) and price > params["escalation_usd"] and top not in chain:
        chain.append(top)
    return chain


def run_check(values, params, today, ask, blocked):
    """Two layers: rules set the floor, the model may only raise it. Returns (status, findings)."""
    floor, findings = rules.check_package(values, params, today)
    trace = []
    verdict, why = workflow.soft_check({"id": "handoff", "title": "Handoff check"}, values, floor,
                                       ask, blocked, trace)
    if verdict is None:
        findings.append({"status": "needs_human_check", "source": "model", "message":
                         "The assistant's check did not finish. A person must check this package."})
        return rules.combine_status(floor, "needs_human_check"), findings
    findings += [{"status": verdict["status"], "source": "model", "message": m}
                 for m in verdict["findings"]]
    return rules.combine_status(floor, verdict["status"]), findings


def send(sandbox_id, sender, to_role, raw_values, due, db, kits, roles, params, today,
         ask, blocked):
    if (sender["role_id"], to_role) not in edges(kits):
        raise Refused(403, f"There is no handoff from {sender['role_id']} to {to_role}.")
    values = clean_values(raw_values)
    missing = [f for f in FIELDS if values.get(f) in (None, "")]
    if missing:
        raise Refused(400, "Missing: " + ", ".join(missing) + ".")
    if due:
        try:
            datetime.date.fromisoformat(due)
        except (TypeError, ValueError):
            raise Refused(400, "The due date is not a valid date.")
    status, findings = run_check(values, params, today, ask, blocked)
    package = {
        "id": secrets.token_urlsafe(8), "from_role": sender["role_id"], "from_person": sender["token"],
        "chain": approval_chain(to_role, values, params, roles), "stage": 0, "state": "sent",
        "claimed_by": None, "values": values, "check_status": status,
        "findings": findings, "due": due or None, "return_reason": None,
    }
    db.save_package(sandbox_id, package)
    return package


def current_role(package):
    return package["chain"][package["stage"]]


def holder(package):
    return package["claimed_by"]


def overdue(package, today):
    return bool(package["state"] == "sent" and package["due"]
                and datetime.date.fromisoformat(package["due"]) < today)


def view(package, me, today, roles_by_id):
    """What one viewer may see. Never includes anyone's token."""
    here = current_role(package)
    mine = holder(package) == me["token"]
    open_to_my_role = package["state"] == "sent" and here == me["role_id"]
    return {
        "id": package["id"], "from_role": package["from_role"],
        "from_title": roles_by_id.get(package["from_role"], package["from_role"]),
        "to_role": here, "to_title": roles_by_id.get(here, here), "chain": package["chain"],
        "stage": package["stage"], "state": package["state"], "values": package["values"],
        "check_status": package["check_status"], "findings": package["findings"],
        "due": package["due"], "overdue": overdue(package, today),
        "return_reason": package["return_reason"],
        "i_sent_it": package["from_person"] == me["token"], "i_hold_it": mine,
        "can_claim": open_to_my_role and holder(package) is None
                     and package["from_person"] != me["token"],
        "can_decide": open_to_my_role and mine and package["from_person"] != me["token"],
        "can_resend": package["state"] == "returned" and package["from_person"] == me["token"],
    }


def _require_open_for(package, me):
    if package["state"] != "sent":
        raise Refused(409, "This package is not waiting for a decision.")
    if current_role(package) != me["role_id"]:
        raise Refused(403, "This package is not waiting for your role.")


def claim(package, me):
    _require_open_for(package, me)
    if package["from_person"] == me["token"]:
        raise Refused(403, "You cannot take your own package.")
    if holder(package) is not None:
        raise Refused(409, "Someone already holds this package.")
    package["claimed_by"] = me["token"]


def unclaim(package, me):
    if package["claimed_by"] != me["token"]:
        raise Refused(409, "You do not hold this package.")
    package["claimed_by"] = None


def decide(package, me, decision, reason):
    _require_open_for(package, me)
    if package["from_person"] == me["token"]:
        raise Refused(403, "You cannot decide on your own package.")
    if holder(package) != me["token"]:
        raise Refused(409, "Take the package first.")
    if decision == "accept":
        if package["check_status"] == "blocked":
            raise Refused(409, "A blocked package cannot be accepted. Return it with a reason.")
        package["claimed_by"] = None
        if package["stage"] + 1 < len(package["chain"]):
            package["stage"] += 1
        else:
            package["state"] = "accepted"
    elif decision == "return":
        if not str(reason or "").strip():
            raise Refused(400, "Say why you are returning it.")
        package["state"] = "returned"
        package["return_reason"] = str(reason).strip()[:500]
        package["claimed_by"] = None
    else:
        raise Refused(400, "Decision must be accept or return.")


def resend(package, me, raw_values, params, today, ask, blocked, roles):
    if package["state"] != "returned" or package["from_person"] != me["token"]:
        raise Refused(409, "Only the sender can resend a returned package.")
    values = clean_values(raw_values)
    missing = [f for f in FIELDS if values.get(f) in (None, "")]
    if missing:
        raise Refused(400, "Missing: " + ", ".join(missing) + ".")
    status, findings = run_check(values, params, today, ask, blocked)
    package.update(values=values, check_status=status, findings=findings, state="sent",
                   stage=0, claimed_by=None, return_reason=None,
                   chain=approval_chain(package["chain"][0], values, params, roles))


def today_summary(packages, me, today):
    """The Today panel: counts of documents, computed from current state only."""
    waiting = [p for p in packages if p["state"] == "sent" and holder(p) == me["token"]
               and current_role(p) == me["role_id"]]
    returned = [p for p in packages if p["state"] == "returned" and p["from_person"] == me["token"]]
    queue = [p for p in packages if p["state"] == "sent" and current_role(p) == me["role_id"]
             and holder(p) is None and p["from_person"] != me["token"]]
    late = [p for p in packages if overdue(p, today) and current_role(p) == me["role_id"]]
    return {"waiting_for_me": len(waiting), "returned_to_me": len(returned),
            "in_team_queue": len(queue), "overdue_for_my_role": len(late)}
