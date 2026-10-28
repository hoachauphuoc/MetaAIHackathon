"""Flask entry point. Routes stay thin: rules, store, chart and muse hold the logic."""
import datetime
import json
import os
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory

import assistants
import brief
import chart
import chat
import handoff_schema
import handoffs
import handover
import muse
import onboarding
import rules
import sam
import store
import tools
import trust
import vision
import voice
import workflow
import workspace


def sse(event, data):
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def create_app(db_path=None):
    app = Flask(__name__)
    app.config["STORE"] = store.Store(db_path or os.environ.get("DB_PATH", ":memory:"))
    db = app.config["STORE"]
    app.config["MAX_CONTENT_LENGTH"] = 6 * 1024 * 1024  # a 4 MB photo as base64, plus the form
    muse.cost_listener = db.add_cost

    @app.errorhandler(store.SandboxExpired)
    def sandbox_expired(e):
        if isinstance(e, store.PersonLeft):
            # The link is revoked; ask the browser to drop what it kept (chat history).
            response = jsonify(error="link_revoked", message="This link has been revoked.")
            response.headers["Clear-Site-Data"] = '"storage"'
            return response, 410
        return jsonify(error="sandbox_expired", message="This sandbox has ended. Start again."), 410

    def current_sandbox():
        sandbox_id = request.headers.get("X-Sandbox", "")
        db.require_sandbox(sandbox_id)
        return sandbox_id

    @app.after_request
    def security_headers(response):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
            "frame-ancestors 'none'")
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"  # the invite token sits in the URL
        return response

    def page(name):
        return send_from_directory(Path(__file__).parent / "static", name)

    @app.get("/")
    def index_page():
        return page("index.html")

    @app.get("/join/<token>")
    def join_page(token):
        return page("join.html")

    @app.get("/trust")
    def trust_html():
        return page("trust.html")

    @app.get("/health")
    def health():
        return jsonify(ok=True)

    @app.post("/api/sandbox")
    def new_sandbox():
        return jsonify(sandbox=db.create_sandbox()), 201

    @app.post("/api/sandbox/muse")
    def muse_switch():
        """Lets a visitor see the labelled demo mode on demand (golden path step 9)."""
        sandbox_id = current_sandbox()
        db.set_muse_off(sandbox_id, bool((request.get_json(silent=True) or {}).get("off")))
        return jsonify(ok=True)

    @app.get("/api/survey/demo")
    def survey_demo():
        path = Path(__file__).parent / "data" / "demo_survey.json"
        return jsonify(answers=json.loads(path.read_text(encoding="utf-8")))

    @app.post("/api/chart")
    def make_chart():
        sandbox_id = current_sandbox()
        answers = (request.get_json(silent=True) or {}).get("answers") or {}
        try:
            return jsonify(chart.generate(answers, lambda: db.spend_model_call(sandbox_id)))
        except ValueError as e:
            return jsonify(error="bad_answers", message=str(e)), 400

    @app.post("/api/chart/validate")
    def validate_chart():
        current_sandbox()
        body = request.get_json(silent=True) or {}
        errors = rules.validate_chart(body.get("roles") or [], body.get("size") or 0)
        return jsonify(ok=not errors, errors=errors)

    @app.post("/api/company")
    def accept_chart():
        """Accept locks this version of the chart; a changed chart must be accepted again."""
        sandbox_id = current_sandbox()
        body = request.get_json(silent=True) or {}
        roles, size = body.get("roles") or [], body.get("size") or 0
        errors = rules.validate_chart(roles, size)
        if errors:
            return jsonify(error="invalid_chart", errors=errors), 400
        previous = db.get_company(sandbox_id)
        company = {"company": body.get("company", ""), "size": size, "roles": roles,
                   "version": (previous or {}).get("version", 0) + 1}
        if (previous or {}).get("handoff_schema"):
            company["handoff_schema"] = previous["handoff_schema"]
        if (previous or {}).get("levels"):
            company["levels"] = previous["levels"]
        db.save_company(sandbox_id, company)
        return jsonify(company), 201

    def accepted_company(sandbox_id):
        company = db.get_company(sandbox_id)
        if not company:
            raise LookupError("Accept the chart first.")
        return company

    @app.post("/api/handoff-schema/generate")
    def generate_handoff_schema():
        """A proposal only: nothing is stored until the owner accepts it."""
        sandbox_id = current_sandbox()
        company = accepted_company(sandbox_id)
        answers = (request.get_json(silent=True) or {}).get("answers") or {}
        return jsonify(handoff_schema.generate(answers, company["roles"],
                                               lambda: db.spend_model_call(sandbox_id)))

    @app.get("/api/handoff-schema")
    def current_handoff_schema():
        company = accepted_company(current_sandbox())
        return jsonify(schema=effective_schema(company),
                       standard={k: v for k, v in rules.SCHEMAS.items()})

    @app.post("/api/handoff-schema")
    def accept_handoff_schema():
        """The owner accepts a form; the server validates again whatever the browser sends."""
        sandbox_id = current_sandbox()
        company = accepted_company(sandbox_id)
        schema = (request.get_json(silent=True) or {}).get("schema")
        errors = rules.validate_handoff_schema(schema)
        if errors:
            return jsonify(error="invalid_form", errors=errors), 400
        if company.get("levels"):
            above = effective_params(company)
            mine = {"margin_floor_pct": rules.rule_threshold(schema, "min_margin", above) or above["margin_floor_pct"],
                    "escalation_usd": rules.rule_threshold(schema, "escalate_over", above) or above["escalation_usd"]}
            errors = rules.validate_child_rules(above, mine, "The levels above")
            if errors:
                return jsonify(error="loosens_parent", errors=errors), 422
        company["handoff_schema"] = handoff_schema.canonical(schema)
        company["version"] = company.get("version", 0) + 1
        db.save_company(sandbox_id, company)
        return jsonify(schema=company["handoff_schema"]), 201

    @app.errorhandler(vision.BadImage)
    def bad_image(e):
        return jsonify(error="bad_image", message=str(e)), 400

    @app.errorhandler(413)
    def too_large(e):
        return jsonify(error="too_large", message="The photo is larger than 4 MB."), 413

    @app.post("/api/handoff-schema/from-photo")
    def handoff_schema_from_photo():
        """A proposal from a photo of the paper form; stored only through the accept route."""
        sandbox_id = current_sandbox()
        accepted_company(sandbox_id)
        body = request.get_json(silent=True) or {}
        industry = handoff_schema.clean_text((body.get("answers") or {}).get("industry"), 40).lower()
        return jsonify(vision.form_from_image(body.get("image"), industry,
                                              lambda: db.spend_model_call(sandbox_id)))

    @app.errorhandler(LookupError)
    def not_found(e):
        return jsonify(error="not_found", message=str(e)), 404

    @app.post("/api/assistants")
    def make_assistant():
        sandbox_id = current_sandbox()
        company = accepted_company(sandbox_id)
        role_id = (request.get_json(silent=True) or {}).get("role_id")
        role = next((r for r in company["roles"] if r["id"] == role_id), None)
        if role is None:
            raise LookupError("No such role.")
        kit = assistants.build(role, company["roles"], lambda: db.spend_model_call(sandbox_id))
        db.save_assistant(sandbox_id, role_id, kit)
        return jsonify(kit)

    @app.get("/api/assistants")
    def list_assistants():
        return jsonify(assistants=db.get_assistants(current_sandbox()))

    @app.get("/api/people")
    def people():
        return jsonify(people=db.list_people(current_sandbox()))

    @app.get("/api/owner/brief")
    def owner_brief():
        """Read-only: approvals stay in the role inbox, where maker-checker applies."""
        sandbox_id = current_sandbox()
        company = accepted_company(sandbox_id)
        # "Team member" is the default label, not a name; ruling it out would drop ordinary lines.
        names = [p["display_name"] for p in db.list_people(sandbox_id) if p["display_name"] != "Team member"]
        return jsonify(brief.write(brief.facts(db.list_packages(sandbox_id), company["roles"], datetime.date.today()),
                                   names, lambda: db.spend_model_call(sandbox_id), ask))

    @app.post("/api/people/<int:person_id>/offboard")
    def offboard(person_id):
        if not db.offboard(current_sandbox(), person_id):
            raise LookupError("No such person.")
        return jsonify(ok=True)

    @app.post("/api/invites")
    def make_invite():
        sandbox_id = current_sandbox()
        company = accepted_company(sandbox_id)
        body = request.get_json(silent=True) or {}
        role = next((r for r in company["roles"] if r["id"] == body.get("role_id")), None)
        if role is None:
            raise LookupError("No such role.")
        name = str(body.get("display_name") or "").strip()[:80] or "Team member"
        token = db.add_person(sandbox_id, role["id"], name, role["headcount"])
        if token is None:
            return jsonify(error="role_full", message=f"{role['title']} has no free seat."), 409
        return jsonify(token=token, url=f"/join/{token}"), 201

    @app.get("/api/invite/<token>")
    def invite(token):
        person = db.person_by_token(token)
        company = db.get_company(person["sandbox_id"]) or {}
        kit = db.get_assistants(person["sandbox_id"]).get(person["role_id"])
        role = next((r for r in company.get("roles", []) if r["id"] == person["role_id"]), None)
        return jsonify(company=company.get("company"), role=role, assistant=kit,
                       display_name=person["display_name"],
                       role_titles={r["id"]: r["title"] for r in company.get("roles", [])},
                       handoff_schema=effective_schema(company), handover_form=rules.HANDOVER_SCHEMA)

    @app.post("/api/chat")
    def chat_route():
        body = request.get_json(silent=True) or {}
        person = db.person_by_token(str(body.get("token") or ""))
        kit = db.get_assistants(person["sandbox_id"]).get(person["role_id"])
        if kit is None:
            raise LookupError("This role has no assistant yet.")
        messages = chat.messages_for(person, kit, body.get("history"), body.get("message") or "",
                                     personal_schema(db.get_company(person["sandbox_id"]) or {}, body.get("token")))
        blocked = db.spend_model_call(person["sandbox_id"])
        company = db.get_company(person["sandbox_id"]) or {"roles": []}
        reader = workspace.Reader(db.list_packages(person["sandbox_id"]),
                                  {**person, "token": str(body.get("token"))}, company["roles"],
                                  datetime.date.today())

        def events():
            yield sse("meta", {"role": kit["role_title"], "model": muse.SPARK})
            read = None if blocked else workspace.look(
                messages, reader, ask, lambda: db.spend_model_call(person["sandbox_id"]))
            if read and read["looked"]:
                yield sse("read", {"looked": list(dict.fromkeys(read["looked"]))})
            if read and read["text"]:
                yield sse("delta", {"text": read["text"]})
                yield sse("done", {"demo_mode": False, "demo_reason": None, "tokens_in": read["tokens_in"],
                                   "tokens_out": read["tokens_out"], "cost_usd": read["cost_usd"]})
                return
            # Nothing usable from the tools: the plain streamed answer, or the labelled demo answer.
            reason = blocked or (read and read["demo_reason"])
            source = iter(
                [{"done": muse.demo_result(muse.SPARK, reason)}]) if reason else muse.stream(
                muse.SPARK, messages)
            for item in source:
                if "delta" in item:
                    yield sse("delta", {"text": item["delta"]})
                    continue
                done = item["done"]
                if done["demo_mode"]:
                    yield sse("delta", {"text": "Demo mode: Muse did not answer, so there is no "
                                                "draft. A person must write this."})
                yield sse("done", {k: done[k] for k in
                                   ("demo_mode", "demo_reason", "tokens_in", "tokens_out", "cost_usd")})

        return Response(events(), mimetype="text/event-stream",
                        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})

    def workflow_body():
        body = request.get_json(silent=True) or {}
        return body, db.person_by_token(str(body.get("token") or ""))

    @app.post("/api/workflow/plan")
    def workflow_plan():
        body, person = workflow_body()
        company = db.get_company(person["sandbox_id"]) or {}
        kits = db.get_assistants(person["sandbox_id"])
        try:
            plan, errors = workflow.make_plan(body.get("task") or {}, company.get("roles", []), kits)
        except ValueError as e:
            return jsonify(error="bad_task", message=str(e)), 400
        if errors:
            return jsonify(error="invalid_plan", errors=errors), 422
        return jsonify(plan=plan, signature=workflow.sign("plan", plan["run_id"], "-", plan),
                       roles={r["id"]: r["title"] for r in company["roles"]})

    @app.post("/api/workflow/step")
    def workflow_step():
        body, person = workflow_body()
        plan = body.get("plan") or {}
        try:
            workflow.verify_plan(plan, body.get("signature"))
            out = workflow.run_step(
                plan, body.get("step_id"), body.get("receipts") or {}, datetime.date.today(),
                effective_params(db.get_company(person["sandbox_id"]) or {}), lambda: db.spend_model_call(person["sandbox_id"]))
        except PermissionError as e:
            return jsonify(error="not_approved", message=str(e)), 409
        except (StopIteration, KeyError):
            return jsonify(error="bad_step", message="No such step."), 400
        return jsonify(out)

    @app.post("/api/workflow/approve")
    def workflow_approve():
        body, _ = workflow_body()
        try:
            workflow.verify_plan(body.get("plan") or {}, body.get("signature"))
            receipt = workflow.approve(body["plan"], body.get("step_id"), body.get("result"),
                                       body.get("ticket"))
        except PermissionError as e:
            return jsonify(error="forged", message=str(e)), 403
        except ValueError as e:
            return jsonify(error="blocked", message=str(e)), 409
        return jsonify(receipt=receipt)

    @app.post("/api/onboarding")
    def onboarding_plan():
        """The plan goes back to the person's browser only; the server keeps no copy and no progress."""
        body = request.get_json(silent=True) or {}
        person = db.person_by_token(str(body.get("token") or ""))
        kit = db.get_assistants(person["sandbox_id"]).get(person["role_id"])
        if kit is None:
            raise LookupError("This role has no assistant yet.")
        company = db.get_company(person["sandbox_id"]) or {"roles": []}
        return jsonify(onboarding.plan(kit, {r["id"]: r["title"] for r in company["roles"]},
                                       effective_schema(company), ask,
                                       lambda: db.spend_model_call(person["sandbox_id"])))

    @app.post("/api/compare")
    def compare_route():
        body = request.get_json(silent=True) or {}
        person = db.person_by_token(str(body.get("token") or ""))
        kit = db.get_assistants(person["sandbox_id"]).get(person["role_id"])
        if kit is None:
            raise LookupError("This role has no assistant yet.")
        return jsonify(chat.compare(kit, body.get("message") or "",
                                    lambda: db.spend_model_call(person["sandbox_id"]),
                                    personal_schema(db.get_company(person["sandbox_id"]) or {}, body.get("token"))))

    def me_and_context():
        body = request.get_json(silent=True) or {}
        token = str(body.get("token") or request.args.get("token") or "")
        me = {**db.person_by_token(token), "token": token}
        company = db.get_company(me["sandbox_id"]) or {"roles": []}
        return body, me, company

    def ask(messages, **kw):
        return muse.complete(muse.SPARK, messages, **kw)

    def package_for(me, package_id):
        package = db.get_package(me["sandbox_id"], package_id)
        if package is None:
            raise LookupError("No such package.")
        return package

    @app.errorhandler(handoffs.Refused)
    def refused(e):
        return jsonify(error="refused", message=e.message), e.status

    def effective_schema(company):
        schema = company.get("handoff_schema") or rules.DEFAULT_SCHEMA
        return rules.bind_levels(company.get("levels"), tools.PARAMS, schema)[1]

    def effective_params(company):
        return rules.bind_levels(company.get("levels"), tools.PARAMS, rules.DEFAULT_SCHEMA)[0]

    def personal_schema(company, token):
        """The company's form with this person's own, only tighter, numbers in place; for their chat only."""
        mine = db.get_personal_rules(str(token or ""))
        schema = effective_schema(company)
        return rules.bind_levels([mine], effective_params(company), schema)[1] if mine else schema

    @app.route("/api/personal-rules", methods=["GET", "PUT"])
    def personal_rules():
        """Private to the person: no owner or unit route reads this table."""
        body, me, company = me_and_context()
        if request.method == "GET":
            return jsonify(rules=db.get_personal_rules(me["token"]), company=effective_params(company))
        above = effective_params(company)
        values = {rule: body.get(rule) for rule in rules.LEVEL_RULES}
        errors = rules.level_value_errors(values) or rules.validate_child_rules(above, values, "The company")
        if errors:
            return jsonify(error="loosens_parent", errors=errors), 422
        db.save_personal_rules(me["token"], values)
        return jsonify(rules=values)

    @app.get("/api/levels")
    def get_levels():
        company = accepted_company(current_sandbox())
        levels = company.get("levels")
        return jsonify(levels=levels, rules=rules.LEVEL_RULES,
                       effective=rules.provenance(levels, tools.PARAMS) if levels else None)

    @app.post("/api/levels/enable")
    def enable_levels():
        """Two units of this one company, both starting at the company's own numbers."""
        sandbox_id = current_sandbox()
        company = accepted_company(sandbox_id)
        if not company.get("levels"):
            start = {"margin_floor_pct": tools.PARAMS["margin_floor_pct"],
                     "escalation_usd": tools.PARAMS["escalation_usd"]}
            company["levels"] = [{"id": "group", "name": "Group", **start},
                                 {"id": "subsidiary", "name": "Subsidiary", **start}]
            db.save_company(sandbox_id, company)
        return jsonify(levels=company["levels"]), 201

    @app.put("/api/levels/<unit_id>")
    def set_level(unit_id):
        """The one write route for a unit's rules: a child may only tighten its parent's."""
        sandbox_id = current_sandbox()
        company = accepted_company(sandbox_id)
        levels = company.get("levels") or []
        index = next((i for i, u in enumerate(levels) if u["id"] == unit_id), None)
        if index is None:
            return jsonify(error="no_such_unit", message="No such unit in this company."), 404
        body = request.get_json(silent=True) or {}
        values = {rule: body.get(rule) for rule in rules.LEVEL_RULES}
        errors = rules.level_value_errors(values)
        if not errors and index > 0:
            errors = rules.validate_child_rules(levels[index - 1], values, levels[index - 1]["name"])
        if errors:
            return jsonify(error="loosens_parent", errors=errors), 422
        levels[index] = {**levels[index], **values}
        db.save_company(sandbox_id, company)
        return jsonify(levels=levels)

    def view_of(package, me, company):
        titles = {r["id"]: r["title"] for r in company["roles"]}
        return handoffs.view(package, me, datetime.date.today(), titles)

    @app.post("/api/handoffs")
    def send_handoff():
        body, me, company = me_and_context()
        blocked = lambda: db.spend_model_call(me["sandbox_id"])  # noqa: E731
        package = handoffs.send(
            me["sandbox_id"], {**me, "token": me["token"]}, body.get("to_role"),
            body.get("values") or {}, body.get("due"), db, db.get_assistants(me["sandbox_id"]),
            company["roles"], effective_params(company), datetime.date.today(), ask, blocked,
            effective_schema(company))
        return jsonify(view_of(package, me, company)), 201

    @app.post("/api/handover/draft")
    def handover_draft():
        """A private draft for the person leaving; it goes back to their browser only."""
        body, me, company = me_and_context()
        titles = {r["id"]: r["title"] for r in company["roles"]}
        kit = db.get_assistants(me["sandbox_id"]).get(me["role_id"]) or {}
        return jsonify(handover.draft(me["token"], titles.get(me["role_id"], me["role_id"]),
                                      db.list_packages(me["sandbox_id"]), kit, titles, body.get("notes"),
                                      ask, lambda: db.spend_model_call(me["sandbox_id"])))

    @app.post("/api/handover")
    def send_handover():
        body, me, company = me_and_context()
        package = handoffs.send_handover(me["sandbox_id"], me, body.get("values") or {}, db,
                                         company["roles"], effective_params(company), datetime.date.today())
        return jsonify(view_of(package, me, company)), 201

    @app.post("/api/handoffs/from-photo")
    def handoff_from_photo():
        """Read a paper document into the company's form. Nothing is stored: the person checks and sends."""
        body, me, company = me_and_context()
        return jsonify(vision.read_values(body.get("image"), effective_schema(company), effective_params(company),
                                          datetime.date.today(), lambda: db.spend_model_call(me["sandbox_id"])))

    @app.post("/api/transcribe")
    def transcribe():
        """Turn a short spoken job note into text for the message box. Nothing is stored."""
        body, me, company = me_and_context()
        try:
            return jsonify(voice.transcribe(body.get("audio"), lambda: db.spend_model_call(me["sandbox_id"])))
        except voice.BadAudio as e:
            return jsonify(error="bad_audio", message=str(e)), 400

    @app.post("/api/photo/regions")
    def photo_regions():
        """Outline what a short phrase names in a photo so the browser can cover it. Nothing is stored."""
        body, me, company = me_and_context()
        try:
            return jsonify(sam.find_regions(body.get("image"), body.get("phrase"),
                                            lambda: db.spend_model_call(me["sandbox_id"])))
        except (vision.BadImage, ValueError) as e:
            return jsonify(error="bad_request", message=str(e)), 400

    @app.post("/api/handoffs/from-text")
    def handoff_from_text():
        """Read a pasted customer message into the company's form. Nothing is stored: the person checks and sends."""
        body, me, company = me_and_context()
        try:
            return jsonify(vision.read_text(body.get("text"), effective_schema(company), effective_params(company),
                                            datetime.date.today(), lambda: db.spend_model_call(me["sandbox_id"])))
        except ValueError as e:
            return jsonify(error="bad_text", message=str(e)), 400

    @app.post("/api/precheck")
    def precheck():
        """Private pre-check: nothing is stored."""
        body, me, company = me_and_context()
        today = datetime.date.today()
        schema = effective_schema(company)
        status, findings, _ = handoffs.run_check(
            handoffs.clean_values(body.get("values") or {}, schema), effective_params(company), today,
            ask, lambda: db.spend_model_call(me["sandbox_id"]), schema)
        problem = handoffs.due_problem(body.get("due"), today)
        if problem:  # "Check first" must agree with "Send", which refuses this
            findings.insert(0, {"status": "blocked", "source": "rules", "message": problem})
            status = "blocked"
        return jsonify(status=status, findings=findings)

    @app.get("/api/inbox")
    def inbox():
        _, me, company = me_and_context()
        today = datetime.date.today()
        packages = db.list_packages(me["sandbox_id"])
        mine = handoffs.visible_to(packages, me)
        mine.sort(key=lambda p: handoffs.sort_key(p, me, today))
        return jsonify(today=handoffs.today_summary(packages, me, today),
                       packages=[view_of(p, me, company) for p in mine])

    def hold_change(package_id, action):
        _, me, company = me_and_context()
        package = package_for(me, package_id)
        action(package, me)
        db.save_package(me["sandbox_id"], package)
        return jsonify(view_of(package, me, company))

    @app.post("/api/handoffs/<package_id>/again")
    def start_again(package_id):
        """A new draft from one of my own handoffs. Nothing is stored until the person sends it."""
        _, me, company = me_and_context()
        package = package_for(me, package_id)
        return jsonify(handoffs.start_again(package, me, handoffs.package_schema(package)))

    @app.post("/api/handoffs/<package_id>/claim")
    def claim_package(package_id):
        return hold_change(package_id, handoffs.claim)

    @app.post("/api/handoffs/<package_id>/unclaim")
    def unclaim_package(package_id):
        return hold_change(package_id, handoffs.unclaim)

    @app.post("/api/handoffs/<package_id>/decision")
    def decide_package(package_id):
        body, me, company = me_and_context()
        package = package_for(me, package_id)
        acting_role = handoffs.current_role(package)
        handoffs.decide(package, me, body.get("decision"), body.get("reason"))
        db.save_package(me["sandbox_id"], package)
        db.log_decision(package_id, body["decision"], acting_role, str(body.get("reason") or ""))
        return jsonify(view_of(package, me, company))

    @app.post("/api/handoffs/<package_id>/resend")
    def resend_package(package_id):
        body, me, company = me_and_context()
        package = package_for(me, package_id)
        handoffs.resend(package, me, body.get("values") or {}, body.get("due"), effective_params(company),
                        datetime.date.today(), ask, lambda: db.spend_model_call(me["sandbox_id"]),
                        company["roles"])
        db.save_package(me["sandbox_id"], package)
        return jsonify(view_of(package, me, company))

    @app.post("/api/handoffs/<package_id>/suggest")
    def suggest_fix(package_id):
        body, me, company = me_and_context()
        package = package_for(me, package_id)
        return jsonify(handoffs.suggest_fix(
            package, me, datetime.date.today(), effective_params(company), ask,
            lambda: db.spend_model_call(me["sandbox_id"])))

    @app.get("/api/trust")
    def trust_page():
        return jsonify(trust.build(db.table_names()))

    @app.get("/api/company")
    def company():
        """The landing page asks this first. A gone sandbox is the normal answer for a returning
        visitor, so it is a 200 with expired=true: a 410 here would show as a red console line."""
        try:
            return jsonify(company=db.get_company(request.headers.get("X-Sandbox", "")))
        except store.SandboxExpired:
            return jsonify(company=None, expired=True)

    return app


app = create_app()
