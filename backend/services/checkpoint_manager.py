"""
Checkpoint 管理器
负责创建和管理 LangGraph checkpoint 实例
"""

import logging
import os
from typing import Optional

from backend.utils.config import config

logger = logging.getLogger(__name__)


def create_checkpointer(checkpoint_type: Optional[str] = None, db_path: Optional[str] = None):
    """
    创建 checkpointer 实例
    
    Args:
        checkpoint_type: checkpoint 类型（memory/sqlite/postgres），如果为 None 则使用配置
        db_path: 数据库路径（仅用于 SQLite），如果为 None 则使用配置
        
    Returns:
        checkpointer 实例，如果禁用 checkpoint 则返回 None
    """
    if not config.USE_CHECKPOINT:
        logger.info("[CheckpointManager] Checkpoint 已禁用")
        return None
    
    checkpoint_type = checkpoint_type or config.CHECKPOINT_TYPE
    db_path = db_path or config.CHECKPOINT_DB_PATH
    
    try:
        if checkpoint_type == "memory":
            from langgraph.checkpoint.memory import MemorySaver
            checkpointer = MemorySaver()
            logger.info("[CheckpointManager] 使用 MemorySaver（内存存储，不持久化）")
            return checkpointer
            
        elif checkpoint_type == "sqlite":
            import sqlite3
            from langgraph.checkpoint.sqlite import SqliteSaver
            
            # 确保目录存在
            db_dir = os.path.dirname(db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
                logger.info(f"[CheckpointManager] 创建 checkpoint 目录: {db_dir}")
            
            # 创建 SQLite 连接并初始化 SqliteSaver
            conn = sqlite3.connect(db_path, check_same_thread=False)
            checkpointer = SqliteSaver(conn)
            logger.info(f"[CheckpointManager] 使用 SqliteSaver（持久化存储）: {db_path}")
            return checkpointer
            
        elif checkpoint_type == "postgres":
            if not config.DATABASE_URL:
                logger.warning("[CheckpointManager] PostgreSQL 模式需要 DATABASE_URL，回退到 SQLite")
                return create_checkpointer("sqlite", db_path)
            
            from langgraph.checkpoint.postgres import PostgresSaver
            checkpointer = PostgresSaver.from_conn_string(config.DATABASE_URL)
            logger.info("[CheckpointManager] 使用 PostgresSaver（PostgreSQL 持久化存储）")
            return checkpointer
            
        else:
            logger.warning(f"[CheckpointManager] 未知的 checkpoint 类型: {checkpoint_type}，回退到 memory")
            from langgraph.checkpoint.memory import MemorySaver
            return MemorySaver()
            
    except ImportError as e:
        logger.error(f"[CheckpointManager] 导入 checkpoint 模块失败: {str(e)}")
        logger.warning("[CheckpointManager] 回退到 MemorySaver")
        try:
            from langgraph.checkpoint.memory import MemorySaver
            return MemorySaver()
        except ImportError:
            logger.error("[CheckpointManager] 无法创建任何 checkpointer，返回 None")
            return None
    except Exception as e:
        logger.error(f"[CheckpointManager] 创建 checkpointer 失败: {str(e)}")
        logger.warning("[CheckpointManager] 回退到 MemorySaver")
        try:
            from langgraph.checkpoint.memory import MemorySaver
            return MemorySaver()
        except ImportError:
            return None
