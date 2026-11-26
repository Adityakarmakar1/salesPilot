import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    industry: Mapped[str] = mapped_column(String(255), default="")
    website: Mapped[str] = mapped_column(String(255), default="")
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")
    calling_hours: Mapped[str] = mapped_column(String(255), default="")
    hubspot_auto_sync: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class OrganizationMember(Base):
    __tablename__ = "organization_members"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(64), default="Sales Representative")


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    company_name: Mapped[str] = mapped_column(String(255), default="")
    personality: Mapped[str] = mapped_column(String(64), default="Professional")
    languages: Mapped[list] = mapped_column(JSON, default=list)
    voice_provider: Mapped[str] = mapped_column(String(64), default="Deepgram Aura")
    voice_name: Mapped[str] = mapped_column(String(128), default="aura-2-thalia-en")
    speaking_speed: Mapped[float] = mapped_column(Float, default=1.0)
    max_call_duration: Mapped[int] = mapped_column(Integer, default=600)
    calling_hours: Mapped[str] = mapped_column(String(255), default="")
    sales_objectives: Mapped[str] = mapped_column(Text, default="")
    target_audience: Mapped[str] = mapped_column(Text, default="")
    qualification_questions: Mapped[str] = mapped_column(Text, default="")
    escalation_conditions: Mapped[str] = mapped_column(Text, default="")
    followup_behaviour: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str] = mapped_column(String(255), default="")
    phone: Mapped[str] = mapped_column(String(64), default="")
    email: Mapped[str] = mapped_column(String(255), default="")
    location: Mapped[str] = mapped_column(String(255), default="")
    preferred_language: Mapped[str] = mapped_column(String(64), default="English")
    industry: Mapped[str] = mapped_column(String(255), default="")
    lead_source: Mapped[str] = mapped_column(String(128), default="")
    budget: Mapped[str] = mapped_column(String(128), default="")
    requirements: Mapped[str] = mapped_column(Text, default="")
    decision_authority: Mapped[str] = mapped_column(String(128), default="")
    purchase_timeline: Mapped[str] = mapped_column(String(128), default="")
    pain_points: Mapped[str] = mapped_column(Text, default="")
    lead_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lead_status: Mapped[str] = mapped_column(String(64), default="New")
    consent: Mapped[bool] = mapped_column(Boolean, default=False)
    do_not_contact: Mapped[bool] = mapped_column(Boolean, default=False)
    hubspot_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_interaction: Mapped[str] = mapped_column(String(64), default="")
    next_followup: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class Call(Base):
    __tablename__ = "calls"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=False)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), index=True, nullable=False)
    lead_id: Mapped[str | None] = mapped_column(ForeignKey("leads.id"), nullable=True)
    room_name: Mapped[str] = mapped_column(String(255), default="")
    language: Mapped[str] = mapped_column(String(64), default="English")
    status: Mapped[str] = mapped_column(String(64), default="In Progress")
    outcome: Mapped[str] = mapped_column(String(128), default="")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    context_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class CallInsight(Base):
    __tablename__ = "call_insights"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=False)
    call_id: Mapped[str] = mapped_column(ForeignKey("calls.id"), index=True, unique=True, nullable=False)
    lead_id: Mapped[str | None] = mapped_column(ForeignKey("leads.id"), index=True, nullable=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    requirements: Mapped[str] = mapped_column(Text, default="")
    pain_points: Mapped[list] = mapped_column(JSON, default=list)
    product_interests: Mapped[list] = mapped_column(JSON, default=list)
    objections: Mapped[list] = mapped_column(JSON, default=list)
    appointment_status: Mapped[str] = mapped_column(Text, default="")
    next_action: Mapped[str] = mapped_column(Text, default="")
    bant: Mapped[dict] = mapped_column(JSON, default=dict)
    score: Mapped[int] = mapped_column(Integer, default=0)
    category: Mapped[str] = mapped_column(String(32), default="Cold")
    sentiment_overall: Mapped[str] = mapped_column(String(64), default="")
    sentiment_progression: Mapped[list] = mapped_column(JSON, default=list)
    purchase_intent: Mapped[str] = mapped_column(String(64), default="")
    engagement: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class LeadScore(Base):
    __tablename__ = "lead_scores"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=False)
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id"), index=True, nullable=False)
    call_id: Mapped[str | None] = mapped_column(ForeignKey("calls.id"), index=True, nullable=True)
    budget_points: Mapped[float] = mapped_column(Float, default=0.0)
    authority_points: Mapped[float] = mapped_column(Float, default=0.0)
    need_points: Mapped[float] = mapped_column(Float, default=0.0)
    timeline_points: Mapped[float] = mapped_column(Float, default=0.0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    category: Mapped[str] = mapped_column(String(32), default="Cold")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class LeadMemory(Base):
    __tablename__ = "lead_memory"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=False)
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id"), index=True, nullable=False)
    call_id: Mapped[str | None] = mapped_column(ForeignKey("calls.id"), index=True, nullable=True)
    category: Mapped[str] = mapped_column(String(64), default="fact")
    content: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class KbDocument(Base):
    __tablename__ = "kb_documents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(64), default="")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="Processing")
    error: Mapped[str] = mapped_column(Text, default="")
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    embedding_model: Mapped[str] = mapped_column(String(128), default="")
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    vocab: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class KbChunk(Base):
    __tablename__ = "kb_chunks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=False)
    document_id: Mapped[str] = mapped_column(ForeignKey("kb_documents.id"), index=True, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(Text, default="")
    embedding: Mapped[list] = mapped_column(JSON, default=list)
    embedding_model: Mapped[str] = mapped_column(String(128), default="")


class KbQuery(Base):
    __tablename__ = "kb_queries"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=False)
    question: Mapped[str] = mapped_column(Text, default="")
    found: Mapped[bool] = mapped_column(Boolean, default=False)
    top_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    chunks_used: Mapped[list] = mapped_column(JSON, default=list)
    answer: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=False)
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id"), index=True, nullable=False)
    call_id: Mapped[str | None] = mapped_column(ForeignKey("calls.id"), index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")
    notes: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="Scheduled")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=False)
    lead_id: Mapped[str | None] = mapped_column(ForeignKey("leads.id"), index=True, nullable=True)
    call_id: Mapped[str | None] = mapped_column(ForeignKey("calls.id"), index=True, nullable=True)
    kind: Mapped[str] = mapped_column(String(32), default="followup")
    reason: Mapped[str] = mapped_column(Text, default="")
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="Open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ToolCall(Base):
    __tablename__ = "tool_calls"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=False)
    lead_id: Mapped[str | None] = mapped_column(ForeignKey("leads.id"), index=True, nullable=True)
    call_id: Mapped[str | None] = mapped_column(ForeignKey("calls.id"), index=True, nullable=True)
    action: Mapped[str] = mapped_column(String(128), default="")
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class SyncLog(Base):
    __tablename__ = "sync_logs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=False)
    lead_id: Mapped[str | None] = mapped_column(ForeignKey("leads.id"), index=True, nullable=True)
    direction: Mapped[str] = mapped_column(String(64), default="")
    result: Mapped[str] = mapped_column(String(32), default="")
    hubspot_id: Mapped[str] = mapped_column(String(64), default="")
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class TranscriptMessage(Base):
    __tablename__ = "transcript_messages"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    call_id: Mapped[str] = mapped_column(ForeignKey("calls.id"), index=True, nullable=False)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=False)
    speaker: Mapped[str] = mapped_column(String(32), nullable=False)  # "user" | "agent"
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
