"""Flask entry point. Routes stay thin: rules, store, chart and muse hold the logic."""
import datetime
import json
import os
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory

import assistants
import chart
import chat
import muse
import rules
import store
import tools
import trust
import workflow


def sse(event, data):
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def create_app(db_path=None):
    app = Flask(__name__)
    app.config["STORE"] = store.Store(db_path or os.environ.get("DB_PATH", ":memory:"))
    db = app.config["STORE"]
    muse.cost_listener = db.add_cost

    @app.errorhandler(store.SandboxExpired)
    def sandbox_expired(_):
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
        db.save_company(sandbox_id, company)
        return jsonify(company), 201

    def accepted_company(sandbox_id):
        company = db.get_company(sandbox_id)
        if not company:
            raise LookupError("Accept the chart first.")
        return company

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
                       display_name=person["display_name"])

    @app.post("/api/chat")
    def chat_route():
        body = request.get_json(silent=True) or {}
        person = db.person_by_token(str(body.get("token") or ""))
        kit = db.get_assistants(person["sandbox_id"]).get(person["role_id"])
        if kit is None:
            raise LookupError("This role has no assistant yet.")
        messages = chat.messages_for(person, kit, body.get("history"), body.get("message") or "")
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
                                    lambda: db.spend_model_call(person["sandbox_id"])))

    @app.get("/api/trust")
    def trust_page():
        return jsonify(trust.build(db.table_names()))

    @app.get("/api/company")
    def company():
        return jsonify(company=db.get_company(request.headers.get("X-Sandbox", "")))

    return app


app = create_app()
