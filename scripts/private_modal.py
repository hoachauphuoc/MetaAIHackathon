"""Private mode provider: Muse Glimmer 30B (open weights, Apache 2.0) served on Modal with vLLM.

The project owner runs this; Claude does not deploy it. Muse Spark Open (816B) is too large to host
on one GPU, so Private mode uses Glimmer, the open-weights model Meta ships for a single 80 GB GPU.
Modal is not in requirements.txt: install it for yourself with `pip install modal`, then:

    modal setup
    modal secret create muse-private-key VLLM_API_KEY=<a long random string>
    modal deploy scripts/private_modal.py          (prints the endpoint URL)
    modal run scripts/private_modal.py             (cold-start check: loads the model and asks one question)

Then point the app at it (the key goes in a file, never on the command line):
    PRIVATE_PROVIDER=modal
    PRIVATE_BASE_URL=<endpoint URL>/v1
    PRIVATE_MODEL=meta-models/Muse-Glimmer-30B
    PRIVATE_API_KEY_FILE=<file holding the same long random string>

The first request after idle waits for the model to load (about 200 s measured on an H200); the app
gives up after 60 s and labels the step "Private mode unavailable", so warm the endpoint with
`modal run scripts/private_modal.py` a few minutes before a demo. It stays warm for 10 minutes after
the last request, then the GPU is released and billing stops.

Checked on 28/10 against the real model: tool calls parse, reasoning stays out of the answer, and
json_schema is enforced from the first token, so the model answers without a visible reasoning phase.
"""
import os
import subprocess

import modal

MODEL = "meta-models/Muse-Glimmer-30B"
VLLM_VERSION = "0.32.0"  # Glimmer needs 0.28 or later; the 0.21 we first tried predates the model
PARSER = "muse_glimmer"  # reasoning and tool-call parsers ship in vLLM since 0.28 and must be used together
GPU = "H200"  # 141 GB: the weights take 56 GiB and vLLM also profiles an image, which overflowed 80 GB cards
PORT = 8000
MINUTES = 60

image = (modal.Image.from_registry("nvidia/cuda:12.8.1-devel-ubuntu22.04", add_python="3.12")
         .entrypoint([])
         .uv_pip_install(f"vllm=={VLLM_VERSION}", "huggingface_hub[hf_xet]")
         .env({"HF_XET_HIGH_PERFORMANCE": "1"}))
hf_cache = modal.Volume.from_name("huggingface-cache", create_if_missing=True)
vllm_cache = modal.Volume.from_name("vllm-cache", create_if_missing=True)
app = modal.App("muse-glimmer-private")


@app.function(image=image, gpu=GPU, scaledown_window=10 * MINUTES, timeout=30 * MINUTES,
              volumes={"/root/.cache/huggingface": hf_cache, "/root/.cache/vllm": vllm_cache},
              secrets=[modal.Secret.from_name("muse-private-key")])
@modal.concurrent(max_inputs=8)
@modal.web_server(port=PORT, startup_timeout=15 * MINUTES)
def serve():
    # VLLM_API_KEY comes from the secret; vLLM then rejects any request without that bearer token.
    # Tool calls and json_schema output are what the Finance step sends (workflow.py).
    # Glimmer thinks in a `to=self` channel and calls tools in XML, not JSON; without the two muse_glimmer
    # parsers its reasoning leaks into the answer. --generation-config auto takes the sampling Meta
    # recommends (greedy decoding is discouraged). vLLM 0.21 predates the model and wrote gibberish.
    subprocess.Popen([
        "vllm", "serve", MODEL, "--served-model-name", MODEL, "--host", "0.0.0.0", "--port", str(PORT),
        "--max-model-len", "8192", "--max-num-seqs", "8", "--gpu-memory-utilization", "0.92",
        "--enable-auto-tool-choice", "--tool-call-parser", PARSER, "--reasoning-parser", PARSER,
        "--generation-config", "auto",
        # With a reasoning parser vLLM waits for the end of reasoning before it applies json_schema, and
        # Glimmer never signals it, so the schema was ignored. This applies it from the first token.
        "--structured-outputs-config.enable_in_reasoning", "true"])


@app.local_entrypoint()
def check():
    """Cold-start check: waits for the server, then asks one question through the same API the app uses."""
    import json
    import time
    import urllib.request
    url = serve.get_web_url()
    key = os.environ.get("VLLM_API_KEY")
    if not key:
        raise SystemExit("Set VLLM_API_KEY in this shell to the same value as the secret, then rerun.")
    body = json.dumps({"model": MODEL, "max_tokens": 40,
                       "messages": [{"role": "user", "content": "Reply with the single word: ready"}]}).encode()
    request = urllib.request.Request(url + "/v1/chat/completions", body,
                                     {"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    start = time.time()
    with urllib.request.urlopen(request, timeout=20 * MINUTES) as reply:
        answer = json.load(reply)["choices"][0]["message"]["content"]
    print(f"{int(time.time() - start)} s to first answer: {answer.strip()!r}")
