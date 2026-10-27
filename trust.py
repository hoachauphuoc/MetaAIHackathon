"""What /trust says, built from the running configuration so it cannot drift from the code."""
import muse
import rules

# One line per table. A test fails if a table is added without a line here.
STORED = {
    "sandboxes": "A sandbox id, when it was created, how many model calls it made (a count, no content).",
    "companies": "The accepted org chart: role titles, reporting lines and headcounts.",
    "assistants": "One brief per role: goal, allowed skills, everyday jobs, handoffs and limits.",
    "people": "An invite token, a display name and a role. No email, no activity, no metrics.",
    "daily_cost": "Dollars spent per day across the service. No who, no what.",
}

NEVER_STORED = [
    "Chat messages and chat history: they stay in your browser and are sent for each answer only.",
    "Workflow orders, tool results and approvals: they stay in your browser.",
    "Anything about how a person works: habits, speed, experience or per-person statistics.",
    "Employee data is never used to train a model: only Standard mode is used, and any model "
    "whose id ends in -contributor is refused.",
]

LIMITS = [
    "Demo only: an invite link is the whole credential, there are no passwords.",
    "Sandboxes are deleted after 24 hours and may be lost earlier if the service restarts.",
    "Models make mistakes. Every handoff needs a person to press Approve, and a blocked "
    "handoff can never be approved.",
    "Numbers (prices, margins) are computed by code from the company's rate card, not by a model.",
]

MODEL_USE = {
    muse.WONDER: "Designs the org chart from the survey.",
    muse.SPARK: "Writes assistant briefs, answers chat, calls tools and checks handoffs.",
}


def build(table_names):
    private = muse.private_config()
    return {
        "stored": [{"table": t, "what": STORED.get(t, "(undocumented)")} for t in sorted(table_names)],
        "never_stored": NEVER_STORED,
        "models": [{"id": m, "use": u} for m, u in MODEL_USE.items()],
        "private": ({"available": True, "provider": private["provider"], "model": private["model"],
                     "label": f"Open-weights model, hosted by {private['provider']}.",
                     "attribution": "Built with Muse Spark Open"}
                    if private else
                    {"available": False, "label": "Private mode unavailable.",
                     "attribution": "Built with Muse Spark Open"}),
        "private_note": "Finance handoffs run in Private mode. If it is unavailable they are "
                        "marked 'A person must check this', never sent to the standard model.",
        "skills": {"allowed": [s["id"] for s in rules.SKILLS["allowed"]],
                   "forbidden": sorted(rules.FORBIDDEN_SKILLS)},
        "limits": LIMITS,
        "retention": "24 hours",
    }
