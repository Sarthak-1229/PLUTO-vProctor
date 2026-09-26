"""PLUTO vProctor — standalone interview-practice server.

Serves the interview UI (ui/) and the JSON API mounted under /interview. The
only server-side extra beyond that router is /speak: a thin, optional
text-to-speech endpoint used to read a question aloud in the browser. It is
best-effort and degrades to silence when a TTS backend isn't available.

All heavy ML stays CPU-bound or in-browser (see CLAUDE.md / core/config.py):
Tier-2 grading uses local Ollama, STT uses CPU faster-whisper as a fallback to
the browser's Web Speech API, and TTS uses edge-tts. Nothing here loads a GPU
model.

Run:  python -m uvicorn app:app --host 127.0.0.1 --port 8080
"""
import base64
import logging

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("vproctor")

app = FastAPI(title="PLUTO vProctor", version="1.0.0")

# ---------------------------------------------------------------------------
# Interview API.
# MUST be included BEFORE the "/" StaticFiles mount below — the static mount is
# a catch-all and would otherwise shadow every /interview/* route.
# ---------------------------------------------------------------------------
from core.interview.router import router as interview_router  # noqa: E402
app.include_router(interview_router)


# ---------------------------------------------------------------------------
# Optional question-replay TTS.
# ---------------------------------------------------------------------------
def _default_voice() -> str:
    try:
        from core import config
        return getattr(config, "TTS_VOICE", "en-US-AriaNeural")
    except Exception:
        return "en-US-AriaNeural"


class SpeakRequest(BaseModel):
    text: str
    voice: str | None = None


@app.post("/speak")
async def speak(req: SpeakRequest):
    """Synthesize `text` to an MP3 data-URI the browser can play.

    Best-effort: any failure (edge-tts absent, offline, empty text) returns an
    empty ``audio_uri`` so the UI just stays silent — never an HTTP error.
    """
    text = (req.text or "").strip()
    if not text:
        return {"audio_uri": ""}
    voice = req.voice or _default_voice()
    try:
        import edge_tts
        audio = bytearray()
        async for chunk in edge_tts.Communicate(text, voice).stream():
            if chunk.get("type") == "audio":
                audio.extend(chunk["data"])
        if not audio:
            return {"audio_uri": ""}
        uri = "data:audio/mpeg;base64," + base64.b64encode(bytes(audio)).decode("ascii")
        return {"audio_uri": uri}
    except Exception as exc:  # pragma: no cover - optional path
        log.warning("TTS unavailable (%s); returning silent response", exc)
        return {"audio_uri": "", "error": "tts_unavailable"}


# ---------------------------------------------------------------------------
# Root -> interview UI, then the static mount (registered last).
# ---------------------------------------------------------------------------
@app.get("/")
def root():
    return RedirectResponse(url="/interview.html")


app.mount("/", StaticFiles(directory="ui", html=True), name="ui")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8080, reload=False)
