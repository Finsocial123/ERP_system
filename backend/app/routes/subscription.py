"""
subscription_router.py

Mount in main.py:
    from app.routers.subscription_router import router as subscription_router
    app.include_router(subscription_router, prefix="/api/v1/subscriptions", tags=["Subscriptions"])

Endpoints:
    GET  /plans                          → list available plans (school admin)
    POST /razorpay/create-order          → create Razorpay order for a plan
    POST /razorpay/verify-payment        → verify payment → activate subscription
    POST /                               → manual create (super admin only)
    GET  /school/{school_id}             → get active subscription (admin)
    DELETE /school/{school_id}           → cancel subscription (admin)
    GET  /school-summary                 → usage dashboard (admin)
    GET  /my-quota                       → all quotas for current user
    GET  /my-quota/{feature}             → single feature quota
"""

from datetime import datetime, timedelta

import razorpay
from fastapi import APIRouter, Depends, HTTPException, status
from razorpay.errors import SignatureVerificationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_async_db
from app.dependencies.auth import get_current_user, require_roles, current_school_id
from app.models.user import User, UserRole
from app.models.subscription import (
    FeatureAllocation,
    FeatureKey,
    PlanAllocation,
    Subscription,
    SubscriptionPayment,
    SubscriptionPaymentStatus,
    SubscriptionPlan,
    SubscriptionStatus,
    build_allocations,
)
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
    PlanResponse,
    QuotaStatusResponse,
    SchoolUsageSummaryResponse,
    SubscriptionCreate,
    SubscriptionDetailResponse,
    SubscriptionOrderCreate,
    SubscriptionOrderResponse,
    SubscriptionResponse,
    SubscriptionVerify,
)

router = APIRouter()

ADMIN_ROLES = (
    UserRole.SUPER_ADMIN.value,
    UserRole.SCHOOL_OWNER.value,
    UserRole.SCHOOL_ADMIN.value,
)

ROLE_FEATURES: dict[str, list[FeatureKey]] = {
    UserRole.STUDENT.value      : [FeatureKey.chatbot_query, FeatureKey.quiz_generation],
    UserRole.TEACHER.value      : [FeatureKey.notice_post, FeatureKey.ai_curriculum, FeatureKey.video_upload],
    UserRole.SCHOOL_ADMIN.value : [FeatureKey.notice_post, FeatureKey.ai_curriculum, FeatureKey.video_upload],
    UserRole.SCHOOL_OWNER.value : [FeatureKey.notice_post, FeatureKey.ai_curriculum, FeatureKey.video_upload],
    UserRole.SUPER_ADMIN.value  : [FeatureKey.notice_post, FeatureKey.ai_curriculum],
}


# Plans — public to any logged-in school admin

@router.get(
    "/plans",
    response_model=list[PlanResponse],
    summary="List available subscription plans",
)
async def list_plans(
    current_user : User         = Depends(require_roles(*ADMIN_ROLES)),
    db           : AsyncSession = Depends(get_async_db),
):
    """
    Returns all active plans with their feature allocations.
    School admin sees this when choosing a plan to purchase.
    """
    result = await db.execute(
        select(SubscriptionPlan)
        .options(selectinload(SubscriptionPlan.allocations))
        .where(SubscriptionPlan.is_active == True)
        .order_by(SubscriptionPlan.price_paise.asc())
    )
    plans = result.scalars().all()
    return plans


# Razorpay — create order

