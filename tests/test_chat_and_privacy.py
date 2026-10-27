import json
import logging

import pytest

import app as app_module
import muse

ROLES = [{"id": "md", "title": "MD", "reports_to": None, "headcount": 1},
         {"id": "sales", "title": "Sales Lead", "reports_to": "md", "headcount": 2}]


@pytest.fixture
def client():
    return app_module.create_app().test_client()


def setup_company(client):
    h = {"X-Sandbox": client.post("/api/sandbox").json["sandbox"]}
    client.post("/api/company", json={"company": "Acme", "roles": ROLES, "size": 10}, headers=h)
    client.post("/api/assistants", json={"role_id": "sales"}, headers=h)
    return h


def invite(client, h, role="sales"):
    return client.post("/api/invites", json={"role_id": role, "display_name": "Lan"}, headers=h)


def parse_sse(body):
    events = []
    for block in body.decode().strip().split("\n\n"):
        name, data = block.split("\n")
        events.append((name.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return events


def test_assistant_needs_an_accepted_chart(client):
    h = {"X-Sandbox": client.post("/api/sandbox").json["sandbox"]}
    assert client.post("/api/assistants", json={"role_id": "sales"}, headers=h).status_code == 404


def test_invite_opens_the_assistant_of_that_role_only(client):
    h = setup_company(client)
    token = invite(client, h).json["token"]
    r = client.get(f"/api/invite/{token}").json
    assert r["role"]["id"] == "sales" and r["assistant"]["role_id"] == "sales"
    assert r["company"] == "Acme"


def test_role_with_no_free_seat_is_refused(client):
    h = setup_company(client)
    assert invite(client, h, "md").status_code == 201
    assert invite(client, h, "md").status_code == 409


def test_unknown_token_is_410(client):
    assert client.get("/api/invite/nope").status_code == 410
    assert client.post("/api/chat", json={"token": "nope", "message": "hi"}).status_code == 410


def test_chat_in_fake_mode_is_labelled_demo(client):
    h = setup_company(client)
    token = invite(client, h).json["token"]
    r = client.post("/api/chat", json={"token": token, "message": "Draft a quote email"})
    events = parse_sse(r.data)
    assert [e[0] for e in events][0] == "meta" and events[-1][0] == "done"
    assert events[-1][1]["demo_mode"] is True
    assert any("Demo mode" in e[1].get("text", "") for e in events)


def test_chat_streams_deltas_when_muse_answers(client, monkeypatch):
    h = setup_company(client)
    token = invite(client, h).json["token"]
    done = muse._result(muse.SPARK, False, tokens_in=10, tokens_out=5)
    monkeypatch.setattr(muse, "stream", lambda *a, **k: iter(
        [{"delta": "Dear "}, {"delta": "customer"}, {"done": done}]))
    events = parse_sse(client.post("/api/chat", json={"token": token, "message": "x"}).data)
    assert "".join(e[1]["text"] for e in events if e[0] == "delta") == "Dear customer"
    assert events[-1][1]["demo_mode"] is False and events[-1][1]["tokens_in"] == 10


def table_counts(client):
    db = client.application.config["STORE"].db
    names = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
    return {n: db.execute(f"SELECT COUNT(*) FROM {n}").fetchone()[0] for n in names}


def test_chat_leaves_no_trace_in_any_table_or_log(client, monkeypatch, caplog):
    h = setup_company(client)
    token = invite(client, h).json["token"]
    done = muse._result(muse.SPARK, False, tokens_in=10, tokens_out=5)
    monkeypatch.setattr(muse, "stream", lambda *a, **k: iter(
        [{"delta": "SECRET-REPLY"}, {"done": done}]))
    before = table_counts(client)
    with caplog.at_level(logging.DEBUG):
        client.post("/api/chat", json={"token": token, "message": "SECRET-PROMPT",
                                       "history": [{"role": "user", "content": "SECRET-OLD"}]})
    assert table_counts(client) == before
    dump = json.dumps([list(r) for r in client.application.config["STORE"].db.iterdump()])
    assert "SECRET" not in dump and "SECRET" not in caplog.text


def test_chat_history_is_trimmed_and_roles_are_checked():
    import chat
    kit = {"role_title": "Sales Lead", "goal": "g", "jobs": ["a"], "limits": ["l"]}
    history = [{"role": "system", "content": "evil"}] + [
        {"role": "user", "content": str(i)} for i in range(30)]
    msgs = chat.messages_for({}, kit, history, "now")
    assert msgs[0]["role"] == "system" and msgs[-1]["content"] == "now"
    assert len(msgs) == chat.MAX_HISTORY + 2
    assert all(m["content"] != "evil" for m in msgs)
