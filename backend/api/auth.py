"""
认证 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from typing import Optional

from backend.core.security import create_access_token
from backend.core.dependencies import get_current_user_dependency
from backend.core.config import settings
from backend.database import UserDAO
from backend.database.models import User
from backend.utils import (
    hash_password,
    verify_password,
    validate_password_strength,
    validate_username
)

router = APIRouter()


# Pydantic 模型
class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    email: Optional[EmailStr] = None
    display_name: Optional[str] = None


class LoginResponse(BaseModel):
    success: bool
    token: Optional[str] = None
    user: Optional[dict] = None
    message: Optional[str] = None


class UserResponse(BaseModel):
    user_id: int
    username: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    created_at: Optional[str] = None
    last_login: Optional[str] = None


@router.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    用户登录
    
    Returns:
        JWT token 和用户信息
    """
    user_dao = UserDAO()
    
    # 查询用户
    user = user_dao.get_user_by_username(request.username)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已被禁用"
        )
    
    # 验证密码
    if not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )
    
    # 更新最后登录时间
    user_dao.update_last_login(user.user_id)
    
    # 生成 JWT token
    token = create_access_token(
        user_id=user.user_id,
        username=user.username,
        display_name=user.display_name or user.username
    )
    
    # 返回响应
    user_dict = user.to_dict()
    # 移除敏感信息
    user_dict.pop('password_hash', None)
    
    return LoginResponse(
        success=True,
        token=token,
        user=user_dict,
        message="登录成功"
    )


@router.post("/auth/register", response_model=LoginResponse)
async def register(request: RegisterRequest):
    """
    用户注册
    
    Returns:
        JWT token 和用户信息
    """
    user_dao = UserDAO()
    
    # 验证用户名
    valid, error_msg = validate_username(request.username)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    
    # 验证密码强度
    valid, error_msg = validate_password_strength(request.password)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    
    # 检查用户名是否已存在
    if user_dao.username_exists(request.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在"
        )
    
    # 检查邮箱是否已存在
    if request.email and user_dao.email_exists(request.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱已被使用"
        )
    
    # 加密密码
    password_hash = hash_password(request.password)
    
    # 创建用户
    try:
        user_id = user_dao.create_user(
            username=request.username,
            password_hash=password_hash,
            email=request.email,
            display_name=request.display_name or request.username
        )
        
        # 创建用户目录（仅在本地模式下）
        from pathlib import Path
        from backend.utils.config import config
        
        if config.STORAGE_MODE == "local":
            user_dir = Path(f"data/users/user_{user_id}")
            user_dir.mkdir(parents=True, exist_ok=True)
            (user_dir / "uploads").mkdir(exist_ok=True)
            (user_dir / "exports").mkdir(exist_ok=True)
        
        if config.VECTOR_DB_MODE == "local":
            chroma_dir = Path(f"data/chroma/user_{user_id}_collection")
            chroma_dir.mkdir(parents=True, exist_ok=True)
        
        # 获取用户信息
        user = user_dao.get_user_by_id(user_id)
        
        # 生成 JWT token
        token = create_access_token(
            user_id=user.user_id,
            username=user.username,
            display_name=user.display_name or user.username
        )
        
        # 返回响应
        user_dict = user.to_dict()
        user_dict.pop('password_hash', None)
        
        return LoginResponse(
            success=True,
            token=token,
            user=user_dict,
            message="注册成功"
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"注册失败: {str(e)}"
        )


@router.post("/auth/logout")
async def logout():
    """
    用户登出
    
    Returns:
        成功消息
    """
    return {
        "success": True,
        "message": "登出成功"
    }


@router.get("/auth/me", response_model=UserResponse)
async def get_current_user_info(
    user: User = Depends(get_current_user_dependency)
):
    """
    获取当前登录用户信息
    
    Returns:
        用户信息
    """
    user_dict = user.to_dict()
    user_dict.pop('password_hash', None)
    
    return UserResponse(**user_dict)