@router.post(
    "/razorpay/create-order",
    response_model=SubscriptionOrderResponse,
    summary="Create Razorpay order for a subscription plan",
)
async def create_subscription_order(
    body         : SubscriptionOrderCreate,
    current_user : User         = Depends(require_roles(*ADMIN_ROLES)),
    school_id    : int          = Depends(current_school_id),
    db           : AsyncSession = Depends(get_async_db),
):
    """
    School admin selects a plan → this creates a Razorpay order.
    Frontend uses order_id + key to open Razorpay checkout.
    """
    # Check no active subscription already exists
    existing = await get_active_subscription(db, school_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="School already has an active subscription. Cancel it before purchasing a new one.",
        )

    # Fetch plan
    plan = await db.get(SubscriptionPlan, body.plan_id)
    if not plan or not plan.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found or inactive.",
        )

    # Create Razorpay order
    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
    order = client.order.create({
        "amount"  : plan.price_paise,
        "currency": "INR",
        "receipt" : f"sub_{school_id}_{plan.id}_{int(datetime.utcnow().timestamp())}",
        "notes"   : {
            "school_id" : str(school_id),
            "plan_id"   : str(plan.id),
            "plan_name" : plan.name,
        },
    })

    # Save pending payment record
    payment = SubscriptionPayment(
        school_id           = school_id,
        plan_id             = plan.id,
        paid_by_user_id     = current_user.id,
        amount_paise        = plan.price_paise,
        status              = SubscriptionPaymentStatus.pending,
        razorpay_order_id   = order["id"],
    )
    db.add(payment)
    await db.commit()

    return SubscriptionOrderResponse(
        order_id      = order["id"],
        amount        = order["amount"],
        currency      = order["currency"],
        key           = settings.RAZORPAY_KEY_ID,
        plan_id       = plan.id,
        plan_name     = plan.name,
        price_display = f"₹{plan.price_paise / 100:,.0f}",
    )


# Razorpay — verify payment and activate subscription

@router.post(
    "/razorpay/verify-payment",
    response_model=SubscriptionDetailResponse,
    summary="Verify Razorpay payment and activate subscription",
)
async def verify_subscription_payment(
    body         : SubscriptionVerify,
    current_user : User         = Depends(require_roles(*ADMIN_ROLES)),
    school_id    : int          = Depends(current_school_id),
    db           : AsyncSession = Depends(get_async_db),
):
    """
    Called after Razorpay checkout completes.
    1. Verifies signature
    2. Marks payment as completed
    3. Creates Subscription
    4. Snapshots PlanAllocation → FeatureAllocation
    """
    # 1. Verify signature
    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
    try:
        client.utility.verify_payment_signature({
            "razorpay_order_id"   : body.razorpay_order_id,
            "razorpay_payment_id" : body.razorpay_payment_id,
            "razorpay_signature"  : body.razorpay_signature,
        })
    except SignatureVerificationError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payment signature.",
        )

    # 2. Find the pending payment record
    result = await db.execute(
        select(SubscriptionPayment).where(
            SubscriptionPayment.razorpay_order_id == body.razorpay_order_id,
            SubscriptionPayment.school_id == school_id,
        )
    )
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment record not found.",
        )

    # Idempotency — already completed
    if payment.status == SubscriptionPaymentStatus.completed:
        result = await db.execute(
            select(Subscription)
            .options(selectinload(Subscription.allocations))
            .where(Subscription.payment_id == payment.id)
        )
        return result.scalar_one()

    # 3. Mark payment completed
    payment.status              = SubscriptionPaymentStatus.completed
    payment.razorpay_payment_id = body.razorpay_payment_id
    payment.razorpay_signature  = body.razorpay_signature
    await db.flush()

    # 4. Load plan with allocations
    plan = await db.get(
        SubscriptionPlan,
        payment.plan_id,
        options=[selectinload(SubscriptionPlan.allocations)],
    )
    if not plan:
        raise HTTPException(status_code=500, detail="Plan not found.")

    # 5. Create subscription
    now        = datetime.utcnow()
    expires_at = now + timedelta(days=plan.duration_days)

    sub = Subscription(
        school_id  = school_id,
        plan_id    = plan.id,
        payment_id = payment.id,
        plan_name  = plan.name,
        status     = SubscriptionStatus.active,
        started_at = now,
        expires_at = expires_at,
    )
    db.add(sub)
    await db.flush()

    # 6. Snapshot plan allocations → feature allocations
    db.add_all(build_allocations(sub, plan.allocations))
    await db.commit()
    await db.refresh(sub)

    result = await db.execute(
        select(Subscription)
        .options(selectinload(Subscription.allocations))
        .where(Subscription.id == sub.id)
    )
    return result.scalar_one()


