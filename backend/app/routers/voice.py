import base64

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from .. import llm
from ..config import settings
from ..db import get_db
from ..models import Agent, Call, Lead, TranscriptMessage
from ..security import CurrentUser, get_current_user

router = APIRouter(prefix="/calls", tags=["voice"])

DEEPGRAM_LISTEN_URL = "https://api.deepgram.com/v1/listen"
DEEPGRAM_SPEAK_URL = "https://api.deepgram.com/v1/speak"
TTS_MODEL = "aura-2-thalia-en"

LANGUAGE_MAP = {"English": "en", "Hindi": "hi", "Hinglish": "hi"}


def _missing_key_response(names: list[str]) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"detail": f"Missing required environment variable(s): {', '.join(names)}"},
    )


def _build_system_prompt(agent: Agent, lead: Lead | None) -> str:
    parts = [
        f"You are {agent.name}, an AI sales agent for {agent.company_name or 'the company'}.",
        f"Personality: {agent.personality}. Be natural, helpful and concise; you are speaking aloud, so keep replies to 1-3 short sentences.",
        "You must identify yourself as an AI assistant if asked. Never invent prices, features or policies you were not given.",
    ]
    if agent.description:
        parts.append(f"Agent description: {agent.description}")
    if agent.sales_objectives:
        parts.append(f"Sales objectives: {agent.sales_objectives}")
    if agent.target_audience:
        parts.append(f"Target audience: {agent.target_audience}")
    if agent.qualification_questions:
        parts.append(
            "Qualification questions to work through naturally over the conversation (do not ask them all at once): "
            f"{agent.qualification_questions}"
        )
    if agent.escalation_conditions:
        parts.append(f"Escalation conditions: {agent.escalation_conditions}")
    if agent.followup_behaviour:
        parts.append(f"Follow-up behaviour: {agent.followup_behaviour}")
    if lead is not None:
        parts.append(
            f"You are speaking with {lead.full_name}"
            + (f" from {lead.company}" if lead.company else "")
            + (f". Known requirements: {lead.requirements}" if lead.requirements else "")
            + (f". Known pain points: {lead.pain_points}" if lead.pain_points else "")
            + "."
        )
    return "\n".join(parts)


@router.post("/{call_id}/turn")
async def voice_turn(
    call_id: str,
    audio: UploadFile = File(...),
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    call = db.get(Call, call_id)
    if call is None or call.org_id != current.org_id:
        return JSONResponse(status_code=404, content={"detail": "Call not found"})

    missing = []
    if not settings.DEEPGRAM_API_KEY:
        missing.append("DEEPGRAM_API_KEY")
    llm_info = llm.llm_status()
    if not llm_info["connected"]:
        missing.append("OPENAI_API_KEY" if llm_info["provider"] == "openai" else "GROQ_API_KEY")
    if missing:
        return _missing_key_response(missing)

    agent = db.get(Agent, call.agent_id)
    if agent is None:
        return JSONResponse(status_code=404, content={"detail": "Agent for this call no longer exists"})
    lead = db.get(Lead, call.lead_id) if call.lead_id else None

    audio_bytes = await audio.read()
    if not audio_bytes:
        return JSONResponse(status_code=422, content={"detail": "Empty audio upload"})
    content_type = audio.content_type or "audio/webm"
    language_code = LANGUAGE_MAP.get(call.language, "en")

    dg_headers = {"Authorization": f"Token {settings.DEEPGRAM_API_KEY}"}

    # 1) Transcribe with Deepgram (prerecorded)
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                DEEPGRAM_LISTEN_URL,
                params={"model": "nova-2", "smart_format": "true", "language": language_code},
                headers={**dg_headers, "Content-Type": content_type},
                content=audio_bytes,
            )
    except httpx.HTTPError as exc:
        return JSONResponse(status_code=502, content={"detail": f"Deepgram transcription request failed: {exc}"})
    if resp.status_code != 200:
        return JSONResponse(
            status_code=502,
            content={"detail": f"Deepgram transcription failed (HTTP {resp.status_code}): {resp.text[:500]}"},
        )
    try:
        user_text = (
            resp.json()["results"]["channels"][0]["alternatives"][0].get("transcript") or ""
        ).strip()
    except (KeyError, IndexError, ValueError):
        return JSONResponse(status_code=502, content={"detail": "Deepgram returned an unexpected transcription response"})
    if not user_text:
        return JSONResponse(
            status_code=200,
            content={
                "user_text": "",
                "reply_text": "",
                "audio_base64": "",
                "audio_content_type": "audio/mpeg",
                "audio_error": "No speech was detected in the recording — nothing was saved.",
            },
        )
    db.add(TranscriptMessage(call_id=call.id, org_id=call.org_id, speaker="user", text=user_text))
    db.commit()

    # 2) Generate the agent reply with the configured LLM provider
    history = (
        db.query(TranscriptMessage)
        .filter(TranscriptMessage.call_id == call.id)
        .order_by(TranscriptMessage.created_at.asc())
        .all()
    )
    messages = [{"role": "system", "content": _build_system_prompt(agent, lead)}]
    for msg in history:
        messages.append({"role": "user" if msg.speaker == "user" else "assistant", "content": msg.text})
    try:
        reply_text = llm.chat_completion(messages).strip()
    except HTTPException as exc:
        return JSONResponse(
            status_code=200,
            content={
                "user_text": user_text,
                "reply_text": "",
                "audio_base64": "",
                "audio_content_type": "audio/mpeg",
                "audio_error": f"LLM reply generation failed: {exc.detail}",
            },
        )
    except Exception as exc:
        return JSONResponse(
            status_code=200,
            content={
                "user_text": user_text,
                "reply_text": "",
                "audio_base64": "",
                "audio_content_type": "audio/mpeg",
                "audio_error": f"LLM reply generation failed: {exc}",
            },
        )
    if not reply_text:
        return JSONResponse(
            status_code=200,
            content={
                "user_text": user_text,
                "reply_text": "",
                "audio_base64": "",
                "audio_content_type": "audio/mpeg",
                "audio_error": "LLM returned an empty reply — nothing was fabricated.",
            },
        )
    db.add(TranscriptMessage(call_id=call.id, org_id=call.org_id, speaker="agent", text=reply_text))
    db.commit()

    # 3) Speak the reply with Deepgram Aura
    audio_b64 = ""
    audio_error = ""
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                DEEPGRAM_SPEAK_URL,
                params={"model": TTS_MODEL},
                headers={**dg_headers, "Content-Type": "application/json"},
                json={"text": reply_text},
            )
        if resp.status_code == 200 and resp.content:
            audio_b64 = base64.b64encode(resp.content).decode()
        else:
            audio_error = f"Deepgram Speak failed (HTTP {resp.status_code}): {resp.text[:500]}"
    except httpx.HTTPError as exc:
        audio_error = f"Deepgram Speak request failed: {exc}"

    return {
        "user_text": user_text,
        "reply_text": reply_text,
        "audio_base64": audio_b64,
        "audio_content_type": "audio/mpeg",
        "audio_error": audio_error,
    }
