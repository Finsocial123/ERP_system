"""
curriculum.py — patched to pass school_id into generate_curriculum for
tenant-safe AI response caching.

Changes vs original
--------------------
* `generate_curriculum` endpoint now extracts `school_id` and passes it
  to `curriculum_service.generate_curriculum`.
* No other logic changes.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_async_db
from app.dependencies.auth import get_current_user, require_roles, current_school_id  # ← current_school_id added
from app.models.user import User
from app.schemas.curriculum import CurriculumApproveRequest, CurriculumPlan, CurriculumRequest
from app.services import curriculum_service
from app.models.user import UserRole

ACCESS_ROLES = (
    UserRole.SUPER_ADMIN.value,
    UserRole.SCHOOL_OWNER.value,
    UserRole.SCHOOL_ADMIN.value,
    UserRole.TEACHER.value,
)

router = APIRouter(prefix='/curriculum', tags={'AI Curriculum'})


@router.post('/generate', response_model=CurriculumPlan)
async def generate_curriculum(
    request: CurriculumRequest,
    school_id: int = Depends(current_school_id),        
    current_user: User = Depends(require_roles(*ACCESS_ROLES)),
):
    return await curriculum_service.generate_curriculum(request, school_id=school_id)  


@router.post('/approve')
async def approve_curriculum(
    request: CurriculumApproveRequest,
    school_id: int = Depends(current_school_id),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_roles(*ACCESS_ROLES)),
):
    course = await curriculum_service.save_curriculum(
        plan=request.plan,
        course_id=request.course_id,
        school_id=school_id,
        class_id=request.class_id,
        section_id=request.section_id,
        subject_id=request.subject_id,
        current_user=current_user,
        db=db,
    )
    return {
        'message': 'Curriculum saved successfully',
        'course_id': course.id,
        'course_title': course.title,
        'lessons_created': len(request.plan.lessons),
    }
