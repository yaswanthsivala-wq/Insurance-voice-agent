# AI Insurance Voice Agent

A voice-intake tool for insurance teams. A customer or agent speaks — in **any
language** — and the app transcribes the audio, understands it, writes a
one-line English summary, and files it into the right line of business
(**Auto / Health / Life / Property**) on a live dashboard.

Built to run on **100% free tiers** with no credit card.

## Stack

| Layer            | Service                                   | Notes |
|------------------|-------------------------------------------|-------|
| Speech-to-text   | **Groq — Whisper Large v3 (turbo)**       | 99+ languages, auto-detected |
| Understanding    | **Groq — Llama 3.3 70B**                  | summary + classification, JSON mode |
| Backend          | Flask + gunicorn                          | two endpoints |
| Frontend         | Vanilla HTML / CSS / JS                    | live mic waveform, no build step |
| Hosting          | Render / Railway (free tier)              | `render.yaml` included |

> Replaces the previous IBM Watson STT + WatsonX/Granite integration. One Groq
> API key now covers both the transcription and the understanding step.

## Run locally

```bash
git clone <your-repo-url>
cd <repo>

python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # then paste your key into .env
python app.py                      # http://localhost:5000
```

Get a free Groq key at **https://console.groq.com** (no credit card).

## Environment variables

| Variable        | Required | Default                   |
|-----------------|----------|---------------------------|
| `GROQ_API_KEY`  | yes      | —                         |
| `SUPABASE_URL`  | no       | — (falls back to SQLite)  |
| `SUPABASE_KEY`  | no       | — (secret key `sb_secret_…`) |
| `STT_MODEL`     | no       | `whisper-large-v3-turbo`  |
| `LLM_MODEL`     | no       | `llama-3.3-70b-versatile` |
| `DATABASE_PATH` | no       | `intakes.db`              |

Set **both** `SUPABASE_URL` and `SUPABASE_KEY` to store intakes permanently in
Supabase; leave them blank to use a local SQLite file.

## Deploy to Render (free)

1. Push this repo to GitHub.
2. On Render: **New → Web Service → connect the repo.** `render.yaml` sets the
   build/start commands automatically.
3. Add `GROQ_API_KEY` under **Environment** (never commit it).
4. Deploy. Your public URL is live.

## Endpoints

| Method | Path          | Purpose                                  |
|--------|---------------|------------------------------------------|
| GET    | `/`           | The dashboard UI                         |
| GET    | `/health`     | Liveness check (`{"status":"ok"}`)       |
| POST   | `/transcribe` | Mic recording (webm) → transcript + JSON |
| POST   | `/upload`     | Uploaded audio file → transcript + JSON  |
| GET    | `/history`    | All recorded intakes, newest first       |
| DELETE | `/history`    | Clear all recorded intakes               |

Every completed intake is saved to a SQLite database (`intakes.db`). The
dashboard rebuilds from it on refresh, and the **History** button shows the full
record — type, summary, full transcript, language, and time — for each one.

Both audio endpoints return:

```json
{
  "transcript": "raw transcript in the spoken language",
  "summary":    "one-line English summary",
  "type":       "Auto | Health | Life | Property | Review",
  "language":   "detected language"
}
```

## Permanent storage with Supabase

Storage is automatic: with `SUPABASE_URL` + `SUPABASE_KEY` set, intakes go to
Supabase (permanent); without them, they go to a local SQLite file. Check which
backend is live at `/health` (`"storage": "supabase"` or `"sqlite"`).

One-time setup:

1. Create a free project at supabase.com.
2. In the project's **SQL Editor**, run:

   ```sql
   create table if not exists intakes (
       id         bigint generated always as identity primary key,
       created_at timestamptz not null default now(),
       type       text not null,
       summary    text not null,
       transcript text,
       language   text,
       source     text
   );
   ```

3. From the **Connect** dialog (or **Settings → API Keys**), copy the Project
   URL and a **secret** key (`sb_secret_…`). Set them as `SUPABASE_URL` and
   `SUPABASE_KEY`. The secret key is server-side only — never expose it in the
   browser or commit it.

## Notes

- Max upload size is 25 MB.
- The mic records continuously until you press **Stop** — the on-screen timer
  shows it's still listening. Classification runs on the complete conversation.
- If storage is briefly unavailable, the transcription is still returned; only
  the history record is skipped.
