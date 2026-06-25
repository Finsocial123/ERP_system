"""Class-level section helpers.

Sections are now owned by SchoolClass.sections (comma/newline separated names).
The legacy sections table/section_id columns are kept only during migration so
old data and foreign keys do not break. New feature logic should validate and
filter by section_name.
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.async_query import async_query
from app.models.academic import SchoolClass

MAX_SECTION_NAME_LENGTH = 80
VIRTUAL_SECTION_BASE = 1_000_000


@dataclass(frozen=True)
class ClassSectionOption:
    id: int
    name: str
    class_id: int
    academic_session_id: int | None = None
    is_active: bool = True
    extra: str | None = None


def parse_section_names(value: str | None) -> list[str]:
    if not value:
        return []
    names: list[str] = []
    seen: set[str] = set()
    for raw in value.replace(";", ",").replace("\n", ",").split(","):
        name = raw.strip()
        if not name:
            continue
        name = name[:MAX_SECTION_NAME_LENGTH]
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        names.append(name)
    return names


def format_section_names(value: str | list[str] | None) -> str | None:
    names = parse_section_names(value) if isinstance(value, str) or value is None else parse_section_names(",".join(value))
    return ", ".join(names) if names else None


def virtual_section_id(class_id: int, index: int) -> int:
    """Stable UI id for a section name without depending on sections.id."""
    return (class_id * VIRTUAL_SECTION_BASE) + index + 1


def _virtual_index(class_id: int, section_id: int) -> int | None:
    base = class_id * VIRTUAL_SECTION_BASE
    index = section_id - base - 1
    return index if index >= 0 else None


async def class_section_options(
    db: AsyncSession,
    school_id: int,
    session_id: int | None = None,
    class_id: int | None = None,
) -> list[ClassSectionOption]:
    query = async_query(db, SchoolClass).filter(
        SchoolClass.school_id == school_id,
        SchoolClass.is_active.is_(True),
    )
    if session_id is not None:
        query = query.filter(SchoolClass.academic_session_id == session_id)
    if class_id is not None:
        query = query.filter(SchoolClass.id == class_id)
    classes = await query.order_by(SchoolClass.name.asc()).all()
    rows: list[ClassSectionOption] = []
    for school_class in classes:
        for index, name in enumerate(parse_section_names(school_class.sections)):
            rows.append(
                ClassSectionOption(
                    id=virtual_section_id(school_class.id, index),
                    name=name,
                    class_id=school_class.id,
                    academic_session_id=school_class.academic_session_id,
                    is_active=True,
                    extra=str(school_class.id),
                )
            )
    return rows


async def validate_class_section_name(
    db: AsyncSession,
    school_id: int,
    class_id: int | None,
    section_name: str | None = None,
    section_id: int | None = None,
    session_id: int | None = None,
) -> str | None:
    """Return canonical section name from SchoolClass.sections.

    Accepts section_name directly or the virtual section_id emitted by /sections
    and metadata endpoints. Returns None for "All sections".
    """
    if class_id is None:
        if section_name or section_id is not None:
            raise HTTPException(status_code=400, detail="Class is required before selecting a section")
        return None

    school_class = await async_query(db, SchoolClass).filter(
        SchoolClass.id == class_id,
        SchoolClass.school_id == school_id,
    ).first()
    if not school_class:
        raise HTTPException(status_code=404, detail="Class not found for this school")
    if session_id is not None and school_class.academic_session_id not in (None, session_id):
        raise HTTPException(status_code=400, detail="Selected class does not belong to the selected academic session")

    names = parse_section_names(school_class.sections)
    if section_name is not None and str(section_name).strip() != "":
        wanted = str(section_name).strip().casefold()
        for name in names:
            if name.casefold() == wanted:
                return name
        raise HTTPException(status_code=400, detail="Selected section does not belong to selected class")

    if section_id is not None:
        index = _virtual_index(class_id, section_id)
        if index is None or index >= len(names):
            raise HTTPException(status_code=400, detail="Selected section does not belong to selected class")
        return names[index]

    return None


def same_section(a: str | None, b: str | None) -> bool:
    return (a or "").strip().casefold() == (b or "").strip().casefold()

async def virtual_section_id_for_name(
    db: AsyncSession,
    school_id: int,
    class_id: int | None,
    section_name: str | None,
    session_id: int | None = None,
) -> int | None:
    if class_id is None or not section_name:
        return None
    for option in await class_section_options(db, school_id, session_id=session_id, class_id=class_id):
        if same_section(option.name, section_name):
            return option.id
    return None
