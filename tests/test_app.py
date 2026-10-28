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
    r = client.get("/api/company", headers={"X-Sandbox": "nope"})
    assert r.status_code == 410
    assert r.json["error"] == "sandbox_expired"


def test_missing_sandbox_header_gets_410(client):
    assert client.get("/api/company").status_code == 410


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
