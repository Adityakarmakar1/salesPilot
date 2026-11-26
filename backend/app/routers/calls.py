import time
import uuid
from datetime import datetime, timezone

import jwt as pyjwt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import Agent, Call, CallInsight, Lead, LeadMemory, LeadScore, Task, TranscriptMessage
from ..schemas import CallDetailOut, CallEndRequest, CallOut, CallStartRequest, CallStartResponse, TranscriptMessageOut
from ..security import CurrentUser, get_current_user

router = APIRouter(prefix="/calls", tags=["calls"])


def _build_context_snapshot(db: Session, org_id: str, lead: Lead) -> dict | None:
    """What the agent should already know about this lead from prior calls.

    Returns None when there is no prior insight or memory for the lead.
    """
    latest_insight = (
        db.query(CallInsight)
        .filter(CallInsight.lead_id == lead.id, CallInsight.org_id == org_id)
        .order_by(CallInsight.created_at.desc())
        .first()
    )
    has_memory = (
        db.query(LeadMemory)
        .filter(LeadMemory.lead_id == lead.id, LeadMemory.org_id == org_id)
        .first()
    )
    if latest_insight is None and has_memory is None:
        return None

    latest_score = (
        db.query(LeadScore)
        .filter(LeadScore.lead_id == lead.id, LeadScore.org_id == org_id)
        .order_by(LeadScore.created_at.desc())
        .first()
    )
    known_bant: dict = {}
    if latest_score is not None:
        if lead.budget:
            known_bant["budget"] = lead.budget
        if lead.decision_authority:
            known_bant["authority"] = lead.decision_authority
        if lead.requirements:
            known_bant["need"] = lead.requirements
        if lead.purchase_timeline:
            known_bant["timeline"] = lead.purchase_timeline

    open_followups = (
        db.query(Task)
        .filter(Task.lead_id == lead.id, Task.org_id == org_id, Task.kind == "followup", Task.status == "Open")
        .order_by(Task.created_at.desc())
        .all()
    )
    return {
        "last_summary": latest_insight.summary if latest_insight else "",
        "known_bant": known_bant,
        "open_followups": [task.reason for task in open_followups if task.reason],
    }


def mint_livekit_token(room: str, identity: str) -> str:
    now = int(time.time())
    payload = {
        "iss": settings.LIVEKIT_API_KEY,
        "sub": identity,
        "iat": now,
        "nbf": now,
        "exp": now + 60 * 60 * 6,
        "video": {
            "roomJoin": True,
            "room": room,
            "canPublish": True,
            "canSubscribe": True,
            "canPublishData": True,
        },
    }
    return pyjwt.encode(payload, settings.LIVEKIT_API_SECRET, algorithm="HS256")


def _get_call_or_404(db: Session, org_id: str, call_id: str) -> Call:
    call = db.get(Call, call_id)
    if call is None or call.org_id != org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Call not found")
    return call


@router.post("/start", response_model=CallStartResponse, status_code=status.HTTP_201_CREATED)
def start_call(body: CallStartRequest, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    agent = db.get(Agent, body.agent_id)
    if agent is None or agent.org_id != current.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent not found")
    lead = None
    if body.lead_id:
        lead = db.get(Lead, body.lead_id)
        if lead is None or lead.org_id != current.org_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Lead not found")
        if lead.do_not_contact:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Lead is marked Do Not Contact — voice sessions are blocked for this lead.",
            )
    context_snapshot = _build_context_snapshot(db, current.org_id, lead) if lead is not None else None
    room = f"salespilot-{uuid.uuid4().hex[:8]}"
    call = Call(
        org_id=current.org_id,
        agent_id=body.agent_id,
        lead_id=body.lead_id,
        room_name=room,
        language=body.language,
        status="In Progress",
        context_snapshot=context_snapshot,
    )
    db.add(call)
    db.commit()
    db.refresh(call)
    response = CallStartResponse(call=CallOut.model_validate(call))
    if body.mode == "livekit":
        if not (settings.LIVEKIT_URL and settings.LIVEKIT_API_KEY and settings.LIVEKIT_API_SECRET):
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "LiveKit mode requires LIVEKIT_URL, LIVEKIT_API_KEY and LIVEKIT_API_SECRET to be set",
            )
        response.livekit_url = settings.LIVEKIT_URL
        response.token = mint_livekit_token(room, identity=f"user-{current.user.id}")
        response.room = room
    return response


@router.post("/{call_id}/end", response_model=CallOut)
def end_call(
    call_id: str, body: CallEndRequest, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)
):
    call = _get_call_or_404(db, current.org_id, call_id)
    ended = datetime.now(timezone.utc)
    call.ended_at = ended
    started = call.started_at
    if started is not None and started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    call.duration_seconds = max(0, int((ended - started).total_seconds())) if started else 0
    call.outcome = body.outcome
    call.status = "Completed" if body.outcome == "Completed" else "Ended"
    db.commit()
    db.refresh(call)
    return call


@router.get("", response_model=list[CallOut])
def list_calls(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Call).filter(Call.org_id == current.org_id).order_by(Call.created_at.desc()).all()


@router.get("/{call_id}", response_model=CallDetailOut)
def get_call(call_id: str, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    call = _get_call_or_404(db, current.org_id, call_id)
    messages = (
        db.query(TranscriptMessage)
        .filter(TranscriptMessage.call_id == call.id)
        .order_by(TranscriptMessage.created_at.asc())
        .all()
    )
    detail = CallDetailOut.model_validate(call)
    detail.transcript = [TranscriptMessageOut.model_validate(m) for m in messages]
    return detail
