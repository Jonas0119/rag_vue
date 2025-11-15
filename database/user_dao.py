"""
用户数据访问对象 (User DAO)
"""
from typing import Optional, List
from datetime import datetime
import json

from .db_manager import DatabaseManager, get_db_manager
from .models import User, UserStats


class UserDAO:
    """用户数据访问对象"""
    
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or get_db_manager()
    
    def create_user(self, username: str, password_hash: str, 
                   email: Optional[str] = None,
                   display_name: Optional[str] = None) -> int:
        """
        创建新用户
        
        Returns:
            user_id: 新创建用户的 ID
        """
        query = """
            INSERT INTO users (username, password_hash, email, display_name)
            VALUES (?, ?, ?, ?)
        """
        user_id = self.db.execute_insert(
            query, 
            (username, password_hash, email, display_name or username)
        )
        
        # 同时创建用户统计记录
        self._init_user_stats(user_id)
        
        return user_id
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """根据 ID 获取用户"""
        query = "SELECT * FROM users WHERE user_id = ?"
        row = self.db.execute_one(query, (user_id,))
        return User.from_db_row(row) if row else None
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """根据用户名获取用户"""
        query = "SELECT * FROM users WHERE username = ?"
        row = self.db.execute_one(query, (username,))
        return User.from_db_row(row) if row else None
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """根据邮箱获取用户"""
        query = "SELECT * FROM users WHERE email = ?"
        row = self.db.execute_one(query, (email,))
        return User.from_db_row(row) if row else None
    
    def update_user(self, user_id: int, **kwargs):
        """更新用户信息"""
        allowed_fields = ['email', 'display_name', 'avatar_url', 'preferences', 'is_active']
        updates = []
        params = []
        
        for field, value in kwargs.items():
            if field in allowed_fields:
                if field == 'preferences' and isinstance(value, dict):
                    value = json.dumps(value)
                updates.append(f"{field} = ?")
                params.append(value)
        
        if not updates:
            return 0
        
        params.append(user_id)
        query = f"UPDATE users SET {', '.join(updates)} WHERE user_id = ?"
        return self.db.execute_update(query, tuple(params))
    
    def update_last_login(self, user_id: int):
        """更新最后登录时间"""
        query = "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE user_id = ?"
        return self.db.execute_update(query, (user_id,))
    
    def delete_user(self, user_id: int):
        """删除用户（软删除：设为不活跃）"""
        query = "UPDATE users SET is_active = FALSE WHERE user_id = ?"
        return self.db.execute_update(query, (user_id,))
    
    def username_exists(self, username: str) -> bool:
        """检查用户名是否已存在"""
        query = "SELECT COUNT(*) as count FROM users WHERE username = ?"
        row = self.db.execute_one(query, (username,))
        return row['count'] > 0 if row else False
    
    def email_exists(self, email: str) -> bool:
        """检查邮箱是否已存在"""
        query = "SELECT COUNT(*) as count FROM users WHERE email = ?"
        row = self.db.execute_one(query, (email,))
        return row['count'] > 0 if row else False
    
    def get_all_users(self, active_only: bool = True) -> List[User]:
        """获取所有用户"""
        query = "SELECT * FROM users"
        if active_only:
            query += " WHERE is_active = TRUE"
        query += " ORDER BY created_at DESC"
        
        rows = self.db.execute_query(query)
        return [User.from_db_row(row) for row in rows]
    
    # ==================== 用户统计相关 ====================
    
    def _init_user_stats(self, user_id: int):
        """初始化用户统计"""
        query = """
            INSERT INTO user_stats (user_id, last_active)
            VALUES (?, CURRENT_TIMESTAMP)
        """
        self.db.execute_insert(query, (user_id,))
    
    def get_user_stats(self, user_id: int) -> Optional[UserStats]:
        """获取用户统计"""
        query = "SELECT * FROM user_stats WHERE user_id = ?"
        row = self.db.execute_one(query, (user_id,))
        return UserStats.from_db_row(row) if row else None
    
    def update_user_stats(self, user_id: int, **kwargs):
        """更新用户统计"""
        allowed_fields = ['total_sessions', 'total_messages', 'total_documents', 
                         'storage_used', 'total_tokens']
        updates = []
        params = []
        
        for field, value in kwargs.items():
            if field in allowed_fields:
                updates.append(f"{field} = ?")
                params.append(value)
        
        if not updates:
            return 0
        
        params.append(user_id)
        query = f"UPDATE user_stats SET {', '.join(updates)}, last_active = CURRENT_TIMESTAMP WHERE user_id = ?"
        return self.db.execute_update(query, tuple(params))
    
    def increment_stat(self, user_id: int, field: str, increment: int = 1):
        """增加统计数值"""
        allowed_fields = ['total_sessions', 'total_messages', 'total_documents', 'total_tokens']
        if field not in allowed_fields:
            raise ValueError(f"Invalid field: {field}")
        
        query = f"""
            UPDATE user_stats 
            SET {field} = {field} + ?, last_active = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """
        return self.db.execute_update(query, (increment, user_id))

