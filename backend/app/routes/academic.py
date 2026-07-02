from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.async_query import async_query
from app.core.database import get_async_db
from app.core.sections import class_section_options, format_section_names, parse_section_names
from app.dependencies.academic_session import selected_academic_session_id, writable_selected_academic_session_id, assert_item_session_is_writable
from app.dependencies.auth import current_school_id, get_current_user, require_school_admin
from app.models.academic import AcademicSession, Department, SchoolClass, Section, Subject
from app.models.people import ClassTeacherAssignment, ParentGuardian, Student, Teacher, TeacherSubject
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


async def _get_or_404(db: AsyncSession, model, item_id: int, school_id: int):
    item = await async_query(db, model).filter(
        model.id == item_id,
        model.school_id == school_id,
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail=f"{model.__name__} not found")
    return item


def _apply_updates(instance, payload):
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(instance, key, value)


async def _commit_or_duplicate(db: AsyncSession, message: str):
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail=message)


async def _active_session(db: AsyncSession, school_id: int) -> AcademicSession | None:
    return await async_query(db, AcademicSession).filter(
        AcademicSession.school_id == school_id,
        AcademicSession.is_active.is_(True),
    ).order_by(AcademicSession.id.desc()).first()


async def _session_id_for_payload(
    db: AsyncSession,
    school_id: int,
    request: Request,
    current_user: User,
    payload_session_id: int | None,
) -> int | None:
    return await writable_selected_academic_session_id(
        db=db,
        school_id=school_id,
        request=request,
        current_user=current_user,
        explicit_session_id=payload_session_id,
    )


async def _validate_department(db: AsyncSession, department_id: int | None, school_id: int, session_id: int | None = None):
    if department_id is None:
        return None
    query = async_query(db, Department).filter(Department.id == department_id, Department.school_id == school_id)
    if session_id is not None:
        query = query.filter(Department.academic_session_id == session_id)
    item = await query.first()
    if not item:
        raise HTTPException(status_code=404, detail="Department not found for selected academic session")
    return item


async def _validate_class(db: AsyncSession, class_id: int | None, school_id: int, session_id: int | None = None):
    if class_id is None:
        return None
    query = async_query(db, SchoolClass).filter(SchoolClass.id == class_id, SchoolClass.school_id == school_id)
    if session_id is not None:
        query = query.filter(SchoolClass.academic_session_id == session_id)
    item = await query.first()
    if not item:
        raise HTTPException(status_code=404, detail="Class not found for selected academic session")
    return item




async def _replicate_previous_active_students(
    db: AsyncSession,
    school_id: int,
    source_session_id: int | None,
    target_session_id: int,
    class_map: dict[int, int],
    section_map: dict[int, int],
) -> None:
    """Copy active student rows into the new academic session.

    The new session gets its own Student rows, so edits like class/section change
    stay isolated from the previous session. Guardian rows are also copied so
    guardian edits in the new session do not mutate older-session records. Login
    users are intentionally reused, so students/parents keep the same credentials.
    """
    if not source_session_id or source_session_id == target_session_id:
        return

    existing_admission_numbers = {
        row.admission_no
        for row in await async_query(db, Student).filter(
            Student.school_id == school_id,
            Student.academic_session_id == target_session_id,
        ).all()
    }

    students = await async_query(db, Student).options(selectinload(Student.guardian)).filter(
        Student.school_id == school_id,
        Student.academic_session_id == source_session_id,
        Student.is_active.is_(True),
    ).order_by(Student.id.asc()).all()

    for old in students:
        if old.admission_no in existing_admission_numbers:
            continue

        new_guardian_id = None
        if old.guardian:
            guardian = ParentGuardian(
                school_id=school_id,
                user_id=old.guardian.user_id,
                full_name=old.guardian.full_name,
                relation=old.guardian.relation,
                email=old.guardian.email,
                phone=old.guardian.phone,
                alternate_phone=old.guardian.alternate_phone,
                occupation=old.guardian.occupation,
                address=old.guardian.address,
                is_active=old.guardian.is_active,
            )
            db.add(guardian)
            await db.flush()
            new_guardian_id = guardian.id

        db.add(Student(
            school_id=school_id,
            academic_session_id=target_session_id,
            user_id=old.user_id,
            guardian_id=new_guardian_id,
            class_id=class_map.get(old.class_id) if old.class_id else None,
            section_id=section_map.get(old.section_id) if old.section_id else None,
            section_name=old.section_name,
            admission_no=old.admission_no,
            roll_number=old.roll_number,
            first_name=old.first_name,
            last_name=old.last_name,
            email=old.email,
            phone=old.phone,
            gender=old.gender,
            date_of_birth=old.date_of_birth,
            blood_group=old.blood_group,
            photo_url=old.photo_url,
            address=old.address,
            admission_date=old.admission_date,
            status=old.status,
            is_active=old.is_active,
        ))
        existing_admission_numbers.add(old.admission_no)


