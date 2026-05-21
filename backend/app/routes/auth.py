from datetime import datetime, timedelta
import hashlib

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token, get_password_hash, verify_password
from app.core.utils import build_school_code, generate_reset_token, normalize_login_id, normalize_school_code, slugify
from app.dependencies.auth import get_current_user
from app.models.school import School
from app.models.user import User, UserRole
from app.schemas.auth import (
    AuthResponse,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    ResetPasswordRequest,
    SchoolRegisterRequest,
)
from app.schemas.common import MessageResponse

router = APIRouter(prefix="/auth", tags=["Auth"])

GENERIC_LOGIN_ERROR = "Invalid school code, login ID, or password"
GENERIC_RESET_MESSAGE = "If this account exists, password reset instructions have been generated."


def _hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _school_by_code(db: Session, code: str) -> School | None:
    return db.query(School).filter(School.school_code == normalize_school_code(code), School.is_active.is_(True)).first()


def _generate_unique_school_code(db: Session, school_name: str, requested_code: str | None = None) -> str:
    if requested_code:
        code = normalize_school_code(requested_code)
        if len(code) < 3:
            raise HTTPException(status_code=400, detail="School code must contain at least 3 letters or numbers")
        if db.query(School).filter(School.school_code == code).first():
            raise HTTPException(status_code=409, detail="School code is already taken")
        return code

    counter = 1
    code = normalize_school_code(build_school_code(school_name, counter))
    while db.query(School).filter(School.school_code == code).first():
        counter += 1
        code = normalize_school_code(build_school_code(school_name, counter))
    return code


def _find_user_for_login(db: Session, school_id: int, login_id: str) -> User | None:
    normalized = normalize_login_id(login_id)
    email_value = login_id.strip().lower()
    return (
        db.query(User)
        .filter(
            User.school_id == school_id,
            or_(User.login_id == normalized, User.email == email_value),
        )
        .first()
    )


@router.post("/register-school", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register_school(payload: SchoolRegisterRequest, db: Session = Depends(get_db)):
    owner_email = str(payload.owner_email).lower()
    existing_user = db.query(User).filter(User.email == owner_email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Owner email is already registered")

    base_slug = slugify(payload.school_name)
    slug = base_slug
    counter = 1
    while db.query(School).filter(School.slug == slug).first():
        counter += 1
        slug = f"{base_slug}-{counter}"

    school_code = _generate_unique_school_code(db, payload.school_name, payload.school_code)

    school = School(
        name=payload.school_name,
        slug=slug,
        school_code=school_code,
        institution_type=payload.institution_type,
        email=str(payload.school_email) if payload.school_email else None,
        phone=payload.school_phone,
        address=payload.address,
        city=payload.city,
        state=payload.state,
        country=payload.country,
    )
    db.add(school)
    db.flush()

    owner = User(
        school_id=school.id,
        full_name=payload.owner_name,
        email=owner_email,
        phone=payload.owner_phone,
        login_id=normalize_login_id(owner_email),
        hashed_password=get_password_hash(payload.owner_password),
        role=UserRole.SCHOOL_OWNER.value,
        must_change_password=False,
    )
    db.add(owner)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="School or owner already exists")

    db.refresh(owner)
    db.refresh(school)
    token = create_access_token(owner.id, {"role": owner.role, "school_id": owner.school_id})
    return AuthResponse(access_token=token, user=owner, school=school)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    login_identifier = payload.login_id or (str(payload.email).lower() if payload.email else "")
    if not login_identifier.strip():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_LOGIN_ERROR)

    school = _school_by_code(db, payload.school_code)
    if not school:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_LOGIN_ERROR)

    user = _find_user_for_login(db, school.id, login_identifier)
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_LOGIN_ERROR)
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is inactive. Contact your school admin.")

    user.last_login_at = datetime.utcnow()
    user.failed_login_attempts = 0
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id, {"role": user.role, "school_id": user.school_id})
    return AuthResponse(access_token=token, user=user, school=school)


@router.get("/me", response_model=AuthResponse)
def me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    school = db.get(School, current_user.school_id) if current_user.school_id else None
    token = create_access_token(current_user.id, {"role": current_user.role, "school_id": current_user.school_id})
    return AuthResponse(access_token=token, user=current_user, school=school)


@router.post("/change-password", response_model=MessageResponse)
def change_password(payload: ChangePasswordRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")

    current_user.hashed_password = get_password_hash(payload.new_password)
    current_user.must_change_password = False
    current_user.password_reset_token_hash = None
    current_user.password_reset_expires_at = None
    db.commit()
    return {"message": "Password changed successfully"}


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    school = _school_by_code(db, payload.school_code)
    token: str | None = None

    if school:
        user = _find_user_for_login(db, school.id, payload.login_id)
        if user and user.is_active:
            token = generate_reset_token()
            user.password_reset_token_hash = _hash_reset_token(token)
            user.password_reset_expires_at = datetime.utcnow() + timedelta(minutes=30)
            db.commit()

    # In production you would email/SMS this token. For local development we return
    # it so the feature can be tested without SMTP setup.
    return ForgotPasswordResponse(
        message=GENERIC_RESET_MESSAGE,
        reset_token=token,
        reset_url=f"/reset-password?token={token}" if token else None,
    )


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    token_hash = _hash_reset_token(payload.token)
    user = db.query(User).filter(User.password_reset_token_hash == token_hash).first()
    if not user or not user.password_reset_expires_at or user.password_reset_expires_at < datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")

    user.hashed_password = get_password_hash(payload.new_password)
    user.must_change_password = False
    user.password_reset_token_hash = None
    user.password_reset_expires_at = None
    db.commit()
    return {"message": "Password reset successfully. You can login with your new password."}
