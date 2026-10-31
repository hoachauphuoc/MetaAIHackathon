"""Cases written by a council of Muse testers and run here as plain HTTP calls (FAKE_AI, no model is called).

tests/council_cases.json holds the cases; each step is {method, path, headers, json, save, expect}. Strings may use
{name} for a value saved by an earlier step (`save`: {name: "json.key.sub"}); `sandbox_a` and `sandbox_b` are two fresh
sandboxes. A model proposes a case, but this file decides pass or fail: a case whose expectation was wrong is fixed or
removed with a note in its "note" field, never skipped.
"""
import json
import re
from pathlib import Path

import pytest

import app as app_module

CASES = json.loads((Path(__file__).parent / "council_cases.json").read_text(encoding="utf-8"))


def fill(value, env):
    if isinstance(value, str):
        whole = re.fullmatch(r"\{(\w+)\}", value)
        if whole and whole[1] in env:
            return env[whole[1]]  # a saved object or number goes in as itself, not as its text
        return re.sub(r"\{(\w+)\}", lambda m: str(env.get(m[1], m[0])), value)
    if isinstance(value, list):
        return [fill(v, env) for v in value]
    if isinstance(value, dict):
        return {k: fill(v, env) for k, v in value.items()}
    return value


def dig(data, path):
    for part in (path.split(".")[1:] if path.split(".")[0] == "json" else path.split(".")):
        data = data[int(part)] if isinstance(data, list) else data[part]
    return data


def present(data, path):
    try:
        dig(data, path)
        return True
    except (KeyError, IndexError, TypeError, ValueError):
        return False


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_council_case(case):
    client = app_module.create_app().test_client()
    env = {"sandbox_a": client.post("/api/sandbox").json["sandbox"],
           "sandbox_b": client.post("/api/sandbox").json["sandbox"]}
    for step in case["steps"]:
        step = fill(step, env)
        kw = {"headers": step.get("headers") or {}}
        if "json" in step:
            kw["json"] = step["json"]
        r = client.open(step["path"], method=step["method"], **kw)
        expect = step.get("expect", {})
        assert r.status_code != 500, f"{case['id']}: {step['method']} {step['path']} gave 500"
        if "status" in expect:
            assert r.status_code in expect["status"], f"{step['path']}: {r.status_code} not in {expect['status']}"
        body = r.get_json(silent=True)
        for key in expect.get("json_has", []):
            assert body is not None and present(body, key), f"{step['path']}: missing {key}"
        for path, wanted in expect.get("json_eq", {}).items():
            assert body is not None and dig(body, path) == wanted, f"{step['path']}: {path} != {wanted!r}"
        for text in expect.get("body_lacks", []):
            assert text not in r.get_data(as_text=True), f"{step['path']}: body holds {text!r}"
        for name, path in (step.get("save") or {}).items():
            env[name] = dig(body, path)
