from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.database import get_async_db
from app.core.security import decode_token
from app.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.async_query import async_query
security = HTTPBearer(auto_error=True)

async def get_current_user(credentials: HTTPAuthorizationCredentials=Depends(security), db: AsyncSession=Depends(get_async_db)) -> User:
    token = credentials.credentials
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail='Invalid or expired token')
    user_id = payload.get('sub')
    try:
        user_id_int = int(user_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail='Invalid token payload')
    user = await async_query(db, User).filter(User.id == user_id_int).first()
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    if not user.is_active:
        raise HTTPException(status_code=403, detail='Account is deactivated')
    return user

def require_role(allowed_roles: list[str]):

    def role_checker(current_user: User=Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail=f'Access denied. Required roles: {allowed_roles}')
        return current_user
    return role_checker
