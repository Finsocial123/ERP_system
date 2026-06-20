from dataclasses import dataclass

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.dependencies.auth import get_current_user, current_school_id
from app.models.user import User
from app.models.subscription import FeatureKey, Subscription, UserFeatureUsage
from app.services.subscription_service import check_quota, consume


@dataclass
class QuotaContext:
    subscription: Subscription
    usage: UserFeatureUsage
    Feature_key: FeatureKey


def _make_quota_dep(feature_key: FeatureKey, amount: int = 1):
    async def dep(
        current_user : User = Depends(get_current_user),
        school_id : int = Depends(current_school_id),
        db : AsyncSession = Depends(get_async_db)
    ) -> QuotaContext:
        sub, usage = await check_quota(
            db=db,
            user_id=current_user.id,
            school_id=school_id,
            user_role=current_user.role,
            feature_key=feature_key,
            amount=amount,
        )
        return QuotaContext(subscription=sub, usage=usage, feature_key=feature_key)
    return dep



# Students — chatbot pre-check (amount=1, consume actual tokens after LLM call)
require_chatbot_quota    = _make_quota_dep(FeatureKey.chatbot_query, amount=1)
 
# Teachers / Admins — notice generator pre-check
require_notice_quota     = _make_quota_dep(FeatureKey.notice_post, amount=1)
 
# Teachers / Admins — curriculum generator pre-check
require_curriculum_quota = _make_quota_dep(FeatureKey.ai_curriculum, amount=1)



def require_video_quota(duration_seconds: int):
    async def dep(
        current_user : User = Depends(get_current_user),
        school_id : int = Depends(current_school_id),
        db : AsyncSession = Depends(get_async_db)
    ) -> QuotaContext:
        sub, usage = await check_quota(
            db=db,
            user_id=current_user.id,
            school_id=school_id,
            user_role=current_user.role,
            feature_key=FeatureKey.video_upload,
            amount=duration_seconds,
        )
        return QuotaContext(subscription=sub, usage=usage, feature_key=FeatureKey.video_upload)
    return dep
