# SalesPilot AI

An autonomous AI sales voice-agent platform: a business creates an organization,
configures its own AI sales agent, manages leads (built-in CRM + CSV import), and
tests real voice conversations in the browser — speech-to-text, an LLM conversation
driven by the agent's stored configuration, and spoken replies — with every call,
transcript and dashboard number computed from real stored records. Nothing is
mocked: no seeded demo leads, no fake KPIs, no simulated calls.

This package is the **deployable version** of SalesPilot AI — the full
Phases 1–7 product, packaged to run at your own public URL so the browser
microphone and LiveKit work in a normal top-level browser context.

**Providers:** the product runs on **LiveKit + Deepgram + Groq** (HubSpot
optional). It does **not** require an OpenAI account: the LLM is Groq by
default (`LLM_PROVIDER=groq`), speech is Deepgram (STT + Aura TTS), and
knowledge-base embeddings default to a clearly labeled local lexical model.
OpenAI remains an optional alternative LLM (`LLM_PROVIDER=openai`) and, in
that mode only, an optional embeddings upgrade.

## Architecture

```
frontend/dist/   Hand-written static SPA (no build step): index.html + styles.css + app.js
                 Talks to the API with fetch(), JWT in localStorage.
backend/         FastAPI app. REST API under /api/v1, JWT auth, organization_id
                 tenant scoping on every query. Serves frontend/dist at / when present.
voice-agent/     LiveKit Agents worker (separate process) for real-time rooms:
                 Deepgram STT -> Groq LLM -> Deepgram Aura TTS, Silero VAD.
PostgreSQL       Application data (DATABASE_URL). SQLite works for a local spin-up.
```

Voice works two ways:

- **Turn-based mode (default, works everywhere):** the browser records a turn with
  the microphone, uploads it to the backend, which transcribes with Deepgram,
  generates the reply with the configured LLM (Groq by default) from the agent's
  stored configuration, synthesizes speech with Deepgram Aura and returns it for
  playback. Both sides are saved as the call transcript.
- **LiveKit live mode:** the backend mints a LiveKit room token; the browser joins
  the room directly (WebRTC) and the `voice-agent/` worker joins as the agent.
  This needs the worker running (see below) and a browser that can reach LiveKit.

## Run it locally

### Option A — Docker Compose (recommended)

```bash
cp .env.example .env        # fill in JWT_SECRET and any provider keys you have
docker compose up --build
```

Open http://localhost:8000, register the first account (this creates your
organization), and start adding leads.

### Option B — Manual

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL="sqlite:///./salespilot.db"   # or a Postgres URL
export JWT_SECRET="a-long-random-string"
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open http://localhost:8000 — the API and the frontend are served by the same process.

## Deploy to Render (step by step)

1. Create a free account at https://render.com and push this repo to GitHub
   (or GitLab) — `git init && git add . && git commit -m "SalesPilot AI"` then
   create a remote repo and push. **Check `.env` is not committed** (it's in
   `.gitignore`).
2. In Render: **New → Blueprint**, connect your Git provider and select the repo.
   Render reads `render.yaml`: it will create one Docker web service
   (`salespilot-ai`, root `Dockerfile`) and one free Postgres database, and wire
   `DATABASE_URL` automatically. `JWT_SECRET` is generated for you.
3. When prompted, fill the secret env vars: `LIVEKIT_URL`, `LIVEKIT_API_KEY`,
   `LIVEKIT_API_SECRET`, `DEEPGRAM_API_KEY`, `GROQ_API_KEY` (a free key from
   console.groq.com works) and optionally `HUBSPOT_ACCESS_TOKEN`. (You can deploy
   without them — leads, agents and the dashboard work; voice, analysis and
   integrations will honestly show "Not connected" until the keys are set under
   **Service → Environment**.)
4. Click **Apply** and wait for the build/deploy to finish.
5. Open the service URL (e.g. `https://salespilot-ai.onrender.com`), register
   your account, and test voice from **Live Voice Testing** — in this top-level
   browser context the microphone permission prompt works normally.
6. Note: the free web service sleeps when idle, so the first request after a
   break can take ~30–60s.

## Deploy to Railway (alternative)

1. Create an account at https://railway.app and a **New Project → Deploy from
   GitHub repo**, selecting this repo (Railway builds the root `Dockerfile`).
2. Add a **PostgreSQL** service to the project.
3. In the app service → **Variables**, set `DATABASE_URL` to the Postgres
   service's connection URL (use the `${{Postgres.DATABASE_URL}}` reference),
   `JWT_SECRET` to a long random string, and the provider keys you have
   (`LIVEKIT_*`, `DEEPGRAM_API_KEY`, `GROQ_API_KEY`, optional `HUBSPOT_ACCESS_TOKEN`).
