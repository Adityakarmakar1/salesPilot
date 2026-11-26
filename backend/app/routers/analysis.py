import json
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import hubspot as hubspot_service
from .. import llm
from ..config import settings
from ..db import get_db
from ..models import (
    Call,
    CallInsight,
    Lead,
    LeadMemory,
    LeadScore,
    Organization,
    Task,
    ToolCall,
    TranscriptMessage,
)
from ..schemas import CallInsightOut, LeadIntelligenceOut, SentimentHistoryItem
from ..security import CurrentUser, get_current_user

router = APIRouter(prefix="/calls", tags=["analysis"])
leads_router = APIRouter(prefix="/leads", tags=["analysis"])

BANT_WEIGHTS = {"budget": 25, "authority": 20, "need": 35, "timeline": 20}
HUMAN_REQUEST_RE = re.compile(r"\b(human|real person|manager|agent|someone real)\b", re.IGNORECASE)

SYSTEM_PROMPT = """You are a sales-call analyst. You are given the transcript of a sales call between an AI sales agent (speaker "agent") and a customer (speaker "user").

Extract ONLY what was actually said in the transcript. Never invent, assume or infer facts that were not stated.

Rules:
- For each BANT item (budget, authority, need, timeline): "value" is a short summary of what the customer said about it, or null when it was not discussed at all. "quote" is the customer's VERBATIM words supporting it, or null. "level" is "established" only when the customer stated it explicitly, "partial" when it was implied or vague, and "unknown" when it was not discussed. "confidence" is a number between 0 and 1.
- sentiment_overall is the customer's overall sentiment: one of "Positive", "Neutral", "Negative".
- sentiment_progression is a list of stages in order, each {"stage": "opening"|"middle"|"closing", "sentiment": "Positive"|"Neutral"|"Negative"}.
- purchase_intent is how likely the customer is to buy, judged separately from sentiment: one of "High", "Medium", "Low", "None". A polite, happy customer can still have low purchase intent.
- engagement is one of "High", "Medium", "Low".
- pain_points, product_interests and objections are lists of short strings, each grounded in something the customer actually said. Use empty lists when none were mentioned.
- requirements is a plain-text summary of what the customer said they need (empty string if not discussed).
- appointment_status is a plain-text note on whether an appointment was discussed/booked (empty string if not discussed).
- next_action is the follow-up the agent promised or the obvious agreed next step (empty string if none).
- summary is a 2-4 sentence factual summary of the call.
- Write your output in English, but keep every "quote" in the customer's original words and script, exactly as spoken.

Respond with a single JSON object with exactly these keys:
{"summary": str, "requirements": str, "pain_points": [str], "product_interests": [str], "objections": [str], "appointment_status": str, "next_action": str, "bant": {"budget": {"value": str|null, "level": "established"|"partial"|"unknown", "confidence": number, "quote": str|null}, "authority": {...}, "need": {...}, "timeline": {...}}, "sentiment_overall": str, "sentiment_progression": [{"stage": str, "sentiment": str}], "purchase_intent": str, "engagement": str}"""


def _get_call_or_404(db: Session, org_id: str, call_id: str) -> Call:
    call = db.get(Call, call_id)
    if call is None or call.org_id != org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Call not found")
    return call


def _get_lead_or_404(db: Session, org_id: str, lead_id: str) -> Lead:
    lead = db.get(Lead, lead_id)
    if lead is None or lead.org_id != org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lead not found")
    return lead


