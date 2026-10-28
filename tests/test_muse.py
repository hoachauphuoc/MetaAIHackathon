import logging
from types import SimpleNamespace

import pytest

import muse


def fake_response(text="hi", tokens_in=100, tokens_out=50):
    msg = SimpleNamespace(content=text, tool_calls=None)
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)],
                           usage=SimpleNamespace(prompt_tokens=tokens_in, completion_tokens=tokens_out))


class FakeClient:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture
def real_path(monkeypatch):
    monkeypatch.delenv("FAKE_AI", raising=False)


def use_client(monkeypatch, *outcomes):
    client = FakeClient(outcomes)
    monkeypatch.setattr(muse, "_client", lambda cfg=None: client)
    return client


def test_contributor_models_are_refused():
    with pytest.raises(muse.Refused):
        muse.complete("muse-spark-1.3-contributor", [])


def test_unknown_models_are_refused():
    with pytest.raises(muse.Refused):
        muse.complete("gpt-4o", [])


def test_fake_ai_never_calls_a_model(monkeypatch):
    monkeypatch.setenv("FAKE_AI", "1")
    monkeypatch.setattr(muse, "_client", lambda: pytest.fail("model was called"))
    out = muse.complete("muse-spark-1.3", [{"role": "user", "content": "x"}])
    assert out["demo_mode"] is True


def test_real_answer_is_not_demo_mode_and_cost_comes_from_usage(real_path, monkeypatch):
    use_client(monkeypatch, fake_response("hello", 1_000_000, 1_000_000))
    out = muse.complete("muse-spark-1.3", [])
    assert out["demo_mode"] is False
    assert out["text"] == "hello"
    assert out["cost_usd"] == pytest.approx(1.25 + 4.25)


def test_one_retry_then_success(real_path, monkeypatch):
    client = use_client(monkeypatch, TimeoutError(), fake_response())
    assert muse.complete("muse-wonder-1.0", [])["demo_mode"] is False
    assert client.calls == 2


def test_two_failures_return_labelled_demo_mode(real_path, monkeypatch):
    client = use_client(monkeypatch, TimeoutError(), TimeoutError())
    out = muse.complete("muse-spark-1.3", [])
    assert out["demo_mode"] is True
    assert out["demo_reason"] == "TimeoutError"
    assert out["text"] == ""
    assert client.calls == 2


def test_missing_key_is_demo_mode_not_a_crash(real_path, monkeypatch):
    monkeypatch.delenv("META_API_KEY", raising=False)
    monkeypatch.delenv("META_API_KEY_FILE", raising=False)
    assert muse.complete("muse-spark-1.3", [])["demo_mode"] is True


def test_logs_never_contain_message_text(real_path, monkeypatch, caplog):
    use_client(monkeypatch, fake_response("the answer is SECRET-REPLY"))
    with caplog.at_level(logging.DEBUG):
        muse.complete("muse-spark-1.3", [{"role": "user", "content": "SECRET-PROMPT"}])
    assert "SECRET" not in caplog.text
    assert "in=100 out=50" in caplog.text


class APITimeoutError(Exception):
    """Named like the OpenAI SDK's error: muse.complete reads the class name."""


def test_a_cold_private_container_is_labelled_starting_and_never_uses_the_meta_api(real_path, monkeypatch):
    for key, value in (("PRIVATE_PROVIDER", "modal"), ("PRIVATE_BASE_URL", "https://x"),
                       ("PRIVATE_MODEL", "glimmer"), ("PRIVATE_API_KEY_FILE", "k")):
        monkeypatch.setenv(key, value)
    seen = []
    monkeypatch.setattr(muse, "_client", lambda cfg=None: seen.append(cfg) or FakeClient(
        [APITimeoutError(), APITimeoutError()]))
    out = muse.complete(None, [], private=True)
    assert out["demo_mode"] and out["demo_reason"] == muse.PRIVATE_STARTING
    assert seen and all(cfg is not None for cfg in seen)
    assert len(seen) == 1, "a cold start is not retried: two waits would pass the 120 s request limit"