# Manual create — super admin only, bypasses payment

@router.post(
    "/",
    response_model=SubscriptionDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Manually create a subscription (super admin only)",
)
async def create_school_subscription(
    body         : SubscriptionCreate,
    current_user : User         = Depends(require_roles(UserRole.SUPER_ADMIN.value)),
    db           : AsyncSession = Depends(get_async_db),
):
    """
    Super admin only — bypasses payment for testing or manual activation.
    """
    sub = await create_subscription(
        db         = db,
        school_id  = body.school_id,
        plan_id    = body.plan_id,
        started_at = body.started_at,
        expires_at = body.expires_at,
    )
    await db.refresh(sub, ["allocations"])
    return sub


# Admin — view / cancel subscription

@router.get(
    "/school/{school_id}",
    response_model=SubscriptionDetailResponse,
    summary="Get active subscription for a school",
)
async def get_school_subscription(
    school_id    : int,
    current_user : User         = Depends(require_roles(*ADMIN_ROLES)),
    db           : AsyncSession = Depends(get_async_db),
):
    sub = await get_active_subscription(db, school_id)
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active subscription found.",
        )
    await db.refresh(sub, ["allocations"])
    return sub


@router.delete(
    "/school/{school_id}",
    response_model=SubscriptionResponse,
    summary="Cancel a school's subscription",
)
async def cancel_school_subscription(
    school_id    : int,
    current_user : User         = Depends(require_roles(*ADMIN_ROLES)),
    db           : AsyncSession = Depends(get_async_db),
):
    return await cancel_subscription(db, school_id)


# Admin — usage dashboard

@router.get(
    "/school-summary",
    response_model=SchoolUsageSummaryResponse,
    summary="School-wide usage summary",
)
async def school_usage_summary(
    current_user : User         = Depends(require_roles(*ADMIN_ROLES)),
    school_id    : int          = Depends(current_school_id),
    db           : AsyncSession = Depends(get_async_db),
):
    summary = await get_school_usage_summary(db, school_id)
    feature_rows = [
        FeatureUsageSummary(**row, feature_key=fk)
        for fk, row in summary["usage_by_feature"].items()
    ]
    return SchoolUsageSummaryResponse(
        subscription     = summary["subscription"],
        usage_by_feature = feature_rows,
    )


# User — quota status

@router.get(
    "/my-quota",
    response_model=AllQuotasResponse,
    summary="All quota statuses for the current user",
)
async def get_my_quotas(
    current_user : User         = Depends(get_current_user),
    school_id    : int          = Depends(current_school_id),
    db           : AsyncSession = Depends(get_async_db),
):
    features = ROLE_FEATURES.get(current_user.role, [])
    quotas = []
    for fk in features:
        status_dict = await get_quota_status(
            db         = db,
            user_id    = current_user.id,
            school_id  = school_id,
            user_role  = current_user.role,
            feature_key= fk,
        )
        quotas.append(QuotaStatusResponse(**status_dict))

    return AllQuotasResponse(
        user_id   = current_user.id,
        school_id = school_id,
        quotas    = quotas,
    )


@router.get(
    "/my-quota/{feature}",
    response_model=QuotaStatusResponse,
    summary="Quota status for one specific feature",
)
async def get_my_quota_for_feature(
    feature      : FeatureKey,
    current_user : User         = Depends(get_current_user),
    school_id    : int          = Depends(current_school_id),
    db           : AsyncSession = Depends(get_async_db),
):
    status_dict = await get_quota_status(
        db          = db,
        user_id     = current_user.id,
        school_id   = school_id,
        user_role   = current_user.role,
        feature_key = feature,
    )
    return QuotaStatusResponse(**status_dict)