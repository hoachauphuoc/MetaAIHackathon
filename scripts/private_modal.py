"""Private mode provider: Muse Glimmer 30B (open weights, Apache 2.0) served on Modal with vLLM.

The project owner runs this; Claude does not deploy it. Muse Spark Open (816B) is too large to host
on one GPU, so Private mode uses Glimmer, the open-weights model Meta ships for a single 80 GB GPU.
Modal is not in requirements.txt: install it for yourself with `pip install modal`, then:

    modal setup
    modal secret create muse-private-key VLLM_API_KEY=<a long random string>
    modal deploy scripts/private_modal.py          (prints the endpoint URL)
    modal run scripts/private_modal.py             (cold-start check: asks the deployed endpoint one question)

Then point the app at it (the key goes in a file, never on the command line):
    PRIVATE_PROVIDER=modal
    PRIVATE_BASE_URL=<endpoint URL>/v1
    PRIVATE_MODEL=meta-models/Muse-Glimmer-30B
    PRIVATE_API_KEY_FILE=<file holding the same long random string>

The first request after idle waits for the model to load (166 s timed on an H200, docs/MEASURED.md set 10, before
snapshots); the app gives up after 35 s and labels the step "Private mode starting". A GPU memory snapshot is meant to
cut that: the server loads once at deploy, goes to sleep (weights offloaded to CPU), and Modal stores the container
state, so a cold start restores it and wakes the GPU instead of reloading 56 GiB. It is untested for Glimmer: after
`modal deploy` run `modal run scripts/private_modal.py` once while the app is idle (10+ minutes) and read the seconds
it prints. If the deploy or the wake fails, `GLIMMER_SNAPSHOT=0 modal deploy scripts/private_modal.py` serves without
snapshots. Snapshots only exist for deployed apps, so `modal run` here asks the deployed endpoint. The container stays
warm for 10 minutes after the last request, then the GPU is released and billing stops.

For the judging days only, keep one container awake so no judge meets the cold start, then set it back:
    GLIMMER_MIN_CONTAINERS=1 modal deploy scripts/private_modal.py     (bills the GPU every second it stays up)
    modal deploy scripts/private_modal.py                              (back to zero: billing stops when idle)
An awake H200 is billed by the second whether or not anyone asks, so this is a window, never the default.

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
MIN_CONTAINERS = int(os.environ.get("GLIMMER_MIN_CONTAINERS", "0"))  # read at deploy time; 0 scales to zero

image = (modal.Image.from_registry("nvidia/cuda:12.8.1-devel-ubuntu22.04", add_python="3.12")
         .entrypoint([])
         .uv_pip_install(f"vllm=={VLLM_VERSION}", "huggingface_hub[hf_xet]")
         .env({"HF_XET_HIGH_PERFORMANCE": "1",
               "VLLM_SERVER_DEV_MODE": "1",  # without it vLLM has no /sleep and /wake_up (404) and startup fails in a loop
               "TORCHINDUCTOR_COMPILE_THREADS": "1"}))  # Modal's advice for snapshot compatibility
hf_cache = modal.Volume.from_name("huggingface-cache", create_if_missing=True)
vllm_cache = modal.Volume.from_name("vllm-cache", create_if_missing=True)
app = modal.App("muse-glimmer-private")


SNAPSHOT = os.environ.get("GLIMMER_SNAPSHOT", "1") != "0"  # read at deploy time
URL = f"http://localhost:{PORT}"


def _post(path):
    import urllib.request
    urllib.request.urlopen(urllib.request.Request(URL + path, b"", {"Authorization": f"Bearer {os.environ['VLLM_API_KEY']}"}),
                           timeout=5 * MINUTES).read()


def _wait_ready(proc):
    import time
    import urllib.request
    while True:
        if proc.poll() is not None:
            raise RuntimeError(f"vllm exited with {proc.returncode}")
        try:
            urllib.request.urlopen(URL + "/health", timeout=5)
            return
        except OSError:
            time.sleep(2)


@app.cls(image=image, gpu=GPU, scaledown_window=10 * MINUTES, timeout=30 * MINUTES, min_containers=MIN_CONTAINERS,
         volumes={"/root/.cache/huggingface": hf_cache, "/root/.cache/vllm": vllm_cache},
         secrets=[modal.Secret.from_name("muse-private-key")],
         enable_memory_snapshot=SNAPSHOT, experimental_options={"enable_gpu_snapshot": SNAPSHOT})
@modal.concurrent(max_inputs=8)
class Glimmer:
    @modal.enter(snap=True)
    def start(self):
        # VLLM_API_KEY comes from the secret; vLLM then rejects any /v1 request without that bearer token.
        # Tool calls and json_schema output are what the Finance step sends (workflow.py).
        # Glimmer thinks in a `to=self` channel and calls tools in XML, not JSON; without the two muse_glimmer
        # parsers its reasoning leaks into the answer. --generation-config auto takes the sampling Meta
        # recommends (greedy decoding is discouraged). vLLM 0.21 predates the model and wrote gibberish.
        # --enable-sleep-mode lets the state be snapshotted with the weights offloaded to CPU.
        self.proc = subprocess.Popen([
            "vllm", "serve", MODEL, "--served-model-name", MODEL, "--host", "0.0.0.0", "--port", str(PORT),
            "--max-model-len", "8192", "--max-num-seqs", "8", "--gpu-memory-utilization", "0.92",
            "--enable-auto-tool-choice", "--tool-call-parser", PARSER, "--reasoning-parser", PARSER,
            "--generation-config", "auto", "--enable-sleep-mode",
            # With a reasoning parser vLLM waits for the end of reasoning before it applies json_schema, and
            # Glimmer never signals it, so the schema was ignored. This applies it from the first token.
            "--structured-outputs-config.enable_in_reasoning", "true"])
        _wait_ready(self.proc)
        _post("/sleep?level=1")

    @modal.enter(snap=False)
    def wake(self):
        _post("/wake_up")
        _wait_ready(self.proc)

    @modal.web_server(port=PORT, startup_timeout=15 * MINUTES)
    def serve(self):
        pass

    @modal.exit()
    def stop(self):
        self.proc.terminate()


@app.local_entrypoint()
def check():
    """Cold-start check: waits for the server, then asks one question through the same API the app uses."""
    import json
    import time
    import urllib.error
    import urllib.request
    url = modal.Cls.from_name("muse-glimmer-private", "Glimmer")().serve.get_web_url()
    key = os.environ.get("VLLM_API_KEY")
    if not key:
        raise SystemExit("Set VLLM_API_KEY in this shell to the same value as the secret, then rerun.")
    body = json.dumps({"model": MODEL, "max_tokens": 400,
                       "messages": [{"role": "user", "content": "Reply with the single word: ready"}]}).encode()
    request = urllib.request.Request(url + "/v1/chat/completions", body,
                                     {"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    start = time.time()
    while True:
        try:
            with urllib.request.urlopen(request, timeout=20 * MINUTES) as reply:
                answer = json.load(reply)["choices"][0]["message"]["content"]
            break
        except urllib.error.HTTPError as e:
            # Modal answers 303 "See Other" while the container starts; urllib gives up after 10 of them, so ask again.
            if e.code != 303 or time.time() - start > 20 * MINUTES:
                raise
    print(f"{int(time.time() - start)} s to first answer: {(answer or '(no text: reasoning used the tokens)').strip()!r}")
