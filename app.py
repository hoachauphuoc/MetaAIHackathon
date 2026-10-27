"""Flask entry point. Routes stay thin: rules, store, chart and muse hold the logic."""
import datetime
import json
import os
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory

import assistants
import chart
import chat
import handoff_schema
import handoffs
import muse
import rules
import store
import tools
import trust
import vision
import workflow


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
                       handoff_schema=effective_schema(company))

    @app.post("/api/chat")
    def chat_route():
        body = request.get_json(silent=True) or {}
        person = db.person_by_token(str(body.get("token") or ""))
        kit = db.get_assistants(person["sandbox_id"]).get(person["role_id"])
        if kit is None:
            raise LookupError("This role has no assistant yet.")
        messages = chat.messages_for(person, kit, body.get("history"), body.get("message") or "",
                                     effective_schema(db.get_company(person["sandbox_id"]) or {}))
        blocked = db.spend_model_call(person["sandbox_id"])

        def events():
            yield sse("meta", {"role": kit["role_title"], "model": muse.SPARK})
            source = iter(
                [{"done": muse.demo_result(muse.SPARK, blocked)}]) if blocked else muse.stream(
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
                tools.PARAMS, lambda: db.spend_model_call(person["sandbox_id"]))
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

    @app.post("/api/compare")
    def compare_route():
        body = request.get_json(silent=True) or {}
        person = db.person_by_token(str(body.get("token") or ""))
        kit = db.get_assistants(person["sandbox_id"]).get(person["role_id"])
        if kit is None:
            raise LookupError("This role has no assistant yet.")
        return jsonify(chat.compare(kit, body.get("message") or "",
                                    lambda: db.spend_model_call(person["sandbox_id"]),
                                    effective_schema(db.get_company(person["sandbox_id"]) or {})))

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
        return company.get("handoff_schema") or rules.DEFAULT_SCHEMA

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
            company["roles"], tools.PARAMS, datetime.date.today(), ask, blocked,
            effective_schema(company))
        return jsonify(view_of(package, me, company)), 201

    @app.post("/api/handoffs/from-photo")
    def handoff_from_photo():
        """Read a paper document into the company's form. Nothing is stored: the person checks and sends."""
        body, me, company = me_and_context()
        return jsonify(vision.read_values(body.get("image"), effective_schema(company), tools.PARAMS,
                                          datetime.date.today(), lambda: db.spend_model_call(me["sandbox_id"])))

    @app.post("/api/precheck")
    def precheck():
        """Private pre-check: nothing is stored."""
        body, me, company = me_and_context()
        today = datetime.date.today()
        schema = effective_schema(company)
        status, findings, _ = handoffs.run_check(
            handoffs.clean_values(body.get("values") or {}, schema), tools.PARAMS, today,
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
        # A returned package is the sender's to fix; the receiving team has nothing to do with it.
        mine = [p for p in packages if p["from_person"] == me["token"]
                or (p["state"] != "returned" and handoffs.current_role(p) == me["role_id"])]
        mine.sort(key=lambda p: handoffs.sort_key(p, me, today))
        return jsonify(today=handoffs.today_summary(packages, me, today),
                       packages=[view_of(p, me, company) for p in mine])

    def hold_change(package_id, action):
        _, me, company = me_and_context()
        package = package_for(me, package_id)
        action(package, me)
        db.save_package(me["sandbox_id"], package)
        return jsonify(view_of(package, me, company))

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
        handoffs.resend(package, me, body.get("values") or {}, body.get("due"), tools.PARAMS,
                        datetime.date.today(), ask, lambda: db.spend_model_call(me["sandbox_id"]),
                        company["roles"])
        db.save_package(me["sandbox_id"], package)
        return jsonify(view_of(package, me, company))

    @app.post("/api/handoffs/<package_id>/suggest")
    def suggest_fix(package_id):
        body, me, company = me_and_context()
        package = package_for(me, package_id)
        return jsonify(handoffs.suggest_fix(
            package, me, datetime.date.today(), tools.PARAMS, ask,
            lambda: db.spend_model_call(me["sandbox_id"])))

    @app.get("/api/trust")
    def trust_page():
        return jsonify(trust.build(db.table_names()))

    @app.get("/api/company")
    def company():
        return jsonify(company=db.get_company(request.headers.get("X-Sandbox", "")))

    return app


app = create_app()
