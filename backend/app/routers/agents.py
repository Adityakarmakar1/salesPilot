from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Agent
from ..schemas import AgentCreate, AgentOut, AgentUpdate
from ..security import CurrentUser, get_current_user

router = APIRouter(prefix="/agents", tags=["agents"])


def _get_agent_or_404(db: Session, org_id: str, agent_id: str) -> Agent:
    agent = db.get(Agent, agent_id)
    if agent is None or agent.org_id != org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent not found")
    return agent


@router.get("", response_model=list[AgentOut])
def list_agents(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Agent).filter(Agent.org_id == current.org_id).order_by(Agent.created_at.desc()).all()


@router.post("", response_model=AgentOut, status_code=status.HTTP_201_CREATED)
def create_agent(body: AgentCreate, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    agent = Agent(org_id=current.org_id, **body.model_dump())
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@router.get("/{agent_id}", response_model=AgentOut)
def get_agent(agent_id: str, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return _get_agent_or_404(db, current.org_id, agent_id)


@router.patch("/{agent_id}", response_model=AgentOut)
def update_agent(
    agent_id: str, body: AgentUpdate, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)
):
    agent = _get_agent_or_404(db, current.org_id, agent_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(agent, field, value)
    db.commit()
    db.refresh(agent)
    return agent


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent(agent_id: str, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    agent = _get_agent_or_404(db, current.org_id, agent_id)
    db.delete(agent)
    db.commit()
    return None
