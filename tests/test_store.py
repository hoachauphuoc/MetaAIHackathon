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
    spent = [s.spend_model_call(sandbox) for _ in range(store.MODEL_CALL_CAP + 1)]
    assert spent.count(None) == store.MODEL_CALL_CAP
    assert spent[-1] == "Demo limit reached"


def test_switching_muse_off_blocks_calls_with_its_own_label(s):
    sandbox = s.create_sandbox()
    s.set_muse_off(sandbox, True)
    assert s.spend_model_call(sandbox) == "Muse switched off"
    s.set_muse_off(sandbox, False)
    assert s.spend_model_call(sandbox) is None


def test_no_table_can_hold_chat(s):
    tables = {r[0] for r in s.db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert tables == {"sandboxes", "companies", "assistants", "people", "daily_cost"}


def test_daily_ceiling_stops_all_sandboxes(s, monkeypatch):
    monkeypatch.setattr(store, "DAILY_CEILING_USD", 1.0)
    a, b = s.create_sandbox(), s.create_sandbox()
    assert s.spend_model_call(a) is None
    s.add_cost(0.6)
    s.add_cost(0.6)
    assert s.spend_model_call(a) == "Demo limit reached"
    assert s.spend_model_call(b) == "Demo limit reached"


def test_parallel_requests_share_one_connection_safely(s):
    import concurrent.futures
    sandbox = s.create_sandbox()

    def work(_):
        s.spend_model_call(sandbox)
        s.save_assistant(sandbox, "r", {"x": 1})
        return s.get_assistants(sandbox)

    with concurrent.futures.ThreadPoolExecutor(8) as pool:
        results = list(pool.map(work, range(200)))
    assert all(r == {"r": {"x": 1}} for r in results)
