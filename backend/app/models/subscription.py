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
    UniqueConstraint
)

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from models.school import School

class SubscriptionStatus(str, enum.Enum):
    active = "active"
    expired = "expired"
    cancelled = "cancelled"


class UserRole(str, enum.Enum):
    student = "student"
    teacher = "teacher"
    admin = "admin"

class FeatureKey(str, enum.Enum):
    chatbot_query = "chatbot_query"
    notice_post = "notice_post"
    ai_curriculum = "ai_curriculum"
    video_upload = "video_upload"


class Subscription(Base):
    __tablename__ = "subscription"

    id : Mapped[int] = mapped_column(primary_key=True, index=True)
    school_id : Mapped[int] = mapped_column(
        Integer, ForeignKey("schools.id", ondelete="CASCADE")
    )
    plan_name : Mapped[str] = mapped_column(String(100), nullable=False)
    status : Mapped[SubscriptionStatus] = mapped_column(Enum(SubscriptionStatus), nullable=False, default=SubscriptionStatus.active)
    started_at : Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at : Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at : Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    school : Mapped["School"] = relationship("School")
    allocations : Mapped[list["FeatureAllocation"]] = relationship(back_populates="subscription", cascade="all, delete-orphan")
    usages : Mapped[list["UserFeatureUsage"]] = relationship(back_populates="subscription", cascade="all, delete-orphan")

    def is_active(self) -> bool:
        return  (
            self.status == SubscriptionStatus.active and self.expires_at > datetime.utcnow()
        )
    



class FeatureAllocation(Base):
    __tablename__ = "feature_allocation"
    __table_args__ = (
        UniqueConstraint(
            "subscription_id", "role", "feature_key",
            name="uq_alloc_sub_role_feature"
        ),
    )

    id : Mapped[int] = mapped_column(primary_key=True, index=True)
    Subscription_id : Mapped[int] = mapped_column(
        Integer, ForeignKey("subscription.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    role : Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False)
    feature_key : Mapped[FeatureKey] = mapped_column(Enum(FeatureKey), nullable=False)

    limit_value : Mapped[int] = mapped_column(BigInteger, nullable=False)
    is_unlimited : Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at : Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    subscription: Mapped["Subscription"] = relationship(back_populates="allocation")


class UserFeatureUsage(Base):
    __tablename__ = "user_feature_usage"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "subscription_id", "feature_key",
            name="uq_usage_user_sub_feature"
        )
    )

    id : Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id : Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True
    )

    subscription_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("subscriptions.id", ondelete="CASCADE")
    )
    feature_key: Mapped[FeatureKey] = mapped_column(Enum(FeatureKey), nullable=False)

    used_value : Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)


    period_start : Mapped[datetime] = mapped_column(DateTime, nullable=False)
    period_end : Mapped[datetime] = mapped_column(DateTime, nullable=False)

    last_used_at : Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at : Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    subscription: Mapped["Subscription"] = relationship(back_populates="usages")




DEFAULT_ALLOCATIONS: list[dict] = [
    # Students: 20 000 tokens for chatbot
    {"role": UserRole.student, "feature_key": FeatureKey.chatbot_query, "limit_value": 20_000},
 
    # Teachers: 10 notices · 10 curricula · 7 200 s (120 min) video upload
    {"role": UserRole.teacher, "feature_key": FeatureKey.notice_post,   "limit_value": 10},
    {"role": UserRole.teacher, "feature_key": FeatureKey.ai_curriculum, "limit_value": 10},
    {"role": UserRole.teacher, "feature_key": FeatureKey.video_upload,  "limit_value": 7_200},
 
    # Admins: 10 notices · 10 curricula (no video cap by default)
    {"role": UserRole.admin, "feature_key": FeatureKey.notice_post,   "limit_value": 10},
    {"role": UserRole.admin, "feature_key": FeatureKey.ai_curriculum, "limit_value": 10},
]




def build_allocation(subscription: Subscription) -> list[FeatureAllocation]:

    return [
        FeatureAllocation(
            subscription_id=subscription.id,
            role=row["role"],
            feature_key=row["feature_key"],
            limit_value=row["limit_value"],
        )
        for row in DEFAULT_ALLOCATIONS
    ]