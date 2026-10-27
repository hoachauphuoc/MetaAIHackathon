"""Deterministic tools. The model chooses the arguments; this code computes every number."""
import datetime
import hashlib
import json
from pathlib import Path

PARAMS = json.loads((Path(__file__).parent / "data" / "params.json").read_text(encoding="utf-8"))


def _whole(value, name, low, high):
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f"{name} must be a whole number from {low} to {high}")
    return value


def _money(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(f"{name} must be a positive number")
    return round(float(value), 2)


def quote_price(route, pallets):
    rate = PARAMS["rate_card"].get(route)
    if rate is None:
        raise ValueError(f"route must be one of: {', '.join(PARAMS['rate_card'])}")
    pallets = _whole(pallets, "pallets", 1, 5000)
    price, cost = rate["price"] * pallets, rate["cost"] * pallets
    return {"route": route, "pallets": pallets, "price": price, "cost": cost,
            "margin_pct": margin_pct(price, cost)}


def margin_pct(price, cost):
    price, cost = _money(price, "price"), _money(cost, "cost")
    return round((price - cost) / price * 100, 1)


def check_margin(price, cost):
    pct = margin_pct(price, cost)
    return {"price": price, "cost": cost, "margin_pct": pct,
            "floor_pct": PARAMS["margin_floor_pct"], "below_floor": pct < PARAMS["margin_floor_pct"]}


def make_calendar_event(title, date):
    try:
        day = datetime.date.fromisoformat(date)
    except (TypeError, ValueError):
        raise ValueError("date must look like 2026-11-20")
    title = "".join(c for c in str(title)[:120] if c.isprintable() and c not in ",;\\")
    stamp = day.strftime("%Y%m%d")
    ics = ("BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Role Assistants//EN\r\nBEGIN:VEVENT\r\n"
           f"UID:{stamp}-{hashlib.sha1(title.encode()).hexdigest()[:8]}@role-assistants\r\nDTSTAMP:{stamp}T000000Z\r\n"
           f"DTSTART;VALUE=DATE:{stamp}\r\nSUMMARY:{title}\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n")
    return {"title": title, "date": date, "ics": ics}


TOOLS = {"quote_price": quote_price, "check_margin": check_margin,
         "make_calendar_event": make_calendar_event}

# Function-calling definitions, built from the same names so a tool cannot exist in one place only.
SCHEMAS = {
    "quote_price": {"route": {"type": "string", "enum": list(PARAMS["rate_card"])},
                    "pallets": {"type": "integer"}},
    "check_margin": {"price": {"type": "number"}, "cost": {"type": "number"}},
    "make_calendar_event": {"title": {"type": "string"}, "date": {"type": "string"}},
}


def definition(name):
    props = SCHEMAS[name]
    return {"type": "function", "function": {
        "name": name, "description": (TOOLS[name].__doc__ or name.replace("_", " ")),
        "parameters": {"type": "object", "properties": props, "required": list(props),
                       "additionalProperties": False}}}


def run(name, arguments):
    """Run a tool the model asked for. Unknown tools and bad arguments raise ValueError."""
    if name not in TOOLS:
        raise ValueError(f"unknown tool {name}")
    try:
        args = json.loads(arguments) if isinstance(arguments, str) else dict(arguments)
        if set(args) != set(SCHEMAS[name]):
            raise ValueError("wrong arguments")
        return TOOLS[name](**args)
    except (TypeError, json.JSONDecodeError):
        raise ValueError(f"{name}: arguments could not be read")
