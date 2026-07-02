from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator



# Plan schemas


class PlanAllocationResponse(BaseModel):
    role         : str
    feature_key  : str
    limit_value  : int
    is_unlimited : bool
    unit         : str = ""

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def set_unit(self) -> "PlanAllocationResponse":
        unit_map = {
            "chatbot_query"  : "tokens",
            "notice_post"    : "tokens",
            "ai_curriculum"  : "tokens",
            "video_upload"   : "seconds",
            "quiz_generation": "tokens",
        }
        self.unit = unit_map.get(self.feature_key, "units")
        return self


class PlanResponse(BaseModel):
    """Returned from GET /plans — what school admin sees when choosing a plan."""
    id            : int
    name          : str
    description   : Optional[str]
    price_paise   : int
    duration_days : int
    is_active     : bool
    allocations   : list[PlanAllocationResponse] = []

    # Human-readable price
    price_display : str = ""

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def set_price_display(self) -> "PlanResponse":
        rupees = self.price_paise / 100
        self.price_display = f"₹{rupees:,.0f}"
        return self



# Razorpay schemas


class SubscriptionOrderCreate(BaseModel):
    """POST /razorpay/create-order — school admin picks a plan and initiates payment."""
    plan_id : int = Field(..., description="ID of the plan to purchase")


class SubscriptionOrderResponse(BaseModel):
    """Returned after creating a Razorpay order — frontend uses this to open checkout."""
    order_id      : str
    amount        : int    # in paise
    currency      : str
    key           : str    # Razorpay key_id for frontend
    plan_id       : int
    plan_name     : str
    price_display : str


class SubscriptionVerify(BaseModel):
    """POST /razorpay/verify-payment — sent after Razorpay checkout succeeds."""
    razorpay_order_id   : str
    razorpay_payment_id : str
    razorpay_signature  : str
    plan_id             : int



# Subscription schemas (existing, unchanged)


class SubscriptionCreate(BaseModel):
    """Manual creation — super admin only, bypasses payment."""
    school_id  : int      = Field(..., description="ID of the school being subscribed")
    plan_id    : int      = Field(..., description="ID of the plan")
    started_at : datetime = Field(..., description="When the subscription begins (UTC)")
    expires_at : datetime = Field(..., description="When the subscription ends (UTC)")

    @model_validator(mode="after")
    def expires_after_start(self) -> "SubscriptionCreate":
        if self.expires_at <= self.started_at:
            raise ValueError("expires_at must be after started_at")
        return self


class SubscriptionResponse(BaseModel):
    id         : int
    school_id  : int
    plan_id    : int
    plan_name  : str
    status     : str
    started_at : datetime
    expires_at : datetime
    created_at : datetime
    updated_at : datetime

    model_config = {"from_attributes": True}


class FeatureAllocationResponse(BaseModel):
    id              : int
    subscription_id : int
    role            : str
    feature_key     : str
    limit_value     : int
    is_unlimited    : bool
    unit            : str = ""

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def set_unit(self) -> "FeatureAllocationResponse":
        unit_map = {
            "chatbot_query"  : "tokens",
            "notice_post"    : "tokens",
            "ai_curriculum"  : "tokens",
            "video_upload"   : "seconds",
            "quiz_generation": "tokens",
        }
        self.unit = unit_map.get(self.feature_key, "units")
        return self


class SubscriptionDetailResponse(SubscriptionResponse):
    allocations: list[FeatureAllocationResponse] = []



# Quota schemas (existing, updated with quiz_generation display)


class QuotaStatusResponse(BaseModel):
    feature_key             : str
    limit                   : Optional[int]
    used                    : int
    remaining               : Optional[int]
    is_unlimited            : bool
    has_active_subscription : bool
    subscription_expires_at : Optional[datetime]
    limit_display           : str = ""
    used_display            : str = ""
    remaining_display       : str = ""

    model_config = {"from_attributes": False}

    @model_validator(mode="after")
    def build_display(self) -> "QuotaStatusResponse":
        fk = self.feature_key

        if self.is_unlimited:
            self.limit_display     = "Unlimited"
            self.used_display      = str(self.used)
            self.remaining_display = "Unlimited"
            return self

        if not self.has_active_subscription:
            self.limit_display     = "No subscription"
            self.used_display      = "—"
            self.remaining_display = "—"
            return self

        limit     = self.limit     or 0
        used      = self.used      or 0
        remaining = self.remaining or 0

        if fk == "video_upload":
            self.limit_display     = f"{limit // 60} min"
            self.used_display      = f"{used // 60} min"
            self.remaining_display = f"{remaining // 60} min"
        elif fk in ("chatbot_query", "notice_post", "ai_curriculum", "quiz_generation"):
            self.limit_display     = f"{limit:,} tokens"
            self.used_display      = f"{used:,} tokens"
            self.remaining_display = f"{remaining:,} tokens"
        else:
            self.limit_display     = str(limit)
            self.used_display      = str(used)
            self.remaining_display = str(remaining)

        return self


class AllQuotasResponse(BaseModel):
    user_id   : int
    school_id : int
    quotas    : list[QuotaStatusResponse]


class FeatureUsageSummary(BaseModel):
    feature_key    : str
    role           : str
    total_used     : int
    limit_per_user : int
    unit           : str = ""

    @model_validator(mode="after")
    def set_unit(self) -> "FeatureUsageSummary":
        unit_map = {
            "chatbot_query"  : "tokens",
            "notice_post"    : "tokens",
            "ai_curriculum"  : "tokens",
            "video_upload"   : "seconds",
            "quiz_generation": "tokens",
        }
        self.unit = unit_map.get(self.feature_key, "units")
        return self


class SchoolUsageSummaryResponse(BaseModel):
    subscription     : Optional[SubscriptionResponse]
    usage_by_feature : list[FeatureUsageSummary]


class AllocationUpdateRequest(BaseModel):
    limit_value  : Optional[int]  = Field(None, gt=0)
    is_unlimited : Optional[bool] = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> "AllocationUpdateRequest":
        if self.limit_value is None and self.is_unlimited is None:
            raise ValueError("Provide at least one of limit_value or is_unlimited")
        return self