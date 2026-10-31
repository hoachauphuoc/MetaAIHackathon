"""Load test of the Meta API in Standard mode: N sequential requests with one fixed short prompt.

Usage: python scripts/load_test.py 100 [model] [meta|baseten]
(the key comes from META_API_KEY or META_API_KEY_FILE for meta, BASETEN_API_KEY_FILE for baseten, PRIVATE_API_KEY_FILE
for glimmer; never printed)
Reports latency p50 and p95, the error count, and the tokens used. This measures the endpoint under a steady
stream of identical requests. It is NOT evidence about users: no person is involved and no product data is sent.
"""
import os
import statistics
import sys
import time

from openai import OpenAI

PROVIDERS = {
    "meta": ("https://api.meta.ai/v1", "muse-spark-1.3", lambda: os.environ.get("META_API_KEY_FILE")),
    "baseten": ("https://inference.baseten.co/v1", "meta-models/muse-spark-open-1026",
                lambda: os.environ.get("BASETEN_API_KEY_FILE", "C:/Users/phuochoa/.bjt/Baseten.txt")),
    "glimmer": ("https://hoachauphuoc--muse-glimmer-private-glimmer-serve.us-east.modal.run/v1", "meta-models/Muse-Glimmer-30B",
                lambda: os.environ.get("PRIVATE_API_KEY_FILE")),
}
PROMPT = "Reply with the single word: ok"


def key(provider):
    path = PROVIDERS[provider][2]()
    if path:
        return open(path, encoding="utf-8").read().strip()
    return os.environ["META_API_KEY"]


def main(n, model, provider):
    base_url = PROVIDERS[provider][0]
    client = OpenAI(api_key=key(provider), base_url=base_url, max_retries=0, timeout=60)
    latencies, errors, tokens = [], 0, 0
    for _ in range(n):
        start = time.time()
        try:
            r = client.chat.completions.create(model=model, messages=[{"role": "user", "content": PROMPT}],
                                               max_tokens=5, reasoning_effort="minimal")
            latencies.append((time.time() - start) * 1000)
            tokens += r.usage.total_tokens
        except Exception as e:  # every failure is counted, none is hidden
            errors += 1
            print(f"error {type(e).__name__}")
    ms = sorted(latencies)
    p50 = statistics.median(ms) if ms else float("nan")
    p95 = ms[min(len(ms) - 1, int(round(0.95 * (len(ms) - 1))))] if ms else float("nan")
    print(f"provider={provider} model={model} requests={n} ok={len(ms)} errors={errors} p50_ms={p50:.0f} p95_ms={p95:.0f} tokens={tokens}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    provider = sys.argv[3] if len(sys.argv) > 3 else "meta"
    model = sys.argv[2] if len(sys.argv) > 2 else PROVIDERS[provider][1]
    main(int(sys.argv[1]), model, provider)
