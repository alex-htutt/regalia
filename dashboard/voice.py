"""Speech-to-text for the voice agent.

The browser records a short clip (MediaRecorder → webm/opus) and POSTs it to
`/api/voice/transcribe`; this module turns it into text. Two engines, tried in
order:

  local   faster-whisper on the CPU — free, offline, nothing leaves the machine.
          Lazily imported and the model loaded once per process (the first clip
          pays a one-time download/load; later clips take well under a second
          on `base.en`).
  openai  the OpenAI transcription endpoint, only when faster-whisper isn't
          installed and an OpenAI key is configured. Same key/base as the
          `openai` chat tier.

Speech *output* is not here: the page speaks replies with the browser's own
speechSynthesis (Windows voices inside WebView2), so no audio comes back.

Wake word: in hands-free mode the page transcribes every speech burst it hears
and only acts on ones that start with "Regalia". `wake_split()` does that match
fuzzily, because Whisper spells an unfamiliar proper noun several ways
("Regalia", "Ragalia", "Re-galia").

stdlib + config only at import time; faster-whisper is imported on first use.
"""

from __future__ import annotations

import difflib
import io
import json
import re
import threading
import urllib.error
import urllib.request
import uuid

import config

WAKE_WORD = "regalia"
DEFAULT_MODEL = "base.en"
# A clip is a few seconds of opus; 10 MB is minutes of audio. Anything bigger is
# a mistake (or abuse), not a voice command.
MAX_AUDIO_BYTES = 10 * 1024 * 1024
# Whisper reports, per segment, how likely it is that nothing was said. Above
# this, the "text" is usually a hallucination on room noise ("Thank you.").
_NO_SPEECH_MAX = 0.6

_model = None
_model_name = ""
_model_lock = threading.Lock()


class VoiceError(Exception):
    """A UI-safe transcription failure; `status` is the HTTP code to return."""

    def __init__(self, message: str, status: int = 500):
        super().__init__(message)
        self.message = message
        self.status = status


def _whisper_model_name() -> str:
    return config.value("whisper_model", "REGALIA_WHISPER_MODEL", DEFAULT_MODEL)


def _local_available() -> bool:
    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        return False
    return True


def _openai_key() -> str:
    return config.secret("openai_api_key", "OPENAI_API_KEY")


def status() -> dict:
    """Which engine a transcription would use right now (no model load)."""
    if _local_available():
        return {"ready": True, "engine": "local", "model": _whisper_model_name()}
    if _openai_key():
        return {"ready": True, "engine": "openai", "model": "whisper-1"}
    return {
        "ready": False, "engine": None, "model": None,
        "error": "Install faster-whisper (pip install faster-whisper) or add an OpenAI key.",
    }


def _load_local():
    """The process-wide WhisperModel, (re)loaded when the configured name changes."""
    global _model, _model_name
    name = _whisper_model_name()
    with _model_lock:
        if _model is None or _model_name != name:
            from faster_whisper import WhisperModel
            # int8 on CPU: ~4x smaller and faster than float32 with no audible
            # accuracy loss for short commands, and it runs on any machine.
            _model = WhisperModel(name, device="cpu", compute_type="int8")
            _model_name = name
        return _model


def warm() -> None:
    """Load the local model ahead of the first clip (no-op once loaded)."""
    _load_local()


def _wav_samples(audio: bytes):
    """WAV bytes → mono float32 samples at 16 kHz (what Whisper consumes).

    Decoded here with the stdlib `wave` module rather than handed to
    faster-whisper as a file: its decoder goes through PyAV, and faster-whisper
    1.2.1 passes an argument (`metadata_errors`) that PyAV 15+ removed, so every
    clip failed. The page always uploads 16 kHz 16-bit mono WAV; anything else
    PCM is downmixed/resampled, and non-WAV input is a clear 415.
    """
    import wave

    import numpy as np  # a ctranslate2 dependency, so present whenever faster-whisper is

    try:
        with wave.open(io.BytesIO(audio)) as w:
            rate, channels, width = w.getframerate(), w.getnchannels(), w.getsampwidth()
            frames = w.readframes(w.getnframes())
    except (wave.Error, EOFError) as e:
        raise VoiceError("The local engine needs WAV audio.", 415) from e
    if width != 2:
        raise VoiceError("The local engine needs 16-bit WAV audio.", 415)
    samples = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    if rate != 16000 and samples.size:
        n = int(samples.size * 16000 / rate)
        samples = np.interp(np.linspace(0, samples.size - 1, n),
                            np.arange(samples.size), samples).astype(np.float32)
    return samples


