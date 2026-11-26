import csv
import io
from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query, Response
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
    LeadScore,
    Task,
    TranscriptMessage,
)
from ..security import CurrentUser, get_current_user

router = APIRouter(prefix="/analytics", tags=["analytics"])

QUALIFIED_STATUSES = {"Qualified", "Hot", "Warm", "Appointment Booked", "Converted"}


@router.get("/overview")
def overview(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    leads = db.query(Lead).filter(Lead.org_id == current.org_id).all()
    calls = db.query(Call).filter(Call.org_id == current.org_id).all()

    def distribution(values) -> list[dict]:
        counts = Counter(v for v in values if v)
        return [{"name": name, "value": count} for name, count in counts.most_common()]

    scores = [lead.lead_score for lead in leads if lead.lead_score is not None]
    score_buckets = Counter()
    for score in scores:
        if score >= 80:
            score_buckets["Hot (80-100)"] += 1
        elif score >= 50:
            score_buckets["Warm (50-79)"] += 1
        else:
            score_buckets["Cold (0-49)"] += 1

    return {
        "total_leads": len(leads),
        "qualified_leads": sum(1 for lead in leads if lead.lead_status in QUALIFIED_STATUSES),
        "hot_leads": sum(1 for lead in leads if lead.lead_status == "Hot"),
        "warm_leads": sum(1 for lead in leads if lead.lead_status == "Warm"),
        "cold_leads": sum(1 for lead in leads if lead.lead_status == "Cold"),
        "appointments_booked": sum(1 for lead in leads if lead.lead_status == "Appointment Booked"),
        "converted_leads": sum(1 for lead in leads if lead.lead_status == "Converted"),
        "followups_due": sum(1 for lead in leads if lead.next_followup),
        "status_distribution": distribution(lead.lead_status for lead in leads),
        "source_distribution": distribution(lead.lead_source for lead in leads),
        "language_distribution": distribution(lead.preferred_language for lead in leads),
        "score_distribution": [{"name": name, "value": count} for name, count in score_buckets.items()],
        "total_calls": len(calls),
        "completed_calls": sum(1 for call in calls if call.status == "Completed"),
    }


# ---------- Full analytics (Phase 6) ----------
def _aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _in_range(rows, cutoff: datetime | None):
    if cutoff is None:
        return list(rows)
    return [row for row in rows if _aware(getattr(row, "created_at", None)) is not None and _aware(row.created_at) >= cutoff]


def _counter_dict(values) -> dict:
    return dict(Counter(v for v in values if v))


def _top_strings(lists, limit: int = 10) -> list[dict]:
    counts = Counter()
    for items in lists:
        for item in items or []:
            text = str(item).strip()
            if text:
                counts[text] += 1
    return [{"name": name, "count": count} for name, count in counts.most_common(limit)]


def compute_full(db: Session, org_id: str, range_days: int) -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(days=range_days) if range_days and range_days > 0 else None

    leads = _in_range(db.query(Lead).filter(Lead.org_id == org_id).all(), cutoff)
    all_org_leads = db.query(Lead).filter(Lead.org_id == org_id).all()
    calls = _in_range(db.query(Call).filter(Call.org_id == org_id).all(), cutoff)
    insights = _in_range(db.query(CallInsight).filter(CallInsight.org_id == org_id).all(), cutoff)
    appointments = _in_range(db.query(Appointment).filter(Appointment.org_id == org_id).all(), cutoff)
    tasks = _in_range(db.query(Task).filter(Task.org_id == org_id).all(), cutoff)
    kb_documents = _in_range(db.query(KbDocument).filter(KbDocument.org_id == org_id).all(), cutoff)
    kb_queries = _in_range(db.query(KbQuery).filter(KbQuery.org_id == org_id).all(), cutoff)
    kb_chunks = db.query(KbChunk).filter(KbChunk.org_id == org_id).all()
    if cutoff is not None:
        doc_ids = {doc.id for doc in kb_documents}
        kb_chunks = [chunk for chunk in kb_chunks if chunk.document_id in doc_ids]
    agents = db.query(Agent).filter(Agent.org_id == org_id).all()

    # Latest LeadScore per lead (over all time — it describes the lead's current state).
    all_scores = (
        db.query(LeadScore).filter(LeadScore.org_id == org_id).order_by(LeadScore.created_at.asc()).all()
    )
    latest_score_by_lead: dict[str, LeadScore] = {}
    for score in all_scores:
        latest_score_by_lead[score.lead_id] = score

    lead_scores_values = [lead.lead_score for lead in leads if lead.lead_score is not None]
    converted = sum(1 for lead in leads if lead.lead_status == "Converted")

    call_ids = {call.id for call in calls}
    transcript_call_ids = {
        row[0]
        for row in db.query(TranscriptMessage.call_id).filter(TranscriptMessage.org_id == org_id).distinct().all()
    }
    insights_by_call = {insight.call_id: insight for insight in db.query(CallInsight).filter(CallInsight.org_id == org_id).all()}
    analyzed_calls = [call for call in calls if call.id in insights_by_call]
    durations = [call.duration_seconds for call in calls if call.duration_seconds is not None]

    # Weekly sentiment trend.
    weekly: dict[str, Counter] = {}
    for insight in insights:
        created = _aware(insight.created_at)
        if created is None:
            continue
        week_start = (created - timedelta(days=created.weekday())).date().isoformat()
        weekly.setdefault(week_start, Counter())[insight.sentiment_overall or "Unknown"] += 1
    weekly_trend = [
        {"week_start": week, "counts": dict(counts)} for week, counts in sorted(weekly.items())
    ]

    completeness = []
    for insight in insights:
        bant = insight.bant or {}
        known = sum(1 for key in ("budget", "authority", "need", "timeline") if (bant.get(key) or {}).get("level") not in (None, "unknown"))
        completeness.append(known / 4.0)

    finished_appointments = sum(1 for a in appointments if a.status in ("Completed", "Cancelled", "No-show"))
    completed_appointments = sum(1 for a in appointments if a.status == "Completed")
    now = datetime.now(timezone.utc)

    agent_performance = []
    for agent in agents:
        agent_calls = [call for call in calls if call.agent_id == agent.id]
        agent_call_ids = {call.id for call in agent_calls}
        agent_insights = [insights_by_call[cid] for cid in agent_call_ids if cid in insights_by_call]
        agent_performance.append(
            {
                "agent_id": agent.id,
                "name": agent.name,
                "calls": len(agent_calls),
                "analyzed": len(agent_insights),
                "avg_score": round(sum(i.score for i in agent_insights) / len(agent_insights), 2) if agent_insights else 0,
                "hot_leads": len({i.lead_id for i in agent_insights if i.category == "Hot" and i.lead_id}),
                "appointments_booked": sum(1 for a in appointments if a.call_id in agent_call_ids),
            }
        )

    return {
        "range_days": range_days or 0,
        "leads": {
            "total": len(leads),
            "by_status": _counter_dict(lead.lead_status for lead in leads),
            "by_source": _counter_dict(lead.lead_source for lead in leads),
            "by_language": _counter_dict(lead.preferred_language for lead in leads),
            "by_category": _counter_dict(
                latest_score_by_lead[lead.id].category for lead in all_org_leads if lead.id in latest_score_by_lead
            ),
            "avg_score": round(sum(lead_scores_values) / len(lead_scores_values), 2) if lead_scores_values else 0,
            "converted": converted,
            "conversion_rate": round(converted / len(leads), 4) if leads else 0,
        },
        "calls": {
            "total": len(calls),
            "total_duration": sum(durations),
            "avg_duration": round(sum(durations) / len(durations), 2) if durations else 0,
            "by_outcome": _counter_dict(call.outcome for call in calls),
            "by_language": _counter_dict(call.language for call in calls),
            "by_agent": dict(Counter(call.agent_id for call in calls)),
            "with_transcripts": sum(1 for call in calls if call.id in transcript_call_ids),
            "analyzed": len(analyzed_calls),
            "analyzed_rate": round(len(analyzed_calls) / len(calls), 4) if calls else 0,
            "avg_qualification_score": round(sum(i.score for i in insights) / len(insights), 2) if insights else 0,
        },
        "insights": {
            "sentiment_distribution": _counter_dict(i.sentiment_overall for i in insights),
            "weekly_trend": weekly_trend,
            "intent_distribution": _counter_dict(i.purchase_intent for i in insights),
            "top_objections": _top_strings([i.objections for i in insights]),
            "top_pain_points": _top_strings([i.pain_points for i in insights]),
            "top_interests": _top_strings([i.product_interests for i in insights]),
            "bant_completeness_avg": round(sum(completeness) / len(completeness), 4) if completeness else 0,
        },
        "appointments": {
            "by_status": _counter_dict(a.status for a in appointments),
            "completion_rate": round(completed_appointments / finished_appointments, 4) if finished_appointments else 0,
        },
        "tasks": {
            "open": sum(1 for t in tasks if t.status == "Open"),
            "done": sum(1 for t in tasks if t.status == "Done"),
            "overdue": sum(1 for t in tasks if t.status == "Open" and _aware(t.due_at) is not None and _aware(t.due_at) < now),
            "escalations": sum(1 for t in tasks if t.kind == "escalation"),
            "followups": sum(1 for t in tasks if t.kind == "followup"),
        },
        "kb": {
            "documents": len(kb_documents),
            "ready": sum(1 for d in kb_documents if d.status == "Ready"),
            "chunks": len(kb_chunks),
            "queries": len(kb_queries),
            "hits": sum(1 for q in kb_queries if q.found),
            "hit_rate": round(sum(1 for q in kb_queries if q.found) / len(kb_queries), 4) if kb_queries else 0,
        },
        "agents": agent_performance,
    }


@router.get("/full")
def full_analytics(
    range_days: int = Query(0),
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return compute_full(db, current.org_id, range_days)


# ---------- CSV exports ----------
def _csv_safe(value) -> str:
    text = "" if value is None else str(value)
    if text[:1] in ("=", "+", "-", "@"):
        return "'" + text
    return text


def _csv_response(filename: str, header: list[str], rows: list[list]) -> Response:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([_csv_safe(h) for h in header])
    for row in rows:
        writer.writerow([_csv_safe(v) for v in row])
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/leads.csv")
def leads_csv(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    leads = db.query(Lead).filter(Lead.org_id == current.org_id).order_by(Lead.created_at.desc()).all()
    rows = [
        [
            lead.full_name,
            lead.company,
            lead.phone,
            lead.email,
            lead.lead_status,
            lead.lead_score if lead.lead_score is not None else "",
            lead.lead_source,
            lead.preferred_language,
            _aware(lead.created_at).isoformat() if lead.created_at else "",
        ]
        for lead in leads
    ]
    return _csv_response(
        "leads.csv",
        ["name", "company", "phone", "email", "status", "score", "source", "language", "created_at"],
        rows,
    )


@router.get("/summary.csv")
def summary_csv(
    range_days: int = Query(0),
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = compute_full(db, current.org_id, range_days)
    rows: list[list] = []

    def add(section: str, metric: str, value):
        rows.append([section, metric, value])

    add("leads", "total", data["leads"]["total"])
    add("leads", "avg_score", data["leads"]["avg_score"])
    add("leads", "converted", data["leads"]["converted"])
    add("leads", "conversion_rate", data["leads"]["conversion_rate"])
    for name, count in data["leads"]["by_status"].items():
        add("leads_by_status", name, count)
    for name, count in data["leads"]["by_category"].items():
        add("leads_by_category", name, count)
    add("calls", "total", data["calls"]["total"])
    add("calls", "total_duration", data["calls"]["total_duration"])
    add("calls", "avg_duration", data["calls"]["avg_duration"])
    add("calls", "with_transcripts", data["calls"]["with_transcripts"])
    add("calls", "analyzed", data["calls"]["analyzed"])
    add("calls", "analyzed_rate", data["calls"]["analyzed_rate"])
    add("calls", "avg_qualification_score", data["calls"]["avg_qualification_score"])
    for name, count in data["insights"]["sentiment_distribution"].items():
        add("sentiment", name, count)
    for name, count in data["insights"]["intent_distribution"].items():
        add("purchase_intent", name, count)
    add("insights", "bant_completeness_avg", data["insights"]["bant_completeness_avg"])
    for name, count in data["appointments"]["by_status"].items():
        add("appointments_by_status", name, count)
    add("appointments", "completion_rate", data["appointments"]["completion_rate"])
    for metric in ("open", "done", "overdue", "escalations", "followups"):
        add("tasks", metric, data["tasks"][metric])
    for metric in ("documents", "ready", "chunks", "queries", "hits", "hit_rate"):
        add("kb", metric, data["kb"][metric])
    for agent in data["agents"]:
        add("agent_calls", agent["name"], agent["calls"])
        add("agent_avg_score", agent["name"], agent["avg_score"])
    return _csv_response("summary.csv", ["section", "metric", "value"], rows)
