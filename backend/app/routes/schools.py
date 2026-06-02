from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.utils import normalize_school_code
from app.dependencies.auth import current_school_id, get_current_user, require_school_admin
from app.models.branding import SchoolBranding
from app.models.school import School
from app.models.user import User
from app.schemas.school import (
    DEFAULT_LOGO_THEME,
    LogoUploadResponse,
    SchoolBrandingPublic,
    SchoolBrandingRead,
    SchoolBrandingUpdate,
    SchoolRead,
    SchoolUpdate,
)

router = APIRouter(prefix="/schools", tags=["Schools"])

UPLOAD_ROOT = Path(__file__).resolve().parents[2] / "uploads"
ALLOWED_LOGO_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_LOGO_MIME_TYPES = {"image/png", "image/jpeg", "image/webp"}
MAX_LOGO_BYTES = 3 * 1024 * 1024


def _get_or_create_branding(db: Session, school: School) -> SchoolBranding:
    branding = db.query(SchoolBranding).filter(SchoolBranding.school_id == school.id).first()
    if branding:
        if school.logo_url and not branding.logo_url:
            branding.logo_url = school.logo_url
            db.commit()
            db.refresh(branding)
        return branding

    branding = SchoolBranding(
        school_id=school.id,
        logo_url=school.logo_url,
        **DEFAULT_LOGO_THEME,
    )
    db.add(branding)
    db.commit()
    db.refresh(branding)
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


@router.get("/branding/by-code/{school_code}", response_model=SchoolBrandingPublic)
def get_public_branding_by_school_code(school_code: str, db: Session = Depends(get_db)):
    school = (
        db.query(School)
        .filter(School.school_code == normalize_school_code(school_code), School.is_active.is_(True))
        .first()
    )
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    branding = _get_or_create_branding(db, school)
    return _public_branding_payload(school, branding)


@router.get("/branding/me", response_model=SchoolBrandingRead)
def get_my_school_branding(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.school_id:
        raise HTTPException(status_code=400, detail="User is not linked to a school")
    school = db.get(School, current_user.school_id)
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    return _get_or_create_branding(db, school)


@router.put("/branding/me", response_model=SchoolBrandingRead)
def update_my_school_branding(
    payload: SchoolBrandingUpdate,
    current_user: User = Depends(require_school_admin),
    db: Session = Depends(get_db),
):
    school = db.get(School, current_user.school_id)
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    branding = _get_or_create_branding(db, school)

    values = payload.model_dump(exclude_unset=True)
    for key, value in values.items():
        setattr(branding, key, value)

    if "logo_url" in values:
        school.logo_url = values["logo_url"]

    db.commit()
    db.refresh(branding)
    return branding


@router.post("/branding/logo", response_model=LogoUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_school_logo(
    file: UploadFile = File(...),
    current_user: User = Depends(require_school_admin),
    db: Session = Depends(get_db),
):
    school = db.get(School, current_user.school_id)
    if not school:
        raise HTTPException(status_code=404, detail="School not found")

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_LOGO_EXTENSIONS or file.content_type not in ALLOWED_LOGO_MIME_TYPES:
        raise HTTPException(status_code=400, detail="Upload a PNG, JPG, JPEG, or WEBP logo")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Logo file is empty")
    if len(content) > MAX_LOGO_BYTES:
        raise HTTPException(status_code=400, detail="Logo must be 3 MB or smaller")

    target_dir = UPLOAD_ROOT / "schools" / str(school.id) / "branding"
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"logo-{uuid4().hex}{suffix}"
    target_path = target_dir / safe_name
    target_path.write_bytes(content)

    logo_url = f"/uploads/schools/{school.id}/branding/{safe_name}"
    branding = _get_or_create_branding(db, school)
    branding.logo_url = logo_url
    branding.theme_source = "manual" if branding.theme_source == "preset" else branding.theme_source
    school.logo_url = logo_url
    db.commit()
    db.refresh(branding)

    return LogoUploadResponse(logo_url=logo_url, branding=branding)


@router.get("/me", response_model=SchoolRead)
def get_my_school(school_id: int = Depends(current_school_id), db: Session = Depends(get_db)):
    school = db.get(School, school_id)
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    return school


@router.put("/me", response_model=SchoolRead)
def update_my_school(
    payload: SchoolUpdate,
    current_user: User = Depends(require_school_admin),
    db: Session = Depends(get_db),
):
    school = db.get(School, current_user.school_id)
    if not school:
        raise HTTPException(status_code=404, detail="School not found")

    values = payload.model_dump(exclude_unset=True)
    if "school_code" in values and values["school_code"]:
        values["school_code"] = normalize_school_code(values["school_code"])
        duplicate = db.query(School).filter(School.school_code == values["school_code"], School.id != school.id).first()
        if duplicate:
            raise HTTPException(status_code=409, detail="School code is already taken")

    for key, value in values.items():
        setattr(school, key, value)

    if "logo_url" in values:
        branding = _get_or_create_branding(db, school)
        branding.logo_url = values["logo_url"]

    db.commit()
    db.refresh(school)
    return school
