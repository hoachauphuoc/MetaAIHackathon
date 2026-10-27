"""Flask entry point. Routes stay thin: rules, store and muse hold the logic."""
import os

from flask import Flask, jsonify, request

import store


def create_app(db_path=None):
    app = Flask(__name__)
    app.config["STORE"] = store.Store(db_path or os.environ.get("DB_PATH", ":memory:"))

    @app.errorhandler(store.SandboxExpired)
    def sandbox_expired(_):
        return jsonify(error="sandbox_expired", message="This sandbox has ended. Start again."), 410

    @app.get("/health")
    def health():
        return jsonify(ok=True)

    @app.post("/api/sandbox")
    def new_sandbox():
        return jsonify(sandbox=app.config["STORE"].create_sandbox()), 201

    @app.get("/api/company")
    def company():
        sandbox_id = request.headers.get("X-Sandbox", "")
        return jsonify(company=app.config["STORE"].get_company(sandbox_id))

    return app


app = create_app()
