"""Auth routes — register, login, profile, token refresh."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from service.database import get_db
from service.auth import register_user, login_user, require_auth
from service.models_db import User

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: str
    username: str
    password: str
    referral_code: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class ProfileResponse(BaseModel):
    id: str
    email: str
    username: str
    full_name: str
    tier: str
    is_verified: bool
    is_admin: bool = False
    referral_code: str


@router.post("/register")
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    try:
        user = register_user(db, req.email, req.username, req.password, req.referral_code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    from service.auth import create_token
    token = create_token(user.id, user.email, user.tier)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "username": user.username, "tier": user.tier},
    }


@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    return login_user(db, req.email, req.password)


@router.get("/me", response_model=ProfileResponse)
def get_profile(user: User = Depends(require_auth)):
    return ProfileResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        tier=user.tier,
        is_verified=user.is_verified,
        is_admin=user.is_admin,
        referral_code=user.referral_code,
    )