def _transcribe_local(audio: bytes) -> str:
    samples = _wav_samples(audio)
    model = _load_local()
    english_only = _model_name.endswith(".en")
    segments, _info = model.transcribe(
        samples,
        language="en" if english_only else None,
        beam_size=1,
        vad_filter=True,
        # Deliberately no `hotwords`/`initial_prompt` of "Regalia": both are fed
        # to the decoder as *preceding* text, so Whisper treats a leading
        # "Regalia," as already said and drops it — deleting the wake word.
        # wake_split()'s fuzzy match covers the spelling drift instead.
        condition_on_previous_text=False,
    )
    return " ".join(
        s.text.strip() for s in segments if s.no_speech_prob < _NO_SPEECH_MAX
    ).strip()


def _multipart(fields: dict, file_field: str, filename: str, data: bytes,
               content_type: str) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    out = io.BytesIO()
    for k, v in fields.items():
        out.write(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
    out.write(
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"{file_field}\"; "
        f"filename=\"{filename}\"\r\nContent-Type: {content_type}\r\n\r\n".encode()
    )
    out.write(data)
    out.write(f"\r\n--{boundary}--\r\n".encode())
    return out.getvalue(), f"multipart/form-data; boundary={boundary}"


def _transcribe_openai(audio: bytes, mime: str) -> str:
    base = config.value("openai_base", "OPENAI_BASE", "https://api.openai.com/v1").rstrip("/")
    ext = "webm" if "webm" in mime else "ogg" if "ogg" in mime else "wav" if "wav" in mime else "mp4"
    body, ctype = _multipart(
        {"model": "whisper-1", "language": "en"},
        "file", f"clip.{ext}", audio, mime or "application/octet-stream",
    )
    req = urllib.request.Request(
        f"{base}/audio/transcriptions", data=body, method="POST",
        headers={"Authorization": f"Bearer {_openai_key()}", "Content-Type": ctype},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise VoiceError(f"OpenAI transcription failed (HTTP {e.code}).", 502) from e
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise VoiceError("Couldn't reach the OpenAI transcription endpoint.", 502) from e
    return str(payload.get("text") or "").strip()


def transcribe(audio: bytes, mime: str = "audio/webm") -> dict:
    """Clip bytes → {"text", "engine"}. Raises VoiceError on any failure."""
    if not audio:
        raise VoiceError("No audio received.", 400)
    if len(audio) > MAX_AUDIO_BYTES:
        raise VoiceError("That clip is too long.", 413)
    st = status()
    if not st["ready"]:
        raise VoiceError(st["error"], 503)
    if st["engine"] == "local":
        try:
            text = _transcribe_local(audio)
        except VoiceError:
            raise
        except Exception as e:  # decode errors, model download failures, …
            raise VoiceError(f"Local transcription failed: {e}", 500) from e
    else:
        text = _transcribe_openai(audio, mime)
    return {"text": text, "engine": st["engine"]}


_WORD = re.compile(r"[a-z0-9']+")


def _is_wake(token: str) -> bool:
    return difflib.SequenceMatcher(None, token, WAKE_WORD).ratio() >= 0.75


def wake_split(text: str) -> tuple[bool, str]:
    """(heard the wake word?, the command after it).

    The wake word must be among the first three words ("Regalia, …",
    "Hey Regalia …", "OK so Regalia …"), alone or split in two ("Re galia").
    The command keeps the original casing/punctuation of everything after it.
    """
    words = [(m.group(), m.start(), m.end()) for m in _WORD.finditer(text.lower())]
    for i in range(min(3, len(words))):
        end = None
        if _is_wake(words[i][0]):
            end = words[i][2]
        elif i + 1 < len(words) and _is_wake(words[i][0] + words[i + 1][0]):
            end = words[i + 1][2]
        if end is not None:
            return True, text[end:].lstrip(" ,.!?;:-").strip()
    return False, ""
