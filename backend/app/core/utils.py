import re
import secrets
import string
from uuid import uuid4


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"(^-|-$)", "", value)
    return value or f"school-{uuid4().hex[:8]}"


def normalize_school_code(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.strip().upper())


def build_school_code(name_or_slug: str, counter: int | None = None) -> str:
    base = re.sub(r"[^A-Z0-9]", "", name_or_slug.upper())[:8]
    if not base:
        base = f"SCH{uuid4().hex[:5].upper()}"
    if counter is not None and counter > 1:
        suffix = str(counter)
        return f"{base[: max(3, 10 - len(suffix))]}{suffix}"
    return base


def normalize_login_id(value: str) -> str:
    value = value.strip()
    if "@" in value:
        return value.lower()
    return re.sub(r"\s+", "", value).upper()


def generate_temporary_password(length: int = 10) -> str:
    # Avoid confusing characters like O/0 and I/l for school admin copy-paste.
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_reset_token() -> str:
    return secrets.token_urlsafe(32)


def generate_numeric_otp(length: int = 6) -> str:
    return "".join(secrets.choice(string.digits) for _ in range(length))