async def _replicate_previous_active_setup(
    db: AsyncSession,
    school_id: int,
    source_session_id: int | None,
    target_session_id: int,
) -> None:
    if not source_session_id or source_session_id == target_session_id:
        return

    dept_map: dict[int, int] = {}
    class_map: dict[int, int] = {}
    section_map: dict[int, int] = {}
    subject_map: dict[int, int] = {}
    teacher_map: dict[int, int] = {}

    departments = await async_query(db, Department).filter(
        Department.school_id == school_id,
        Department.academic_session_id == source_session_id,
        Department.is_active.is_(True),
    ).order_by(Department.id.asc()).all()
    for old in departments:
        new = Department(
            school_id=school_id,
            academic_session_id=target_session_id,
            name=old.name,
            code=old.code,
            description=old.description,
            is_active=old.is_active,
        )
        db.add(new)
        await db.flush()
        dept_map[old.id] = new.id

    classes = await async_query(db, SchoolClass).filter(
        SchoolClass.school_id == school_id,
        SchoolClass.academic_session_id == source_session_id,
        SchoolClass.is_active.is_(True),
    ).order_by(SchoolClass.id.asc()).all()
    for old in classes:
        new = SchoolClass(
            school_id=school_id,
            academic_session_id=target_session_id,
            department_id=dept_map.get(old.department_id) if old.department_id else None,
            name=old.name,
            code=old.code,
            sections=old.sections,
            is_active=old.is_active,
        )
        db.add(new)
        await db.flush()
        class_map[old.id] = new.id

    sections = await async_query(db, Section).filter(
        Section.school_id == school_id,
        Section.academic_session_id == source_session_id,
        Section.is_active.is_(True),
    ).order_by(Section.id.asc()).all()
    for old in sections:
        new_class_id = class_map.get(old.class_id)
        if not new_class_id:
            continue
        new = Section(
            school_id=school_id,
            academic_session_id=target_session_id,
            class_id=new_class_id,
            name=old.name,
            is_active=old.is_active,
        )
        db.add(new)
        await db.flush()
        section_map[old.id] = new.id

    subjects = await async_query(db, Subject).filter(
        Subject.school_id == school_id,
        Subject.academic_session_id == source_session_id,
        Subject.is_active.is_(True),
    ).order_by(Subject.id.asc()).all()
    for old in subjects:
        new_class_id = class_map.get(old.class_id) if old.class_id else None
        if not new_class_id:
            continue
        new = Subject(
            school_id=school_id,
            academic_session_id=target_session_id,
            department_id=dept_map.get(old.department_id) if old.department_id else None,
            class_id=new_class_id,
            name=old.name,
            code=old.code,
            sections=old.sections,
            is_active=old.is_active,
        )
        db.add(new)
        await db.flush()
        subject_map[old.id] = new.id

    teachers = await async_query(db, Teacher).filter(
        Teacher.school_id == school_id,
        Teacher.academic_session_id == source_session_id,
        Teacher.is_active.is_(True),
    ).order_by(Teacher.id.asc()).all()
    for old in teachers:
        new = Teacher(
            school_id=school_id,
            academic_session_id=target_session_id,
            user_id=old.user_id,
            department_id=dept_map.get(old.department_id) if old.department_id else None,
            employee_id=old.employee_id,
            full_name=old.full_name,
            email=old.email,
            phone=old.phone,
            gender=old.gender,
            qualification=old.qualification,
            specialization=old.specialization,
            joining_date=old.joining_date,
            photo_url=old.photo_url,
            address=old.address,
            status=old.status,
            is_active=old.is_active,
        )
        db.add(new)
        await db.flush()
        teacher_map[old.id] = new.id

    teacher_subjects = await async_query(db, TeacherSubject).filter(
        TeacherSubject.school_id == school_id,
        TeacherSubject.academic_session_id == source_session_id,
    ).order_by(TeacherSubject.id.asc()).all()
    for old in teacher_subjects:
        teacher_id = teacher_map.get(old.teacher_id)
        subject_id = subject_map.get(old.subject_id)
        if not teacher_id or not subject_id:
            continue
        db.add(TeacherSubject(
            school_id=school_id,
            academic_session_id=target_session_id,
            teacher_id=teacher_id,
            subject_id=subject_id,
            class_id=class_map.get(old.class_id) if old.class_id else None,
            section_id=section_map.get(old.section_id) if old.section_id else None,
        ))

    class_teachers = await async_query(db, ClassTeacherAssignment).filter(
        ClassTeacherAssignment.school_id == school_id,
        ClassTeacherAssignment.academic_session_id == source_session_id,
    ).order_by(ClassTeacherAssignment.id.asc()).all()
    for old in class_teachers:
        teacher_id = teacher_map.get(old.teacher_id)
        class_id = class_map.get(old.class_id)
        if not teacher_id or not class_id:
            continue
        db.add(ClassTeacherAssignment(
            school_id=school_id,
            academic_session_id=target_session_id,
            teacher_id=teacher_id,
            class_id=class_id,
            section_id=section_map.get(old.section_id) if old.section_id else None,
        ))

    await _replicate_previous_active_students(
        db=db,
        school_id=school_id,
        source_session_id=source_session_id,
        target_session_id=target_session_id,
        class_map=class_map,
        section_map=section_map,
    )


