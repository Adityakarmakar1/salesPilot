"""HubSpot CRM sync service.

Syncs a lead to a HubSpot contact (search by email, then phone; update if
found, create otherwise), attaches a note with the latest qualification
summary, and records every attempt in sync_logs. No token configured is an
honest error, never a fake success.
"""

import httpx
from sqlalchemy.orm import Session

from .config import settings
from .models import Lead, LeadScore, Organization, SyncLog

HUBSPOT_BASE = "https://api.hubapi.com"
NOT_CONNECTED_ERROR = "HubSpot is not connected — HUBSPOT_ACCESS_TOKEN is not set."


def _headers() -> dict:
    return {"Authorization": f"Bearer {settings.HUBSPOT_ACCESS_TOKEN}", "Content-Type": "application/json"}


def _log(db: Session, org_id: str, lead_id: str | None, direction: str, result: str, hubspot_id: str = "", error: str = "") -> SyncLog:
    entry = SyncLog(org_id=org_id, lead_id=lead_id, direction=direction, result=result, hubspot_id=hubspot_id, error=error)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def _search_contact(client: httpx.Client, property_name: str, value: str) -> str | None:
    resp = client.post(
        f"{HUBSPOT_BASE}/crm/v3/objects/contacts/search",
        headers=_headers(),
        json={
            "filterGroups": [{"filters": [{"propertyName": property_name, "operator": "EQ", "value": value}]}],
            "properties": ["email", "phone"],
            "limit": 1,
        },
    )
    if resp.status_code != 200:
        raise _ProviderError(resp)
    results = resp.json().get("results") or []
    return results[0]["id"] if results else None


class _ProviderError(Exception):
    def __init__(self, resp: httpx.Response):
        self.status_code = resp.status_code
        self.body = resp.text[:500]
        super().__init__(f"HubSpot HTTP {resp.status_code}: {self.body}")


def _contact_properties(lead: Lead) -> dict:
    parts = (lead.full_name or "").strip().split(" ", 1)
    properties = {
        "firstname": parts[0] if parts else "",
        "lastname": parts[1] if len(parts) > 1 else "",
        "email": lead.email or "",
        "phone": lead.phone or "",
        "company": lead.company or "",
        "hs_lead_status": lead.lead_status or "",
    }
    return properties


def _note_body(db: Session, lead: Lead) -> str:
    latest = (
        db.query(LeadScore)
        .filter(LeadScore.lead_id == lead.id)
        .order_by(LeadScore.created_at.desc())
        .first()
    )
    lines = [f"SalesPilot AI sync for {lead.full_name}."]
    if lead.lead_status:
        lines.append(f"Lead status: {lead.lead_status}.")
    if latest is not None:
        lines.append(f"Latest BANT score: {latest.total}/100 ({latest.category}).")
    elif lead.lead_score is not None:
        lines.append(f"Lead score: {lead.lead_score}/100.")
    if lead.requirements:
        lines.append(f"Requirements: {lead.requirements}")
    if lead.pain_points:
        lines.append(f"Pain points: {lead.pain_points}")
    return "\n".join(lines)


def sync_lead(db: Session, org: Organization, lead: Lead, trigger: str) -> dict:
    """Sync one lead to HubSpot. Returns {"ok": bool, "hubspot_id": str|None, "error": str|None}.

    Every attempt (including the not-connected case) is written to sync_logs.
    Failures are returned, never raised.
    """
    direction = trigger
    if not settings.HUBSPOT_ACCESS_TOKEN:
        _log(db, org.id, lead.id, direction, "error", error=NOT_CONNECTED_ERROR)
        return {"ok": False, "hubspot_id": None, "error": NOT_CONNECTED_ERROR}

    contact_id: str | None = None
    try:
        with httpx.Client(timeout=10) as client:
            if lead.email:
                contact_id = _search_contact(client, "email", lead.email)
            if contact_id is None and lead.phone:
                contact_id = _search_contact(client, "phone", lead.phone)

            properties = _contact_properties(lead)
            if contact_id:
                resp = client.patch(
                    f"{HUBSPOT_BASE}/crm/v3/objects/contacts/{contact_id}",
                    headers=_headers(),
                    json={"properties": properties},
                )
                if resp.status_code not in (200, 204):
                    raise _ProviderError(resp)
            else:
                resp = client.post(
                    f"{HUBSPOT_BASE}/crm/v3/objects/contacts",
                    headers=_headers(),
                    json={"properties": properties},
                )
                if resp.status_code not in (200, 201):
                    raise _ProviderError(resp)
                contact_id = resp.json().get("id", "")

            lead.hubspot_id = contact_id
            db.commit()

            # Note with the latest qualification summary, associated to the contact.
            # A note failure is recorded on the SyncLog but does not fail the contact sync.
            note_error = ""
            try:
                note_resp = client.post(
                    f"{HUBSPOT_BASE}/crm/v3/objects/notes",
                    headers=_headers(),
                    json={"properties": {"hs_note_body": _note_body(db, lead)}},
                )
                if note_resp.status_code not in (200, 201):
                    raise _ProviderError(note_resp)
                note_id = note_resp.json().get("id", "")
                assoc_resp = client.put(
                    f"{HUBSPOT_BASE}/crm/v3/objects/notes/{note_id}/associations/contacts/{contact_id}/note_to_contact",
                    headers=_headers(),
                )
                if assoc_resp.status_code not in (200, 204):
                    raise _ProviderError(assoc_resp)
            except _ProviderError as exc:
                note_error = f"Contact synced, but the HubSpot note failed: {exc.body}"
            except httpx.HTTPError as exc:
                note_error = f"Contact synced, but the HubSpot note request failed: {exc}"

            _log(db, org.id, lead.id, direction, "success", hubspot_id=contact_id or "", error=note_error)
            return {"ok": True, "hubspot_id": contact_id, "error": note_error or None}
    except _ProviderError as exc:
        _log(db, org.id, lead.id, direction, "error", hubspot_id=contact_id or "", error=exc.body)
        return {"ok": False, "hubspot_id": contact_id, "error": exc.body}
    except httpx.HTTPError as exc:
        message = f"HubSpot request failed: {exc}"[:500]
        _log(db, org.id, lead.id, direction, "error", hubspot_id=contact_id or "", error=message)
        return {"ok": False, "hubspot_id": contact_id, "error": message}
