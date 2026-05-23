import cloudinary
import cloudinary.uploader

from app.core.config import (
    CLOUDINARY_CLOUD_NAME,
    CLOUDINARY_API_KEY,
    CLOUDINARY_API_SECRET
)

cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET
)


def upload_file(
    file,
    folder: str,
    resource_type: str = "auto"
) -> dict:
    """
    Upload a file to Cloudinary.

    Returns dict with:
        - url: secure delivery URL
        - public_id: used later for deletion
    """
    result = cloudinary.uploader.upload(
        file,
        folder=folder,
        resource_type=resource_type
    )

    return {
        "url": result.get("secure_url"),
        "public_id": result.get("public_id")
    }


def delete_file(
    public_id: str,
    resource_type: str = "auto"
) -> bool:
    """
    Delete a file from Cloudinary by its public_id.
    Returns True if deleted successfully.
    """
    if not public_id:
        return False

    result = cloudinary.uploader.destroy(
        public_id,
        resource_type=resource_type
    )

    return result.get("result") == "ok"