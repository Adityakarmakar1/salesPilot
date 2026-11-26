# SalesPilot AI — Development Progress

## This package (deployable build)

A self-hostable version of the complete SalesPilot AI product (Phases 1–7),
packaged so it can run at a public URL in a normal browser — where the
microphone and LiveKit WebRTC work as designed, instead of inside an embedded
app shell that refused both.

**Providers:** LiveKit + Deepgram + **Groq** (HubSpot optional). The product
does **not** require an OpenAI account. `LLM_PROVIDER` defaults to `groq`
(model `llama-3.3-70b-versatile`); OpenAI is an optional alternative provider
(`LLM_PROVIDER=openai`) and, only in that mode, an optional embeddings
upgrade. Speech is Deepgram only (STT + Aura TTS).

### Included and working

- **Frontend** (`frontend/dist/`): dependency-light static SPA (no build step) —
  login/register, dashboard (KPIs + SVG charts computed only from API data,
  honest zeros and empty states), leads CRM (search/filter/add/edit/delete,
  CSV import with in-browser parsing, preview and server-side duplicate/invalid
  summary), lead detail with calls, qualification card, memory timeline and
  sentiment history, AI agent configuration, Live Voice Testing (turn-based +
  LiveKit direct), call history with transcripts and the analysis panel,
  Knowledge Base, Appointments, Tasks, Analytics (with CSV exports),
  integrations status, organization profile + members/roles, data export/wipe
  controls, and a Compliance & Launch Readiness page.
- **Backend** (`backend/`, FastAPI): JWT auth, organization tenant scoping,
  leads/agents/calls APIs, CSV import endpoint, turn-based voice endpoint
  (Deepgram transcription → Groq reply from the agent's stored configuration →
  Deepgram Aura speech), LiveKit token minting, post-call analysis (structured
  extraction + BANT with verbatim quotes; score computed in code:
  Budget 25 / Authority 20 / Need 35 / Timeline 20, partial = half;
  Hot 80–100 / Warm 50–79 / Cold 0–49), lead memory + score history, session
  context snapshots, RAG knowledge base (PDF/DOCX/TXT/CSV + pasted text,
  chunking, labeled embeddings, cosine retrieval in code, grounded ask with
  citations and honest refusals), appointments with conflict detection and
  .ics export, HubSpot sync with a real sync log, escalation/follow-up tasks,
  tool-call audit trail, full analytics + CSV exports, Owner/Administrator
  role gates, workspace export/wipe. Serves the frontend at `/`.
- **Voice agent worker** (`voice-agent/agent.py`): a real LiveKit Agents worker
  (Deepgram STT, **Groq LLM** via the OpenAI-compatible endpoint, Deepgram
  Aura TTS, Silero VAD) that joins rooms as the sales agent and loads per-agent
  behaviour from the backend by room metadata. Requires `GROQ_API_KEY`; it
  refuses to start without it rather than falling back to another provider.
- **Deployment**: root `Dockerfile` (single image: backend + frontend),
  `docker-compose.yml` (Postgres + app), `render.yaml` (Render Blueprint: web
  service + free Postgres, secrets as `sync: false`), `.env.example`,
  README with local, Render and Railway instructions.

### Port record (2026-11-26)

Phases 3–7 were ported from the hosted SalesPilot app (where they were built
and verified first) into this repo: Phase 3 conversational intelligence,
Phase 4 RAG knowledge base, Phase 5 autonomous actions, Phase 6 analytics,
Phase 7 hardening. In the same pass the LLM provider was reworked per the
owner's direction: Groq is the default LLM everywhere (voice replies, call
analysis, knowledge answers, voice-agent worker), the OpenAI TTS fallback was
removed (Deepgram Aura only), and embeddings default to the labeled local
lexical model (`local-lexical-v1`, recorded per document) because Groq has no
embeddings API.

### Known limitations

- The LiveKit agent worker is a **separate process** and is not started by the
  web service or docker-compose app service; run it on a background worker/VM
  for LiveKit live mode. Turn-based voice works without it.
