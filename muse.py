"""The only door to a model. Everything else calls complete().

A failed call never returns made-up model text: the result carries demo_mode=True so the
UI can label it (principle 3). Logs hold model, tokens, cost and latency, never messages.
"""
import json
import logging
import os
import time
import urllib.request
import uuid

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

# Called with the USD cost of every real model answer; the app points it at the daily ceiling.
cost_listener = None


class Refused(ValueError):
    """The model id is not on the allow-list, or would train on employee data."""


def check_model(model, private=False):
    if model.endswith("-contributor"):
        raise Refused(f"{model}: Contributor models may train on data; Standard mode only")
    if not private and model not in PRICES:
        raise Refused(f"{model}: not on the allow-list")


PRIVATE_STARTING = "Private mode starting"
_private_answered_at = None  # when the open-weights endpoint last answered; one number, nothing about who asked"
# A cold container needs about 3 minutes, so waiting longer cannot help: answer "starting" well inside the
# 120 s the host allows a request, or the person sees a 504 and no label.
PRIVATE_TIMEOUT = 35


def private_config():
    """Private mode runs an open-weights Muse model on a provider chosen by PRIVATE_PROVIDER
    (baseten | fireworks | modal). Nothing is configured by default."""
    cfg = {"provider": os.environ.get("PRIVATE_PROVIDER"),
           "base_url": os.environ.get("PRIVATE_BASE_URL"),
           "model": os.environ.get("PRIVATE_MODEL"),
           "key_file": os.environ.get("PRIVATE_API_KEY_FILE")}
    return cfg if all(cfg.values()) else None


def private_status():
    """What the invite page may say before a Private step runs: configured or not, the model id, and how long ago
    the endpoint last answered. Recent means probably warm; nothing is probed, so nothing wakes or bills."""
    cfg = private_config()
    ago = None if _private_answered_at is None else int(time.time() - _private_answered_at)
    return {"configured": cfg is not None, "model": cfg["model"] if cfg else None, "answered_s_ago": ago}


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
                          timeout=PRIVATE_TIMEOUT)
    key = _api_key()
    if not key:
        raise RuntimeError("no Meta API key configured")
    return OpenAI(api_key=key, base_url=BASE_URL, max_retries=0, timeout=60)


