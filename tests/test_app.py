from pathlib import Path

import pytest

import app as app_module


@pytest.fixture
def client():
    return app_module.create_app().test_client()


def test_health(client):
    assert client.get("/health").json == {"ok": True}


def test_new_sandbox_can_read_its_company(client):
    sandbox = client.post("/api/sandbox").json["sandbox"]
    r = client.get("/api/company", headers={"X-Sandbox": sandbox})
    assert r.status_code == 200
    assert r.json == {"company": None}


def test_unknown_sandbox_gets_410_sandbox_expired(client):
    r = client.get("/api/handoff-schema", headers={"X-Sandbox": "nope"})
    assert r.status_code == 410
    assert r.json["error"] == "sandbox_expired"


def test_the_landing_check_for_a_gone_sandbox_is_a_200_not_a_console_error(client):
    assert client.get("/api/company", headers={"X-Sandbox": "nope"}).json == {"company": None, "expired": True}
    assert client.get("/api/company").json == {"company": None, "expired": True}


def test_missing_sandbox_header_gets_410_on_other_routes(client):
    assert client.get("/api/handoff-schema").status_code == 410


def sandbox_headers(client):
    return {"X-Sandbox": client.post("/api/sandbox").json["sandbox"]}


def test_survey_demo_is_prefilled(client):
    assert client.get("/api/survey/demo").json["answers"]["company_name"] == "Harbor Lane Logistics"


def test_chart_in_fake_mode_is_a_labelled_template(client):
    h = sandbox_headers(client)
    answers = client.get("/api/survey/demo").json["answers"]
    r = client.post("/api/chart", json={"answers": answers}, headers=h)
    assert r.status_code == 200
    assert r.json["demo_mode"] is True and r.json["source"] == "template" and r.json["errors"] == []


def test_validate_reports_a_cycle_in_words(client):
    h = sandbox_headers(client)
    roles = [{"id": "a", "title": "A", "reports_to": "b", "headcount": 1},
             {"id": "b", "title": "B", "reports_to": "a", "headcount": 1}]
    r = client.post("/api/chart/validate", json={"roles": roles, "size": 5}, headers=h)
    assert r.json["ok"] is False
    assert any("circle" in e["message"] for e in r.json["errors"])


def test_accept_rejects_an_invalid_chart_and_saves_a_valid_one(client):
    h = sandbox_headers(client)
    bad = [{"id": "a", "title": "A", "reports_to": "a", "headcount": 1}]
    assert client.post("/api/company", json={"roles": bad, "size": 5}, headers=h).status_code == 400
    good = [{"id": "md", "title": "MD", "reports_to": None, "headcount": 1}]
    r = client.post("/api/company", json={"company": "X", "roles": good, "size": 5}, headers=h)
    assert r.status_code == 201 and r.json["version"] == 1
    again = client.post("/api/company", json={"company": "X", "roles": good, "size": 5}, headers=h)
    assert again.json["version"] == 2
    assert client.get("/api/company", headers=h).json["company"]["version"] == 2


def test_one_sandbox_cannot_read_another_sandboxes_accepted_chart(client):
    a, b = sandbox_headers(client), sandbox_headers(client)
    good = [{"id": "md", "title": "MD", "reports_to": None, "headcount": 1}]
    client.post("/api/company", json={"company": "A", "roles": good, "size": 5}, headers=a)
    assert client.get("/api/company", headers=b).json["company"] is None


def test_chart_needs_a_sandbox(client):
    assert client.post("/api/chart", json={"answers": {}}).status_code == 410


def test_pages_are_served_with_a_strict_csp(client):
    for path in ("/", "/join/anything", "/trust"):
        r = client.get(path)
        assert r.status_code == 200 and b"<main" in r.data
        assert "script-src 'self'" in r.headers["Content-Security-Policy"]
        assert r.headers["Referrer-Policy"] == "no-referrer"
    assert client.get("/static/ui.js").status_code == 200


def test_no_script_sets_an_inline_style():
    # The CSP is style-src 'self': an inline style attribute is blocked and logs a console error.
    offenders = [f.name for f in (Path(__file__).parent.parent / "static").glob("*.js")
                 if "style:" in f.read_text(encoding="utf-8") or ".style.cssText" in f.read_text(encoding="utf-8")]
    assert offenders == []


def test_the_chart_can_be_streamed_as_stages_then_the_chart(client):
    h = {"X-Sandbox": client.post("/api/sandbox").json["sandbox"]}
    r = client.post("/api/chart?stream=1", json={"answers": {"company_name": "Acme", "industry": "logistics", "headcount": 14}}, headers=h)
    assert r.mimetype == "text/event-stream"
    events = [b.split("\n")[0] for b in r.get_data(as_text=True).strip().split("\n\n")]
    assert events[0] == "event: stage" and events[-1] == "event: done"
    assert client.post("/api/chart?stream=1", json={"answers": {}}).status_code == 410


def test_a_known_industry_starts_on_its_own_form_and_freight_keeps_the_order_form(client):
    roles = [{"id": "md", "title": "Director", "reports_to": None, "headcount": 1},
             {"id": "ops", "title": "Operations", "reports_to": "md", "headcount": 2}]
    for industry, form in (("Dental clinic", "clinic"), ("software", "services"), ("logistics", "logistics"),
                           (None, "logistics")):
        h = {"X-Sandbox": client.post("/api/sandbox").json["sandbox"]}
        assert client.post("/api/company", json={"roles": roles, "size": 3, "industry": industry}, headers=h).status_code == 201
        assert client.get("/api/handoff-schema", headers=h).json["schema"]["id"] == form


def test_private_status_route_says_only_configured_model_and_last_answer(client, monkeypatch):
    for key in ("PRIVATE_PROVIDER", "PRIVATE_BASE_URL", "PRIVATE_MODEL", "PRIVATE_API_KEY_FILE"):
        monkeypatch.delenv(key, raising=False)
    r = client.get("/api/private/status")
    assert r.status_code == 200 and set(r.get_json()) == {"configured", "model", "answered_s_ago"}
    js = Path("static/join.js").read_text(encoding="utf-8")
    assert "/api/private/status" in js and "may be asleep" in js
    assert "neither ban that nor force its own tool" in Path("static/app.js").read_text(encoding="utf-8")


def test_every_browser_module_parses(tmp_path):
    # Unit tests import only some modules; a quote typo in a page module would otherwise reach the browser.
    import shutil
    import subprocess
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    for js in Path("static").glob("*.js"):
        copy = tmp_path / (js.stem + ".mjs")
        copy.write_text(js.read_text(encoding="utf-8"), encoding="utf-8")
        r = subprocess.run([node, "--check", str(copy)], capture_output=True, text=True)
        assert r.returncode == 0, f"{js.name}: {r.stderr.strip()[:300]}"
