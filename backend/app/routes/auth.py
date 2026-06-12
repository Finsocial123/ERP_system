from datetime import datetime, timedelta
import hashlib
import json
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from app.core.config import settings
from app.core.database import get_async_db
from app.core.security import create_access_token, create_refresh_token, get_password_hash, hash_token, verify_password
from app.core.utils import build_school_code, generate_numeric_otp, generate_reset_token, normalize_login_id, normalize_school_code, slugify
from app.dependencies.auth import get_current_user
from app.models.school import School
from app.models.user import User, UserRole
from app.models.session import RefreshToken
from app.models.people import Teacher
from app.models.verification import PendingSchoolRegistration
from app.schemas.auth import AuthResponse, ChangePasswordRequest, ForgotPasswordRequest, ForgotPasswordResponse, LoginRequest, ResetPasswordRequest, SchoolRegisterRequest, SchoolRegistrationOtpResponse, SchoolRegistrationVerifyRequest, TokenRefreshResponse, UserPublic
from app.schemas.common import MessageResponse
from app.utils.email import EmailNotConfiguredError, send_password_reset_email, send_school_registration_otp_email
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.async_query import async_query
router = APIRouter(prefix='/auth', tags=['Auth'])


async def _build_user_public(db: AsyncSession, user: User) -> UserPublic:
    """Build UserPublic, enriching with photo_url for teachers."""
    user_public = UserPublic.model_validate(user)
    if user.role == UserRole.TEACHER.value and user.id:
        teacher = await async_query(db, Teacher).filter(Teacher.user_id == user.id).first()
        if teacher and teacher.photo_url:
            user_public.photo_url = teacher.photo_url
    return user_public
GENERIC_LOGIN_ERROR = 'Invalid school code, login ID, or password'
GENERIC_RESET_MESSAGE = 'If this account exists, password reset instructions have been sent to the registered email.'
LOGIN_ROLE_GROUPS = {'ADMIN': {UserRole.SUPER_ADMIN.value, UserRole.SCHOOL_OWNER.value, UserRole.SCHOOL_ADMIN.value}, 'TEACHER': {UserRole.TEACHER.value}, 'STUDENT': {UserRole.STUDENT.value}, 'PARENT': {UserRole.PARENT.value}}

def _hash_value(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()

def _hash_reset_token(token: str) -> str:
    return _hash_value(token)

def _refresh_token_max_age_seconds() -> int:
    return settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60


def _access_token_expires_in_seconds() -> int:
    return settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60


def _cookie_domain() -> str | None:
    return settings.REFRESH_TOKEN_COOKIE_DOMAIN.strip() or None


def _client_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get('x-forwarded-for')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()[:64]
    return request.client.host[:64] if request.client and request.client.host else None


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME,
        value=token,
        max_age=_refresh_token_max_age_seconds(),
        path=settings.REFRESH_TOKEN_COOKIE_PATH,
        domain=_cookie_domain(),
        secure=settings.REFRESH_TOKEN_COOKIE_SECURE,
        httponly=True,
        samesite=settings.REFRESH_TOKEN_COOKIE_SAMESITE.lower(),
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME,
        path=settings.REFRESH_TOKEN_COOKIE_PATH,
        domain=_cookie_domain(),
    )


async def _create_refresh_token_record(db: AsyncSession, user: User, request: Request) -> tuple[str, RefreshToken]:
    raw_token = create_refresh_token()
    token = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        user_agent=(request.headers.get('user-agent') or '')[:512] or None,
        ip_address=_client_ip(request),
    )
    db.add(token)
    await db.flush()
    return raw_token, token


async def _issue_auth_response(
    db: AsyncSession,
    response: Response,
    request: Request,
    user: User,
    school: School | None,
) -> AuthResponse:
    refresh_token, _ = await _create_refresh_token_record(db, user, request)
    _set_refresh_cookie(response, refresh_token)
    access_token = create_access_token(user.id, {'role': user.role, 'school_id': user.school_id})
    user_public = await _build_user_public(db, user)
    return AuthResponse(
        access_token=access_token,
        expires_in=_access_token_expires_in_seconds(),
        refresh_expires_in=_refresh_token_max_age_seconds(),
        user=user_public,
        school=school,
    )