4. In **Settings → Networking**, generate a public domain.
5. Open the domain, register, and use the app exactly as on Render.

## Running the LiveKit voice-agent worker (optional)

Only needed for **LiveKit live mode** (and later, phone calls). The turn-based
mode does not need it.

```bash
cd voice-agent
pip install -r requirements.txt
# env: LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET, DEEPGRAM_API_KEY,
#      GROQ_API_KEY, and BACKEND_URL pointing at your deployed backend
python agent.py download-files
python agent.py start
```

Host it as a background worker on Render/Railway or any always-on VM. The worker
registers with LiveKit under the agent name `salespilot-agent`; the backend's
room dispatch must use that same name for the agent to join rooms.

## Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `JWT_SECRET` | Yes | Signs login tokens — long random string |
| `POSTGRES_PASSWORD` | Compose only | Password for the bundled Postgres service |
| `LIVEKIT_URL` | For LiveKit mode | LiveKit Cloud project URL (`wss://…`) |
| `LIVEKIT_API_KEY` | For LiveKit mode | Mints room tokens server-side |
| `LIVEKIT_API_SECRET` | For LiveKit mode | Signs those tokens |
| `DEEPGRAM_API_KEY` | For voice | Speech-to-text + Aura text-to-speech |
| `GROQ_API_KEY` | For LLM features | LLM for voice replies, call analysis and knowledge answers (free key at console.groq.com) |
| `LLM_PROVIDER` | No | `groq` (default) or `openai` |
| `GROQ_MODEL` | No | Groq model override (default `llama-3.3-70b-versatile`) |
| `HUBSPOT_ACCESS_TOKEN` | No | HubSpot CRM sync (Phase 5); unset = "Not connected" |
| `OPENAI_API_KEY` | No | **Optional** — only used when `LLM_PROVIDER=openai`; in that mode it also enables OpenAI embeddings |
| `BACKEND_URL` | Worker only | Where `voice-agent/agent.py` fetches agent config |

## Phase status

- **Phase 1 — Foundation:** auth + organizations + roles, lead CRM,
  CSV import with duplicate detection, agent configuration, dashboard from real data.
- **Phase 2 — Real-Time Voice:** turn-based voice testing (Deepgram STT,
  Groq conversation, Deepgram Aura speech), LiveKit direct mode + agent worker,
  call sessions, live transcripts, call history.
- **Phase 3 — Conversational Intelligence:** post-call analysis (summary,
  requirements, pain points, objections), BANT extraction with verbatim quotes,
  lead scoring computed in code (Budget 25 / Authority 20 / Need 35 / Timeline 20;
  Hot 80–100 / Warm 50–79 / Cold 0–49), sentiment + purchase intent, cross-call
  lead memory, and a context snapshot loaded into a returning lead's next session.
- **Phase 4 — RAG Knowledge Base:** PDF/DOCX/TXT/CSV upload + pasted text,
  chunking, embeddings (labeled local lexical vectors by default; OpenAI
  embeddings only when `LLM_PROVIDER=openai`), similarity retrieval with an
  honest no-content result, and a grounded ask endpoint that answers only from
  retrieved chunks with citations — or refuses.
- **Phase 5 — Autonomous Actions:** in-app appointments with conflict detection
  and .ics export (Google Calendar is reached via .ics, not a live write),
  HubSpot sync (search → create/update + note, real errors logged), human
  escalation + follow-up tasks, Do-Not-Contact session blocking, tool-call audit.
- **Phase 6 — Intelligence & Analytics:** full analytics from database rows only
  (lead/call/insight/appointment/task/KB metrics, per-agent performance),
  date-range filter, CSV exports with formula-injection guarding.
- **Phase 7 — Hardening:** Owner/Administrator role gates on credential, member,
  export and wipe operations; workspace JSON export (no secrets); confirmed
  workspace wipe (operational data only, per-table counts); compliance &
  launch-readiness guidance page (TRAI DLT, consent/DNC, AI disclosure, DPDP).

## Security notes

- API keys exist **only** in host environment variables — never in this repo,
  never in the frontend, never returned by the API (integration status is masked).
- Every API query is scoped by `organization_id` server-side; the frontend never
  filters another tenant's data because it never receives it.
- Passwords are hashed server-side; login tokens are signed with `JWT_SECRET`.
- Rotate any key that has ever been pasted into a chat or ticket.
