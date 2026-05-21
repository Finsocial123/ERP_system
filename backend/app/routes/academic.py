from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import current_school_id, require_school_admin
from app.models.academic import AcademicSession, Department, SchoolClass, Section, Subject
from app.models.user import User
from app.schemas.academic import (
    AcademicSessionCreate,
    AcademicSessionRead,
    AcademicSessionUpdate,
    ClassCreate,
    ClassRead,
    ClassUpdate,
    DepartmentCreate,
    DepartmentRead,
    DepartmentUpdate,
    SectionCreate,
    SectionRead,
    SectionUpdate,
    SubjectCreate,
    SubjectRead,
    SubjectUpdate,
)
from app.schemas.common import MessageResponse

router = APIRouter(tags=["Academic Setup"])


def _get_or_404(db: Session, model, item_id: int, school_id: int):
    item = db.query(model).filter(model.id == item_id, model.school_id == school_id).first()
    if not item:
        raise HTTPException(status_code=404, detail=f"{model.__name__} not found")
    return item


def _apply_updates(instance, payload):
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(instance, key, value)


def _validate_department(db: Session, department_id: int | None, school_id: int):
    if department_id is not None:
        _get_or_404(db, Department, department_id, school_id)


def _validate_class(db: Session, class_id: int | None, school_id: int):
    if class_id is not None:
        _get_or_404(db, SchoolClass, class_id, school_id)


# Academic sessions
@router.get("/academic-sessions", response_model=list[AcademicSessionRead])
def list_sessions(
    school_id: int = Depends(current_school_id),
    db: Session = Depends(get_db),
):
    return db.query(AcademicSession).filter(AcademicSession.school_id == school_id).order_by(AcademicSession.id.desc()).all()


