import base64
from uuid import uuid4

import cloudinary
import cloudinary.uploader
from fastapi import HTTPException, status
from starlette.concurrency import run_in_threadpool

from app.core.config import settings


def _ensure_cloudinary_configured() -> None:
    missing = [
        name
        for name, value in {
            "CLOUDINARY_CLOUD_NAME": settings.CLOUDINARY_CLOUD_NAME,
            "CLOUDINARY_API_KEY": settings.CLOUDINARY_API_KEY,
            "CLOUDINARY_API_SECRET": settings.CLOUDINARY_API_SECRET,
        }.items()
        if not value
    ]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cloudinary is not configured. Missing: {', '.join(missing)}",
        )


def _configure_cloudinary() -> None:
    _ensure_cloudinary_configured()
    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
        secure=True,
    )


async def upload_image_to_cloudinary(
    *,
    content: bytes,
    content_type: str,
    folder: str,
    public_id_prefix: str,
    failure_label: str = "image",
) -> str:
    """Upload an image byte payload to Cloudinary and return the secure URL."""
    _configure_cloudinary()

    encoded = base64.b64encode(content).decode("ascii")
    data_uri = f"data:{content_type};base64,{encoded}"
    public_id = f"{public_id_prefix}-{uuid4().hex}"

    try:
        result = await run_in_threadpool(
            cloudinary.uploader.upload,
            data_uri,
            folder=folder,
            public_id=public_id,
            resource_type="image",
            overwrite=False,
        )
    except Exception as exc:  # Cloudinary SDK raises provider-specific exceptions
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Cloudinary {failure_label} upload failed",
        ) from exc

    secure_url = result.get("secure_url") or result.get("url")
    if not secure_url:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Cloudinary did not return a {failure_label} URL",
        )
    return str(secure_url)


async def upload_school_logo_to_cloudinary(*, school_id: int, content: bytes, content_type: str) -> str:
    """Upload a school logo to Cloudinary and return the secure URL."""
    return await upload_image_to_cloudinary(
        content=content,
        content_type=content_type,
        folder=f"school-erp/schools/{school_id}/branding",
        public_id_prefix="logo",
        failure_label="logo",
    )


async def upload_teacher_profile_photo_to_cloudinary(
    *,
    school_id: int,
    teacher_id: int,
    content: bytes,
    content_type: str,
) -> str:
    """Upload a teacher profile photo to Cloudinary and return the secure URL."""
    return await upload_image_to_cloudinary(
        content=content,
        content_type=content_type,
        folder=f"school-erp/schools/{school_id}/teachers/{teacher_id}/profile",
        public_id_prefix="profile-photo",
        failure_label="teacher profile photo",
    )
