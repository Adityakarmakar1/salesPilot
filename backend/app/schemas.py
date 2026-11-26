from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- Auth ----------
class RegisterRequest(BaseModel):
    email: str
    password: str
    organization_name: str


class LoginRequest(BaseModel):
    email: str
    password: str


class OrganizationOut(ORMModel):
    id: str
    name: str
    industry: str = ""
    website: str = ""
    timezone: str = ""
    calling_hours: str = ""
    hubspot_auto_sync: bool = False
    created_at: datetime | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    organization: OrganizationOut


class MeResponse(BaseModel):
    id: str
    email: str
    role: str
    organization: OrganizationOut


class OrganizationUpdate(BaseModel):
    name: str | None = None
    industry: str | None = None
    website: str | None = None
    timezone: str | None = None
    calling_hours: str | None = None
    hubspot_auto_sync: bool | None = None


# ---------- Members ----------
ROLES = ["Owner", "Administrator", "Sales Manager", "Sales Representative"]


class MemberCreate(BaseModel):
    email: str
    role: str = "Sales Representative"


class MemberRoleUpdate(BaseModel):
    role: str


class MemberOut(BaseModel):
    id: str
    user_id: str
    email: str
    role: str


# ---------- Leads ----------
class LeadBase(BaseModel):
    full_name: str
    company: str = ""
    phone: str = ""
    email: str = ""
    location: str = ""
    preferred_language: str = "English"
    industry: str = ""
    lead_source: str = ""
    budget: str = ""
    requirements: str = ""
    decision_authority: str = ""
    purchase_timeline: str = ""
    pain_points: str = ""
    lead_score: int | None = None
    lead_status: str = "New"
    consent: bool = False
    do_not_contact: bool = False
    last_interaction: str = ""
    next_followup: str = ""


class LeadCreate(LeadBase):
    pass


class LeadUpdate(BaseModel):
    full_name: str | None = None
    company: str | None = None
    phone: str | None = None
    email: str | None = None
    location: str | None = None
    preferred_language: str | None = None
    industry: str | None = None
    lead_source: str | None = None
    budget: str | None = None
    requirements: str | None = None
    decision_authority: str | None = None
    purchase_timeline: str | None = None
    pain_points: str | None = None
    lead_score: int | None = None
    lead_status: str | None = None
    consent: bool | None = None
    do_not_contact: bool | None = None
    last_interaction: str | None = None
    next_followup: str | None = None


class LeadOut(LeadBase, ORMModel):
    id: str
    org_id: str
    hubspot_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class LeadImportRequest(BaseModel):
    rows: list[dict]


class LeadImportResult(BaseModel):
    imported: int
    skippedDuplicates: int
    invalidRows: int


# ---------- Agents ----------
class AgentBase(BaseModel):
    name: str
    description: str = ""
    company_name: str = ""
    personality: str = "Professional"
    languages: list[str] = []
    voice_provider: str = "Deepgram Aura"
    voice_name: str = "aura-2-thalia-en"
    speaking_speed: float = 1.0
    max_call_duration: int = 600
    calling_hours: str = ""
    sales_objectives: str = ""
    target_audience: str = ""
    qualification_questions: str = ""
    escalation_conditions: str = ""
    followup_behaviour: str = ""
    is_active: bool = True


class AgentCreate(AgentBase):
    pass


class AgentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    company_name: str | None = None
    personality: str | None = None
    languages: list[str] | None = None
    voice_provider: str | None = None
    voice_name: str | None = None
    speaking_speed: float | None = None
    max_call_duration: int | None = None
    calling_hours: str | None = None
    sales_objectives: str | None = None
    target_audience: str | None = None
    qualification_questions: str | None = None
    escalation_conditions: str | None = None
    followup_behaviour: str | None = None
    is_active: bool | None = None


class AgentOut(AgentBase, ORMModel):
    id: str
    org_id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ---------- Calls ----------
class CallStartRequest(BaseModel):
    agent_id: str
    lead_id: str | None = None
    language: str = "English"
    mode: str = "turn"  # "livekit" | "turn"


class CallEndRequest(BaseModel):
    outcome: str = "Completed"


class TranscriptMessageOut(ORMModel):
    id: str
    call_id: str
    speaker: str
    text: str
    created_at: datetime | None = None


class CallOut(ORMModel):
    id: str
    org_id: str
    agent_id: str
    lead_id: str | None = None
    room_name: str = ""
    language: str = ""
    status: str = ""
    outcome: str = ""
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_seconds: int | None = None
    context_snapshot: dict | None = None
    created_at: datetime | None = None


class CallDetailOut(CallOut):
    transcript: list[TranscriptMessageOut] = []


class CallStartResponse(BaseModel):
    call: CallOut
    livekit_url: str | None = None
    token: str | None = None
    room: str | None = None


