"""
FastAPI 依赖注入
"""
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from .security import get_current_user, get_optional_user, security
from backend.database.models import User


async def get_current_user_dependency(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """
    获取当前认证用户的依赖
    
    Usage:
        @app.get("/protected")
        async def protected_route(user: User = Depends(get_current_user_dependency)):
            return {"user_id": user.user_id}
    """
    return await get_current_user(credentials)


async def get_optional_user_dependency(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[User]:
    """
    可选获取当前用户的依赖（用于可选认证的端点）
    
    Usage:
        @app.get("/optional")
        async def optional_route(user: Optional[User] = Depends(get_optional_user_dependency)):
            if user:
                return {"user_id": user.user_id}
            return {"message": "未登录"}
    """
    if credentials is None:
        return None
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None
