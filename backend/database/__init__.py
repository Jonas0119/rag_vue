"""
数据库模块
"""
from .db_manager import DatabaseManager, get_db_manager, init_database
from .models import User, Session, Message, Document, UserStats
from .user_dao import UserDAO
from .session_dao import SessionDAO
from .message_dao import MessageDAO
from .document_dao import DocumentDAO
# ParentChildDAO 延迟导入，避免导入 langchain_core（仅在需要时导入）
# from .parent_child_dao import ParentChildDAO

__all__ = [
    'DatabaseManager',
    'get_db_manager',
    'init_database',
    'User',
    'Session',
    'Message',
    'Document',
    'UserStats',
    'UserDAO',
    'SessionDAO',
    'MessageDAO',
    'DocumentDAO',
    # 'ParentChildDAO',  # 延迟导入，不在此处导出
]


def get_parent_child_dao():
    """
    延迟导入 ParentChildDAO，避免在模块级别导入 langchain_core
    
    只有在 USE_PARENT_CHILD_STRATEGY=true 时才需要调用此函数
    """
    from .parent_child_dao import ParentChildDAO
    return ParentChildDAO()

