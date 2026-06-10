"""
schools.py — patched to cache school branding.

Changes vs original
--------------------
* GET /branding/by-code/{school_code}  — served from Redis (TTL 15 min)
* GET /branding/me                     — served from Redis (TTL 15 min)
* PUT /branding/me                     — invalidates both branding keys
* POST /branding/logo                  — invalidates both branding keys
* PUT /me                              — invalidates school + branding keys

The `get_my_school` endpoint is NOT cached because it is only called in
the admin settings panel; the marginal gain does not justify the added
invalidation surface.
"""

from pathlib import Path
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from app.core.database import get_async_db
from app.core.utils import normalize_school_code
from app.core.cloudinary_upload import upload_school_logo_to_cloudinary
from app.dependencies.auth import current_school_id, get_current_user, require_school_admin
from app.models.branding import SchoolBranding
from app.models.school import School
from app.models.user import User
from app.schemas.school import (
    DEFAULT_LOGO_THEME, LogoUploadResponse, SchoolBrandingPublic,
    SchoolBrandingRead, SchoolBrandingUpdate, SchoolRead, SchoolUpdate,
)
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.async_query import async_query
from app.services.cache import cache                        # ← NEW

router = APIRouter(prefix='/schools', tags=['Schools'])
ALLOWED_LOGO_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}
ALLOWED_LOGO_MIME_TYPES = {'image/png', 'image/jpeg', 'image/webp'}
MAX_LOGO_BYTES = 3 * 1024 * 1024


async def _get_or_create_branding(db: AsyncSession, school: School) -> SchoolBranding:
    branding = await async_query(db, SchoolBranding).filter(SchoolBranding.school_id == school.id).first()
    if branding:
        if school.logo_url and (not branding.logo_url):
            branding.logo_url = school.logo_url
            await db.commit()
            await db.refresh(branding)
        return branding
    branding = SchoolBranding(school_id=school.id, logo_url=school.logo_url, **DEFAULT_LOGO_THEME)
    db.add(branding)
    await db.commit()
    await db.refresh(branding)
    return branding


