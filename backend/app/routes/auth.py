from datetime import datetime, timedelta
import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, get_password_hash, verify_password
from app.core.utils import (
    build_school_code,
    generate_numeric_otp,
    generate_reset_token,
    normalize_login_id,
    normalize_school_code,
    slugify,
)
from app.dependencies.auth import get_current_user
from app.models.school import School
from app.models.user import User, UserRole
from app.models.verification import PendingSchoolRegistration
from app.schemas.auth import (
    AuthResponse,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    ResetPasswordRequest,
    SchoolRegisterRequest,
    SchoolRegistrationOtpResponse,
    SchoolRegistrationVerifyRequest,
)
from app.schemas.common import MessageResponse
from app.utils.email import EmailNotConfiguredError, send_password_reset_email, send_school_registration_otp_email

router = APIRouter(prefix="/auth", tags=["Auth"])

GENERIC_LOGIN_ERROR = "Invalid school code, login ID, or password"
GENERIC_RESET_MESSAGE = "If this account exists, password reset instructions have been sent to the registered email."
LOGIN_ROLE_GROUPS = {
    "ADMIN": {UserRole.SUPER_ADMIN.value, UserRole.SCHOOL_OWNER.value, UserRole.SCHOOL_ADMIN.value},
    "TEACHER": {UserRole.TEACHER.value},
    "STUDENT": {UserRole.STUDENT.value},
    "PARENT": {UserRole.PARENT.value},
}


def _hash_value(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _hash_reset_token(token: str) -> str:
    return _hash_value(token)


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


def _find_pending_registration(db: Session, owner_email: str) -> PendingSchoolRegistration | None:
    return (
        db.query(PendingSchoolRegistration)
        .filter(PendingSchoolRegistration.owner_email == owner_email.lower())
        .order_by(PendingSchoolRegistration.id.desc())
        .first()
    )


def _create_school_and_owner(db: Session, payload: SchoolRegisterRequest) -> tuple[School, User]:
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
    return school, owner


def _build_reset_url(token: str) -> str:
    frontend_base_url = settings.FRONTEND_BASE_URL.rstrip("/")
    return f"{frontend_base_url}/reset-password?token={token}"


@router.post("/register-school", response_model=SchoolRegistrationOtpResponse, status_code=status.HTTP_200_OK)
def request_school_registration_otp(payload: SchoolRegisterRequest, db: Session = Depends(get_db)):
    """Start school signup by sending an email OTP to the owner.

    The school and owner user are created only after OTP verification succeeds.
    """
    owner_email = str(payload.owner_email).lower()
    existing_user = db.query(User).filter(User.email == owner_email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Owner email is already registered")

    if payload.school_code:
        _generate_unique_school_code(db, payload.school_name, payload.school_code)

    otp = generate_numeric_otp(6)
    expires_at = datetime.utcnow() + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)

    # Keep only the latest pending signup for this owner email.
    db.query(PendingSchoolRegistration).filter(PendingSchoolRegistration.owner_email == owner_email).delete()
    pending = PendingSchoolRegistration(
        owner_email=owner_email,
        otp_hash=_hash_value(otp),
        payload_json=json.dumps(payload.model_dump(mode="json")),
        expires_at=expires_at,
        attempts=0,
    )
    db.add(pending)
    db.commit()

    message = "Verification OTP sent to owner email."
    try:
        send_school_registration_otp_email(owner_email, otp, payload.school_name)
    except EmailNotConfiguredError as exc:
        if not settings.EMAIL_OTP_DEBUG:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        message = "OTP generated in debug mode. Configure SMTP in backend/.env to send real email."
    except Exception as exc:  # noqa: BLE001 - return a clear setup error for local dev
        if not settings.EMAIL_OTP_DEBUG:
            raise HTTPException(status_code=500, detail="Failed to send verification email") from exc
        message = "OTP generated in debug mode, but email sending failed. Check SMTP settings."

    return SchoolRegistrationOtpResponse(
        message=message,
        owner_email=owner_email,
        expires_in_minutes=settings.OTP_EXPIRE_MINUTES,
        debug_otp=otp if settings.EMAIL_OTP_DEBUG else None,
    )


@router.post("/verify-school-registration", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def verify_school_registration(payload: SchoolRegistrationVerifyRequest, db: Session = Depends(get_db)):
    owner_email = str(payload.owner_email).lower()
    pending = _find_pending_registration(db, owner_email)
    if not pending:
        raise HTTPException(status_code=400, detail="No pending school registration found for this email")

    if pending.expires_at < datetime.utcnow():
        db.delete(pending)
        db.commit()
        raise HTTPException(status_code=400, detail="OTP expired. Please register again to receive a new OTP.")

    if pending.attempts >= settings.OTP_MAX_ATTEMPTS:
        db.delete(pending)
        db.commit()
        raise HTTPException(status_code=400, detail="Too many invalid OTP attempts. Please register again.")

    if pending.otp_hash != _hash_value(payload.otp.strip()):
        pending.attempts += 1
        db.commit()
        remaining = max(settings.OTP_MAX_ATTEMPTS - pending.attempts, 0)
        raise HTTPException(status_code=400, detail=f"Invalid OTP. {remaining} attempt(s) left.")

    registration_payload = SchoolRegisterRequest(**json.loads(pending.payload_json))
    try:
        school, owner = _create_school_and_owner(db, registration_payload)
        db.delete(pending)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="School or owner already exists") from exc

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

    selected_role = (payload.selected_role or "").strip().upper()
    allowed_roles = LOGIN_ROLE_GROUPS.get(selected_role)
    if allowed_roles and user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"This account is registered as {user.role.replace('_', ' ').title()}. Please select the correct portal tab.",
        )

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
    reset_url: str | None = None

    if school:
        user = _find_user_for_login(db, school.id, payload.login_id)
        if user and user.is_active:
            token = generate_reset_token()
            reset_url = _build_reset_url(token)
            user.password_reset_token_hash = _hash_reset_token(token)
            user.password_reset_expires_at = datetime.utcnow() + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)
            db.commit()

            try:
                send_password_reset_email(user.email, reset_url, user.full_name)
            except EmailNotConfiguredError as exc:
                if not settings.EMAIL_OTP_DEBUG:
                    raise HTTPException(status_code=500, detail=str(exc)) from exc
            except Exception as exc:  # noqa: BLE001
                if not settings.EMAIL_OTP_DEBUG:
                    raise HTTPException(status_code=500, detail="Failed to send password reset email") from exc

    return ForgotPasswordResponse(
        message=GENERIC_RESET_MESSAGE,
        reset_token=token if settings.EMAIL_OTP_DEBUG else None,
        reset_url=reset_url if settings.EMAIL_OTP_DEBUG else None,
    )


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    token_hash = _hash_reset_token(payload.token)
    user = db.query(User).filter(User.password_reset_token_hash == token_hash).first()
    if not user or not user.password_reset_expires_at or user.password_reset_expires_at < datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset link")

    user.hashed_password = get_password_hash(payload.new_password)
    user.must_change_password = False
    user.password_reset_token_hash = None
    user.password_reset_expires_at = None
    db.commit()
    return {"message": "Password reset successfully. You can login with your new password."}
