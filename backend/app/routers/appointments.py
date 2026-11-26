from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Appointment, Lead, LeadMemory, ToolCall
from ..schemas import AppointmentCreate, AppointmentCreateResponse, AppointmentOut, AppointmentUpdate
from ..security import CurrentUser, get_current_user

router = APIRouter(prefix="/appointments", tags=["appointments"])

APPOINTMENT_STATUSES = {"Scheduled", "Completed", "Cancelled", "No-show"}


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _to_storage_utc(value: datetime, tz_name: str) -> datetime:
    """Normalize a start time to UTC for storage.

    SQLite does not preserve UTC offsets, so starts_at is always stored as
    the UTC instant; a naive input is interpreted in the appointment's
    timezone.
    """
    if value.tzinfo is None:
        try:
            value = value.replace(tzinfo=ZoneInfo(tz_name or "Asia/Kolkata"))
        except ZoneInfoNotFoundError:
            value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _get_appointment_or_404(db: Session, org_id: str, appointment_id: str) -> Appointment:
    appointment = db.get(Appointment, appointment_id)
    if appointment is None or appointment.org_id != org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Appointment not found")
    return appointment


def _find_conflicts(db: Session, org_id: str, starts_at: datetime, duration_minutes: int, exclude_id: str | None = None) -> list[Appointment]:
    new_start = _aware(starts_at)
    new_end = new_start + timedelta(minutes=duration_minutes)
    conflicts = []
    scheduled = (
        db.query(Appointment)
        .filter(Appointment.org_id == org_id, Appointment.status == "Scheduled")
        .all()
    )
    for existing in scheduled:
        if exclude_id and existing.id == exclude_id:
            continue
        existing_start = _aware(existing.starts_at)
        existing_end = existing_start + timedelta(minutes=existing.duration_minutes)
        if existing_start < new_end and new_start < existing_end:
            conflicts.append(existing)
    return conflicts


@router.post("", response_model=AppointmentCreateResponse, status_code=status.HTTP_201_CREATED)
def create_appointment(body: AppointmentCreate, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    lead = db.get(Lead, body.lead_id)
    if lead is None or lead.org_id != current.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lead not found")
    if body.call_id:
        from ..models import Call

        call = db.get(Call, body.call_id)
        if call is None or call.org_id != current.org_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Call not found")

    starts_at_utc = _to_storage_utc(body.starts_at, body.timezone)
    conflicts = _find_conflicts(db, current.org_id, starts_at_utc, body.duration_minutes)
    appointment = Appointment(
        org_id=current.org_id,
        lead_id=body.lead_id,
        call_id=body.call_id,
        title=body.title or f"Appointment with {lead.full_name}",
        starts_at=starts_at_utc,
        duration_minutes=body.duration_minutes,
        timezone=body.timezone,
        notes=body.notes,
        status="Scheduled",
    )
    db.add(appointment)
    db.flush()

    lead.lead_status = "Appointment Booked"
    db.add(
        LeadMemory(
            org_id=current.org_id,
            lead_id=lead.id,
            call_id=body.call_id,
            category="appointment",
            content=f"Appointment booked: {appointment.title} at {_aware(appointment.starts_at).isoformat()} ({appointment.timezone}).",
        )
    )
    db.add(
        ToolCall(
            org_id=current.org_id,
            lead_id=lead.id,
            call_id=body.call_id,
            action="appointment_booked",
            detail=f"{appointment.title} at {_aware(appointment.starts_at).isoformat()}",
        )
    )
    db.commit()
    db.refresh(appointment)
    return AppointmentCreateResponse(
        appointment=AppointmentOut.model_validate(appointment),
        conflict=bool(conflicts),
        conflicts=[AppointmentOut.model_validate(c) for c in conflicts],
    )


@router.get("", response_model=list[AppointmentOut])
def list_appointments(
    lead_id: str = Query(""),
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Appointment).filter(Appointment.org_id == current.org_id)
    if lead_id:
        query = query.filter(Appointment.lead_id == lead_id)
    return query.order_by(Appointment.starts_at.desc()).all()


@router.get("/{appointment_id}", response_model=AppointmentOut)
def get_appointment(appointment_id: str, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return _get_appointment_or_404(db, current.org_id, appointment_id)


@router.patch("/{appointment_id}", response_model=AppointmentOut)
def update_appointment(
    appointment_id: str,
    body: AppointmentUpdate,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    appointment = _get_appointment_or_404(db, current.org_id, appointment_id)
    if body.status is not None and body.status not in APPOINTMENT_STATUSES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Status must be one of {sorted(APPOINTMENT_STATUSES)}",
        )
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(appointment, field, value)
    if body.starts_at is not None:
        appointment.starts_at = _to_storage_utc(body.starts_at, appointment.timezone)
    db.commit()
    db.refresh(appointment)
    return appointment


@router.delete("/{appointment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_appointment(appointment_id: str, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    appointment = _get_appointment_or_404(db, current.org_id, appointment_id)
    db.delete(appointment)
    db.commit()
    return None


def _to_utc(value: datetime, tz_name: str) -> datetime:
    # starts_at is normalized to UTC before storage (see _to_storage_utc);
    # a naive value read back from SQLite is therefore already UTC.
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@router.get("/{appointment_id}/ics")
def appointment_ics(appointment_id: str, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    appointment = _get_appointment_or_404(db, current.org_id, appointment_id)
    start_utc = _to_utc(appointment.starts_at, appointment.timezone)
    end_utc = start_utc + timedelta(minutes=appointment.duration_minutes)
    fmt = "%Y%m%dT%H%M%SZ"
    stamp = datetime.now(timezone.utc).strftime(fmt)

    def esc(text: str) -> str:
        return (text or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//SalesPilot AI//Appointments//EN",
        "BEGIN:VEVENT",
        f"UID:appointment-{appointment.id}@salespilot.ai",
        f"DTSTAMP:{stamp}",
        f"DTSTART:{start_utc.strftime(fmt)}",
        f"DTEND:{end_utc.strftime(fmt)}",
        f"SUMMARY:{esc(appointment.title)}",
        f"DESCRIPTION:{esc(appointment.notes)}",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return Response(
        content="\r\n".join(lines) + "\r\n",
        media_type="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="appointment-{appointment.id}.ics"'},
    )
