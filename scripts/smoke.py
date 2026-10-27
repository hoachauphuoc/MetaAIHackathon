"""Verify what the Meta Model API really supports before any feature depends on it.

Order follows the plan: access, model ids, structured output, function calling, usage.
Prints one line per check with latency and token counts, never the key.
Usage: python scripts/smoke.py   (key from META_API_KEY or the file in META_API_KEY_FILE)
"""
import json
import os
import sys
import time

from openai import OpenAI

BASE_URL = "https://api.meta.ai/v1"
WONDER = "muse-wonder-1.0"
SPARK = "muse-spark-1.3"

CHART_SCHEMA = {
    "type": "object",
    "properties": {"roles": {"type": "array", "items": {
        "type": "object",
        "properties": {"id": {"type": "string"}, "title": {"type": "string"},
                       "reports_to": {"type": ["string", "null"]}},
        "required": ["id", "title", "reports_to"], "additionalProperties": False}}},
    "required": ["roles"], "additionalProperties": False,
}

ADD_TOOL = {"type": "function", "function": {
    "name": "quote_price",
    "description": "Price a quantity at a unit price.",
    "parameters": {"type": "object",
                   "properties": {"qty": {"type": "integer"}, "unit_price": {"type": "number"}},
                   "required": ["qty", "unit_price"], "additionalProperties": False}}}


def load_key():
    key = os.environ.get("META_API_KEY")
    path = os.environ.get("META_API_KEY_FILE")
    if not key and path:
        with open(path, encoding="utf-8") as f:
            key = f.read().strip()
    if not key:
        sys.exit("No key: set META_API_KEY or META_API_KEY_FILE")
    return key


def run(name, fn):
    start = time.time()
    try:
        detail = fn()
        print(f"OK   {name:<28} {time.time() - start:5.1f}s  {detail}")
        return True
    except Exception as e:  # smoke must report every failure, not stop at the first
        msg = str(e).replace("\n", " ")[:300]
        print(f"FAIL {name:<28} {time.time() - start:5.1f}s  {type(e).__name__}: {msg}")
        return False


def usage_text(r):
    u = r.usage
    return f"in={u.prompt_tokens} out={u.completion_tokens} usage={u.model_dump(exclude_none=True)}"


def main():
    client = OpenAI(api_key=load_key(), base_url=BASE_URL, max_retries=0, timeout=90)
    results = []

    def hello(model):
        r = client.chat.completions.create(
            model=model, messages=[{"role": "user", "content": "Reply with the word ok."}],
            reasoning_effort="minimal", max_tokens=200)
        return usage_text(r)

    for model in (SPARK, WONDER):
        results.append(run(f"access {model}", lambda m=model: hello(m)))

    def structured():
        r = client.chat.completions.create(
            model=WONDER, reasoning_effort="low", max_tokens=1500,
            messages=[{"role": "user", "content":
                       "Org chart for a 6-person logistics company: 3 roles, one root."}],
            response_format={"type": "json_schema", "json_schema": {
                "name": "chart", "strict": True, "schema": CHART_SCHEMA}})
        data = json.loads(r.choices[0].message.content)
        return f"roles={len(data['roles'])} {usage_text(r)}"

    results.append(run("structured output (Wonder)", structured))

    def tool_call():
        r = client.chat.completions.create(
            model=SPARK, reasoning_effort="minimal", max_tokens=300,
            messages=[{"role": "user", "content": "Price 12 units at 9.5 using the tool."}],
            tools=[ADD_TOOL], tool_choice="auto")
        calls = r.choices[0].message.tool_calls or []
        if not calls:
            raise RuntimeError("model returned no tool call")
        return f"{calls[0].function.name}({calls[0].function.arguments}) {usage_text(r)}"

    results.append(run("function calling (Spark)", tool_call))

    print(f"\n{sum(results)}/{len(results)} checks passed")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