def _parse_json_object(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        data = json.loads(cleaned)
    except ValueError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end <= start:
            raise
        data = json.loads(cleaned[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("Model did not return a JSON object")
    return data


def _str_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _normalize_bant(raw) -> dict:
    bant = {}
    raw = raw if isinstance(raw, dict) else {}
    for key in BANT_WEIGHTS:
        item = raw.get(key) if isinstance(raw.get(key), dict) else {}
        level = str(item.get("level") or "unknown").lower()
        if level not in ("established", "partial", "unknown"):
            level = "unknown"
        try:
            confidence = float(item.get("confidence") or 0)
        except (TypeError, ValueError):
            confidence = 0.0
        value = item.get("value")
        quote = item.get("quote")
        bant[key] = {
            "value": str(value) if value not in (None, "") else None,
            "level": level,
            "confidence": max(0.0, min(1.0, confidence)),
            "quote": str(quote) if quote not in (None, "") else None,
        }
    return bant


def _score_bant(bant: dict) -> tuple[dict, int, str]:
    points = {}
    total_float = 0.0
    for key, weight in BANT_WEIGHTS.items():
        level = bant.get(key, {}).get("level", "unknown")
        earned = float(weight) if level == "established" else (weight / 2.0 if level == "partial" else 0.0)
        points[key] = earned
        total_float += earned
    total = int(round(total_float))
    category = "Hot" if total >= 80 else ("Warm" if total >= 50 else "Cold")
    return points, total, category


def _call_llm_analysis(transcript_text: str, language: str) -> dict:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Call language: {language}\n\nTranscript:\n{transcript_text}",
        },
    ]
    # llm.chat_completion raises HTTPException as-is (503 not-connected or the
    # provider error verbatim); this runs before any persistence in
    # analyze_call, so a failure stores nothing.
    content = llm.chat_completion(messages, json_mode=True)
    try:
        return _parse_json_object(content)
    except ValueError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"LLM returned an unparseable analysis: {exc}")


def _add_memory(db: Session, org_id: str, lead_id: str, call_id: str, category: str, content: str):
    content = (content or "").strip()
    if content:
        db.add(LeadMemory(org_id=org_id, lead_id=lead_id, call_id=call_id, category=category, content=content))


def _add_task(db: Session, org_id: str, lead_id: str | None, call_id: str, kind: str, reason: str, due_at=None) -> Task:
    task = Task(org_id=org_id, lead_id=lead_id, call_id=call_id, kind=kind, reason=reason, due_at=due_at, status="Open")
    db.add(task)
    db.flush()
    db.add(
        ToolCall(
            org_id=org_id,
            lead_id=lead_id,
            call_id=call_id,
            action=f"{kind}_created",
            detail=reason,
        )
    )
    return task


