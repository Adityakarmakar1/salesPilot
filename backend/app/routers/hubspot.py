from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import hubspot as hubspot_service
from ..db import get_db
from ..models import Lead, Organization, SyncLog
from ..schemas import SyncLeadResponse, SyncLogOut
from ..security import CurrentUser, get_current_user

router = APIRouter(prefix="/leads", tags=["hubspot"])
logs_router = APIRouter(prefix="/sync-logs", tags=["hubspot"])


@router.post("/{lead_id}/sync-hubspot", response_model=SyncLeadResponse)
def sync_lead_to_hubspot(lead_id: str, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    lead = db.get(Lead, lead_id)
    if lead is None or lead.org_id != current.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lead not found")
    org = db.get(Organization, current.org_id)
    result = hubspot_service.sync_lead(db, org, lead, trigger="manual")
    return SyncLeadResponse(ok=result["ok"], hubspot_id=result["hubspot_id"], error=result["error"])


@logs_router.get("", response_model=list[SyncLogOut])
def list_sync_logs(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(SyncLog)
        .filter(SyncLog.org_id == current.org_id)
        .order_by(SyncLog.created_at.desc())
        .limit(50)
        .all()
    )
