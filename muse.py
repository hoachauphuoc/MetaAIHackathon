"""The only door to a model. Everything else calls complete().

A failed call never returns made-up model text: the result carries demo_mode=True so the
UI can label it (principle 3). Logs hold model, tokens, cost and latency, never messages.
"""
import logging
import os
import time

from openai import OpenAI

BASE_URL = "https://api.meta.ai/v1"

SPARK = "muse-spark-1.3"
WONDER = "muse-wonder-1.0"

# USD per 1M tokens (input, output), checked 26/10. Reasoning tokens are billed as output.
PRICES = {
    SPARK: (1.25, 4.25),
    WONDER: (4.0, 20.0),
}

log = logging.getLogger("muse")


class Refused(ValueError):
    """The model id is not on the allow-list, or would train on employee data."""


def check_model(model, private=False):
    if model.endswith("-contributor"):
        raise Refused(f"{model}: Contributor models may train on data; Standard mode only")
    if not private and model not in PRICES:
        raise Refused(f"{model}: not on the allow-list")


def private_config():
    """Private mode runs an open-weights Muse model on a provider chosen by PRIVATE_PROVIDER
    (baseten | fireworks | modal). Nothing is configured by default."""
    cfg = {"provider": os.environ.get("PRIVATE_PROVIDER"),
           "base_url": os.environ.get("PRIVATE_BASE_URL"),
           "model": os.environ.get("PRIVATE_MODEL"),
           "key_file": os.environ.get("PRIVATE_API_KEY_FILE")}
    return cfg if all(cfg.values()) else None


def cost_usd(model, tokens_in, tokens_out):
    price_in, price_out = PRICES.get(model, (0.0, 0.0))  # open-weights models: price unknown
    return (tokens_in * price_in + tokens_out * price_out) / 1_000_000


def _api_key():
    key = os.environ.get("META_API_KEY")
    path = os.environ.get("META_API_KEY_FILE")
    if not key and path:
        with open(path, encoding="utf-8") as f:
            key = f.read().strip()
    return key


def _client(private=None):
    if private:
        with open(private["key_file"], encoding="utf-8") as f:
            return OpenAI(api_key=f.read().strip(), base_url=private["base_url"], max_retries=0,
                          timeout=60)
    key = _api_key()
    if not key:
        raise RuntimeError("no Meta API key configured")
    return OpenAI(api_key=key, base_url=BASE_URL, max_retries=0, timeout=60)


def _result(model, demo_mode, reason=None, text="", tool_calls=(), tokens_in=0, tokens_out=0,
            latency_ms=0):
    return {
        "model": model, "demo_mode": demo_mode, "demo_reason": reason, "text": text,
        "tool_calls": list(tool_calls), "tokens_in": tokens_in, "tokens_out": tokens_out,
        "cost_usd": cost_usd(model, tokens_in, tokens_out), "latency_ms": latency_ms,
    }


def demo_result(model, reason):
    return _result(model, True, reason)


def complete(model, messages, reasoning_effort="low", private=False, **kwargs):
    """One model call with one retry. Extra kwargs (tools, response_format...) pass through.
    private=True sends the call to the open-weights provider and never to the Meta API: when
    Private mode is not configured the answer is a labelled "unavailable", not a substitute."""
    cfg = None
    if private:
        cfg = private_config()
        if cfg is None:
            return _result("private", True, "Private mode unavailable")
        model = cfg["model"]
    check_model(model, private)
    if os.environ.get("FAKE_AI"):
        return _result(model, True, "FAKE_AI")

    error = None
    for _ in range(2):
        start = time.time()
        try:
            r = _client(cfg).chat.completions.create(
                model=model, messages=messages, reasoning_effort=reasoning_effort, **kwargs)
        except Exception as e:  # any failure, including a missing key, becomes a labelled fallback
            error = type(e).__name__
            continue
        msg = r.choices[0].message
        calls = [{"name": c.function.name, "arguments": c.function.arguments}
                 for c in msg.tool_calls or []]
        out = _result(model, False, text=msg.content or "", tool_calls=calls,
                      tokens_in=r.usage.prompt_tokens, tokens_out=r.usage.completion_tokens,
                      latency_ms=int((time.time() - start) * 1000))
        log.info("model=%s in=%d out=%d cost=%.5f ms=%d", model, out["tokens_in"],
                 out["tokens_out"], out["cost_usd"], out["latency_ms"])
        return out

    log.warning("model=%s failed: %s", model, error)
    return _result(model, True, error)


def stream(model, messages, reasoning_effort="minimal", **kwargs):
    """Yield {"delta": text} chunks, then one {"done": result}. No retry once text has started:
    a half answer must not be followed by a second one."""
    check_model(model)
    if os.environ.get("FAKE_AI"):
        yield {"done": _result(model, True, "FAKE_AI")}
        return
    start, started, tokens_in, tokens_out = time.time(), False, 0, 0
    try:
        for chunk in _client().chat.completions.create(
                model=model, messages=messages, reasoning_effort=reasoning_effort, stream=True,
                stream_options={"include_usage": True}, **kwargs):
            if chunk.usage:
                tokens_in, tokens_out = chunk.usage.prompt_tokens, chunk.usage.completion_tokens
            if chunk.choices and chunk.choices[0].delta.content:
                started = True
                yield {"delta": chunk.choices[0].delta.content}
    except Exception as e:
        log.warning("model=%s stream failed: %s", model, type(e).__name__)
        yield {"done": _result(model, True, type(e).__name__)}
        return
    out = _result(model, False, tokens_in=tokens_in, tokens_out=tokens_out,
                  latency_ms=int((time.time() - start) * 1000))
    log.info("model=%s in=%d out=%d cost=%.5f ms=%d streamed=%s", model, tokens_in, tokens_out,
             out["cost_usd"], out["latency_ms"], started)
    yield {"done": out}
