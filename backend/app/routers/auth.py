from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Organization, OrganizationMember, User
from ..schemas import LoginRequest, MeResponse, OrganizationOut, RegisterRequest, TokenResponse
from ..security import CurrentUser, create_access_token, get_current_user, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "A valid email is required")
    if len(body.password) < 8:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Password must be at least 8 characters")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    user = User(email=email, password_hash=hash_password(body.password))
    org = Organization(name=body.organization_name.strip() or "My Organization")
    db.add_all([user, org])
    db.flush()
    db.add(OrganizationMember(org_id=org.id, user_id=user.id, role="Owner"))
    db.commit()
    db.refresh(org)
    return TokenResponse(access_token=create_access_token(user.id), organization=OrganizationOut.model_validate(org))


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email.strip().lower()).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    membership = db.query(OrganizationMember).filter(OrganizationMember.user_id == user.id).first()
    if membership is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "User does not belong to an organization")
    org = db.get(Organization, membership.org_id)
    return TokenResponse(access_token=create_access_token(user.id), organization=OrganizationOut.model_validate(org))


@router.get("/me", response_model=MeResponse)
def me(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    org = db.get(Organization, current.org_id)
    return MeResponse(
        id=current.user.id,
        email=current.user.email,
        role=current.role,
        organization=OrganizationOut.model_validate(org),
    )