@router.get("/academic-sessions", response_model=list[AcademicSessionRead])
async def list_sessions(
    school_id: int = Depends(current_school_id),
    db: AsyncSession = Depends(get_async_db),
):
    return await async_query(db, AcademicSession).filter(
        AcademicSession.school_id == school_id,
    ).order_by(AcademicSession.id.desc()).all()


@router.post("/academic-sessions", response_model=AcademicSessionRead, status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: AcademicSessionCreate,
    current_user: User = Depends(require_school_admin),
    db: AsyncSession = Depends(get_async_db),
):
    source = await _active_session(db, current_user.school_id)
    if payload.is_active:
        await async_query(db, AcademicSession).filter(
            AcademicSession.school_id == current_user.school_id,
        ).update({"is_active": False})

    item = AcademicSession(school_id=current_user.school_id, **payload.model_dump())
    db.add(item)
    await _commit_or_duplicate(db, "Academic session with this name already exists")
    await db.refresh(item)

    # Newly created sessions start with the setup of the previous active session.
    await _replicate_previous_active_setup(db, current_user.school_id, source.id if source else None, item.id)
    await _commit_or_duplicate(db, "Session setup could not be replicated because duplicate setup data exists")
    await db.refresh(item)
    return item


@router.put("/academic-sessions/{item_id}", response_model=AcademicSessionRead)
async def update_session(
    item_id: int,
    payload: AcademicSessionUpdate,
    current_user: User = Depends(require_school_admin),
    db: AsyncSession = Depends(get_async_db),
):
    item = await _get_or_404(db, AcademicSession, item_id, current_user.school_id)
    if payload.is_active is True:
        await async_query(db, AcademicSession).filter(
            AcademicSession.school_id == current_user.school_id,
        ).update({"is_active": False})
    _apply_updates(item, payload)
    await _commit_or_duplicate(db, "Academic session with this name already exists")
    await db.refresh(item)
    return item


