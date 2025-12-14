"""
数据模型定义
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, List, Any
import json


@dataclass
class User:
    """用户模型"""
    user_id: Optional[int]
    username: str
    password_hash: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    is_active: bool = True
    preferences: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        # 处理时间戳（可能是 datetime 或字符串）
        created_at_str = self.created_at if isinstance(self.created_at, str) else (self.created_at.isoformat() if self.created_at else None)
        last_login_str = self.last_login if isinstance(self.last_login, str) else (self.last_login.isoformat() if self.last_login else None)
        
        return {
            'user_id': self.user_id,
            'username': self.username,
            'email': self.email,
            'display_name': self.display_name or self.username,
            'avatar_url': self.avatar_url,
            'created_at': created_at_str,
            'last_login': last_login_str,
            'is_active': self.is_active,
            'preferences': self.preferences or {}
        }
    
    @staticmethod
    def from_db_row(row) -> 'User':
        """从数据库行创建对象"""
        preferences = json.loads(row['preferences']) if row['preferences'] else None
        return User(
            user_id=row['user_id'],
            username=row['username'],
            password_hash=row['password_hash'],
            email=row['email'],
            display_name=row['display_name'],
            avatar_url=row['avatar_url'],
            created_at=row['created_at'],
            last_login=row['last_login'],
            is_active=bool(row['is_active']),
            preferences=preferences
        )


@dataclass
class Session:
    """会话模型"""
    session_id: str
    user_id: int
    title: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    message_count: int = 0
    is_pinned: bool = False
    status: str = 'active'
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        # 处理时间戳（可能是 datetime 或字符串）
        created_at_str = self.created_at if isinstance(self.created_at, str) else (self.created_at.isoformat() if self.created_at else None)
        updated_at_str = self.updated_at if isinstance(self.updated_at, str) else (self.updated_at.isoformat() if self.updated_at else None)
        
        return {
            'session_id': self.session_id,
            'user_id': self.user_id,
            'title': self.title,
            'created_at': created_at_str,
            'updated_at': updated_at_str,
            'message_count': self.message_count,
            'is_pinned': self.is_pinned,
            'status': self.status
        }
    
    @staticmethod
    def from_db_row(row) -> 'Session':
        """从数据库行创建对象"""
        return Session(
            session_id=row['session_id'],
            user_id=row['user_id'],
            title=row['title'],
            created_at=row['created_at'],
            updated_at=row['updated_at'],
            message_count=row['message_count'],
            is_pinned=bool(row['is_pinned']),
            status=row['status']
        )


@dataclass
class Message:
    """消息模型"""
    message_id: Optional[int]
    session_id: str
    role: str  # 'user' or 'assistant'
    content: str
    retrieved_docs: Optional[List[Dict]] = None
    thinking_process: Optional[List[Dict]] = None
    created_at: Optional[datetime] = None
    tokens_used: int = 0
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        # 处理时间戳（可能是 datetime 或字符串）
        created_at_str = self.created_at if isinstance(self.created_at, str) else (self.created_at.isoformat() if self.created_at else None)
        
        return {
            'message_id': self.message_id,
            'session_id': self.session_id,
            'role': self.role,
            'content': self.content,
            'retrieved_docs': self.retrieved_docs,
            'thinking_process': self.thinking_process,
            'created_at': created_at_str,
            'tokens_used': self.tokens_used
        }
    
    @staticmethod
    def from_db_row(row) -> 'Message':
        """从数据库行创建对象"""
        retrieved_docs = json.loads(row['retrieved_docs']) if row['retrieved_docs'] else None
        thinking_process = json.loads(row['thinking_process']) if row['thinking_process'] else None
        
        return Message(
            message_id=row['message_id'],
            session_id=row['session_id'],
            role=row['role'],
            content=row['content'],
            retrieved_docs=retrieved_docs,
            thinking_process=thinking_process,
            created_at=row['created_at'],
            tokens_used=row['tokens_used']
        )


@dataclass
class Document:
    """文档模型"""
    doc_id: str
    user_id: int
    filename: str
    original_filename: str
    filepath: str
    file_size: int
    file_type: str
    page_count: Optional[int] = None
    chunk_count: int = 0
    vector_collection: Optional[str] = None
    upload_at: Optional[datetime] = None
    status: str = 'active'
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        # 处理 upload_at（可能是 datetime 或字符串）
        upload_at_str = None
        if self.upload_at:
            if isinstance(self.upload_at, str):
                upload_at_str = self.upload_at
            else:
                upload_at_str = self.upload_at.isoformat()
        
        return {
            'doc_id': self.doc_id,
            'user_id': self.user_id,
            'filename': self.filename,
            'original_filename': self.original_filename,
            'filepath': self.filepath,
            'file_size': self.file_size,
            'file_type': self.file_type,
            'page_count': self.page_count,
            'chunk_count': self.chunk_count,
            'vector_collection': self.vector_collection,
            'upload_at': upload_at_str,
            'status': self.status,
            'error_message': self.error_message,
            'metadata': self.metadata or {}
        }
    
    @staticmethod
    def from_db_row(row) -> 'Document':
        """从数据库行创建对象"""
        metadata = json.loads(row['metadata']) if row['metadata'] else None
        
        return Document(
            doc_id=row['doc_id'],
            user_id=row['user_id'],
            filename=row['filename'],
            original_filename=row['original_filename'],
            filepath=row['filepath'],
            file_size=row['file_size'],
            file_type=row['file_type'],
            page_count=row['page_count'],
            chunk_count=row['chunk_count'],
            vector_collection=row['vector_collection'],
            upload_at=row['upload_at'],
            status=row['status'],
            error_message=row['error_message'],
            metadata=metadata
        )


@dataclass
class UserStats:
    """用户统计模型"""
    user_id: int
    total_sessions: int = 0
    total_messages: int = 0
    total_documents: int = 0
    storage_used: int = 0
    total_tokens: int = 0
    last_active: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'user_id': self.user_id,
            'total_sessions': self.total_sessions,
            'total_messages': self.total_messages,
            'total_documents': self.total_documents,
            'storage_used': self.storage_used,
            'total_tokens': self.total_tokens,
            'last_active': self.last_active.isoformat() if self.last_active else None
        }
    
    @staticmethod
    def from_db_row(row) -> 'UserStats':
        """从数据库行创建对象"""
        return UserStats(
            user_id=row['user_id'],
            total_sessions=row['total_sessions'],
            total_messages=row['total_messages'],
            total_documents=row['total_documents'],
            storage_used=row['storage_used'],
            total_tokens=row['total_tokens'],
            last_active=row['last_active']
        )

