

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator



class SubscriptionCreate(BaseModel):
    """POST /subscriptions  — admin creates a subscription for a school."""
    school_id  : int      = Field(..., description="ID of the school being subscribed")
    plan_name  : str      = Field(..., min_length=1, max_length=100, description="e.g. 'Standard', 'Pro'")
    started_at : datetime = Field(..., description="When the subscription begins (UTC)")
    expires_at : datetime = Field(..., description="When the subscription ends (UTC)")

    @model_validator(mode="after")
    def expires_after_start(self) -> "SubscriptionCreate":
        if self.expires_at <= self.started_at:
            raise ValueError("expires_at must be after started_at")
        return self


class SubscriptionResponse(BaseModel):
    """Returned after creating or fetching a subscription."""
    id         : int
    school_id  : int
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

    # Human-readable unit label derived from feature_key
    unit            : str = ""

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def set_unit(self) -> "FeatureAllocationResponse":
        unit_map = {
            "chatbot_query" : "tokens",
            "notice_post"   : "posts",
            "ai_curriculum" : "generations",
            "video_upload"  : "seconds",
        }
        self.unit = unit_map.get(self.feature_key, "units")
        return self


class SubscriptionDetailResponse(SubscriptionResponse):
    """Full subscription with its allocations — for admin detail view."""
    allocations: list[FeatureAllocationResponse] = []




class QuotaStatusResponse(BaseModel):
    """
    Returned from GET /subscriptions/my-quota?feature=chatbot_query
    Safe to expose to any authenticated user for their own feature.
    """
    feature_key              : str
    limit                    : Optional[int]      # None if unlimited
    used                     : int
    remaining                : Optional[int]      # None if unlimited
    is_unlimited             : bool
    has_active_subscription  : bool
    subscription_expires_at  : Optional[datetime]

    # Human-friendly display values — computed from raw numbers
    limit_display     : str = ""
    used_display      : str = ""
    remaining_display : str = ""

    model_config = {"from_attributes": False}

    @model_validator(mode="after")
    def build_display(self) -> "QuotaStatusResponse":
        """
        Convert raw values to human-readable strings based on feature type.
        chatbot_query  → token counts  (e.g. "4,500 / 20,000 tokens")
        video_upload   → minutes       (e.g. "45 / 120 min")
        others         → plain counts  (e.g. "3 / 10")
        """
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

        if fk == "chatbot_query":
            self.limit_display     = f"{limit:,} tokens"
            self.used_display      = f"{used:,} tokens"
            self.remaining_display = f"{remaining:,} tokens"

        elif fk == "video_upload":
            # stored as seconds, display as minutes
            self.limit_display     = f"{limit // 60} min"
            self.used_display      = f"{used // 60} min"
            self.remaining_display = f"{remaining // 60} min"

        else:
            self.limit_display     = str(limit)
            self.used_display      = str(used)
            self.remaining_display = str(remaining)

        return self


class AllQuotasResponse(BaseModel):
    """All quota statuses for the current user — one dict per feature they have access to."""
    user_id  : int
    school_id: int
    quotas   : list[QuotaStatusResponse]




class FeatureUsageSummary(BaseModel):
    """Usage for one feature across all users in the school."""
    feature_key    : str
    role           : str
    total_used     : int
    limit_per_user : int
    unit           : str = ""

    @model_validator(mode="after")
    def set_unit(self) -> "FeatureUsageSummary":
        unit_map = {
            "chatbot_query" : "tokens",
            "notice_post"   : "posts",
            "ai_curriculum" : "generations",
            "video_upload"  : "seconds",
        }
        self.unit = unit_map.get(self.feature_key, "units")
        return self


class SchoolUsageSummaryResponse(BaseModel):
    """
    Returned from GET /subscriptions/school-summary
    Admin-only. Shows the active subscription + aggregated usage per feature.
    """
    subscription    : Optional[SubscriptionResponse]
    usage_by_feature: list[FeatureUsageSummary]




class AllocationUpdateRequest(BaseModel):
    """
    PATCH /subscriptions/{sub_id}/allocations/{alloc_id}
    Admin can bump or reduce a role's limit without recreating the subscription.
    """
    limit_value  : Optional[int]  = Field(None, gt=0)
    is_unlimited : Optional[bool] = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> "AllocationUpdateRequest":
        if self.limit_value is None and self.is_unlimited is None:
            raise ValueError("Provide at least one of limit_value or is_unlimited")
        return self