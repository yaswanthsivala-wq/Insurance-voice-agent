"""
Speech-to-text via Groq (Whisper Large v3).

Replaces the old IBM Watson Speech-to-Text integration. Groq runs Whisper on
its LPU hardware, so a full-length call transcribes in a couple of seconds, it
auto-detects the spoken language (99+ languages, including Telugu/Hindi/Spanish),
and the free tier needs no credit card.

Env vars:
    GROQ_API_KEY   - required
    STT_MODEL      - optional, defaults to whisper-large-v3-turbo
                     (use "whisper-large-v3" for best non-English accuracy)
"""

import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

# whisper-large-v3-turbo: fastest + cheapest, great multilingual.
# whisper-large-v3:       slightly higher accuracy on non-English audio.
STT_MODEL = os.getenv("STT_MODEL", "whisper-large-v3-turbo")

_client = None


def _get_client():
    """Create the Groq client lazily so the app can import without a key set."""
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Add it to your .env file "
                "(see .env.example)."
            )
        _client = Groq(api_key=api_key)
    return _client


def transcribe_audio(file_path, content_type=None):
    """
    Transcribe an audio file and return (text, detected_language).

    content_type is accepted for backwards compatibility with the old Watson
    signature but is ignored — Groq infers the format from the file itself.
    """
    client = _get_client()

    with open(file_path, "rb") as audio_file:
        result = client.audio.transcriptions.create(
            file=(os.path.basename(file_path), audio_file.read()),
            model=STT_MODEL,
            # verbose_json gives us the detected language alongside the text.
            response_format="verbose_json",
            temperature=0.0,
        )

    text = (getattr(result, "text", "") or "").strip()
    language = getattr(result, "language", None) or "unknown"
    return text, language
