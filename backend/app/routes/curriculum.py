from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_async_db
from app.dependencies.auth import get_current_user, require_roles, current_school_id  # ← current_school_id added
from app.models.user import User
from app.schemas.curriculum import CurriculumApproveRequest, CurriculumPlan, CurriculumRequest
from app.services import curriculum_service
from app.models.user import UserRole

from app.dependencies.subscription_dep import require_curriculum_quota, QuotaContext
from app.models.subscription import FeatureKey

import asyncio
from app.core.config import settings
from app.services.subscription_service import consume, refund, log_ai_call

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
    quota: QuotaContext = Depends(require_curriculum_quota),
    db: AsyncSession = Depends(get_async_db)
):
    # deduct 1 generation upfront
    await consume(db, current_user.id, quota.subscription, FeatureKey.ai_curriculum, amount=1)

    try: 
        plan, tokens_used = await curriculum_service.generate_curriculum(
            request, school_id=school_id
        )
    except Exception:
        # LLM failed - give the generation back
        await refund(db, current_user.id, quota.subscription, FeatureKey.ai_curriculum, amount=1)
        raise

    asyncio.create_task(log_ai_call(
        db=db,
        user_id=current_user.id,
        school_id=school_id,
        feature_key=FeatureKey.ai_curriculum,
        prompt_tokens=0,          # or track separately in service
        completion_tokens=0,      # or track separately in service
        total_tokens=tokens_used,
        model=settings.MODEL,
        cache_hit=(tokens_used == 0),
    ))

    return plan




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
