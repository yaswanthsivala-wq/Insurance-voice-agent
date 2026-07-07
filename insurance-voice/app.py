"""
AI Insurance Voice Agent — Flask backend.

Two endpoints, both do the same pipeline:
    audio -> Groq Whisper (transcribe) -> Groq Llama (summarize + classify) -> JSON

    POST /transcribe   mic recordings from the browser (webm)
    POST /upload       uploaded audio files (wav/mp3/m4a/webm/...)
"""

import os
import uuid
import tempfile

from dotenv import load_dotenv

# Load variables from a local .env file (GROQ_API_KEY, etc.) before anything
# reads them. On hosts like Render you set env vars in the dashboard instead;
# load_dotenv() is a no-op there when no .env file exists.
load_dotenv()

from flask import Flask, request, jsonify, render_template

from groq_stt import transcribe_audio
from groq_agent import analyze_transcript
import store

app = Flask(__name__)

# Reject anything over 25 MB before it touches disk (Groq's audio limit ballpark).
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024

# Create the intakes table on startup (safe to call repeatedly).
store.init_db()

ALLOWED_SUFFIXES = {
    "audio/webm": ".webm",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "audio/ogg": ".ogg",
}


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/health")
def health():
    """Cheap liveness check for the deploy platform."""
    return jsonify({
        "status": "ok",
        "groq_key_set": bool(os.getenv("GROQ_API_KEY")),
        "storage": store.backend_name(),
    })


@app.route("/health/storage")
def health_storage():
    """Diagnostic: which backend is active, is it reachable, and what's the
    exact error if not. Open this in a browser to debug storage issues."""
    info = {
        "backend": store.backend_name(),
        "supabase_url_set": bool(os.getenv("SUPABASE_URL")),
        "supabase_key_set": bool(os.getenv("SUPABASE_KEY")),
    }
    try:
        rows = store.get_all()          # real read round-trip
        info["reachable"] = True
        info["row_count"] = len(rows)
    except Exception as exc:
        info["reachable"] = False
        info["error"] = f"{type(exc).__name__}: {exc}"
    return jsonify(info)


def _process(file_storage, default_suffix, source):
    """Shared pipeline: save temp file -> transcribe -> analyze -> persist -> clean up."""
    suffix = ALLOWED_SUFFIXES.get(file_storage.mimetype, default_suffix)
    temp_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}{suffix}")
    file_storage.save(temp_path)

    try:
        transcript, detected_language = transcribe_audio(temp_path)
        print("📝 USER:", transcript or "(empty)")

        result = analyze_transcript(transcript, detected_language)
        print("🏷️  TYPE:", result["type"], "| LANG:", result["language"])

        # Persist the intake. If storage fails, still return the result so the
        # user never loses a transcription — it just won't appear in history.
        try:
            saved = store.save_intake(
                type_=result["type"],
                summary=result["summary"],
                transcript=transcript,
                language=result["language"],
                source=source,
            )
        except Exception as exc:
            print("⚠️  storage failed (returning result anyway):", exc)
            saved = {
                "transcript": transcript,
                "summary": result["summary"],
                "type": result["type"],
                "language": result["language"],
            }
        return saved
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass


@app.route("/transcribe", methods=["POST"])
def transcribe():
    if "audio" not in request.files:
        return jsonify({"error": "No audio received"}), 400
    try:
        return jsonify(_process(request.files["audio"], ".webm", source="mic"))
    except Exception as exc:
        print("❌ /transcribe error:", exc)
        return jsonify({"error": str(exc)}), 500


@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    try:
        return jsonify(_process(request.files["file"], ".wav", source="upload"))
    except Exception as exc:
        print("❌ /upload error:", exc)
        return jsonify({"error": str(exc)}), 500


@app.route("/history", methods=["GET"])
def history():
    """All recorded intakes, newest first — used by the History view and to
    rebuild the dashboard after a page refresh."""
    return jsonify({"intakes": store.get_all()})


@app.route("/history", methods=["DELETE"])
def clear_history():
    store.clear_all()
    return jsonify({"status": "cleared"})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    # Debug (auto-reload + interactive debugger) is handy locally but should be
    # off in any shared setting. Defaults on for local dev; Render runs via
    # gunicorn, which never calls app.run(), so this has no effect in production.
    debug = os.getenv("FLASK_DEBUG", "true").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