def _result(model, demo_mode, reason=None, text="", tool_calls=(), tokens_in=0, tokens_out=0,
            latency_ms=0, answered_by=None):
    # answered_by is the id the provider's own response carried; it stays None when no model answered.
    return {
        "model": model, "answered_by": answered_by, "demo_mode": demo_mode, "demo_reason": reason, "text": text,
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
            if cfg and error in ("APITimeoutError", "APIConnectionError"):
                break  # a second try would only wait out the same cold start
            continue
        msg = r.choices[0].message
        calls = [{"name": c.function.name, "arguments": c.function.arguments}
                 for c in msg.tool_calls or []]
        out = _result(model, False, text=msg.content or "", tool_calls=calls,
                      tokens_in=r.usage.prompt_tokens, tokens_out=r.usage.completion_tokens,
                      latency_ms=int((time.time() - start) * 1000),
                      answered_by=getattr(r, "model", None) or model)
        log.info("model=%s in=%d out=%d cost=%.5f ms=%d", model, out["tokens_in"],
                 out["tokens_out"], out["cost_usd"], out["latency_ms"])
        if cfg:
            global _private_answered_at
            _private_answered_at = time.time()
        if cost_listener:
            cost_listener(out["cost_usd"])
        return out

    log.warning("model=%s failed: %s", model, error)
    if cfg and error in ("APITimeoutError", "APIConnectionError"):
        error = PRIVATE_STARTING  # a cold open-weights container answers after about 3 minutes; never the Meta API
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
    if cost_listener:
        cost_listener(out["cost_usd"])
    yield {"done": out}


TRANSCRIBE = "muse-voice-transcribe-1.0"
TRANSCRIBE_USD_PER_HOUR = 0.18  # billed by audio length, not tokens
ASR_URL = BASE_URL + "/asr/transcribe"


def _multipart(edge, settings, wav):
    """The two parts the speech endpoint wants: the JSON settings and the audio file."""
    crlf = bytes((13, 10))

    def head(disposition, kind):
        return f"--{edge}".encode() + crlf + disposition.encode() + crlf + f"Content-Type: {kind}".encode() + crlf + crlf

    return (head('Content-Disposition: form-data; name="request"', "application/json") + settings + crlf
            + head('Content-Disposition: form-data; name="audio"; filename="note.wav"', "audio/wav") + wav + crlf
            + f"--{edge}--".encode() + crlf)


def transcribe(wav, timeout=60):
    """Speech to text for one short recording (16-bit mono WAV, checked by the caller). The audio is sent once
    and dropped; the result is labelled demo_mode on any failure, like complete()."""
    if os.environ.get("FAKE_AI"):
        return {**_result(TRANSCRIBE, True, "FAKE_AI"), "audio_ms": 0}
    start = time.time()
    try:
        key = _api_key()
        if not key:
            raise RuntimeError("no Meta API key configured")
        edge = "----role-assistants-" + uuid.uuid4().hex  # stdlib multipart: no HTTP library to depend on
        settings = json.dumps({"mode": "ENDPOINTING", "model": TRANSCRIBE, "audioEncoding": "WAV"}).encode()
        body = _multipart(edge, settings, wav)
        req = urllib.request.Request(ASR_URL, data=body, method="POST", headers={
            "Authorization": f"Bearer {key}", "Content-Type": f"multipart/form-data; boundary={edge}"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            reply = json.loads(r.read())
        audio_ms = int(reply.get("audioDurationMs") or 0)
        out = {**_result(TRANSCRIBE, False, text=str(reply.get("transcript") or ""),
                         latency_ms=int((time.time() - start) * 1000)), "audio_ms": audio_ms}
    except Exception as e:
        log.warning("model=%s failed: %s", TRANSCRIBE, type(e).__name__)
        return {**_result(TRANSCRIBE, True, type(e).__name__), "audio_ms": 0}
    out["cost_usd"] = out["audio_ms"] / 3_600_000 * TRANSCRIBE_USD_PER_HOUR
    log.info("model=%s audio_ms=%d cost=%.6f ms=%d", TRANSCRIBE, out["audio_ms"], out["cost_usd"], out["latency_ms"])
    if cost_listener:
        cost_listener(out["cost_usd"])
    return out


SEGMENT = "sam-3.1"
RESPONSES_URL = BASE_URL + "/responses"


def segment(phrase, data_url, timeout=60):
    """Ask SAM 3.1 to outline what a short phrase names in one image. Returns its token text. store=false: Meta keeps
    no copy of the request. SAM's price is not on the pricing page, so the cost is recorded as 0 and the call is
    counted by the daily ceiling instead."""
    if os.environ.get("FAKE_AI"):
        return _result(SEGMENT, True, "FAKE_AI")
    start = time.time()
    try:
        key = _api_key()
        if not key:
            raise RuntimeError("no Meta API key configured")
        body = {"model": SEGMENT, "store": False, "metadata": {"include_confidence": "true"}, "input": [{
            "type": "message", "role": "user", "content": [
                {"type": "input_text", "text": phrase}, {"type": "input_image", "image_url": data_url}]}]}
        req = urllib.request.Request(RESPONSES_URL, data=json.dumps(body).encode(), method="POST", headers={
            "Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            reply = json.loads(r.read())
        text = "".join(part.get("text", "") for item in reply.get("output", []) for part in item.get("content", [])
                       if part.get("type") == "output_text")
    except Exception as e:
        log.warning("model=%s failed: %s", SEGMENT, type(e).__name__)
        return _result(SEGMENT, True, type(e).__name__)
    log.info("model=%s ms=%d", SEGMENT, int((time.time() - start) * 1000))
    return _result(SEGMENT, False, text=text, latency_ms=int((time.time() - start) * 1000))
