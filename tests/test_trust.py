import pytest

import app as app_module
import muse
import trust


@pytest.fixture
def client():
    return app_module.create_app().test_client()


def test_every_table_is_documented_and_nothing_extra_is_claimed(client):
    names = {r[0] for r in client.application.config["STORE"].db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert names == set(trust.STORED)


def test_no_table_or_column_can_hold_chat_or_person_metrics(client):
    db = client.application.config["STORE"].db
    for (table,) in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall():
        for col in (c[1] for c in db.execute(f"PRAGMA table_info({table})")):
            assert not any(w in col for w in ("message", "chat", "prompt", "reply", "score", "rating"))


def test_trust_lists_forbidden_skills_and_the_two_standard_models(client):
    data = client.get("/api/trust").json
    assert {"evaluate_person", "rank_employees", "hr_decision", "monitor_activity"} == set(
        data["skills"]["forbidden"])
    assert {m["id"] for m in data["models"]} == {muse.WONDER, muse.SPARK}
    assert all(not m["id"].endswith("-contributor") for m in data["models"])


def test_trust_links_meta_statements_only_while_every_model_is_standard(client, monkeypatch):
    links = client.get("/api/trust").json["meta_statements"]
    assert links and all(l["url"].startswith("https://") for l in links)
    monkeypatch.setattr(trust, "MODEL_USE", {**trust.MODEL_USE, "muse-spark-1.3-contributor": "x"})
    assert client.get("/api/trust").json["meta_statements"] == []


def test_private_mode_says_unavailable_until_a_provider_is_configured(client, monkeypatch):
    for k in ("PRIVATE_PROVIDER", "PRIVATE_BASE_URL", "PRIVATE_MODEL", "PRIVATE_API_KEY_FILE"):
        monkeypatch.delenv(k, raising=False)
    assert client.get("/api/trust").json["private"]["available"] is False
    monkeypatch.setenv("PRIVATE_PROVIDER", "baseten")
    monkeypatch.setenv("PRIVATE_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("PRIVATE_MODEL", "meta-models/muse-spark-open")
    monkeypatch.setenv("PRIVATE_API_KEY_FILE", "key.txt")
    private = client.get("/api/trust").json["private"]
    assert private["available"] is True and "hosted by baseten" in private["label"]
    assert private["attribution"] == "Model: meta-models/muse-spark-open"


def test_real_model_answers_feed_the_daily_cost(client, monkeypatch):
    from types import SimpleNamespace
    monkeypatch.delenv("FAKE_AI", raising=False)
    msg = SimpleNamespace(content="hi", tool_calls=None)
    reply = SimpleNamespace(choices=[SimpleNamespace(message=msg)],
                            usage=SimpleNamespace(prompt_tokens=1_000_000, completion_tokens=0))
    fake = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **k: reply)))
    monkeypatch.setattr(muse, "_client", lambda cfg=None: fake)
    muse.complete(muse.SPARK, [])
    assert client.application.config["STORE"].cost_today() == pytest.approx(1.25)


def test_private_never_goes_to_the_meta_api_when_unconfigured(monkeypatch):
    for k in ("PRIVATE_PROVIDER", "PRIVATE_BASE_URL", "PRIVATE_MODEL", "PRIVATE_API_KEY_FILE"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.delenv("FAKE_AI", raising=False)
    monkeypatch.setattr(muse, "_client", lambda cfg=None: pytest.fail("a client was created"))
    out = muse.complete(None, [], private=True)
    assert out["demo_mode"] is True and out["demo_reason"] == "Private mode unavailable"


def test_private_contributor_model_is_refused(monkeypatch):
    monkeypatch.delenv("FAKE_AI", raising=False)
    monkeypatch.setenv("PRIVATE_PROVIDER", "baseten")
    monkeypatch.setenv("PRIVATE_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("PRIVATE_MODEL", "meta-models/x-contributor")
    monkeypatch.setenv("PRIVATE_API_KEY_FILE", "key.txt")
    with pytest.raises(muse.Refused):
        muse.complete(None, [], private=True)
