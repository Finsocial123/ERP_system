from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.utils import normalize_school_code
from app.dependencies.auth import current_school_id, require_school_admin
from app.models.school import School
from app.models.user import User
from app.schemas.school import SchoolRead, SchoolUpdate

router = APIRouter(prefix="/schools", tags=["Schools"])


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
    db.commit()
    db.refresh(school)
    return school