async def _find_valid_refresh_token(db: AsyncSession, raw_token: str) -> RefreshToken | None:
    return await async_query(db, RefreshToken).filter(
        RefreshToken.token_hash == hash_token(raw_token),
        RefreshToken.revoked_at.is_(None),
        RefreshToken.expires_at > datetime.utcnow(),
    ).first()

async def _school_by_code(db: AsyncSession, code: str) -> School | None:
    return await async_query(db, School).filter(School.school_code == normalize_school_code(code), School.is_active.is_(True)).first()

async def _generate_unique_school_code(db: AsyncSession, school_name: str, requested_code: str | None=None) -> str:
    if requested_code:
        code = normalize_school_code(requested_code)
        if len(code) < 3:
            raise HTTPException(status_code=400, detail='School code must contain at least 3 letters or numbers')
        if await async_query(db, School).filter(School.school_code == code).first():
            raise HTTPException(status_code=409, detail='School code is already taken')
        return code
    counter = 1
    code = normalize_school_code(build_school_code(school_name, counter))
    while await async_query(db, School).filter(School.school_code == code).first():
        counter += 1
        code = normalize_school_code(build_school_code(school_name, counter))
    return code

async def _find_user_for_login(db: AsyncSession, school_id: int, login_id: str) -> User | None:
    normalized = normalize_login_id(login_id)
    email_value = login_id.strip().lower()
    return await async_query(db, User).filter(User.school_id == school_id, or_(User.login_id == normalized, User.email == email_value)).first()

async def _find_pending_registration(db: AsyncSession, owner_email: str) -> PendingSchoolRegistration | None:
    return await async_query(db, PendingSchoolRegistration).filter(PendingSchoolRegistration.owner_email == owner_email.lower()).order_by(PendingSchoolRegistration.id.desc()).first()

async def _create_school_and_owner(db: AsyncSession, payload: SchoolRegisterRequest) -> tuple[School, User]:
    owner_email = str(payload.owner_email).lower()
    existing_user = await async_query(db, User).filter(User.email == owner_email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail='Owner email is already registered')
    base_slug = slugify(payload.school_name)
    slug = base_slug
    counter = 1
    while await async_query(db, School).filter(School.slug == slug).first():
        counter += 1
        slug = f'{base_slug}-{counter}'
    school_code = await _generate_unique_school_code(db, payload.school_name, payload.school_code)
    school = School(name=payload.school_name, slug=slug, school_code=school_code, institution_type=payload.institution_type, email=str(payload.school_email) if payload.school_email else None, phone=payload.school_phone, address=payload.address, city=payload.city, state=payload.state, country=payload.country)
    db.add(school)
    await db.flush()
    owner = User(school_id=school.id, full_name=payload.owner_name, email=owner_email, phone=payload.owner_phone, login_id=normalize_login_id(owner_email), hashed_password=get_password_hash(payload.owner_password), role=UserRole.SCHOOL_OWNER.value, must_change_password=False)
    db.add(owner)
    return (school, owner)

def _build_reset_url(token: str) -> str:
    frontend_base_url = settings.FRONTEND_BASE_URL.rstrip('/')
    return f'{frontend_base_url}/reset-password?token={token}'

