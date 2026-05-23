from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.dependencies.auth import get_current_user, require_roles
from app.models.user import User 
from app.schemas.curriculum import (
    CurriculumApproveRequest,
    CurriculumPlan,
    CurriculumRequest,
)
from app.services import curriculum_service
from app.models.user import (UserRole)

ACCESS_ROLES = (UserRole.SUPER_ADMIN.value, UserRole.SCHOOL_OWNER.value, UserRole.SCHOOL_ADMIN.value, UserRole.TEACHER.value)

router = APIRouter(prefix="/curriculum", tags={"AI Curriculum"})


@router.post("/generate", response_model=CurriculumPlan)
async def generate_curriculum(
    request: CurriculumRequest,
    current_user: User = Depends(require_roles(*ACCESS_ROLES))
):
    return await curriculum_service.generate_curriculum(request)


@router.post("/approve")
async def approve_curriculum(
    request: CurriculumApproveRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_roles(*ACCESS_ROLES))
):
    course = await curriculum_service.save_curriculum(
        plan=request.plan,
        course_id=request.course_id,
        current_user=current_user,
        db=db
    )
    return {
        "message": "Curriculum saved successfully",
        "course_id": course.id,
        "course_title": course.title,
        "lessons_created": len(request.plan.lessons)
    }

