"""Speech to text for a spoken job note: the recording is checked here, sent to the model once and dropped.

The transcript is only text for the message box. The browser then masks it and the person reads it before the
existing "fill the form from a message" step runs, so nothing in this file stores, logs or approves anything.
"""
import base64
import binascii
import io
import wave

import muse

MAX_SECONDS = 60
RATES = (16000, 24000)  # what the speech endpoint accepts


class BadAudio(ValueError):
    pass


def check_audio(data_url):
    """Return the WAV bytes if they are a mono 16-bit recording of at most 60 s at 16 or 24 kHz."""
    if not isinstance(data_url, str) or not data_url.startswith("data:audio/wav;base64,"):
        raise BadAudio("Send the recording as a WAV file.")
    encoded = data_url.split(",", 1)[1]
    if len(encoded) > MAX_SECONDS * max(RATES) * 2 * 4 // 3 + 400:
        raise BadAudio(f"The recording is longer than {MAX_SECONDS} seconds.")
    try:
        raw = base64.b64decode(encoded, validate=True)
        with wave.open(io.BytesIO(raw)) as w:
            channels, width, rate, frames = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
    except (binascii.Error, ValueError, wave.Error, EOFError):
        raise BadAudio("The recording could not be read.")
    if channels != 1 or width != 2 or rate not in RATES:
        raise BadAudio("The recording must be mono, 16-bit, at 16 or 24 kHz.")
    if frames / rate > MAX_SECONDS:
        raise BadAudio(f"The recording is longer than {MAX_SECONDS} seconds.")
    if frames == 0:
        raise BadAudio("The recording is empty.")
    return raw


def transcribe(data_url, blocked):
    """Returns {text, demo_mode, demo_reason}. The model never gets the recording when the daily ceiling is reached."""
    raw = check_audio(data_url)
    reason = blocked()
    if reason:
        return {"text": "", "demo_mode": True, "demo_reason": reason}
    call = muse.transcribe(raw)
    if call["demo_mode"]:
        return {"text": "", "demo_mode": True, "demo_reason": call["demo_reason"]}
    return {"text": call["text"].strip(), "demo_mode": False, "demo_reason": None}
