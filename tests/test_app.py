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
