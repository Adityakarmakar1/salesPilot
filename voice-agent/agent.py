"""
SalesPilot AI — LiveKit voice-agent worker.

This is the real-time agent that joins LiveKit rooms (browser "LiveKit live"
mode in the frontend, and later SIP phone calls) and speaks as the AI sales
representative: Deepgram STT -> Groq LLM -> Deepgram Aura TTS, with Silero
VAD and turn detection, so callers can interrupt naturally.

It is a SEPARATE process from the web service. Run it on any host that can
reach LiveKit Cloud (a Render background worker, Railway service, or a VM):

    pip install -r requirements.txt
    python agent.py download-files   # one-time: VAD model files
    python agent.py start

Required environment:
    LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET   (LiveKit Cloud project)
    DEEPGRAM_API_KEY                                   (STT + TTS)
    GROQ_API_KEY                                       (LLM, via Groq's OpenAI-compatible endpoint)
Optional:
    BACKEND_URL          Base URL of the SalesPilot backend (agent config)
    WORKER_API_TOKEN     Bearer token used when fetching agent config
    AGENT_NAME / AGENT_COMPANY / AGENT_PERSONALITY / AGENT_OBJECTIVES
                         Fallbacks used when no backend config is available

Room/job metadata: the backend starts each call with metadata like
{"agent_id": 3, "call_id": 12, "language": "English"}; when present, the
worker's behaviour (name, personality, objectives, qualification questions)
is loaded from the backend's agent configuration for that agent_id.
"""

import json
import logging
import os

import httpx
from dotenv import load_dotenv
from livekit import agents
from livekit.agents import Agent, AgentSession, JobContext, RoomInputOptions, WorkerOptions
from livekit.plugins import deepgram, openai, silero

load_dotenv()
logger = logging.getLogger("salespilot-voice-agent")

LANGUAGE_CODES = {"English": "en", "Hindi": "hi", "Hinglish": "hi"}


def _fallback_config() -> dict:
    return {
        "name": os.getenv("AGENT_NAME", "Aarav"),
        "company_name": os.getenv("AGENT_COMPANY", "our company"),
        "personality": os.getenv("AGENT_PERSONALITY", "Consultative"),
        "sales_objectives": os.getenv(
            "AGENT_OBJECTIVES",
            "Understand the customer's needs, answer questions honestly, and "
            "offer a product demo when there is genuine interest.",
        ),
        "qualification_questions": os.getenv("AGENT_QUALIFICATION_QUESTIONS", ""),
        "language": os.getenv("AGENT_LANGUAGE", "English"),
    }


async def fetch_agent_config(agent_id, language_hint: str | None) -> dict:
    """Load agent configuration from the backend API; fall back to env config."""
    config = _fallback_config()
    backend = os.getenv("BACKEND_URL", "").rstrip("/")
    if agent_id and backend:
        headers = {}
        if os.getenv("WORKER_API_TOKEN"):
            headers["Authorization"] = f"Bearer {os.environ['WORKER_API_TOKEN']}"
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(f"{backend}/api/v1/agents/{agent_id}", headers=headers)
                resp.raise_for_status()
                data = resp.json()
            for key in (
                "name", "company_name", "personality", "sales_objectives",
                "qualification_questions", "target_audience", "escalation_conditions",
            ):
                if data.get(key):
                    config[key] = data[key]
            logger.info("Loaded agent config from backend for agent_id=%s", agent_id)
        except Exception as exc:  # backend unreachable / unauthorized — keep env config
            logger.warning("Could not fetch agent config (%s); using env fallback", exc)
    if language_hint:
        config["language"] = language_hint
    return config


def build_instructions(config: dict) -> str:
    questions = ""
    if config.get("qualification_questions"):
        questions = (
            "\nOver the conversation, naturally learn the answers to these "
            f"qualification questions (do not interrogate):\n{config['qualification_questions']}"
        )
    return f"""You are {config['name']}, an AI sales representative for {config['company_name']}.
Personality: {config['personality']}. You are speaking out loud on a live call —
keep every reply short, natural and conversational, one or two sentences at a time.

Objectives: {config['sales_objectives']}{questions}

Rules:
- Disclose that you are an AI assistant if asked, and always if the call starts
  without an introduction.
- Never invent prices, features or policies. If you do not know, say so and
  offer to have a human follow up.
- Respect a request to stop calling immediately and politely end the call.
- Speak in the caller's language: this call starts in {config.get('language', 'English')};
  if the caller switches between English, Hindi and Hinglish, follow them.
"""


def _groq_llm():
    """Build the Groq LLM via the OpenAI-compatible plugin.

    Fails clearly at startup when GROQ_API_KEY is missing — there is no
    silent fallback to OpenAI.
    """
    if not os.environ.get("GROQ_API_KEY"):
        raise RuntimeError(
            "GROQ_API_KEY is not set — the voice agent requires a Groq API key "
            "for its LLM (set GROQ_API_KEY, or see .env.example)."
        )
    return openai.LLM(
        model=os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
        base_url="https://api.groq.com/openai/v1",
        api_key=os.environ["GROQ_API_KEY"],
    )


class SalesAgent(Agent):
    def __init__(self, config: dict) -> None:
        language = config.get("language", "English")
        lang_code = LANGUAGE_CODES.get(language, "en")
        super().__init__(
            instructions=build_instructions(config),
            vad=silero.VAD.load(),
            stt=deepgram.STT(model="nova-3", language=lang_code),
            # Groq is reached through the livekit-plugins-openai plugin
            # because Groq exposes an OpenAI-compatible API; the product
            # does not depend on the OpenAI API itself.
            llm=_groq_llm(),
            tts=deepgram.TTS(model="aura-2-thalia-en"),
        )
        self._config = config

    async def on_enter(self) -> None:
        name = self._config.get("name", "your sales representative")
        company = self._config.get("company_name", "our company")
        await self.session.generate_reply(
            instructions=(
                f"Greet the caller warmly as {name} from {company}, say you are "
                "an AI sales assistant, and ask how you can help today. One short sentence or two."
            )
        )


async def entrypoint(ctx: JobContext) -> None:
    if not os.environ.get("GROQ_API_KEY"):
        logger.error("GROQ_API_KEY is not set — voice agent cannot start its LLM; set GROQ_API_KEY and restart.")
        raise RuntimeError("GROQ_API_KEY is not set")
    metadata = {}
    try:
        metadata = json.loads(ctx.job.metadata or "{}")
    except (ValueError, TypeError):
        metadata = {}
    config = await fetch_agent_config(metadata.get("agent_id"), metadata.get("language"))

    session = AgentSession()
    await session.start(
        agent=SalesAgent(config),
        room=ctx.room,
        room_input_options=RoomInputOptions(close_on_disconnect=True),
    )


if __name__ == "__main__":
    if not os.environ.get("GROQ_API_KEY"):
        print("ERROR: GROQ_API_KEY is not set — the voice agent requires GROQ_API_KEY for its LLM. Set it and restart; there is no OpenAI fallback.")
        raise SystemExit(1)
    agents.cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, agent_name="salespilot-agent"))