- Free-tier hosts sleep when idle (first request can take ~30–60s) and free
  Postgres tiers are small/time-limited — fine for evaluation, not production.
- **No LLM key, no LLM features:** without `GROQ_API_KEY` (or
  `LLM_PROVIDER=openai` + `OPENAI_API_KEY`), voice replies, call analysis and
  knowledge answers return an honest "LLM not connected" error and store
  nothing. A free Groq key is enough.
- Knowledge-base retrieval quality with the default local lexical embeddings
  is simpler than true semantic embeddings; set `LLM_PROVIDER=openai` with a
  funded OpenAI key if you want OpenAI embeddings.
- Google Calendar is **not** written to directly: appointments live in
  SalesPilot and each can be downloaded as an .ics file for calendar import.
  The integrations page states this plainly.
- HubSpot sync makes real API calls and logs real outcomes; the live success
  path can only be fully proven on a deployed copy with network access to
  api.hubapi.com (calls from the development sandbox stall).
- Aura voices are English-first; Hindi/Hinglish speech output quality is
  limited until a Hindi-capable TTS is configured.
- The backend must dispatch LiveKit rooms to the agent name `salespilot-agent`
  for the worker to join; verify this matches the backend's dispatch config.
- SQLite is the zero-config default; Postgres is used via `DATABASE_URL`
  (plain Postgres — embeddings are stored as JSON and ranked in code, so no
  pgvector extension is required).

### Next steps

1. Deploy via Render Blueprint; register the first account; set provider keys
   (`GROQ_API_KEY` instead of any OpenAI key).
2. Run the voice-agent worker and verify a LiveKit live-mode call end to end.
3. Verify the HubSpot live sync path once, on the deployed copy.
4. Before any commercial outbound phone calling in India: TRAI DLT
   registration and the compliance steps on the in-app readiness page.

## Verified locally (2026-11-26, by Muse)

Ran the backend from this repo on throwaway SQLite databases (no real
provider keys; the LLM HTTP layer was stubbed **only inside the local test
harness**, never in shipped code):

- **57/57 end-to-end checks passed** (register → agent/lead → call with a
  BANT-rich transcript → analysis → second-call context → KB → appointments →
  HubSpot no-token path → analytics → CSV exports → role gates → export/wipe):
  score 90/Hot computed in code (25+20+35+10 partial timeline), lead updated
  New→Hot then →Appointment Booked, 5 memory entries, escalations incl. the
  labeled keyword rule quoting the customer's line, follow-up task, context
  snapshot on the next call, no-transcript analysis refused, KB lexical
  fallback labeled `local-lexical-v1` with retrieval hit/miss and grounded
  ask + honest refusal, appointment overlap conflict flagged, ICS with correct
  IST→UTC conversion, analytics hand-checked (analyzed rate, avg score 90,
  KB hit rate 0.5), Sales Rep refused export/wipe with 403, wipe returned
  per-table counts and preserved agents/members.
- **Provider-error honesty:** with the stubbed LLM returning a 429
  `credit_balance_exhausted` body, analysis surfaced it verbatim and stored
  nothing. With **no** LLM key configured at all, analysis and KB ask return
  503 "LLM not connected — GROQ_API_KEY is required…" and store nothing;
  integrations status reports the LLM as Groq/not-connected and contains no
  `openai` entry.
- **Server smoke:** `uvicorn` serves the frontend at `/` (200), `/health` ok,
  unauthenticated API calls 401.
- Earlier Phase 1+2 verification (2026-11-25) with the owner's real keys:
  Deepgram transcribed a real speech clip exactly and produced real Aura
  speech; a genuine LiveKit token was minted and verified. The OpenAI legs
  failed then with `credit_balance_exhausted` — the reason this package no
  longer depends on OpenAI.

Not verified: a live Groq API call (no Groq key exists yet — get one free at
console.groq.com and set `GROQ_API_KEY`), the HubSpot live success path, a
live browser microphone/LiveKit call on a deployed URL, and Hindi/Hinglish
transcript analysis with a real transcript.
