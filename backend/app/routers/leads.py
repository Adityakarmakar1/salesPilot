from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Lead
from ..schemas import LeadCreate, LeadImportRequest, LeadImportResult, LeadOut, LeadUpdate
from ..security import CurrentUser, get_current_user

router = APIRouter(prefix="/leads", tags=["leads"])

LEAD_FIELDS = [
    "full_name", "company", "phone", "email", "location", "preferred_language", "industry",
    "lead_source", "budget", "requirements", "decision_authority", "purchase_timeline",
    "pain_points", "lead_score", "lead_status", "consent", "do_not_contact",
    "last_interaction", "next_followup",
]


def _get_lead_or_404(db: Session, org_id: str, lead_id: str) -> Lead:
    lead = db.get(Lead, lead_id)
    if lead is None or lead.org_id != org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lead not found")
    return lead


@router.get("", response_model=list[LeadOut])
def list_leads(
    q: str = Query(""),
    status_filter: str = Query("", alias="status"),
    source: str = Query(""),
    language: str = Query(""),
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Lead).filter(Lead.org_id == current.org_id)
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Lead.full_name.ilike(like)) | (Lead.company.ilike(like)) | (Lead.email.ilike(like)) | (Lead.phone.ilike(like))
        )
    if status_filter:
        query = query.filter(Lead.lead_status == status_filter)
    if source:
        query = query.filter(Lead.lead_source == source)
    if language:
        query = query.filter(Lead.preferred_language == language)
    return query.order_by(Lead.created_at.desc()).all()


@router.post("", response_model=LeadOut, status_code=status.HTTP_201_CREATED)
def create_lead(body: LeadCreate, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    lead = Lead(org_id=current.org_id, **body.model_dump())
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


@router.get("/{lead_id}", response_model=LeadOut)
def get_lead(lead_id: str, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return _get_lead_or_404(db, current.org_id, lead_id)


@router.patch("/{lead_id}", response_model=LeadOut)
def update_lead(
    lead_id: str, body: LeadUpdate, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)
):
    lead = _get_lead_or_404(db, current.org_id, lead_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(lead, field, value)
    db.commit()
    db.refresh(lead)
    return lead


@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lead(lead_id: str, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    lead = _get_lead_or_404(db, current.org_id, lead_id)
    db.delete(lead)
    db.commit()
    return None


def _clean_row(row: dict) -> dict:
    cleaned = {}
    for field in LEAD_FIELDS:
        if field not in row:
            continue
        value = row[field]
        if field in ("consent", "do_not_contact"):
            cleaned[field] = bool(value) and str(value).lower() not in ("false", "0", "no", "")
        elif field == "lead_score":
            try:
                cleaned[field] = int(value) if value not in (None, "") else None
            except (TypeError, ValueError):
                cleaned[field] = None
        else:
            cleaned[field] = "" if value is None else str(value).strip()
    return cleaned


@router.post("/import", response_model=LeadImportResult)
def import_leads(
    body: LeadImportRequest, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)
):
    existing = db.query(Lead).filter(Lead.org_id == current.org_id).all()
    seen_phones = {lead.phone.strip() for lead in existing if lead.phone and lead.phone.strip()}
    seen_emails = {lead.email.strip().lower() for lead in existing if lead.email and lead.email.strip()}
    imported = skipped = invalid = 0
    for raw in body.rows:
        if not isinstance(raw, dict):
            invalid += 1
            continue
        row = _clean_row(raw)
        name = row.get("full_name", "")
        phone = row.get("phone", "")
        email = row.get("email", "")
        if not name or (not phone and not email):
            invalid += 1
            continue
        if (phone and phone in seen_phones) or (email and email.lower() in seen_emails):
            skipped += 1
            continue
        db.add(Lead(org_id=current.org_id, **{f: row[f] for f in LEAD_FIELDS if f in row}))
        if phone:
            seen_phones.add(phone)
        if email:
            seen_emails.add(email.lower())
        imported += 1
    db.commit()
    return LeadImportResult(imported=imported, skippedDuplicates=skipped, invalidRows=invalid)
