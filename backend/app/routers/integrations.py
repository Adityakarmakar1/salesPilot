from fastapi import APIRouter, Depends

from .. import llm
from ..config import settings
from ..security import CurrentUser, get_current_user

router = APIRouter(prefix="/integrations", tags=["integrations"])

NOT_CONNECTED = "Not connected — credentials required"


@router.get("/status")
def integration_status(current: CurrentUser = Depends(get_current_user)):
    livekit_connected = bool(settings.LIVEKIT_URL and settings.LIVEKIT_API_KEY and settings.LIVEKIT_API_SECRET)
    deepgram_connected = bool(settings.DEEPGRAM_API_KEY)
    llm_info = llm.llm_status()
    hubspot_connected = bool(settings.HUBSPOT_ACCESS_TOKEN)
    calendar_note = "Appointments are managed in SalesPilot and exported as .ics files"
    return {
        "livekit": {
            "connected": livekit_connected,
            "detail": settings.LIVEKIT_URL if livekit_connected else NOT_CONNECTED,
            "url": settings.LIVEKIT_URL,
            "env": ["LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET"],
        },
        "deepgram": {
            "connected": deepgram_connected,
            "detail": "Speech-to-text (Nova-2)" if deepgram_connected else NOT_CONNECTED,
            "env": ["DEEPGRAM_API_KEY"],
        },
        "llm": {
            "connected": llm_info["connected"],
            "provider": llm_info["provider"],
            "model": llm_info["model"],
            "detail": f"{'Groq' if llm_info['provider'] == 'groq' else 'OpenAI'} \u00b7 {llm_info['model']}" if llm_info["connected"] else NOT_CONNECTED,
            "env": ["GROQ_API_KEY"] if llm_info["provider"] == "groq" else ["OPENAI_API_KEY"],
        },
        "tts": {
            "provider": "Deepgram Aura",
            "connected": deepgram_connected,
            "detail": "Voice replies via Deepgram Speak (aura-2-thalia-en)" if deepgram_connected else NOT_CONNECTED,
            "env": ["DEEPGRAM_API_KEY"],
        },
        "google_calendar": {"connected": False, "mode": "ics", "note": calendar_note, "detail": calendar_note, "env": []},
        "googleCalendar": {"connected": False, "mode": "ics", "note": calendar_note},
        "hubspot": {
            "connected": hubspot_connected,
            "detail": "CRM sync — contacts and notes via HUBSPOT_ACCESS_TOKEN" if hubspot_connected else NOT_CONNECTED,
            "env": ["HUBSPOT_ACCESS_TOKEN"],
        },
        "telephony": {"connected": False, "detail": NOT_CONNECTED, "env": ["SIP_PROVIDER_API_KEY"]},
    }