@router.post('/register-school', response_model=SchoolRegistrationOtpResponse, status_code=status.HTTP_200_OK)
async def request_school_registration_otp(payload: SchoolRegisterRequest, db: AsyncSession=Depends(get_async_db)):
    """Start school signup by sending an email OTP to the owner.

    The school and owner user are created only after OTP verification succeeds.
    """
    owner_email = str(payload.owner_email).lower()
    existing_user = await async_query(db, User).filter(User.email == owner_email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail='Owner email is already registered')
    if payload.school_code:
        await _generate_unique_school_code(db, payload.school_name, payload.school_code)
    otp = generate_numeric_otp(6)
    expires_at = datetime.utcnow() + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)
    await async_query(db, PendingSchoolRegistration).filter(PendingSchoolRegistration.owner_email == owner_email).delete()
    pending = PendingSchoolRegistration(owner_email=owner_email, otp_hash=_hash_value(otp), payload_json=json.dumps(payload.model_dump(mode='json')), expires_at=expires_at, attempts=0)
    db.add(pending)
    await db.commit()
    message = 'Verification OTP sent to owner email.'
    try:
        send_school_registration_otp_email(owner_email, otp, payload.school_name)
    except EmailNotConfiguredError as exc:
        if not settings.EMAIL_OTP_DEBUG:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        message = 'OTP generated in debug mode. Configure SMTP in backend/.env to send real email.'
    except Exception as exc:
        if not settings.EMAIL_OTP_DEBUG:
            raise HTTPException(status_code=500, detail='Failed to send verification email') from exc
        message = 'OTP generated in debug mode, but email sending failed. Check SMTP settings.'
    return SchoolRegistrationOtpResponse(message=message, owner_email=owner_email, expires_in_minutes=settings.OTP_EXPIRE_MINUTES, debug_otp=otp if settings.EMAIL_OTP_DEBUG else None)

@router.post('/verify-school-registration', response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def verify_school_registration(payload: SchoolRegistrationVerifyRequest, response: Response, request: Request, db: AsyncSession=Depends(get_async_db)):
    owner_email = str(payload.owner_email).lower()
    pending = await _find_pending_registration(db, owner_email)
    if not pending:
        raise HTTPException(status_code=400, detail='No pending school registration found for this email')
    if pending.expires_at < datetime.utcnow():
        await db.delete(pending)
        await db.commit()
        raise HTTPException(status_code=400, detail='OTP expired. Please register again to receive a new OTP.')
    if pending.attempts >= settings.OTP_MAX_ATTEMPTS:
        await db.delete(pending)
        await db.commit()
        raise HTTPException(status_code=400, detail='Too many invalid OTP attempts. Please register again.')
    if pending.otp_hash != _hash_value(payload.otp.strip()):
        pending.attempts += 1
        await db.commit()
        remaining = max(settings.OTP_MAX_ATTEMPTS - pending.attempts, 0)
        raise HTTPException(status_code=400, detail=f'Invalid OTP. {remaining} attempt(s) left.')
    registration_payload = SchoolRegisterRequest(**json.loads(pending.payload_json))
    try:
        school, owner = await _create_school_and_owner(db, registration_payload)
        await db.delete(pending)
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail='School or owner already exists') from exc
    await db.refresh(owner)
    await db.refresh(school)
    auth_response = await _issue_auth_response(db, response, request, owner, school)
    await db.commit()
    return auth_response

@router.post('/login', response_model=AuthResponse)
async def login(payload: LoginRequest, response: Response, request: Request, db: AsyncSession=Depends(get_async_db)):
    login_identifier = payload.login_id or (str(payload.email).lower() if payload.email else '')
    if not login_identifier.strip():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_LOGIN_ERROR)
    school = await _school_by_code(db, payload.school_code)
    if not school:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_LOGIN_ERROR)
    user = await _find_user_for_login(db, school.id, login_identifier)
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_LOGIN_ERROR)
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Account is inactive. Contact your school admin.')
    selected_role = (payload.selected_role or '').strip().upper()
    allowed_roles = LOGIN_ROLE_GROUPS.get(selected_role)
    if allowed_roles and user.role not in allowed_roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"This account is registered as {user.role.replace('_', ' ').title()}. Please select the correct portal tab.")
    user.last_login_at = datetime.utcnow()
    user.failed_login_attempts = 0
    auth_response = await _issue_auth_response(db, response, request, user, school)
    await db.commit()
    return auth_response


@router.post('/refresh', response_model=TokenRefreshResponse)
async def refresh_access_token(request: Request, response: Response, db: AsyncSession=Depends(get_async_db)):
    raw_refresh_token = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    if not raw_refresh_token:
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Refresh token is missing')

    stored_token = await _find_valid_refresh_token(db, raw_refresh_token)
    if not stored_token:
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Refresh token is invalid or expired')

    user = await db.get(User, stored_token.user_id)
    if not user or not user.is_active:
        stored_token.revoked_at = datetime.utcnow()
        await db.commit()
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='User not found or inactive')

    now = datetime.utcnow()
    stored_token.revoked_at = now
    stored_token.last_used_at = now
    new_refresh_token, new_record = await _create_refresh_token_record(db, user, request)
    await db.flush()
    stored_token.replaced_by_token_id = new_record.id
    await db.commit()

    _set_refresh_cookie(response, new_refresh_token)
    access_token = create_access_token(user.id, {'role': user.role, 'school_id': user.school_id})
    return TokenRefreshResponse(
        access_token=access_token,
        expires_in=_access_token_expires_in_seconds(),
    )


