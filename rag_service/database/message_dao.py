"""
消息数据访问对象 (Message DAO)
"""
from typing import Optional, List, Dict
import json

from .db_manager import DatabaseManager, get_db_manager
from .models import Message


class MessageDAO:
    """消息数据访问对象"""
    
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or get_db_manager()
    
    def create_message(self, session_id: str, role: str, content: str,
                      retrieved_docs: Optional[List[Dict]] = None,
                      thinking_process: Optional[List[Dict]] = None,
                      tokens_used: int = 0) -> int:
        """
        创建新消息
        
        Args:
            session_id: 会话 ID
            role: 'user' 或 'assistant'
            content: 消息内容
            retrieved_docs: 检索到的文档（JSON）
            thinking_process: 思考过程（JSON）
            tokens_used: Token 消耗
        
        Returns:
            message_id: 新创建消息的 ID
        """
        # 根据数据库类型选择不同的 INSERT 语句
        if self.db.db_type == "postgresql":
            query = """
                INSERT INTO messages (
                    session_id, role, content, 
                    retrieved_docs, thinking_process, tokens_used
                )
                VALUES (?, ?, ?, ?, ?, ?)
                RETURNING message_id
            """
        else:
            query = """
                INSERT INTO messages (
                    session_id, role, content, 
                    retrieved_docs, thinking_process, tokens_used
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """
        
        # 将字典/列表转为 JSON 字符串
        retrieved_docs_json = json.dumps(retrieved_docs) if retrieved_docs else None
        thinking_process_json = json.dumps(thinking_process) if thinking_process else None
        
        # 清理 content 中的 NULL 字符（PostgreSQL 不允许字符串包含 NULL 字符）
        # 虽然消息内容通常不会包含 NULL 字符，但为了安全起见进行清理
        cleaned_content = content.replace('\x00', '') if content else ''
        
        message_id = self.db.execute_insert(
            query,
            (session_id, role, cleaned_content, retrieved_docs_json, thinking_process_json, tokens_used)
        )
        
        return message_id
    
    def get_message(self, message_id: int) -> Optional[Message]:
        """获取单条消息"""
        query = "SELECT * FROM messages WHERE message_id = ?"
        row = self.db.execute_one(query, (message_id,))
        return Message.from_db_row(row) if row else None
    
    def get_session_messages(self, session_id: str, limit: Optional[int] = None) -> List[Message]:
        """
        获取会话的所有消息
        
        Args:
            session_id: 会话 ID
            limit: 限制返回数量（从最新开始）
        """
        query = "SELECT * FROM messages WHERE session_id = ? ORDER BY created_at ASC"
        if limit:
            query += f" LIMIT {limit}"
        
        rows = self.db.execute_query(query, (session_id,))
        return [Message.from_db_row(row) for row in rows]
    
    def get_recent_messages(self, session_id: str, count: int = 10) -> List[Message]:
        """获取最近的 N 条消息"""
        query = """
            SELECT * FROM messages 
            WHERE session_id = ? 
            ORDER BY created_at DESC 
            LIMIT ?
        """
        rows = self.db.execute_query(query, (session_id, count))
        messages = [Message.from_db_row(row) for row in rows]
        return list(reversed(messages))  # 返回时按时间正序
    
    def delete_message(self, message_id: int):
        """删除单条消息"""
        query = "DELETE FROM messages WHERE message_id = ?"
        return self.db.execute_update(query, (message_id,))
    
    def delete_session_messages(self, session_id: str):
        """删除会话的所有消息"""
        query = "DELETE FROM messages WHERE session_id = ?"
        return self.db.execute_update(query, (session_id,))
    
    def get_message_count(self, session_id: str) -> int:
        """获取会话消息数量"""
        query = "SELECT COUNT(*) as count FROM messages WHERE session_id = ?"
        row = self.db.execute_one(query, (session_id,))
        return row['count'] if row else 0
    
    def get_total_tokens(self, session_id: str) -> int:
        """获取会话的总 Token 消耗"""
        query = "SELECT SUM(tokens_used) as total FROM messages WHERE session_id = ?"
        row = self.db.execute_one(query, (session_id,))
        return row['total'] if row and row['total'] else 0
    
    def search_messages(self, session_id: str, keyword: str, limit: int = 20) -> List[Message]:
        """在会话中搜索消息"""
        query = """
            SELECT * FROM messages 
            WHERE session_id = ? AND content LIKE ?
            ORDER BY created_at DESC
            LIMIT ?
        """
        keyword_pattern = f"%{keyword}%"
        rows = self.db.execute_query(query, (session_id, keyword_pattern, limit))
        return [Message.from_db_row(row) for row in rows]

