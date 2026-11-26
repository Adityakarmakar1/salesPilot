from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import (
    Agent,
    Appointment,
    Call,
    CallInsight,
    KbChunk,
    KbDocument,
    KbQuery,
    Lead,
    LeadMemory,
    LeadScore,
    Organization,
    OrganizationMember,
    SyncLog,
    Task,
    ToolCall,
    TranscriptMessage,
    User,
)
from ..schemas import ROLES, MemberCreate, MemberOut, MemberRoleUpdate, OrganizationOut, OrganizationUpdate, WipeRequest
from ..security import CurrentUser, get_current_user

router = APIRouter(prefix="/organizations", tags=["organizations"])

ADMIN_ROLES = ("Owner", "Administrator")


def require_admin(current: CurrentUser) -> CurrentUser:
    if current.role not in ADMIN_ROLES:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "This action requires an Owner or Administrator role",
        )
    return current


def _member_out(db: Session, member: OrganizationMember) -> MemberOut:
    user = db.get(User, member.user_id)
    return MemberOut(id=member.id, user_id=member.user_id, email=user.email if user else "", role=member.role)


@router.get("/current", response_model=OrganizationOut)
def get_current_org(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.get(Organization, current.org_id)


@router.patch("/current", response_model=OrganizationOut)
def update_current_org(
    body: OrganizationUpdate, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)
):
    require_admin(current)
    org = db.get(Organization, current.org_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(org, field, value)
    db.commit()
    db.refresh(org)
    return org


@router.get("/members", response_model=list[MemberOut])
def list_members(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    members = db.query(OrganizationMember).filter(OrganizationMember.org_id == current.org_id).all()
    return [_member_out(db, m) for m in members]


@router.post("/members", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
def add_member(body: MemberCreate, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.role not in ROLES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Role must be one of {ROLES}")
    user = db.query(User).filter(User.email == body.email.strip().lower()).first()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No registered user with that email")
    existing = (
        db.query(OrganizationMember)
        .filter(OrganizationMember.org_id == current.org_id, OrganizationMember.user_id == user.id)
        .first()
    )
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "User is already a member of this organization")
    member = OrganizationMember(org_id=current.org_id, user_id=user.id, role=body.role)
    db.add(member)
    db.commit()
    db.refresh(member)
    return _member_out(db, member)


@router.patch("/members/{member_id}", response_model=MemberOut)
def update_member_role(
    member_id: str,
    body: MemberRoleUpdate,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current)
    if body.role not in ROLES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Role must be one of {ROLES}")
    member = db.get(OrganizationMember, member_id)
    if member is None or member.org_id != current.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")
    member.role = body.role
    db.commit()
    db.refresh(member)
    return _member_out(db, member)


def _row(obj, exclude: tuple = ()) -> dict:
    data = {}
    for column in obj.__table__.columns:
        if column.name in exclude:
            continue
        value = getattr(obj, column.name)
        if isinstance(value, datetime):
            value = value.isoformat()
        data[column.name] = value
    return data


def _rows(db: Session, model, org_id: str, exclude: tuple = ()) -> list[dict]:
    return [_row(obj, exclude) for obj in db.query(model).filter(model.org_id == org_id).all()]


@router.get("/current/export")
def export_current_org(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """Full JSON export of the organization's data (admin only).

    The database stores no provider secrets or credentials, so the bundle
    contains none — API keys live only in server environment variables.
    """
    require_admin(current)
    org = db.get(Organization, current.org_id)
    members = db.query(OrganizationMember).filter(OrganizationMember.org_id == current.org_id).all()
    return {
        "organization": _row(org),
        "members": [_member_out(db, m).model_dump() for m in members],
        "agents": _rows(db, Agent, current.org_id),
        "leads": _rows(db, Lead, current.org_id),
        "calls": _rows(db, Call, current.org_id),
        "insights": _rows(db, CallInsight, current.org_id),
        "scores": _rows(db, LeadScore, current.org_id),
        "memory": _rows(db, LeadMemory, current.org_id),
        "appointments": _rows(db, Appointment, current.org_id),
        "tasks": _rows(db, Task, current.org_id),
        # Metadata only — extracted text and chunk embeddings are not exported.
        "kb_documents": _rows(db, KbDocument, current.org_id, exclude=("extracted_text", "vocab")),
        "sync_logs": _rows(db, SyncLog, current.org_id),
        "tool_calls": _rows(db, ToolCall, current.org_id),
    }


@router.post("/current/wipe")
def wipe_current_org(
    body: WipeRequest, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Delete all operational data for the organization (admin only).

    Requires confirm_text == "DELETE". The organization itself, its members
    and its agents are preserved.
    """
    require_admin(current)
    if body.confirm_text != "DELETE":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            'Nothing was deleted. Send {"confirm_text": "DELETE"} to confirm the wipe.',
        )
    tables = [
        ("sync_logs", SyncLog),
        ("tool_calls", ToolCall),
        ("tasks", Task),
        ("appointments", Appointment),
        ("kb_queries", KbQuery),
        ("kb_chunks", KbChunk),
        ("kb_documents", KbDocument),
        ("lead_memory", LeadMemory),
        ("lead_scores", LeadScore),
        ("call_insights", CallInsight),
        ("transcript_messages", TranscriptMessage),
        ("calls", Call),
        ("leads", Lead),
    ]
    deleted = {}
    for name, model in tables:
        deleted[name] = db.query(model).filter(model.org_id == current.org_id).delete(synchronize_session=False)
    db.commit()
    return {"deleted": deleted}


@router.delete("/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(member_id: str, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    member = db.get(OrganizationMember, member_id)
    if member is None or member.org_id != current.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")
    if member.role == "Owner":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The organization Owner cannot be removed")
    db.delete(member)
    db.commit()
    return None