@router.post('/logout', response_model=MessageResponse)
async def logout(request: Request, response: Response, db: AsyncSession=Depends(get_async_db)):
    raw_refresh_token = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    if raw_refresh_token:
        stored_token = await async_query(db, RefreshToken).filter(
            RefreshToken.token_hash == hash_token(raw_refresh_token),
            RefreshToken.revoked_at.is_(None),
        ).first()
        if stored_token:
            stored_token.revoked_at = datetime.utcnow()
            stored_token.last_used_at = datetime.utcnow()
            await db.commit()

    _clear_refresh_cookie(response)
    return {'message': 'Logged out successfully'}

@router.get('/me', response_model=AuthResponse)
async def me(current_user: User=Depends(get_current_user), db: AsyncSession=Depends(get_async_db)):
    school = await db.get(School, current_user.school_id) if current_user.school_id else None
    token = create_access_token(current_user.id, {'role': current_user.role, 'school_id': current_user.school_id})
    user_public = await _build_user_public(db, current_user)
    return AuthResponse(access_token=token, expires_in=_access_token_expires_in_seconds(), user=user_public, school=school)

@router.post('/change-password', response_model=MessageResponse)
async def change_password(payload: ChangePasswordRequest, current_user: User=Depends(get_current_user), db: AsyncSession=Depends(get_async_db)):
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Current password is incorrect')
    current_user.hashed_password = get_password_hash(payload.new_password)
    current_user.must_change_password = False
    current_user.password_reset_token_hash = None
    current_user.password_reset_expires_at = None
    await db.commit()
    return {'message': 'Password changed successfully'}

@router.post('/forgot-password', response_model=ForgotPasswordResponse)
async def forgot_password(payload: ForgotPasswordRequest, db: AsyncSession=Depends(get_async_db)):
    school = await _school_by_code(db, payload.school_code)
    token: str | None = None
    reset_url: str | None = None
    if school:
        user = await _find_user_for_login(db, school.id, payload.login_id)
        if user and user.is_active:
            token = generate_reset_token()
            reset_url = _build_reset_url(token)
            user.password_reset_token_hash = _hash_reset_token(token)
            user.password_reset_expires_at = datetime.utcnow() + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)
            await db.commit()
            try:
                send_password_reset_email(user.email, reset_url, user.full_name)
            except EmailNotConfiguredError as exc:
                if not settings.EMAIL_OTP_DEBUG:
                    raise HTTPException(status_code=500, detail=str(exc)) from exc
            except Exception as exc:
                if not settings.EMAIL_OTP_DEBUG:
                    raise HTTPException(status_code=500, detail='Failed to send password reset email') from exc
    return ForgotPasswordResponse(message=GENERIC_RESET_MESSAGE, reset_token=token if settings.EMAIL_OTP_DEBUG else None, reset_url=reset_url if settings.EMAIL_OTP_DEBUG else None)

@router.post('/reset-password', response_model=MessageResponse)
async def reset_password(payload: ResetPasswordRequest, db: AsyncSession=Depends(get_async_db)):
    token_hash = _hash_reset_token(payload.token)
    user = await async_query(db, User).filter(User.password_reset_token_hash == token_hash).first()
    if not user or not user.password_reset_expires_at or user.password_reset_expires_at < datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid or expired reset link')
    user.hashed_password = get_password_hash(payload.new_password)
    user.must_change_password = False
    user.password_reset_token_hash = None
    user.password_reset_expires_at = None
    await async_query(db, RefreshToken).filter(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None)).update({'revoked_at': datetime.utcnow()})
    await db.commit()
    return {'message': 'Password reset successfully. You can login with your new password.'}