@router.post("/{call_id}/analyze", response_model=CallInsightOut)
def analyze_call(call_id: str, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    call = _get_call_or_404(db, current.org_id, call_id)
    messages = (
        db.query(TranscriptMessage)
        .filter(TranscriptMessage.call_id == call.id)
        .order_by(TranscriptMessage.created_at.asc())
        .all()
    )
    if not messages:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No transcript captured — nothing to analyze.")

    transcript_text = "\n".join(f"{m.speaker}: {m.text}" for m in messages)
    data = _call_llm_analysis(transcript_text, call.language)

    bant = _normalize_bant(data.get("bant"))
    points, total, category = _score_bant(bant)
    summary = str(data.get("summary") or "")
    requirements = str(data.get("requirements") or "")
    pain_points = _str_list(data.get("pain_points"))
    product_interests = _str_list(data.get("product_interests"))
    objections = _str_list(data.get("objections"))
    appointment_status = str(data.get("appointment_status") or "")
    next_action = str(data.get("next_action") or "")
    sentiment_overall = str(data.get("sentiment_overall") or "")
    progression = data.get("sentiment_progression")
    sentiment_progression = progression if isinstance(progression, list) else []
    purchase_intent = str(data.get("purchase_intent") or "")
    engagement = str(data.get("engagement") or "")

    lead = db.get(Lead, call.lead_id) if call.lead_id else None
    if lead is not None and lead.org_id != current.org_id:
        lead = None

    # Re-analysis replaces the previous insight and its auto-created tasks/tool calls.
    existing = db.query(CallInsight).filter(CallInsight.call_id == call.id).first()
    if existing is not None:
        db.delete(existing)
    db.query(Task).filter(Task.call_id == call.id).delete(synchronize_session=False)
    db.query(ToolCall).filter(ToolCall.call_id == call.id).delete(synchronize_session=False)
    db.flush()

    insight = CallInsight(
        org_id=current.org_id,
        call_id=call.id,
        lead_id=lead.id if lead else None,
        summary=summary,
        requirements=requirements,
        pain_points=pain_points,
        product_interests=product_interests,
        objections=objections,
        appointment_status=appointment_status,
        next_action=next_action,
        bant=bant,
        score=total,
        category=category,
        sentiment_overall=sentiment_overall,
        sentiment_progression=sentiment_progression,
        purchase_intent=purchase_intent,
        engagement=engagement,
    )
    db.add(insight)

    if lead is not None:
        db.add(
            LeadScore(
                org_id=current.org_id,
                lead_id=lead.id,
                call_id=call.id,
                budget_points=points["budget"],
                authority_points=points["authority"],
                need_points=points["need"],
                timeline_points=points["timeline"],
                total=total,
                category=category,
            )
        )

        # Update the lead from what was actually extracted.
        lead.lead_score = total
        if bant["budget"]["value"]:
            lead.budget = bant["budget"]["value"]
        if bant["authority"]["value"]:
            lead.decision_authority = bant["authority"]["value"]
        if bant["timeline"]["value"]:
            lead.purchase_timeline = bant["timeline"]["value"]
        if requirements:
            lead.requirements = requirements
        if pain_points:
            lead.pain_points = "; ".join(pain_points)
        if lead.lead_status in ("New", "Contacted"):
            lead.lead_status = category

        # Lead memory.
        if requirements:
            _add_memory(db, current.org_id, lead.id, call.id, "requirement", requirements)
        for objection in objections:
            _add_memory(db, current.org_id, lead.id, call.id, "objection", objection)
        for interest in product_interests:
            _add_memory(db, current.org_id, lead.id, call.id, "interest", interest)
        if next_action:
            _add_memory(db, current.org_id, lead.id, call.id, "followup_promised", next_action)
        if appointment_status:
            _add_memory(db, current.org_id, lead.id, call.id, "appointment", appointment_status)

        # Escalation rules (Phase 5 hooks).
        if sentiment_overall == "Negative":
            _add_task(
                db, current.org_id, lead.id, call.id, "escalation",
                f"Escalation: overall sentiment on call {call.id} was Negative.",
            )
        if purchase_intent == "High" and objections:
            _add_task(
                db, current.org_id, lead.id, call.id, "escalation",
                f"Escalation: purchase intent is High but objections were raised: {'; '.join(objections)}",
            )
        keyword_hit = next((m.text for m in messages if m.speaker == "user" and HUMAN_REQUEST_RE.search(m.text)), None)
        if keyword_hit:
            _add_task(
                db, current.org_id, lead.id, call.id, "escalation",
                f"Escalation (keyword rule): customer asked for a human/manager — \"{keyword_hit}\"",
            )

        # Follow-up promised / agreed.
        if next_action:
            _add_task(
                db, current.org_id, lead.id, call.id, "followup",
                next_action, due_at=datetime.now(timezone.utc) + timedelta(days=2),
            )

    db.commit()
    db.refresh(insight)

    # Auto HubSpot sync after analysis — failures are logged, never raised.
    if lead is not None:
        org = db.get(Organization, current.org_id)
        if org is not None and org.hubspot_auto_sync and (lead.email or lead.phone) and settings.HUBSPOT_ACCESS_TOKEN:
            try:
                hubspot_service.sync_lead(db, org, lead, trigger="post-analysis")
            except Exception:
                db.rollback()

    return insight


@router.get("/{call_id}/insight", response_model=CallInsightOut)
def get_insight(call_id: str, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    call = _get_call_or_404(db, current.org_id, call_id)
    insight = db.query(CallInsight).filter(CallInsight.call_id == call.id, CallInsight.org_id == current.org_id).first()
    if insight is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This call has not been analyzed yet")
    return insight


@leads_router.get("/{lead_id}/intelligence", response_model=LeadIntelligenceOut)
def lead_intelligence(lead_id: str, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    lead = _get_lead_or_404(db, current.org_id, lead_id)
    scores = (
        db.query(LeadScore)
        .filter(LeadScore.lead_id == lead.id, LeadScore.org_id == current.org_id)
        .order_by(LeadScore.created_at.desc())
        .all()
    )
    memory = (
        db.query(LeadMemory)
        .filter(LeadMemory.lead_id == lead.id, LeadMemory.org_id == current.org_id)
        .order_by(LeadMemory.created_at.desc())
        .all()
    )
    insights = (
        db.query(CallInsight)
        .filter(CallInsight.lead_id == lead.id, CallInsight.org_id == current.org_id)
        .order_by(CallInsight.created_at.desc())
        .all()
    )
    return LeadIntelligenceOut(
        scores=scores,
        memory=memory,
        sentiment_history=[
            SentimentHistoryItem(call_id=i.call_id, overall=i.sentiment_overall, intent=i.purchase_intent, created_at=i.created_at)
            for i in insights
        ],
    )