def _public_branding_payload(school: School, branding: SchoolBranding) -> SchoolBrandingPublic:
    return SchoolBrandingPublic(
        school_name=school.name,
        school_code=school.school_code,
        logo_url=branding.logo_url or school.logo_url,
        primary_color=branding.primary_color,
        secondary_color=branding.secondary_color,
        accent_color=branding.accent_color,
        sidebar_color=branding.sidebar_color,
        background_color=branding.background_color,
        text_color=branding.text_color,
        theme_mode=branding.theme_mode,
        theme_source=branding.theme_source,
        preset_name=branding.preset_name,
        border_radius=branding.border_radius,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get('/branding/by-code/{school_code}', response_model=SchoolBrandingPublic)
async def get_public_branding_by_school_code(
    school_code: str,
    db: AsyncSession = Depends(get_async_db),
):
    normalized = normalize_school_code(school_code)

    # Cache hit
    cached = await cache.get_branding_by_code(normalized)
    if cached is not None:
        return cached

    # Cache miss
    school = await async_query(db, School).filter(
        School.school_code == normalized, School.is_active.is_(True)
    ).first()
    if not school:
        raise HTTPException(status_code=404, detail='School not found')
    branding = await _get_or_create_branding(db, school)
    payload = _public_branding_payload(school, branding)
    data = payload.model_dump()

    await cache.set_branding_by_code(normalized, data)
    return data


@router.get('/branding/me', response_model=SchoolBrandingRead)
async def get_my_school_branding(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    if not current_user.school_id:
        raise HTTPException(status_code=400, detail='User is not linked to a school')

    # Cache hit
    cached = await cache.get_branding(current_user.school_id)
    if cached is not None:
        return cached

    # Cache miss
    school = await db.get(School, current_user.school_id)
    if not school:
        raise HTTPException(status_code=404, detail='School not found')
    branding = await _get_or_create_branding(db, school)
    data = SchoolBrandingRead.model_validate(branding).model_dump()

    await cache.set_branding(current_user.school_id, data)
    return data


@router.put('/branding/me', response_model=SchoolBrandingRead)
async def update_my_school_branding(
    payload: SchoolBrandingUpdate,
    current_user: User = Depends(require_school_admin),
    db: AsyncSession = Depends(get_async_db),
):
    school = await db.get(School, current_user.school_id)
    if not school:
        raise HTTPException(status_code=404, detail='School not found')
    branding = await _get_or_create_branding(db, school)
    values = payload.model_dump(exclude_unset=True)
    for key, value in values.items():
        setattr(branding, key, value)
    if 'logo_url' in values:
        school.logo_url = values['logo_url']
    await db.commit()
    await db.refresh(branding)

    # Invalidate
    await cache.invalidate_branding(current_user.school_id, school.school_code)

    return branding


@router.post('/branding/logo', response_model=LogoUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_school_logo(
    file: UploadFile = File(...),
    current_user: User = Depends(require_school_admin),
    db: AsyncSession = Depends(get_async_db),
):
    school = await db.get(School, current_user.school_id)
    if not school:
        raise HTTPException(status_code=404, detail='School not found')
    suffix = Path(file.filename or '').suffix.lower()
    if suffix not in ALLOWED_LOGO_EXTENSIONS or file.content_type not in ALLOWED_LOGO_MIME_TYPES:
        raise HTTPException(status_code=400, detail='Upload a PNG, JPG, JPEG, or WEBP logo')
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail='Logo file is empty')
    if len(content) > MAX_LOGO_BYTES:
        raise HTTPException(status_code=400, detail='Logo must be 3 MB or smaller')
    logo_url = await upload_school_logo_to_cloudinary(
        school_id=school.id,
        content=content,
        content_type=file.content_type or 'image/png',
    )
    branding = await _get_or_create_branding(db, school)
    branding.logo_url = logo_url
    branding.theme_source = 'manual' if branding.theme_source == 'preset' else branding.theme_source
    school.logo_url = logo_url
    await db.commit()
    await db.refresh(branding)

    # Invalidate
    await cache.invalidate_branding(current_user.school_id, school.school_code)

    return LogoUploadResponse(logo_url=logo_url, branding=branding)


@router.get('/me', response_model=SchoolRead)
async def get_my_school(
    school_id: int = Depends(current_school_id),
    db: AsyncSession = Depends(get_async_db),
):
    school = await db.get(School, school_id)
    if not school:
        raise HTTPException(status_code=404, detail='School not found')
    return school


@router.put('/me', response_model=SchoolRead)
async def update_my_school(
    payload: SchoolUpdate,
    current_user: User = Depends(require_school_admin),
    db: AsyncSession = Depends(get_async_db),
):
    school = await db.get(School, current_user.school_id)
    if not school:
        raise HTTPException(status_code=404, detail='School not found')
    values = payload.model_dump(exclude_unset=True)
    if 'school_code' in values and values['school_code']:
        values['school_code'] = normalize_school_code(values['school_code'])
        duplicate = await async_query(db, School).filter(
            School.school_code == values['school_code'], School.id != school.id
        ).first()
        if duplicate:
            raise HTTPException(status_code=409, detail='School code is already taken')
    old_code = school.school_code
    for key, value in values.items():
        setattr(school, key, value)
    if 'logo_url' in values:
        branding = await _get_or_create_branding(db, school)
        branding.logo_url = values['logo_url']
    await db.commit()
    await db.refresh(school)

    # Invalidate branding (school name/code/logo may have changed)
    await cache.invalidate_branding(current_user.school_id, old_code)
    if school.school_code != old_code:
        await cache.invalidate_branding(current_user.school_id, school.school_code)

    return school
