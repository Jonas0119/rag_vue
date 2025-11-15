"""
认证管理器 - 用户认证和会话管理
"""
import streamlit as st
from typing import Optional
import os

from database import UserDAO
from utils import hash_password, verify_password, validate_password_strength, validate_username


class AuthManager:
    """认证管理器"""
    
    def __init__(self, cookie_name: str = "rag_auth_token",
                 cookie_key: Optional[str] = None,
                 cookie_expiry_days: int = 30):
        """
        初始化认证管理器
        
        Args:
            cookie_name: Cookie 名称
            cookie_key: Cookie 加密密钥
            cookie_expiry_days: Cookie 有效期（天）
        """
        self.user_dao = UserDAO()
        self.cookie_name = cookie_name
        self.cookie_key = cookie_key or os.getenv('AUTH_COOKIE_KEY', 'default_secret_key')
        self.cookie_expiry_days = cookie_expiry_days
    
    def login(self, username: str, password: str) -> tuple[bool, Optional[int], str]:
        """
        用户登录
        
        Args:
            username: 用户名
            password: 密码
        
        Returns:
            (登录是否成功, user_id, 错误信息)
        """
        # 查询用户
        user = self.user_dao.get_user_by_username(username)
        
        if not user:
            return False, None, "用户名或密码错误"
        
        if not user.is_active:
            return False, None, "账户已被禁用"
        
        # 验证密码
        if not verify_password(password, user.password_hash):
            return False, None, "用户名或密码错误"
        
        # 更新最后登录时间
        self.user_dao.update_last_login(user.user_id)
        
        return True, user.user_id, ""
    
    def register(self, username: str, password: str, 
                email: Optional[str] = None,
                display_name: Optional[str] = None) -> tuple[bool, Optional[int], str]:
        """
        用户注册
        
        Args:
            username: 用户名
            password: 密码
            email: 邮箱（可选）
            display_name: 显示名称（可选）
        
        Returns:
            (注册是否成功, user_id, 错误信息)
        """
        # 验证用户名
        valid, error_msg = validate_username(username)
        if not valid:
            return False, None, error_msg
        
        # 验证密码强度
        valid, error_msg = validate_password_strength(password)
        if not valid:
            return False, None, error_msg
        
        # 检查用户名是否已存在
        if self.user_dao.username_exists(username):
            return False, None, "用户名已存在"
        
        # 检查邮箱是否已存在
        if email and self.user_dao.email_exists(email):
            return False, None, "邮箱已被使用"
        
        # 加密密码
        password_hash = hash_password(password)
        
        # 创建用户
        try:
            user_id = self.user_dao.create_user(
                username=username,
                password_hash=password_hash,
                email=email,
                display_name=display_name or username
            )
            
            # 创建用户目录
            self._create_user_directories(user_id)
            
            return True, user_id, ""
        
        except Exception as e:
            return False, None, f"注册失败: {str(e)}"
    
    def _create_user_directories(self, user_id: int):
        """为新用户创建目录结构"""
        import os
        from pathlib import Path
        
        # 创建用户目录
        user_dir = Path(f"data/users/user_{user_id}")
        user_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建子目录
        (user_dir / "uploads").mkdir(exist_ok=True)
        (user_dir / "exports").mkdir(exist_ok=True)
        
        # 创建向量库目录
        chroma_dir = Path(f"data/chroma/user_{user_id}_collection")
        chroma_dir.mkdir(parents=True, exist_ok=True)
    
    def logout(self):
        """用户登出"""
        # 清除 session state
        for key in ['authenticated', 'user_id', 'username', 'display_name']:
            if key in st.session_state:
                del st.session_state[key]
    
    def is_authenticated(self) -> bool:
        """检查用户是否已登录"""
        return st.session_state.get('authenticated', False)
    
    def get_current_user_id(self) -> Optional[int]:
        """获取当前登录用户的 ID"""
        return st.session_state.get('user_id')
    
    def get_current_username(self) -> Optional[str]:
        """获取当前登录用户的用户名"""
        return st.session_state.get('username')
    
    def set_session(self, user_id: int, username: str, display_name: str):
        """设置登录会话"""
        st.session_state['authenticated'] = True
        st.session_state['user_id'] = user_id
        st.session_state['username'] = username
        st.session_state['display_name'] = display_name

