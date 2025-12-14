"""
会话数据访问对象 (Session DAO)
"""
from typing import Optional, List, Dict
from datetime import datetime
import uuid

from .db_manager import DatabaseManager, get_db_manager
from .models import Session


class SessionDAO:
    """会话数据访问对象"""
    
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or get_db_manager()
    
    def create_session(self, user_id: int, title: str) -> str:
        """
        创建新会话
        
        Returns:
            session_id: 新创建会话的 ID (UUID)
        """
        session_id = str(uuid.uuid4())
        query = """
            INSERT INTO sessions (session_id, user_id, title)
            VALUES (?, ?, ?)
        """
        self.db.execute_insert(query, (session_id, user_id, title))
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """获取单个会话"""
        query = "SELECT * FROM sessions WHERE session_id = ?"
        row = self.db.execute_one(query, (session_id,))
        return Session.from_db_row(row) if row else None
    
    def get_user_sessions(self, user_id: int, status: str = 'active', 
                         limit: int = 50) -> List[Session]:
        """
        获取用户的所有会话
        
        Args:
            user_id: 用户 ID
            status: 会话状态 ('active', 'archived')
            limit: 返回数量限制
        """
        query = """
            SELECT * FROM sessions 
            WHERE user_id = ? AND status = ?
            ORDER BY is_pinned DESC, updated_at DESC
            LIMIT ?
        """
        rows = self.db.execute_query(query, (user_id, status, limit))
        return [Session.from_db_row(row) for row in rows]
    
    def get_sessions_grouped_by_time(self, user_id: int) -> Dict[str, List[Session]]:
        """
        获取用户会话并按时间分组
        
        Returns:
            分组后的字典: {'today': [], 'yesterday': [], 'this_week': [], ...}
        """
        # 根据数据库类型选择不同的日期函数
        if self.db.db_type == "postgresql":
            query = """
                SELECT *,
                    CASE 
                        WHEN DATE(updated_at) = CURRENT_DATE THEN 'today'
                        WHEN DATE(updated_at) = CURRENT_DATE - INTERVAL '1 day' THEN 'yesterday'
                        WHEN updated_at >= CURRENT_DATE - INTERVAL '7 days' THEN 'this_week'
                        WHEN updated_at >= CURRENT_DATE - INTERVAL '30 days' THEN 'this_month'
                        ELSE 'older'
                    END as time_group
                FROM sessions
                WHERE user_id = ? AND status = 'active'
                ORDER BY is_pinned DESC, updated_at DESC
                LIMIT 50
            """
        else:
            query = """
                SELECT *,
                    CASE 
                        WHEN DATE(updated_at) = DATE('now') THEN 'today'
                        WHEN DATE(updated_at) = DATE('now', '-1 day') THEN 'yesterday'
                        WHEN DATE(updated_at) >= DATE('now', '-7 day') THEN 'this_week'
                        WHEN DATE(updated_at) >= DATE('now', '-30 day') THEN 'this_month'
                        ELSE 'older'
                    END as time_group
                FROM sessions
                WHERE user_id = ? AND status = 'active'
                ORDER BY is_pinned DESC, updated_at DESC
                LIMIT 50
            """
        rows = self.db.execute_query(query, (user_id,))
        
        # 按时间分组
        grouped = {
            'pinned': [],
            'today': [],
            'yesterday': [],
            'this_week': [],
            'this_month': [],
            'older': []
        }
        
        for row in rows:
            session = Session.from_db_row(row)
            if session.is_pinned:
                grouped['pinned'].append(session)
            else:
                time_group = row['time_group']
                grouped[time_group].append(session)
        
        return grouped
    
    def update_session(self, session_id: str, update_time: bool = False, **kwargs):
        """
        更新会话信息
        
        Args:
            session_id: 会话ID
            update_time: 是否更新 updated_at（默认False，置顶/标题修改等不应更新时间）
            **kwargs: 要更新的字段
        """
        allowed_fields = ['title', 'is_pinned', 'status']
        updates = []
        params = []
        
        for field, value in kwargs.items():
            if field in allowed_fields:
                updates.append(f"{field} = ?")
                params.append(value)
        
        if not updates:
            return 0
        
        # 可选：更新 updated_at
        if update_time:
            updates.append("updated_at = CURRENT_TIMESTAMP")
        
        params.append(session_id)
        
        query = f"UPDATE sessions SET {', '.join(updates)} WHERE session_id = ?"
        return self.db.execute_update(query, tuple(params))
    
    def update_session_time(self, session_id: str):
        """更新会话的 updated_at 时间"""
        query = "UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE session_id = ?"
        return self.db.execute_update(query, (session_id,))
    
    def increment_message_count(self, session_id: str, increment: int = 1):
        """增加消息计数"""
        query = """
            UPDATE sessions 
            SET message_count = message_count + ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE session_id = ?
        """
        return self.db.execute_update(query, (increment, session_id))
    
    def pin_session(self, session_id: str, pinned: bool = True):
        """置顶/取消置顶会话（不更新 updated_at）"""
        query = "UPDATE sessions SET is_pinned = ? WHERE session_id = ?"
        return self.db.execute_update(query, (pinned, session_id))
    
    def archive_session(self, session_id: str):
        """归档会话"""
        return self.update_session(session_id, status='archived')
    
    def delete_session(self, session_id: str):
        """删除会话（级联删除消息）"""
        query = "DELETE FROM sessions WHERE session_id = ?"
        return self.db.execute_update(query, (session_id,))
    
    def search_sessions(self, user_id: int, keyword: str, limit: int = 20) -> List[Session]:
        """搜索会话"""
        query = """
            SELECT * FROM sessions 
            WHERE user_id = ? AND status = 'active' 
            AND title LIKE ?
            ORDER BY updated_at DESC
            LIMIT ?
        """
        keyword_pattern = f"%{keyword}%"
        rows = self.db.execute_query(query, (user_id, keyword_pattern, limit))
        return [Session.from_db_row(row) for row in rows]
    
    def get_session_count(self, user_id: int, status: str = 'active') -> int:
        """获取用户会话数量"""
        query = "SELECT COUNT(*) as count FROM sessions WHERE user_id = ? AND status = ?"
        row = self.db.execute_one(query, (user_id, status))
        return row['count'] if row else 0

