"""
subscription_service.py — patched for your UserRole enum and auth pattern.

Your UserRole values: SUPER_ADMIN, SCHOOL_OWNER, SCHOOL_ADMIN, TEACHER, STUDENT
These are mapped to RoleKey buckets (admin / teacher / student) before quota checks.
"""

from datetime import datetime
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import UserRole
from app.models.subscription import AICallLog
from app.models.subscription import (
    FeatureAllocation,
    FeatureKey,
    RoleKey,
    Subscription,
    SubscriptionStatus,
    UserFeatureUsage,
    build_allocations,
)



# Map your granular UserRole → RoleKey quota bucket


def resolve_role_key(user_role: str) -> RoleKey:
    """
    Converts your UserRole enum value to the RoleKey used in FeatureAllocation.

    STUDENT                              → RoleKey.student
    TEACHER                              → RoleKey.teacher
    SCHOOL_ADMIN, SCHOOL_OWNER,
    SUPER_ADMIN                          → RoleKey.admin
    """
    mapping = {
        UserRole.STUDENT.value      : RoleKey.student,
        UserRole.TEACHER.value      : RoleKey.teacher,
        UserRole.SCHOOL_ADMIN.value : RoleKey.admin,
        UserRole.SCHOOL_OWNER.value : RoleKey.admin,
        UserRole.SUPER_ADMIN.value  : RoleKey.admin,
    }
    role_key = mapping.get(user_role)
    if not role_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Unrecognised role '{user_role}' for quota resolution.",
        )
    return role_key



# helpers


async def _get_allocation(
    db: AsyncSession,
    subscription_id: int,
    role_key: RoleKey,
    feature_key: FeatureKey,
) -> Optional[FeatureAllocation]:
    result = await db.execute(
        select(FeatureAllocation).where(
            FeatureAllocation.subscription_id == subscription_id,
            FeatureAllocation.role == role_key,
            FeatureAllocation.feature_key == feature_key,
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



# Subscription management


async def create_subscription(
    db: AsyncSession,
    school_id: int,
    plan_id: int,
    started_at: datetime,
    expires_at: datetime,
) -> Subscription:
    from sqlalchemy.orm import selectinload
    from app.models.subscription import SubscriptionPlan

    existing = await get_active_subscription(db, school_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="School already has an active subscription.",
        )

    plan = await db.get(
        SubscriptionPlan, plan_id,
        options=[selectinload(SubscriptionPlan.allocations)]
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found.")

    sub = Subscription(
        school_id=school_id,
        plan_id=plan_id,
        payment_id=None,   # manual create — make payment_id Optional in model
        plan_name=plan.name,
        status=SubscriptionStatus.active,
        started_at=started_at,
        expires_at=expires_at,
    )
    db.add(sub)
    await db.flush()

    db.add_all(build_allocations(sub, plan.allocations))
    await db.commit()
    await db.refresh(sub)
    return sub

async def get_active_subscription(
    db: AsyncSession,
    school_id: int,
) -> Optional[Subscription]:
    result = await db.execute(
        select(Subscription).where(
            Subscription.school_id == school_id,
            Subscription.status == SubscriptionStatus.active,
            Subscription.expires_at > datetime.utcnow(),
        )
    )
    return result.scalar_one_or_none()


async def cancel_subscription(
    db: AsyncSession,
    school_id: int,
) -> Subscription:
    sub = await get_active_subscription(db, school_id)
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active subscription found for this school.",
        )
    sub.status = SubscriptionStatus.cancelled
    await db.commit()
    await db.refresh(sub)
    return sub



# Quota check + consumption


async def get_quota_status(
    db: AsyncSession,
    user_id: int,
    school_id: int,
    user_role: str,       # raw User.role string e.g. "TEACHER"
    feature_key: FeatureKey,
) -> dict:
    role_key = resolve_role_key(user_role)
    sub = await get_active_subscription(db, school_id)

    if not sub:
        return {
            "feature_key": feature_key,
            "limit": 0, "used": 0, "remaining": 0,
            "is_unlimited": False,
            "has_active_subscription": False,
            "subscription_expires_at": None,
        }

    alloc = await _get_allocation(db, sub.id, role_key, feature_key)
    if not alloc:
        return {
            "feature_key": feature_key,
            "limit": 0, "used": 0, "remaining": 0,
            "is_unlimited": False,
            "has_active_subscription": True,
            "subscription_expires_at": sub.expires_at.isoformat(),
        }

    usage = await _get_or_create_usage(db, user_id, sub, feature_key)
    await db.commit()

    if alloc.is_unlimited:
        return {
            "feature_key": feature_key,
            "limit": None, "remaining": None,
            "used": usage.used_value,
            "is_unlimited": True,
            "has_active_subscription": True,
            "subscription_expires_at": sub.expires_at.isoformat(),
        }

    remaining = max(0, alloc.limit_value - usage.used_value)
    return {
        "feature_key": feature_key,
        "limit": alloc.limit_value,
        "used": usage.used_value,
        "remaining": remaining,
        "is_unlimited": False,
        "has_active_subscription": True,
        "subscription_expires_at": sub.expires_at.isoformat(),
    }


async def check_quota(
    db: AsyncSession,
    user_id: int,
    school_id: int,
    user_role: str,       # raw User.role string e.g. "TEACHER"
    feature_key: FeatureKey,
    amount: int = 1,
) -> tuple[Subscription, UserFeatureUsage]:
    """
    Pre-flight check. Raises 403/429 if user cannot proceed.
    Returns (subscription, usage) — pass both to consume() after the action.
    """
    role_key = resolve_role_key(user_role)

    sub = await get_active_subscription(db, school_id)
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active subscription. Please contact your administrator.",
        )

    alloc = await _get_allocation(db, sub.id, role_key, feature_key)
    if not alloc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Feature '{feature_key}' is not available for your role.",
        )

    if alloc.is_unlimited:
        usage = await _get_or_create_usage(db, user_id, sub, feature_key)
        await db.commit()
        return sub, usage

    usage = await _get_or_create_usage(db, user_id, sub, feature_key)
    if usage.used_value + amount > alloc.limit_value:
        remaining = max(0, alloc.limit_value - usage.used_value)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "quota_exceeded",
                "feature": feature_key,
                "limit": alloc.limit_value,
                "used": usage.used_value,
                "remaining": remaining,
                "message": f"You have used all your {feature_key} quota for this period.",
            },
        )

    await db.commit()
    return sub, usage


