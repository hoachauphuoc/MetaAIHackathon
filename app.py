"""Flask entry point. Routes stay thin: rules, store, chart and muse hold the logic."""
import json
import os
from pathlib import Path

from flask import Flask, jsonify, request

import chart
import rules
import store


def create_app(db_path=None):
    app = Flask(__name__)
    app.config["STORE"] = store.Store(db_path or os.environ.get("DB_PATH", ":memory:"))
    db = app.config["STORE"]

    @app.errorhandler(store.SandboxExpired)
    def sandbox_expired(_):
        return jsonify(error="sandbox_expired", message="This sandbox has ended. Start again."), 410

    def current_sandbox():
        sandbox_id = request.headers.get("X-Sandbox", "")
        db.require_sandbox(sandbox_id)
        return sandbox_id

    @app.get("/health")
    def health():
        return jsonify(ok=True)

    @app.post("/api/sandbox")
    def new_sandbox():
        return jsonify(sandbox=db.create_sandbox()), 201

    @app.get("/api/survey/demo")
    def survey_demo():
        path = Path(__file__).parent / "data" / "demo_survey.json"
        return jsonify(answers=json.loads(path.read_text(encoding="utf-8")))

    @app.post("/api/chart")
    def make_chart():
        sandbox_id = current_sandbox()
        answers = (request.get_json(silent=True) or {}).get("answers") or {}
        try:
            return jsonify(chart.generate(answers, lambda: db.try_spend_model_call(sandbox_id)))
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

    @app.get("/api/company")
    def company():
        return jsonify(company=db.get_company(request.headers.get("X-Sandbox", "")))

    return app


app = create_app()