@router.post("/academic-sessions", response_model=AcademicSessionRead, status_code=status.HTTP_201_CREATED)
def create_session(
    payload: AcademicSessionCreate,
    current_user: User = Depends(require_school_admin),
    db: Session = Depends(get_db),
):
    if payload.is_active:
        db.query(AcademicSession).filter(AcademicSession.school_id == current_user.school_id).update({"is_active": False})
    item = AcademicSession(school_id=current_user.school_id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/academic-sessions/{item_id}", response_model=AcademicSessionRead)
def update_session(
    item_id: int,
    payload: AcademicSessionUpdate,
    current_user: User = Depends(require_school_admin),
    db: Session = Depends(get_db),
):
    item = _get_or_404(db, AcademicSession, item_id, current_user.school_id)
    if payload.is_active is True:
        db.query(AcademicSession).filter(AcademicSession.school_id == current_user.school_id).update({"is_active": False})
    _apply_updates(item, payload)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/academic-sessions/{item_id}", response_model=MessageResponse)
def delete_session(item_id: int, current_user: User = Depends(require_school_admin), db: Session = Depends(get_db)):
    item = _get_or_404(db, AcademicSession, item_id, current_user.school_id)
    db.delete(item)
    db.commit()
    return {"message": "Academic session deleted"}


# Departments
@router.get("/departments", response_model=list[DepartmentRead])
def list_departments(school_id: int = Depends(current_school_id), db: Session = Depends(get_db)):
    return db.query(Department).filter(Department.school_id == school_id).order_by(Department.id.desc()).all()


@router.post("/departments", response_model=DepartmentRead, status_code=status.HTTP_201_CREATED)
def create_department(payload: DepartmentCreate, current_user: User = Depends(require_school_admin), db: Session = Depends(get_db)):
    item = Department(school_id=current_user.school_id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/departments/{item_id}", response_model=DepartmentRead)
def update_department(item_id: int, payload: DepartmentUpdate, current_user: User = Depends(require_school_admin), db: Session = Depends(get_db)):
    item = _get_or_404(db, Department, item_id, current_user.school_id)
    _apply_updates(item, payload)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/departments/{item_id}", response_model=MessageResponse)
def delete_department(item_id: int, current_user: User = Depends(require_school_admin), db: Session = Depends(get_db)):
    item = _get_or_404(db, Department, item_id, current_user.school_id)
    db.delete(item)
    db.commit()
    return {"message": "Department deleted"}


# Classes
@router.get("/classes", response_model=list[ClassRead])
def list_classes(school_id: int = Depends(current_school_id), db: Session = Depends(get_db)):
    return db.query(SchoolClass).filter(SchoolClass.school_id == school_id).order_by(SchoolClass.id.desc()).all()


@router.post("/classes", response_model=ClassRead, status_code=status.HTTP_201_CREATED)
def create_class(payload: ClassCreate, current_user: User = Depends(require_school_admin), db: Session = Depends(get_db)):
    _validate_department(db, payload.department_id, current_user.school_id)
    item = SchoolClass(school_id=current_user.school_id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/classes/{item_id}", response_model=ClassRead)
def update_class(item_id: int, payload: ClassUpdate, current_user: User = Depends(require_school_admin), db: Session = Depends(get_db)):
    item = _get_or_404(db, SchoolClass, item_id, current_user.school_id)
    if "department_id" in payload.model_dump(exclude_unset=True):
        _validate_department(db, payload.department_id, current_user.school_id)
    _apply_updates(item, payload)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/classes/{item_id}", response_model=MessageResponse)
def delete_class(item_id: int, current_user: User = Depends(require_school_admin), db: Session = Depends(get_db)):
    item = _get_or_404(db, SchoolClass, item_id, current_user.school_id)
    db.delete(item)
    db.commit()
    return {"message": "Class deleted"}


# Sections
@router.get("/sections", response_model=list[SectionRead])
def list_sections(
    class_id: int | None = Query(default=None),
    school_id: int = Depends(current_school_id),
    db: Session = Depends(get_db),
):
    query = db.query(Section).filter(Section.school_id == school_id)
    if class_id is not None:
        query = query.filter(Section.class_id == class_id)
    return query.order_by(Section.id.desc()).all()


@router.post("/sections", response_model=SectionRead, status_code=status.HTTP_201_CREATED)
def create_section(payload: SectionCreate, current_user: User = Depends(require_school_admin), db: Session = Depends(get_db)):
    _validate_class(db, payload.class_id, current_user.school_id)
    item = Section(school_id=current_user.school_id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/sections/{item_id}", response_model=SectionRead)
def update_section(item_id: int, payload: SectionUpdate, current_user: User = Depends(require_school_admin), db: Session = Depends(get_db)):
    item = _get_or_404(db, Section, item_id, current_user.school_id)
    if "class_id" in payload.model_dump(exclude_unset=True):
        _validate_class(db, payload.class_id, current_user.school_id)
    _apply_updates(item, payload)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/sections/{item_id}", response_model=MessageResponse)
def delete_section(item_id: int, current_user: User = Depends(require_school_admin), db: Session = Depends(get_db)):
    item = _get_or_404(db, Section, item_id, current_user.school_id)
    db.delete(item)
    db.commit()
    return {"message": "Section deleted"}


# Subjects
@router.get("/subjects", response_model=list[SubjectRead])
def list_subjects(school_id: int = Depends(current_school_id), db: Session = Depends(get_db)):
    return db.query(Subject).filter(Subject.school_id == school_id).order_by(Subject.id.desc()).all()


@router.post("/subjects", response_model=SubjectRead, status_code=status.HTTP_201_CREATED)
def create_subject(payload: SubjectCreate, current_user: User = Depends(require_school_admin), db: Session = Depends(get_db)):
    _validate_department(db, payload.department_id, current_user.school_id)
    _validate_class(db, payload.class_id, current_user.school_id)
    item = Subject(school_id=current_user.school_id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/subjects/{item_id}", response_model=SubjectRead)
def update_subject(item_id: int, payload: SubjectUpdate, current_user: User = Depends(require_school_admin), db: Session = Depends(get_db)):
    item = _get_or_404(db, Subject, item_id, current_user.school_id)
    values = payload.model_dump(exclude_unset=True)
    if "department_id" in values:
        _validate_department(db, payload.department_id, current_user.school_id)
    if "class_id" in values:
        _validate_class(db, payload.class_id, current_user.school_id)
    _apply_updates(item, payload)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/subjects/{item_id}", response_model=MessageResponse)
def delete_subject(item_id: int, current_user: User = Depends(require_school_admin), db: Session = Depends(get_db)):
    item = _get_or_404(db, Subject, item_id, current_user.school_id)
    db.delete(item)
    db.commit()
    return {"message": "Subject deleted"}
