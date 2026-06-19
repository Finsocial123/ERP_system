from datetime import datetime
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app import models
from app.models.subscription import (
    DEFAULT_ALLOCATIONS,
    FeatureAllocation,
    FeatureKey,
    SubscriptionStatus,
    Subscription,
    UserFeatureUsage,
    UserRole,
    build_allocation
)



async def _get_allocation(
    db: AsyncSession,
    subscription_id: int,
    role: UserRole,
    feature_key: FeatureKey,
) -> Optional[FeatureAllocation]:
    result = await db.exectue(
        select(FeatureAllocation).where(
            FeatureAllocation.subscription_id == subscription_id,
            FeatureAllocation.role == role,
            FeatureAllocation.feature_key == feature_key
        )
    )
    return result.scalar_one_or_none()



async def _get_or_create_usage(
    db: AsyncSession,
    user_id: int,
    subscription: Subscription,
    feature_key: FeatureKey,
) -> UserFeatureUsage: 
    
    result = await db.execute(
        select(UserFeatureUsage).where(
            UserFeatureUsage.user_id == user_id,
            UserFeatureUsage.subscription_id == subscription.id,
            UserFeatureUsage.feature_key == feature_key,
        )
    )

    usage = result.scalar_one_or_none()

    if usage is None:
        usage = UserFeatureUsage(
            user_id=user_id,
            subscription_id=subscription.id,
            feature_key=feature_key,
            used_value=0,
            period_start=subscription.started_at,
            period_end=subscription.expires_at,
        )
        db.add(usage)
        await db.flush()

    return usage

async def create_subscription(
    db: AsyncSession,
    school_id: int,
    plan_name: str,
    started_at: datetime,
    expires_at: datetime
) -> Subscription:
    
    existing = await get_active_subscription(db, school_id)
    if existing:
        raise HTTPException(
            status_code = status.HTTP_400_BAD_REQUEST,
            detail = "School already has an active subscription."
            "cancel it before creating a new one."
        )
    
    sub = SubscriptionStatus(
        school_id=school_id,
        plan_name=plan_name,
        status=SubscriptionStatus.active,
        started_at=started_at,
        expires_at=expires_at
    )
    db.add(sub)
    await db.flush()

    db.add_all(build_allocation(sub))
    await db.commit()
    await db.refresh(sub)
    return sub


async def get_active_subscription(
    db: AsyncSession,
    school_id: int,
):
    result = db.execute(
        select(Subscription)
            .where(
                Subscription.school_id == school_id,
                Subscription.status == SubscriptionStatus.active,
                Subscription.expires_at > datetime.utcnow()
            ) 
    )
    return result.scalar_one_or_none()


async def cancel_subscription(
    db: AsyncSession,
    school_id: int
):
    sub = await get_active_subscription(db, school_id)
    
    if not sub: 
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active subscription found for this school"
        )

    sub.status = SubscriptionStatus.cancelled
    await db.commit()
    await db.refresh(sub)
    return sub





