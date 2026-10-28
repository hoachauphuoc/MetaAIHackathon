"""What /trust says, built from the running configuration so it cannot drift from the code."""
import muse
import rules

# One line per table. A test fails if a table is added without a line here.
STORED = {
    "sandboxes": "A sandbox id, when it was created, how many model calls it made (a count, no content).",
    "companies": "The accepted org chart (role titles, reporting lines, headcounts) and the handoff form the "
                 "owner chose: field names and rules about documents, never about people. If the company uses "
                 "levels, each unit's margin floor and approval limit: company rules, nothing about a person.",
    "assistants": "One brief per role: goal, allowed skills, everyday jobs, handoffs and limits.",
    "people": "An invite token, a display name and a role. No email, no activity, no metrics.",
    "personal_rules": "Private rules a person sets for their own assistant: readable only with that person's "
                      "invite link, never shown to the owner, a unit or anyone else, never counted or summarised.",
    "packages": "Handed-off business documents (a quote package: customer, route, price, dates), "
                "who sent and who holds it, its check result. Company records, kept for the sandbox. "
                "A handover a leaving person chose to send is one of them: their own words about open work.",
    "decisions": "Accept or return decisions on a document: the role that acted, the reason, the date.",
    "daily_cost": "Dollars spent per day across the service. No who, no what.",
}

NEVER_STORED = [
    "Chat messages and chat history: they stay in your browser and are sent for each answer only.",
    "Workflow orders, tool results and approvals: they stay in your browser.",
    "A suggested fix for a returned package: shown to the sender once and never saved. Only the "
    "version the sender chooses to resend is stored.",
    "Photos of paper documents: sent to the model once to fill the form, then dropped.",
    "What the chat assistant read to answer you: it can only read your own documents, nothing "
    "it reads is kept, and it cannot claim, accept, return or send anything.",
    "The owner's morning brief: written on request from the open documents, never saved. It counts "
    "documents by role, never by person.",
    "A new person's first-three-days plan and their ticks: they stay in that person's browser; "
    "nobody, including the owner, sees how far they got.",
    "A handover draft: shown only to the person leaving until they choose to send it.",
    "Anything about how a person works: habits, speed, experience or per-person statistics.",
    "Employee data is never used to train a model: only Standard mode is used, and any model "
    "whose id ends in -contributor is refused.",
]

LIMITS = [
    "Demo only: an invite link is the whole credential, there are no passwords.",
    "Sandboxes are deleted after 24 hours and may be lost earlier if the service restarts.",
    "Emails, phone numbers, card numbers and ID numbers are masked in your browser before the "
    "notes of a handoff or a chat message are sent to a model. Names cannot be detected, and the "
    "other form fields are not masked, so keep personal names out of them. A handover is masked "
    "field by field. Photos are not masked: cover names and phone numbers before taking one.",
    "Reading a photo can go wrong. The values only fill the form; the person checks every field "
    "and the rules check them again. A field the model says it cannot read is left empty and marked.",
    "Models make mistakes. Every handoff needs a person to press Approve, and a blocked "
    "handoff can never be approved.",
    "Numbers (prices, margins) are computed by code from the company's rate card, not by a model.",
]

MODEL_USE = {
    muse.WONDER: "Designs the org chart from the survey.",
    muse.SPARK: "Writes assistant briefs, answers chat, calls tools, checks and summarises handoffs, "
                "suggests a fix for a returned package, reads photos of paper documents, writes the "
                "owner's morning brief, plans a new person's first days and drafts a leaver's handover.",
}


# Where Meta states how Standard mode treats content, so a reader can check the claim at its source.
# Shown only while every model in use is a Standard-mode id; see docs/research FINDINGS.md.
META_STATEMENTS = [
    {"label": "Meta's model list: which versions are Standard mode and which may train on content",
     "url": "https://ai.developer.meta.com/docs/models/"},
    {"label": "Meta Model API: pricing and the data-use line for each model",
     "url": "https://developer.meta.com/ai/products/meta-model-api/"},
]


def build(table_names):
    private = muse.private_config()
    standard = not any(m.endswith("-contributor") for m in MODEL_USE)
    return {
        "meta_statements": META_STATEMENTS if standard else [],
        "stored": [{"table": t, "what": STORED.get(t, "(undocumented)")} for t in sorted(table_names)],
        "never_stored": NEVER_STORED,
        "models": [{"id": m, "use": u} for m, u in MODEL_USE.items()],
        "private": ({"available": True, "provider": private["provider"], "model": private["model"],
                     "label": f"Open-weights model, hosted by {private['provider']}.",
                     "attribution": f"Model: {private['model']}"}
                    if private else
                    {"available": False, "label": "Private mode unavailable.",
                     "attribution": "No open-weights model is connected."}),
        "private_note": "Finance handoffs run in Private mode. If it is unavailable they are "
                        "marked 'A person must check this', never sent to the standard model.",
        "skills": {"allowed": [s["id"] for s in rules.SKILLS["allowed"]],
                   "forbidden": sorted(rules.FORBIDDEN_SKILLS)},
        "limits": LIMITS,
        "retention": "24 hours",
    }
