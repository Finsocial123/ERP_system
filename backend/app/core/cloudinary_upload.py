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


async def upload_school_logo_to_cloudinary(*, school_id: int, content: bytes, content_type: str) -> str:
    """Upload a school logo to Cloudinary and return the secure URL."""
    _ensure_cloudinary_configured()

    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
        secure=True,
    )

    encoded = base64.b64encode(content).decode("ascii")
    data_uri = f"data:{content_type};base64,{encoded}"
    folder = f"school-erp/schools/{school_id}/branding"
    public_id = f"logo-{uuid4().hex}"

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
            detail="Cloudinary logo upload failed",
        ) from exc

    secure_url = result.get("secure_url") or result.get("url")
    if not secure_url:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Cloudinary did not return a logo URL",
        )
    return str(secure_url)