# ---------- Analysis (Phase 3) ----------
class BantItem(BaseModel):
    value: str | None = None
    level: str = "unknown"  # established | partial | unknown
    confidence: float = 0.0
    quote: str | None = None


class CallInsightOut(ORMModel):
    id: str
    org_id: str
    call_id: str
    lead_id: str | None = None
    summary: str = ""
    requirements: str = ""
    pain_points: list = []
    product_interests: list = []
    objections: list = []
    appointment_status: str = ""
    next_action: str = ""
    bant: dict = {}
    score: int = 0
    category: str = ""
    sentiment_overall: str = ""
    sentiment_progression: list = []
    purchase_intent: str = ""
    engagement: str = ""
    created_at: datetime | None = None


class LeadScoreOut(ORMModel):
    id: str
    org_id: str
    lead_id: str
    call_id: str | None = None
    budget_points: float = 0.0
    authority_points: float = 0.0
    need_points: float = 0.0
    timeline_points: float = 0.0
    total: int = 0
    category: str = ""
    created_at: datetime | None = None


class LeadMemoryOut(ORMModel):
    id: str
    org_id: str
    lead_id: str
    call_id: str | None = None
    category: str = ""
    content: str = ""
    created_at: datetime | None = None


class SentimentHistoryItem(BaseModel):
    call_id: str
    overall: str = ""
    intent: str = ""
    created_at: datetime | None = None


class LeadIntelligenceOut(BaseModel):
    scores: list[LeadScoreOut] = []
    memory: list[LeadMemoryOut] = []
    sentiment_history: list[SentimentHistoryItem] = []


# ---------- Knowledge Base (Phase 4) ----------
class KbDocumentCreate(BaseModel):
    name: str
    text: str


class KbChunkOut(ORMModel):
    id: str
    document_id: str
    chunk_index: int = 0
    text: str = ""
    embedding_model: str = ""


class KbDocumentOut(ORMModel):
    id: str
    org_id: str
    name: str = ""
    doc_type: str = ""
    size_bytes: int = 0
    status: str = ""
    error: str = ""
    chunk_count: int = 0
    embedding_model: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None


class KbDocumentDetailOut(KbDocumentOut):
    chunks: list[KbChunkOut] = []


class KbRetrieveRequest(BaseModel):
    question: str
    top_k: int = 5


class KbRetrieveResult(BaseModel):
    document_id: str
    document_name: str = ""
    chunk_index: int = 0
    score: float = 0.0
    text: str = ""


class KbRetrieveResponse(BaseModel):
    found: bool = False
    results: list[KbRetrieveResult] = []


class KbAskRequest(BaseModel):
    question: str


class KbChunkUsed(BaseModel):
    document_id: str
    document_name: str = ""
    chunk_index: int = 0
    score: float = 0.0


class KbAskResponse(BaseModel):
    found: bool = False
    answer: str = ""
    chunks_used: list[KbChunkUsed] = []


# ---------- Appointments (Phase 5) ----------
class AppointmentCreate(BaseModel):
    lead_id: str
    call_id: str | None = None
    title: str = ""
    starts_at: datetime
    duration_minutes: int = 30
    timezone: str = "Asia/Kolkata"
    notes: str = ""


class AppointmentUpdate(BaseModel):
    title: str | None = None
    starts_at: datetime | None = None
    duration_minutes: int | None = None
    timezone: str | None = None
    notes: str | None = None
    status: str | None = None


class AppointmentOut(ORMModel):
    id: str
    org_id: str
    lead_id: str
    call_id: str | None = None
    title: str = ""
    starts_at: datetime | None = None
    duration_minutes: int = 30
    timezone: str = "Asia/Kolkata"
    notes: str = ""
    status: str = ""
    created_at: datetime | None = None


class AppointmentCreateResponse(BaseModel):
    appointment: AppointmentOut
    conflict: bool = False
    conflicts: list[AppointmentOut] = []


# ---------- Tasks (Phase 5) ----------
class TaskCreate(BaseModel):
    lead_id: str | None = None
    reason: str
    due_at: datetime | None = None


class TaskOut(ORMModel):
    id: str
    org_id: str
    lead_id: str | None = None
    call_id: str | None = None
    kind: str = ""
    reason: str = ""
    due_at: datetime | None = None
    status: str = ""
    created_at: datetime | None = None
    completed_at: datetime | None = None


# ---------- HubSpot sync (Phase 5) ----------
class SyncLeadResponse(BaseModel):
    ok: bool
    hubspot_id: str | None = None
    error: str | None = None


class SyncLogOut(ORMModel):
    id: str
    org_id: str
    lead_id: str | None = None
    direction: str = ""
    result: str = ""
    hubspot_id: str = ""
    error: str = ""
    created_at: datetime | None = None


# ---------- Organization hardening (Phase 7) ----------
class WipeRequest(BaseModel):
    confirm_text: str = ""
