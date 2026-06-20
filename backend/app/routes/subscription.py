"""
subscription_router.py — patched for your auth pattern and UserRole enum.

Mount in main.py:
    from app.routers.subscription_router import router as subscription_router
    app.include_router(subscription_router, prefix="/api/v1/subscriptions", tags=["Subscriptions"])
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.dependencies.auth import get_current_user, require_roles, current_school_id
from app.models.user import User, UserRole
from app.models.subscription import FeatureAllocation, FeatureKey
from app.services.subscription_service import (
    cancel_subscription,
    create_subscription,
    get_active_subscription,
    get_quota_status,
    get_school_usage_summary,
)
from app.schemas.subscription import (
    AllocationUpdateRequest,
    AllQuotasResponse,
    FeatureUsageSummary,
    QuotaStatusResponse,
    SchoolUsageSummaryResponse,
    SubscriptionCreate,
    SubscriptionDetailResponse,
    SubscriptionResponse,
)

router = APIRouter(prefix='/subscription', tags={'Subscription Management'})

ADMIN_ROLES = (
    UserRole.SUPER_ADMIN.value,
    UserRole.SCHOOL_OWNER.value,
    UserRole.SCHOOL_ADMIN.value,
)

# Features exposed per role for the /my-quota endpoint
ROLE_FEATURES: dict[str, list[FeatureKey]] = {
    UserRole.STUDENT.value      : [FeatureKey.chatbot_query],
    UserRole.TEACHER.value      : [FeatureKey.notice_post, FeatureKey.ai_curriculum, FeatureKey.video_upload],
    UserRole.SCHOOL_ADMIN.value : [FeatureKey.notice_post, FeatureKey.ai_curriculum],
    UserRole.SCHOOL_OWNER.value : [FeatureKey.notice_post, FeatureKey.ai_curriculum],
    UserRole.SUPER_ADMIN.value  : [FeatureKey.notice_post, FeatureKey.ai_curriculum],
}



# Admin — subscription management

@router.post(
    "/",
    response_model=SubscriptionDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a subscription for a school",
)
async def create_school_subscription(
    body         : SubscriptionCreate,
    current_user : User = Depends(require_roles(*ADMIN_ROLES)),
    db           : AsyncSession = Depends(get_async_db),
):
    sub = await create_subscription(
        db=db,
        school_id=body.school_id,
        plan_name=body.plan_name,
        started_at=body.started_at,
        expires_at=body.expires_at,
    )
    await db.refresh(sub, ["allocations"])
    return sub


@router.get(
    "/school/{school_id}",
    response_model=SubscriptionDetailResponse,
    summary="Get active subscription for a school",
)
async def get_school_subscription(
    school_id    : int,
    current_user : User = Depends(require_roles(*ADMIN_ROLES)),
    db           : AsyncSession = Depends(get_async_db),
):
    sub = await get_active_subscription(db, school_id)
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active subscription found.")
    await db.refresh(sub, ["allocations"])
    return sub


@router.delete(
    "/school/{school_id}",
    response_model=SubscriptionResponse,
    summary="Cancel a school's subscription",
)
async def cancel_school_subscription(
    school_id    : int,
    current_user : User = Depends(require_roles(*ADMIN_ROLES)),
    db           : AsyncSession = Depends(get_async_db),
):
    return await cancel_subscription(db, school_id)


@router.patch(
    "/{sub_id}/allocations/{alloc_id}",
    summary="Adjust a feature allocation mid-period",
)
async def update_allocation(
    sub_id       : int,
    alloc_id     : int,
    body         : AllocationUpdateRequest,
    current_user : User = Depends(require_roles(*ADMIN_ROLES)),
    db           : AsyncSession = Depends(get_async_db),
):
    result = await db.execute(
        select(FeatureAllocation).where(
            FeatureAllocation.id == alloc_id,
            FeatureAllocation.subscription_id == sub_id,
        )
    )
    alloc = result.scalar_one_or_none()
    if not alloc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Allocation not found.")

    if body.limit_value is not None:
        alloc.limit_value = body.limit_value
    if body.is_unlimited is not None:
        alloc.is_unlimited = body.is_unlimited

    await db.commit()
    await db.refresh(alloc)
    return {
        "id": alloc.id, "role": alloc.role,
        "feature_key": alloc.feature_key,
        "limit_value": alloc.limit_value,
        "is_unlimited": alloc.is_unlimited,
    }


@router.get(
    "/school-summary",
    response_model=SchoolUsageSummaryResponse,
    summary="School-wide usage summary for admin dashboard",
)
async def school_usage_summary(
    current_user : User = Depends(require_roles(*ADMIN_ROLES)),
    school_id    : int  = Depends(current_school_id),
    db           : AsyncSession = Depends(get_async_db),
):
    summary = await get_school_usage_summary(db, school_id)
    feature_rows = [
        FeatureUsageSummary(**row, feature_key=fk)
        for fk, row in summary["usage_by_feature"].items()
    ]
    return SchoolUsageSummaryResponse(
        subscription=summary["subscription"],
        usage_by_feature=feature_rows,
    )




@router.get(
    "/my-quota",
    response_model=AllQuotasResponse,
    summary="All quota statuses for the current user",
)
async def get_my_quotas(
    current_user : User = Depends(get_current_user),
    school_id    : int  = Depends(current_school_id),
    db           : AsyncSession = Depends(get_async_db),
):
    features = ROLE_FEATURES.get(current_user.role, [])
    quotas = []
    for fk in features:
        status_dict = await get_quota_status(
            db=db,
            user_id=current_user.id,
            school_id=school_id,
            user_role=current_user.role,
            feature_key=fk,
        )
        quotas.append(QuotaStatusResponse(**status_dict))

    return AllQuotasResponse(
        user_id=current_user.id,
        school_id=school_id,
        quotas=quotas,
    )


@router.get(
    "/my-quota/{feature}",
    response_model=QuotaStatusResponse,
    summary="Quota status for one specific feature",
)
async def get_my_quota_for_feature(
    feature      : FeatureKey,
    current_user : User = Depends(get_current_user),
    school_id    : int  = Depends(current_school_id),
    db           : AsyncSession = Depends(get_async_db),
):
    status_dict = await get_quota_status(
        db=db,
        user_id=current_user.id,
        school_id=school_id,
        user_role=current_user.role,
        feature_key=feature,
    )
    return QuotaStatusResponse(**status_dict)