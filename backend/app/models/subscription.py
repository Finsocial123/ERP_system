import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.school import School


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class SubscriptionStatus(str, enum.Enum):
    active    = "active"
    expired   = "expired"
    cancelled = "cancelled"


class SubscriptionPaymentStatus(str, enum.Enum):
    pending   = "pending"
    completed = "completed"
    failed    = "failed"


class RoleKey(str, enum.Enum):
    student = "student"
    teacher = "teacher"
    admin   = "admin"


class FeatureKey(str, enum.Enum):
    chatbot_query   = "chatbot_query"    # tokens
    notice_post     = "notice_post"      # tokens
    ai_curriculum   = "ai_curriculum"    # tokens
    video_upload    = "video_upload"     # seconds
    quiz_generation = "quiz_generation"  # tokens


# ---------------------------------------------------------------------------
# SubscriptionPlan
# You define these once — seed manually in DB.
# School admins pick from these plans.
# ---------------------------------------------------------------------------

class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id          : Mapped[int]  = mapped_column(primary_key=True, index=True)
    name        : Mapped[str]  = mapped_column(String(100), nullable=False, unique=True)
    description : Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Price in paise (INR) — e.g. 99900 = ₹999
    price_paise : Mapped[int]  = mapped_column(Integer, nullable=False)

    # Duration in days — e.g. 365 for annual, 30 for monthly
    duration_days : Mapped[int] = mapped_column(Integer, nullable=False, default=365)

    is_active   : Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at  : Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at  : Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    allocations : Mapped[list["PlanAllocation"]] = relationship(back_populates="plan", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# PlanAllocation
# Defines what each role gets under a specific plan.
# ---------------------------------------------------------------------------

class PlanAllocation(Base):
    __tablename__ = "plan_allocations"
    __table_args__ = (
        UniqueConstraint(
            "plan_id", "role", "feature_key",
            name="uq_plan_alloc_plan_role_feature"
        ),
    )

    id          : Mapped[int]      = mapped_column(primary_key=True, index=True)
    plan_id     : Mapped[int]      = mapped_column(
        Integer, ForeignKey("subscription_plans.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    role        : Mapped[RoleKey]   = mapped_column(Enum(RoleKey), nullable=False)
    feature_key : Mapped[FeatureKey] = mapped_column(Enum(FeatureKey), nullable=False)

    limit_value  : Mapped[int]  = mapped_column(BigInteger, nullable=False)
    is_unlimited : Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at  : Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    plan : Mapped["SubscriptionPlan"] = relationship(back_populates="allocations")


# ---------------------------------------------------------------------------
# SubscriptionPayment
# Tracks Razorpay payment for a subscription purchase.
# ---------------------------------------------------------------------------

class SubscriptionPayment(Base):
    __tablename__ = "subscription_payments"

    id                  : Mapped[int] = mapped_column(primary_key=True, index=True)
    school_id           : Mapped[int] = mapped_column(
        Integer, ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    plan_id             : Mapped[int] = mapped_column(
        Integer, ForeignKey("subscription_plans.id"),
        nullable=False
    )
    paid_by_user_id     : Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"),
        nullable=False
    )

    amount_paise        : Mapped[int] = mapped_column(Integer, nullable=False)
    status              : Mapped[SubscriptionPaymentStatus] = mapped_column(
        Enum(SubscriptionPaymentStatus),
        nullable=False,
        default=SubscriptionPaymentStatus.pending,
    )

    razorpay_order_id   : Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    razorpay_payment_id : Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    razorpay_signature  : Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    created_at  : Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at  : Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    plan        : Mapped["SubscriptionPlan"] = relationship("SubscriptionPlan")
    paid_by     : Mapped["User"]             = relationship("User")


# ---------------------------------------------------------------------------
# Subscription
# One active subscription per school at a time.
# Created automatically when payment is verified.
# ---------------------------------------------------------------------------

class Subscription(Base):
    __tablename__ = "subscription"

    id         : Mapped[int] = mapped_column(primary_key=True, index=True)
    school_id  : Mapped[int] = mapped_column(
        Integer, ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    plan_id    : Mapped[int] = mapped_column(
        Integer, ForeignKey("subscription_plans.id"),
        nullable=False
    )
    payment_id : Mapped[int] = mapped_column(
        Integer, ForeignKey("subscription_payments.id"),
        nullable=False
    )

    plan_name  : Mapped[str]                = mapped_column(String(100), nullable=False)
    status     : Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus), nullable=False, default=SubscriptionStatus.active
    )
    started_at : Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at : Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at : Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at : Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    school      : Mapped["School"]                  = relationship("School")
    plan        : Mapped["SubscriptionPlan"]         = relationship("SubscriptionPlan")
    payment     : Mapped["SubscriptionPayment"]      = relationship("SubscriptionPayment")
    allocations : Mapped[list["FeatureAllocation"]]  = relationship(back_populates="subscription", cascade="all, delete-orphan")
    usages      : Mapped[list["UserFeatureUsage"]]   = relationship(back_populates="subscription", cascade="all, delete-orphan")

    def is_active(self) -> bool:
        return (
            self.status == SubscriptionStatus.active
            and self.expires_at > datetime.utcnow()
        )


# ---------------------------------------------------------------------------
# FeatureAllocation
# Copied from PlanAllocation when a subscription is activated.
# Snapshot — changes to PlanAllocation don't affect active subscriptions.
# ---------------------------------------------------------------------------

class FeatureAllocation(Base):
    __tablename__ = "feature_allocation"
    __table_args__ = (
        UniqueConstraint(
            "subscription_id", "role", "feature_key",
            name="uq_alloc_sub_role_feature"
        ),
    )

    id              : Mapped[int]        = mapped_column(primary_key=True, index=True)
    subscription_id : Mapped[int]        = mapped_column(
        Integer, ForeignKey("subscription.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    role        : Mapped[RoleKey]    = mapped_column(Enum(RoleKey), nullable=False)
    feature_key : Mapped[FeatureKey] = mapped_column(Enum(FeatureKey), nullable=False)

    limit_value  : Mapped[int]  = mapped_column(BigInteger, nullable=False)
    is_unlimited : Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at : Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at : Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    subscription : Mapped["Subscription"] = relationship(back_populates="allocations")


# ---------------------------------------------------------------------------
# UserFeatureUsage
# ---------------------------------------------------------------------------

class UserFeatureUsage(Base):
    __tablename__ = "user_feature_usage"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "subscription_id", "feature_key",
            name="uq_usage_user_sub_feature"
        ),
    )

    id              : Mapped[int]        = mapped_column(primary_key=True, index=True)
    user_id         : Mapped[int]        = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    subscription_id : Mapped[int]        = mapped_column(
        Integer, ForeignKey("subscription.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    feature_key : Mapped[FeatureKey] = mapped_column(Enum(FeatureKey), nullable=False)

    used_value   : Mapped[int]               = mapped_column(BigInteger, nullable=False, default=0)
    period_start : Mapped[datetime]          = mapped_column(DateTime, nullable=False)
    period_end   : Mapped[datetime]          = mapped_column(DateTime, nullable=False)
    last_used_at : Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at   : Mapped[datetime]          = mapped_column(DateTime, default=datetime.utcnow)

    subscription : Mapped["Subscription"] = relationship(back_populates="usages")


# ---------------------------------------------------------------------------
# AICallLog
# ---------------------------------------------------------------------------

class AICallLog(Base):
    __tablename__ = "ai_call_logs"

    id                : Mapped[int]       = mapped_column(primary_key=True)
    user_id           : Mapped[int]       = mapped_column(ForeignKey("users.id"))
    school_id         : Mapped[int]       = mapped_column(ForeignKey("schools.id"))
    feature_key       : Mapped[FeatureKey] = mapped_column(Enum(FeatureKey))
    prompt_tokens     : Mapped[int]       = mapped_column(Integer, default=0)
    completion_tokens : Mapped[int]       = mapped_column(Integer, default=0)
    total_tokens      : Mapped[int]       = mapped_column(Integer, default=0)
    model             : Mapped[str]       = mapped_column(String(100))
    cache_hit         : Mapped[bool]      = mapped_column(Boolean, default=False)
    created_at        : Mapped[datetime]  = mapped_column(DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# build_allocations
# Called after Subscription is created.
# Copies PlanAllocation rows into FeatureAllocation (snapshot).
# plan.allocations must be loaded before calling this.
# ---------------------------------------------------------------------------

def build_allocations(
    subscription: Subscription,
    plan_allocations: list[PlanAllocation],
) -> list[FeatureAllocation]:
    """
    Snapshot plan limits into the subscription.
    Pass plan.allocations loaded from DB.

    Usage in webhook handler:
        plan = await db.get(SubscriptionPlan, plan_id, options=[selectinload(SubscriptionPlan.allocations)])
        db.add_all(build_allocations(sub, plan.allocations))
    """
    return [
        FeatureAllocation(
            subscription_id=subscription.id,
            role=alloc.role,
            feature_key=alloc.feature_key,
            limit_value=alloc.limit_value,
            is_unlimited=alloc.is_unlimited,
        )
        for alloc in plan_allocations
    ]


# # ---------------------------------------------------------------------------
# # Seed SQL — run once in Supabase SQL editor
# # Adjust prices and limits to match your business model.
# # ---------------------------------------------------------------------------
# SEED_SQL = """
# -- Plans
# INSERT INTO subscription_plans (name, description, price_paise, duration_days, is_active)
# VALUES
#   ('Basic',      'Essential AI features for small schools',   99900,  365, true),
#   ('Pro',        'Advanced AI for growing schools',          199900,  365, true),
#   ('Enterprise', 'Unlimited AI for large institutions',      499900,  365, true)
# ON CONFLICT (name) DO NOTHING;

# -- Basic plan allocations
# INSERT INTO plan_allocations (plan_id, role, feature_key, limit_value, is_unlimited)
# SELECT p.id, 'student', 'chatbot_query',   20000,  false FROM subscription_plans p WHERE p.name = 'Basic'
# UNION ALL
# SELECT p.id, 'student', 'quiz_generation', 50000,  false FROM subscription_plans p WHERE p.name = 'Basic'
# UNION ALL
# SELECT p.id, 'teacher', 'notice_post',     50000,  false FROM subscription_plans p WHERE p.name = 'Basic'
# UNION ALL
# SELECT p.id, 'teacher', 'ai_curriculum',   100000, false FROM subscription_plans p WHERE p.name = 'Basic'
# UNION ALL
# SELECT p.id, 'teacher', 'video_upload',    7200,   false FROM subscription_plans p WHERE p.name = 'Basic'
# UNION ALL
# SELECT p.id, 'admin',   'notice_post',     50000,  false FROM subscription_plans p WHERE p.name = 'Basic'
# UNION ALL
# SELECT p.id, 'admin',   'ai_curriculum',   100000, false FROM subscription_plans p WHERE p.name = 'Basic'
# UNION ALL
# SELECT p.id, 'admin',   'video_upload',    7200,   false FROM subscription_plans p WHERE p.name = 'Basic'
# ON CONFLICT DO NOTHING;

# -- Pro plan allocations
# INSERT INTO plan_allocations (plan_id, role, feature_key, limit_value, is_unlimited)
# SELECT p.id, 'student', 'chatbot_query',   50000,  false FROM subscription_plans p WHERE p.name = 'Pro'
# UNION ALL
# SELECT p.id, 'student', 'quiz_generation', 100000, false FROM subscription_plans p WHERE p.name = 'Pro'
# UNION ALL
# SELECT p.id, 'teacher', 'notice_post',     150000, false FROM subscription_plans p WHERE p.name = 'Pro'
# UNION ALL
# SELECT p.id, 'teacher', 'ai_curriculum',   300000, false FROM subscription_plans p WHERE p.name = 'Pro'
# UNION ALL
# SELECT p.id, 'teacher', 'video_upload',    14400,  false FROM subscription_plans p WHERE p.name = 'Pro'
# UNION ALL
# SELECT p.id, 'admin',   'notice_post',     150000, false FROM subscription_plans p WHERE p.name = 'Pro'
# UNION ALL
# SELECT p.id, 'admin',   'ai_curriculum',   300000, false FROM subscription_plans p WHERE p.name = 'Pro'
# UNION ALL
# SELECT p.id, 'admin',   'video_upload',    14400,  false FROM subscription_plans p WHERE p.name = 'Pro'
# ON CONFLICT DO NOTHING;

# -- Enterprise plan allocations (unlimited)
# INSERT INTO plan_allocations (plan_id, role, feature_key, limit_value, is_unlimited)
# SELECT p.id, 'student', 'chatbot_query',   0, true FROM subscription_plans p WHERE p.name = 'Enterprise'
# UNION ALL
# SELECT p.id, 'student', 'quiz_generation', 0, true FROM subscription_plans p WHERE p.name = 'Enterprise'
# UNION ALL
# SELECT p.id, 'teacher', 'notice_post',     0, true FROM subscription_plans p WHERE p.name = 'Enterprise'
# UNION ALL
# SELECT p.id, 'teacher', 'ai_curriculum',   0, true FROM subscription_plans p WHERE p.name = 'Enterprise'
# UNION ALL
# SELECT p.id, 'teacher', 'video_upload',    0, true FROM subscription_plans p WHERE p.name = 'Enterprise'
# UNION ALL
# SELECT p.id, 'admin',   'notice_post',     0, true FROM subscription_plans p WHERE p.name = 'Enterprise'
# UNION ALL
# SELECT p.id, 'admin',   'ai_curriculum',   0, true FROM subscription_plans p WHERE p.name = 'Enterprise'
# UNION ALL
# SELECT p.id, 'admin',   'video_upload',    0, true FROM subscription_plans p WHERE p.name = 'Enterprise'
# ON CONFLICT DO NOTHING;
# """