from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.core.database import get_async_db
from app.core.security import decode_token
from app.models.user import User, UserRole
from sqlalchemy.ext.asyncio import AsyncSession
bearer_scheme = HTTPBearer(auto_error=False)

async def get_current_user(credentials: HTTPAuthorizationCredentials | None=Depends(bearer_scheme), db: AsyncSession=Depends(get_async_db)) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Not authenticated')
    try:
        payload = decode_token(credentials.credentials)
        if payload.get('type', 'access') != 'access':
            raise ValueError('Invalid token type')
        user_id = int(payload.get('sub'))
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid token')
    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='User not found or inactive')
    return user

def require_roles(*allowed_roles: UserRole | str):
    allowed = {role.value if isinstance(role, UserRole) else role for role in allowed_roles}

    def checker(current_user: User=Depends(get_current_user)) -> User:
        if current_user.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='You do not have permission')
        return current_user
    return checker

def require_school_admin(current_user: User=Depends(get_current_user)) -> User:
    allowed = {UserRole.SCHOOL_OWNER.value, UserRole.SCHOOL_ADMIN.value, UserRole.SUPER_ADMIN.value}
    if current_user.role not in allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Admin access required')
    if current_user.role != UserRole.SUPER_ADMIN.value and (not current_user.school_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='User is not linked to a school')
    return current_user

def current_school_id(current_user: User=Depends(get_current_user)) -> int:
    if not current_user.school_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='User is not linked to a school')
    return current_user.school_id
