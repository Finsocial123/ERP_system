from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_async_db
from app.dependencies.auth import get_current_user, require_roles
from app.models.notice import NoticeStatus
from app.models.user import User, UserRole
from app.schemas.notice import NoticeCreate, NoticeListOut, NoticeOut, NoticePinUpdate, NoticeUpdate, NoticeEnhanceRequest, NoticeEnhanceOut, NoticeGenerateRequest, NoticeGenerateOut, NoticePriority
from app.services import notice_service
router = APIRouter(prefix='/notices', tags=['Notice Board'])

@router.post('/enhance', response_model=NoticeEnhanceOut)
async def enhance_notice(payload: NoticeEnhanceRequest, db: AsyncSession=Depends(get_async_db), current_user: User=Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_OWNER, UserRole.SCHOOL_ADMIN, UserRole.TEACHER))):
    enhanced = await notice_service.enhance_notice_content(payload.content, current_user, db)
    return {'original': payload.content, 'enhanced': enhanced}

@router.post('/generate', response_model=NoticeGenerateOut)
async def generate_notice_from_description(payload: NoticeGenerateRequest,db: AsyncSession=Depends(get_async_db), current_user: User=Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.SCHOOL_OWNER, UserRole.SCHOOL_ADMIN, UserRole.TEACHER))):
    generated = await notice_service.generate_notice_content(payload.description, current_user, db)
    return {'description': payload.description, 'generated': generated}

@router.post('/', response_model=NoticeOut, status_code=201)
async def create_notice(payload: NoticeCreate, db: AsyncSession=Depends(get_async_db), current_user: User=Depends(get_current_user)):
    return await notice_service.create_notice(db, payload, current_user)

@router.get('/', response_model=NoticeListOut)
async def list_notices(skip: int=Query(0, ge=0), limit: int=Query(20, ge=1, le=100), status: NoticeStatus | None=Query(None), priority: NoticePriority | None=Query(None), pinned_only: bool=Query(False), db: AsyncSession=Depends(get_async_db), current_user: User=Depends(get_current_user), exclude_self: bool=Query(False), created_by_self: bool=Query(False), unread_only: bool=Query(False)):
    return await notice_service.list_notices(db, current_user, skip, limit, status, priority, pinned_only, exclude_self, created_by_self, unread_only=unread_only)

@router.get('/{notice_id}', response_model=NoticeOut)
async def get_notice(notice_id: int, db: AsyncSession=Depends(get_async_db), current_user: User=Depends(get_current_user)):
    return await notice_service.get_notice(db, notice_id, current_user)

@router.patch('/{notice_id}', response_model=NoticeOut)
async def update_notice(notice_id: int, payload: NoticeUpdate, db: AsyncSession=Depends(get_async_db), current_user: User=Depends(get_current_user)):
    return await notice_service.update_notice(db, notice_id, payload, current_user)

@router.patch('/{notice_id}/pin', response_model=NoticeOut)
async def pin_notice(notice_id: int, payload: NoticePinUpdate, db: AsyncSession=Depends(get_async_db), current_user: User=Depends(get_current_user)):
    return await notice_service.pin_notice(db, notice_id, payload.is_pinned, current_user)

@router.post('/{notice_id}/read', status_code=200)
async def mark_read(notice_id: int, db: AsyncSession=Depends(get_async_db), current_user: User=Depends(get_current_user)):
    return await notice_service.mark_read(db, notice_id, current_user)

@router.delete('/{notice_id}', status_code=204)
async def delete_notice(notice_id: int, db: AsyncSession=Depends(get_async_db), current_user: User=Depends(get_current_user)):
    await notice_service.delete_notice(db, notice_id, current_user)
