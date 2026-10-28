"""A spoken job note: the recording is checked by code, sent once, dropped, and only its text comes back."""
import base64
import io
import wave

import pytest

import app as app_module
import muse
import voice

ROLES = [{"id": "md", "title": "MD", "reports_to": None, "headcount": 1},
         {"id": "sales", "title": "Sales", "reports_to": "md", "headcount": 2}]


def wav_url(seconds=1.0, rate=16000, channels=1, width=2):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(width)
        w.setframerate(rate)
        w.writeframes(b"\x00" * int(seconds * rate) * channels * width)
    return "data:audio/wav;base64," + base64.b64encode(buf.getvalue()).decode()


@pytest.fixture
def client():
    return app_module.create_app().test_client()


@pytest.fixture
def token(client):
    h = {"X-Sandbox": client.post("/api/sandbox").json["sandbox"]}
    client.post("/api/company", json={"company": "Acme", "roles": ROLES, "size": 20}, headers=h)
    client.post("/api/assistants", json={"role_id": "sales"}, headers=h)
    return client.post("/api/invites", json={"role_id": "sales"}, headers=h).json["token"]


def counts(client):
    db = client.application.config["STORE"]
    return {t: db.db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in db.table_names()}


@pytest.mark.parametrize("bad", [
    None, "not a data url", "data:audio/mpeg;base64,AAAA", "data:audio/wav;base64,!!!",
    "data:audio/wav;base64," + base64.b64encode(b"RIFF0000WAVEnope").decode(),
    wav_url(rate=44100), wav_url(channels=2), wav_url(width=1), wav_url(seconds=voice.MAX_SECONDS + 1),
    wav_url(seconds=0)],
    ids=["none", "text", "mp3", "not-base64", "broken-wav", "44k", "stereo", "8bit", "too-long", "empty"])
def test_only_short_mono_16_bit_recordings_reach_the_model(bad):
    with pytest.raises(voice.BadAudio):
        voice.check_audio(bad)


def test_a_good_recording_is_accepted_at_both_rates():
    assert voice.check_audio(wav_url(rate=16000)) and voice.check_audio(wav_url(rate=24000))


def test_the_recording_is_sent_once_and_only_text_comes_back_and_nothing_is_stored(client, token, monkeypatch):
    sent = []
    monkeypatch.setattr(muse, "transcribe", lambda wav, **k: sent.append(wav) or {
        "demo_mode": False, "demo_reason": None, "text": " Ten pallets Hanoi to Haiphong. "})
    before = counts(client)
    r = client.post("/api/transcribe", json={"token": token, "audio": wav_url()})
    assert r.status_code == 200 and r.json == {"text": "Ten pallets Hanoi to Haiphong.", "demo_mode": False,
                                               "demo_reason": None}
    assert len(sent) == 1 and sent[0][:4] == b"RIFF"
    assert counts(client) == before


def test_a_bad_recording_is_refused_before_any_model_call(client, token, monkeypatch):
    called = []
    monkeypatch.setattr(muse, "transcribe", lambda *a, **k: called.append(1))
    r = client.post("/api/transcribe", json={"token": token, "audio": wav_url(channels=2)})
    assert r.status_code == 400 and r.json["error"] == "bad_audio" and not called


def test_without_a_model_the_answer_is_labelled_and_empty(client, token):
    r = client.post("/api/transcribe", json={"token": token, "audio": wav_url()})
    assert r.json["demo_mode"] is True and r.json["text"] == ""


def test_the_ceiling_stops_the_call_and_says_so(client, token, monkeypatch):
    monkeypatch.setattr(muse, "transcribe", lambda *a, **k: pytest.fail("must not be called"))
    db = client.application.config["STORE"]
    monkeypatch.setattr(db, "spend_model_call", lambda sandbox: "Daily limit reached")
    r = client.post("/api/transcribe", json={"token": token, "audio": wav_url()})
    assert r.json["demo_mode"] is True and r.json["demo_reason"] == "Daily limit reached"


def test_the_cost_is_billed_by_audio_length(monkeypatch):
    sent = []

    class Reply:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b'{"transcript": "hi", "audioDurationMs": 3600000}'

    monkeypatch.delenv("FAKE_AI", raising=False)
    monkeypatch.setenv("META_API_KEY", "test")
    monkeypatch.setattr(muse.urllib.request, "urlopen", lambda req, timeout: sent.append(req) or Reply())
    spent = []
    monkeypatch.setattr(muse, "cost_listener", spent.append)
    out = muse.transcribe(b"RIFFdata")
    assert out["text"] == "hi" and out["demo_mode"] is False and spent == [muse.TRANSCRIBE_USD_PER_HOUR]
    assert sent[0].full_url == muse.ASR_URL and b"RIFFdata" in sent[0].data and b'"muse-voice-transcribe-1.0"' in sent[0].data
    assert sent[0].get_header("Authorization") == "Bearer test"
