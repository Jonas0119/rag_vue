"""
会话服务 - 会话和消息管理
"""
from typing import Optional, List, Dict
import re

from backend.database import SessionDAO, MessageDAO


class SessionService:
    """会话服务"""
    
    def __init__(self):
        self.session_dao = SessionDAO()
        self.message_dao = MessageDAO()
    
    def create_session(self, user_id: int, first_question: str) -> str:
        """
        创建新会话
        
        Args:
            user_id: 用户 ID
            first_question: 首个问题（用于生成标题）
        
        Returns:
            session_id
        """
        # 生成会话标题
        title = self.generate_title(first_question)
        
        # 创建会话
        session_id = self.session_dao.create_session(user_id, title)
        
        return session_id
    
    def generate_title(self, first_question: str, max_length: int = 20) -> str:
        """
        根据首个问题生成会话标题
        
        Args:
            first_question: 首个问题
            max_length: 最大长度
        
        Returns:
            会话标题
        """
        # 移除特殊字符
        title = re.sub(r'[^\w\s\u4e00-\u9fff]', '', first_question)
        title = title.strip()
        
        # 截断到指定长度
        if len(title) > max_length:
            title = title[:max_length] + "..."
        
        return title or "新建对话"
    
    def save_message(self, session_id: str, role: str, content: str,
                    retrieved_docs: Optional[List[Dict]] = None,
                    thinking_process: Optional[List[Dict]] = None,
                    tokens_used: int = 0):
        """
        保存消息
        
        Args:
            session_id: 会话 ID
            role: 'user' 或 'assistant'
            content: 消息内容
            retrieved_docs: 检索到的文档
            thinking_process: 思考过程
            tokens_used: Token 消耗
        """
        # 保存消息
        self.message_dao.create_message(
            session_id=session_id,
            role=role,
            content=content,
            retrieved_docs=retrieved_docs,
            thinking_process=thinking_process,
            tokens_used=tokens_used
        )
        
        # 更新会话时间和消息计数
        self.session_dao.increment_message_count(session_id, 1)
    
    def get_session_messages(self, session_id: str) -> List[Dict]:
        """
        获取会话的所有消息
        
        Args:
            session_id: 会话 ID
        
        Returns:
            消息列表（字典格式）
        """
        messages = self.message_dao.get_session_messages(session_id)
        return [msg.to_dict() for msg in messages]
    
    def get_user_sessions(self, user_id: int, limit: int = 50) -> Dict[str, List]:
        """
        获取用户会话（按时间分组）
        
        Args:
            user_id: 用户 ID
            limit: 返回数量限制
        
        Returns:
            分组后的会话字典
        """
        grouped = self.session_dao.get_sessions_grouped_by_time(user_id)
        
        # 转换为字典格式
        result = {}
        for group_name, sessions in grouped.items():
            result[group_name] = [s.to_dict() for s in sessions]
        
        return result
    
    def update_session_title(self, session_id: str, new_title: str):
        """更新会话标题"""
        self.session_dao.update_session(session_id, title=new_title)
    
    def pin_session(self, session_id: str, pinned: bool = True):
        """置顶/取消置顶会话"""
        self.session_dao.pin_session(session_id, pinned)
    
    def delete_session(self, session_id: str):
        """删除会话（级联删除消息）"""
        self.session_dao.delete_session(session_id)
    
    def export_session_markdown(self, session_id: str) -> str:
        """
        导出会话为 Markdown 格式
        
        Args:
            session_id: 会话 ID
        
        Returns:
            Markdown 文本
        """
        import json
        from datetime import datetime
        
        # 获取会话信息
        session = self.session_dao.get_session(session_id)
        if not session:
            return ""
        
        # 获取所有消息
        messages = self.message_dao.get_session_messages(session_id)
        
        # 生成 Markdown
        md_content = f"# {session.title}\n\n"
        md_content += f"**创建时间：** {session.created_at}\n\n"
        md_content += f"**消息数量：** {session.message_count}\n\n"
        md_content += "---\n\n"
        
        for msg in messages:
            role_emoji = "👤" if msg.role == 'user' else "🤖"
            role_name = "用户" if msg.role == 'user' else "AI 助手"
            
            md_content += f"## {role_emoji} {role_name}\n\n"
            md_content += f"{msg.content}\n\n"
            
            # 添加检索结果（如果有）
            if msg.retrieved_docs:
                md_content += "### 📄 检索结果\n\n"
                docs = msg.retrieved_docs if isinstance(msg.retrieved_docs, list) else json.loads(msg.retrieved_docs)
                for i, doc in enumerate(docs, 1):
                    similarity = doc.get('similarity', 0)
                    content = doc.get('content', '')
                    md_content += f"{i}. **相似度: {similarity:.0%}** - {content[:100]}...\n"
                md_content += "\n"
            
            # 添加时间戳
            md_content += f"*{msg.created_at}*\n\n"
            md_content += "---\n\n"
        
        return md_content


# 全局会话服务实例
_session_service: Optional[SessionService] = None


def get_session_service() -> SessionService:
    """获取全局会话服务实例（单例）"""
    global _session_service
    if _session_service is None:
        _session_service = SessionService()
    return _session_service