async def consume(
    db: AsyncSession,
    user_id: int,
    subscription: Subscription,
    feature_key: FeatureKey,
    amount: int,
) -> UserFeatureUsage:
    """
    Increment used_value AFTER the action succeeds.

    For all AI features (chatbot, notice, curriculum):
        actual_tokens = response.usage.prompt_tokens + response.usage.completion_tokens
        await consume(db, user_id, sub, feature_key, amount=actual_tokens)

    For video upload:
        await consume(db, user_id, sub, FeatureKey.video_upload, amount=duration_seconds)
    """
    usage = await _get_or_create_usage(db, user_id, subscription, feature_key)
    usage.used_value += amount
    usage.last_used_at = datetime.utcnow()
    await db.commit()
    await db.refresh(usage)
    return usage


async def refund(
    db: AsyncSession,
    user_id: int,
    subscription: Subscription,
    feature_key: FeatureKey,
    amount: int = 1,
) -> None:
    usage = await _get_or_create_usage(db, user_id, subscription, feature_key)
    usage.used_value = max(0, usage.used_value - amount) # never go below 0
    await db.commit()


async def log_ai_call(db, user_id, school_id, feature_key, prompt_tokens, completion_tokens, model, cache_hit=False):
    log = AICallLog(
        user_id=user_id, school_id=school_id, feature_key=feature_key,
        prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        model=model, cache_hit=cache_hit,
    )
    db.add(log)
    await db.commit()

# Admin dashboard


async def get_school_usage_summary(
    db: AsyncSession,
    school_id: int,
) -> dict:
    sub = await get_active_subscription(db, school_id)
    if not sub:
        return {"subscription": None, "usage_by_feature": {}}

    result = await db.execute(
        select(UserFeatureUsage).where(UserFeatureUsage.subscription_id == sub.id)
    )
    all_usages = result.scalars().all()

    feature_totals: dict[str, int] = {}
    for u in all_usages:
        key = u.feature_key.value
        feature_totals[key] = feature_totals.get(key, 0) + u.used_value

    usage_by_feature = {}

    result2 = await db.execute(
        select(FeatureAllocation).where(FeatureAllocation.subscription_id == sub.id)
    )
    allocations = result2.scalar().all()

    for alloc in allocations:
        fk = alloc.feature_key.value
        usage_by_feature[fk] = {
            "total_used": feature_totals.get(fk, 0),
            "limit_per_user": alloc.limit_value,
            "role": alloc.role.value,
        }

    return {
        "subscription": {
            "id": sub.id,
            "plan_name": sub.plan_name,
            "status": sub.status.value,
            "started_at": sub.started_at.isoformat(),
            "expires_at": sub.expires_at.isoformat(),
        },
        "usage_by_feature": usage_by_feature,
    }