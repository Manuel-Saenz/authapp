from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import rate_limit
import security
from database import get_db
from models import User
from schemas import (
    AuthRequest,
    ErrorResponse,
    OkResponse,
    RegisterRequest,
    RegisterResponse,
    SetupConfirmRequest,
)

router = APIRouter()

_AUTH_ERROR = ErrorResponse(status="error", message="Invalid credentials or OTP code")


# ── POST /register ────────────────────────────────────────────────────────────

@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    email = body.email.lower()

    secret = security.generate_totp_secret()
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        if existing.password_hash is not None:
            raise HTTPException(status_code=409, detail="Email already registered")
        existing.password_hash = security.hash_password(body.password)
        existing.totp_secret = secret
        existing.totp_confirmed = False
        db.commit()
    else:
        user = User(
            email=email,
            password_hash=security.hash_password(body.password),
            totp_secret=secret,
            totp_confirmed=False,
        )
        db.add(user)
        db.commit()

    totp_uri = security.build_totp_uri(secret, email)
    return RegisterResponse(
        status="ok",
        totp_uri=totp_uri,
        message="Scan this URI with Google Authenticator, then call /setup-confirm",
    )


# ── POST /setup-confirm ───────────────────────────────────────────────────────

@router.post("/setup-confirm", response_model=OkResponse)
def setup_confirm(body: SetupConfirmRequest, db: Session = Depends(get_db)):
    email = body.email.lower()
    user = db.query(User).filter(User.email == email).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.totp_confirmed:
        raise HTTPException(status_code=400, detail="TOTP already confirmed")

    if not security.verify_totp(user.totp_secret, body.totp_code):
        raise HTTPException(status_code=400, detail="Invalid TOTP code")

    user.totp_confirmed = True
    db.commit()

    return OkResponse(status="ok")


# ── POST /authenticate ────────────────────────────────────────────────────────

@router.post("/authenticate", response_model=OkResponse | ErrorResponse)
def authenticate(body: AuthRequest, db: Session = Depends(get_db)):
    email = body.email.lower()

    # Rate limit check
    if rate_limit.is_rate_limited(email):
        return ErrorResponse(
            status="error",
            message="Too many failed attempts. Try again in 15 minutes.",
        )

    user = db.query(User).filter(User.email == email).first()

    # Always run bcrypt verify to prevent timing-based user enumeration
    if not user:
        security.dummy_verify()
        rate_limit.record_attempt(email)
        return _AUTH_ERROR

    if user.password_hash is None or not security.verify_password(body.password, user.password_hash):
        rate_limit.record_attempt(email)
        return _AUTH_ERROR

    if not user.totp_confirmed:
        rate_limit.record_attempt(email)
        return ErrorResponse(status="error", message="TOTP setup not completed")

    if user.totp_secret is None or not security.verify_totp(user.totp_secret, body.totp_code):
        rate_limit.record_attempt(email)
        return _AUTH_ERROR

    # Replay attack guard
    if security.is_code_used(email, body.totp_code):
        rate_limit.record_attempt(email)
        return _AUTH_ERROR

    security.mark_code_used(email, body.totp_code)
    rate_limit.clear_attempts(email)
    return OkResponse(status="ok")
