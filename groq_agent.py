"""
Understanding layer via Groq (Llama 3.3 70B).

Replaces the old IBM WatsonX / Granite integration. Takes a raw transcript in
any language and returns a small, strict JSON object the dashboard can use:

    {
      "summary":  "one-line summary in English",
      "type":     "Auto" | "Health" | "Life" | "Property" | "Review",
      "language": "detected language name"
    }

Groq's JSON mode guarantees valid JSON, which removes the fragile string
parsing the old code relied on.

Env vars:
    GROQ_API_KEY  - required
    LLM_MODEL     - optional, defaults to llama-3.3-70b-versatile
"""

import os
import json
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")

VALID_TYPES = {"Auto", "Health", "Life", "Property"}

SYSTEM_PROMPT = (
    "You are an insurance intake assistant. A customer or agent has just spoken, "
    "possibly in a language other than English (English, Telugu, Hindi, Spanish, "
    "and others). Read the transcript, understand the intent, and file it.\n\n"
    "Return ONLY a JSON object with exactly these keys:\n"
    '  "summary":  a single clear sentence in English describing what the caller needs\n'
    '  "type":     exactly one of: "Auto", "Health", "Life", "Property". '
    'If the transcript is empty, noise, or does not fit any of these, use "Review".\n'
    '  "language": the name of the language the caller spoke, in English '
    '(e.g. "English", "Hindi", "Spanish")\n\n'
    "Do not add commentary, markdown, or any keys other than these three."
)


def _get_client():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Add it to your .env file (see .env.example)."
        )
    return Groq(api_key=api_key)


def analyze_transcript(transcript, detected_language=None):
    """
    Summarize + classify a transcript. Always returns a dict with
    summary / type / language keys, even on error, so the caller never crashes.
    """
    transcript = (transcript or "").strip()
    if not transcript:
        return {
            "summary": "No speech detected.",
            "type": "Review",
            "language": detected_language or "unknown",
        }

    client = _get_client()

    user_content = f"Transcript:\n{transcript}"
    if detected_language:
        user_content += f"\n\n(Speech-to-text detected the language as: {detected_language})"

    try:
        completion = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=300,
        )
        raw = completion.choices[0].message.content
        data = json.loads(raw)
    except Exception as exc:  # network error, bad JSON, etc.
        print("❌ Groq analyze error:", exc)
        return {
            "summary": transcript[:160],
            "type": "Review",
            "language": detected_language or "unknown",
        }

    summary = str(data.get("summary", "")).strip() or transcript[:160]
    ins_type = str(data.get("type", "")).strip().title()
    if ins_type not in VALID_TYPES:
        ins_type = "Review"
    language = str(data.get("language", "")).strip() or detected_language or "unknown"

    return {"summary": summary, "type": ins_type, "language": language}