@router.delete("/academic-sessions/{item_id}", response_model=MessageResponse)
async def delete_session(
    item_id: int,
    current_user: User = Depends(require_school_admin),
    db: AsyncSession = Depends(get_async_db),
):
    item = await _get_or_404(db, AcademicSession, item_id, current_user.school_id)
    await db.delete(item)
    await db.commit()
    return {"message": "Academic session deleted"}


@router.get("/departments", response_model=list[DepartmentRead])
async def list_departments(
    request: Request,
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    session_id = await selected_academic_session_id(db, school_id, request=request, current_user=current_user)
    query = async_query(db, Department).filter(Department.school_id == school_id)
    if session_id is not None:
        query = query.filter(Department.academic_session_id == session_id)
    return await query.order_by(Department.id.desc()).all()


@router.post("/departments", response_model=DepartmentRead, status_code=status.HTTP_201_CREATED)
async def create_department(
    payload: DepartmentCreate,
    request: Request,
    current_user: User = Depends(require_school_admin),
    db: AsyncSession = Depends(get_async_db),
):
    session_id = await _session_id_for_payload(db, current_user.school_id, request, current_user, payload.academic_session_id)
    data = payload.model_dump()
    data["academic_session_id"] = session_id
    if "sections" in data:
        data["sections"] = format_section_names(data.get("sections"))
    item = Department(school_id=current_user.school_id, **data)
    db.add(item)
    await _commit_or_duplicate(db, "Department already exists in this academic session")
    await db.refresh(item)
    return item


@router.put("/departments/{item_id}", response_model=DepartmentRead)
async def update_department(
    item_id: int,
    payload: DepartmentUpdate,
    request: Request,
    current_user: User = Depends(require_school_admin),
    db: AsyncSession = Depends(get_async_db),
):
    item = await _get_or_404(db, Department, item_id, current_user.school_id)
    await assert_item_session_is_writable(db, current_user.school_id, item)
    values = payload.model_dump(exclude_unset=True)
    if "academic_session_id" in values:
        values["academic_session_id"] = await _session_id_for_payload(db, current_user.school_id, request, current_user, values.get("academic_session_id"))
    for key, value in values.items():
        setattr(item, key, value)
    await _commit_or_duplicate(db, "Department already exists in this academic session")
    await db.refresh(item)
    return item


@router.delete("/departments/{item_id}", response_model=MessageResponse)
async def delete_department(
    item_id: int,
    current_user: User = Depends(require_school_admin),
    db: AsyncSession = Depends(get_async_db),
):
    item = await _get_or_404(db, Department, item_id, current_user.school_id)
    await assert_item_session_is_writable(db, current_user.school_id, item)
    await db.delete(item)
    await db.commit()
    return {"message": "Department deleted"}


@router.get("/classes", response_model=list[ClassRead])
async def list_classes(
    request: Request,
    school_id: int = Depends(current_school_id),
    db: AsyncSession = Depends(get_async_db),
):
    session_id = await selected_academic_session_id(db, school_id, request=request)
    query = async_query(db, SchoolClass).filter(SchoolClass.school_id == school_id)
    if session_id is not None:
        query = query.filter(SchoolClass.academic_session_id == session_id)
    return await query.order_by(SchoolClass.id.desc()).all()


@router.post("/classes", response_model=ClassRead, status_code=status.HTTP_201_CREATED)
async def create_class(
    payload: ClassCreate,
    request: Request,
    current_user: User = Depends(require_school_admin),
    db: AsyncSession = Depends(get_async_db),
):
    session_id = await _session_id_for_payload(db, current_user.school_id, request, current_user, payload.academic_session_id)
    await _validate_department(db, payload.department_id, current_user.school_id, session_id)
    data = payload.model_dump()
    data["academic_session_id"] = session_id
    if "sections" in data:
        data["sections"] = format_section_names(data.get("sections"))
    item = SchoolClass(school_id=current_user.school_id, **data)
    db.add(item)
    await _commit_or_duplicate(db, "Class already exists in this academic session")
    await db.refresh(item)
    return item


@router.put("/classes/{item_id}", response_model=ClassRead)
async def update_class(
    item_id: int,
    payload: ClassUpdate,
    request: Request,
    current_user: User = Depends(require_school_admin),
    db: AsyncSession = Depends(get_async_db),
):
    item = await _get_or_404(db, SchoolClass, item_id, current_user.school_id)
    await assert_item_session_is_writable(db, current_user.school_id, item)
    values = payload.model_dump(exclude_unset=True)
    session_id = values.get("academic_session_id", item.academic_session_id)
    if "academic_session_id" in values:
        session_id = await _session_id_for_payload(db, current_user.school_id, request, current_user, values.get("academic_session_id"))
        values["academic_session_id"] = session_id
    if "department_id" in values:
        await _validate_department(db, values.get("department_id"), current_user.school_id, session_id)
    if "sections" in values:
        values["sections"] = format_section_names(values.get("sections"))
    for key, value in values.items():
        setattr(item, key, value)
    await _commit_or_duplicate(db, "Class already exists in this academic session")
    await db.refresh(item)
    return item


@router.delete("/classes/{item_id}", response_model=MessageResponse)
async def delete_class(
    item_id: int,
    current_user: User = Depends(require_school_admin),
    db: AsyncSession = Depends(get_async_db),
):
    item = await _get_or_404(db, SchoolClass, item_id, current_user.school_id)
    await assert_item_session_is_writable(db, current_user.school_id, item)
    await db.delete(item)
    await db.commit()
    return {"message": "Class deleted"}


@router.get("/sections", response_model=list[SectionRead])
async def list_sections(
    request: Request,
    class_id: int | None = Query(default=None),
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    session_id = await selected_academic_session_id(db, school_id, request=request, current_user=current_user)
    return await class_section_options(db, school_id, session_id=session_id, class_id=class_id)


async def _find_virtual_section_or_404(
    db: AsyncSession,
    school_id: int,
    item_id: int,
    session_id: int | None = None,
):
    for option in await class_section_options(db, school_id, session_id=session_id):
        if option.id == item_id:
            return option
    raise HTTPException(status_code=404, detail="Section not found in class sections")


@router.post("/sections", response_model=SectionRead, status_code=status.HTTP_201_CREATED)
async def create_section(
    payload: SectionCreate,
    request: Request,
    current_user: User = Depends(require_school_admin),
    db: AsyncSession = Depends(get_async_db),
):
    session_id = await _session_id_for_payload(db, current_user.school_id, request, current_user, payload.academic_session_id)
    school_class = await _validate_class(db, payload.class_id, current_user.school_id, session_id)
    names = parse_section_names(school_class.sections)
    if payload.name.strip().casefold() not in {name.casefold() for name in names}:
        names.append(payload.name.strip()[:80])
    school_class.sections = format_section_names(names)
    await _commit_or_duplicate(db, "Class sections could not be saved")
    option = (await class_section_options(db, current_user.school_id, session_id=session_id, class_id=school_class.id))[-1]
    return option


@router.put("/sections/{item_id}", response_model=SectionRead)
async def update_section(
    item_id: int,
    payload: SectionUpdate,
    request: Request,
    current_user: User = Depends(require_school_admin),
    db: AsyncSession = Depends(get_async_db),
):
    session_id = await _session_id_for_payload(db, current_user.school_id, request, current_user, payload.academic_session_id)
    option = await _find_virtual_section_or_404(db, current_user.school_id, item_id, session_id=session_id)
    target_class_id = payload.class_id or option.class_id
    school_class = await _validate_class(db, target_class_id, current_user.school_id, session_id)
    names = parse_section_names(school_class.sections)
    old_key = option.name.casefold()
    new_name = (payload.name or option.name).strip()[:80]
    names = [new_name if name.casefold() == old_key else name for name in names]
    school_class.sections = format_section_names(names)
    await _commit_or_duplicate(db, "Class sections could not be saved")
    updated = [row for row in await class_section_options(db, current_user.school_id, session_id=session_id, class_id=school_class.id) if row.name.casefold() == new_name.casefold()]
    return updated[0] if updated else option


@router.delete("/sections/{item_id}", response_model=MessageResponse)
async def delete_section(
    item_id: int,
    request: Request,
    current_user: User = Depends(require_school_admin),
    db: AsyncSession = Depends(get_async_db),
):
    session_id = await selected_academic_session_id(db, current_user.school_id, request=request, current_user=current_user)
    option = await _find_virtual_section_or_404(db, current_user.school_id, item_id, session_id=session_id)
    school_class = await _validate_class(db, option.class_id, current_user.school_id, option.academic_session_id)
    names = [name for name in parse_section_names(school_class.sections) if name.casefold() != option.name.casefold()]
    school_class.sections = format_section_names(names)
    await db.commit()
    return {"message": "Section removed from class"}


@router.get("/subjects", response_model=list[SubjectRead])
async def list_subjects(
    request: Request,
    class_id: int | None = Query(default=None),
    school_id: int = Depends(current_school_id),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    session_id = await selected_academic_session_id(db, school_id, request=request, current_user=current_user)
    query = async_query(db, Subject).filter(Subject.school_id == school_id)
    if session_id is not None:
        query = query.filter(Subject.academic_session_id == session_id)
    if class_id is not None:
        await _validate_class(db, class_id, school_id, session_id)
        query = query.filter(Subject.class_id == class_id)
    return await query.order_by(Subject.id.desc()).all()


@router.post("/subjects", response_model=SubjectRead, status_code=status.HTTP_201_CREATED)
async def create_subject(
    payload: SubjectCreate,
    request: Request,
    current_user: User = Depends(require_school_admin),
    db: AsyncSession = Depends(get_async_db),
):
    session_id = await _session_id_for_payload(db, current_user.school_id, request, current_user, payload.academic_session_id)
    await _validate_department(db, payload.department_id, current_user.school_id, session_id)
    await _validate_class(db, payload.class_id, current_user.school_id, session_id)
    data = payload.model_dump()
    data["academic_session_id"] = session_id
    item = Subject(school_id=current_user.school_id, **data)
    db.add(item)
    await _commit_or_duplicate(db, "Subject already exists for this class in this academic session")
    await db.refresh(item)
    return item


@router.put("/subjects/{item_id}", response_model=SubjectRead)
async def update_subject(
    item_id: int,
    payload: SubjectUpdate,
    request: Request,
    current_user: User = Depends(require_school_admin),
    db: AsyncSession = Depends(get_async_db),
):
    item = await _get_or_404(db, Subject, item_id, current_user.school_id)
    await assert_item_session_is_writable(db, current_user.school_id, item)
    values = payload.model_dump(exclude_unset=True)
    session_id = values.get("academic_session_id", item.academic_session_id)
    if "academic_session_id" in values:
        session_id = await _session_id_for_payload(db, current_user.school_id, request, current_user, values.get("academic_session_id"))
        values["academic_session_id"] = session_id
    if "department_id" in values:
        await _validate_department(db, values.get("department_id"), current_user.school_id, session_id)
    if "class_id" in values:
        if values.get("class_id") is None:
            raise HTTPException(status_code=400, detail="Class is required for every subject")
        await _validate_class(db, values.get("class_id"), current_user.school_id, session_id)
    for key, value in values.items():
        setattr(item, key, value)
    await _commit_or_duplicate(db, "Subject already exists for this class in this academic session")
    await db.refresh(item)
    return item


@router.delete("/subjects/{item_id}", response_model=MessageResponse)
async def delete_subject(
    item_id: int,
    current_user: User = Depends(require_school_admin),
    db: AsyncSession = Depends(get_async_db),
):
    item = await _get_or_404(db, Subject, item_id, current_user.school_id)
    await assert_item_session_is_writable(db, current_user.school_id, item)
    await db.delete(item)
    await db.commit()
    return {"message": "Subject deleted"}
