"""
JWT 认证和安全工具
"""
from datetime import datetime, timedelta
from typing import Optional
import jwt
from fastapi import HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .config import settings
from backend.database import UserDAO

security = HTTPBearer()


def create_access_token(user_id: int, username: str, display_name: str) -> str:
    """
    创建 JWT access token
    
    Args:
        user_id: 用户 ID
        username: 用户名
        display_name: 显示名称
    
    Returns:
        JWT token 字符串
    """
    payload = {
        "user_id": user_id,
        "username": username,
        "display_name": display_name,
        "exp": datetime.utcnow() + timedelta(days=settings.JWT_EXPIRY_DAYS),
        "iat": datetime.utcnow(),
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token


def decode_token(token: str) -> Optional[dict]:
    """
    解码并验证 JWT token
    
    Args:
        token: JWT token 字符串
    
    Returns:
        token payload 字典，如果无效则返回 None
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = security
) -> "User":
    """
    从 JWT token 获取当前用户
    
    Args:
        credentials: HTTP Bearer token 凭证
    
    Returns:
        User 对象
    
    Raises:
        HTTPException: 如果 token 无效或用户不存在
    """
    token = credentials.credentials
    payload = decode_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("user_id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 从数据库获取用户
    user_dao = UserDAO()
    user = user_dao.get_user_by_id(user_id)
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已被禁用",
        )
    
    return user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = None
) -> Optional["User"]:
    """
    可选地获取当前用户（用于可选认证的端点）
    
    Args:
        credentials: HTTP Bearer token 凭证（可选）
    
    Returns:
        User 对象或 None
    """
    if credentials is None:
        return None
    
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None
