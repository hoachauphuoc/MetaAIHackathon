import time

import pytest

import store


@pytest.fixture
def s():
    return store.Store()


def test_sandbox_cannot_read_another_sandboxes_company(s):
    a, b = s.create_sandbox(), s.create_sandbox()
    s.save_company(a, {"name": "Alpha"})
    s.save_company(b, {"name": "Beta"})
    assert s.get_company(a) == {"name": "Alpha"}
    assert s.get_company(b) == {"name": "Beta"}


def test_unknown_sandbox_is_expired(s):
    with pytest.raises(store.SandboxExpired):
        s.get_company("nope")


def test_sandbox_and_its_data_are_deleted_after_24_hours(s):
    old = time.time() - store.SANDBOX_TTL - 1
    sandbox = s.create_sandbox(now=old)
    s.db.execute("INSERT INTO companies VALUES (?, ?)", (sandbox, "{}"))
    with pytest.raises(store.SandboxExpired):
        s.require_sandbox(sandbox)
    assert s.db.execute("SELECT COUNT(*) FROM companies").fetchone()[0] == 0


def test_model_call_cap(s):
    sandbox = s.create_sandbox()
    spent = [s.try_spend_model_call(sandbox) for _ in range(store.MODEL_CALL_CAP + 1)]
    assert spent.count(True) == store.MODEL_CALL_CAP
    assert spent[-1] is False


def test_no_table_can_hold_chat(s):
    tables = {r[0] for r in s.db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert tables == {"sandboxes", "companies", "assistants", "people"}
