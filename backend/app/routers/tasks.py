from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Lead, Task
from ..schemas import TaskCreate, TaskOut
from ..security import CurrentUser, get_current_user

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _get_task_or_404(db: Session, org_id: str, task_id: str) -> Task:
    task = db.get(Task, task_id)
    if task is None or task.org_id != org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    return task


@router.get("", response_model=list[TaskOut])
def list_tasks(
    status_filter: str = Query("", alias="status"),
    kind: str = Query(""),
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Task).filter(Task.org_id == current.org_id)
    if status_filter:
        query = query.filter(Task.status == status_filter)
    if kind:
        query = query.filter(Task.kind == kind)
    return query.order_by(Task.created_at.desc()).all()


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(body: TaskCreate, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.lead_id:
        lead = db.get(Lead, body.lead_id)
        if lead is None or lead.org_id != current.org_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Lead not found")
    task = Task(
        org_id=current.org_id,
        lead_id=body.lead_id,
        kind="followup",
        reason=body.reason,
        due_at=body.due_at,
        status="Open",
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.post("/{task_id}/complete", response_model=TaskOut)
def complete_task(task_id: str, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    task = _get_task_or_404(db, current.org_id, task_id)
    task.status = "Done"
    task.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(task)
    return task
