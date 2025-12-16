"""
Parent-Child 映射 DAO
用于存储/读取 parent_id -> parent_doc 的映射
"""

import json
import logging
from typing import Dict, Optional

from langchain_core.documents import Document as LCDocument

from .db_manager import DatabaseManager, get_db_manager

logger = logging.getLogger(__name__)


class ParentChildDAO:
    """Parent-Child 映射数据访问对象"""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or get_db_manager()

    def save_parent_map(self, user_id: int, doc_id: str, parent_map: Dict[str, LCDocument]):
        """
        保存某个 doc_id 的 parent_map（全量写入，先删后插）
        使用批量插入优化性能（从 N 次数据库往返减少到 1 次）
        """
        # 先删除旧映射
        self.delete_parent_map(user_id, doc_id)

        # 如果没有数据，直接返回
        if not parent_map:
            return

        # 准备批量插入数据
        query = """
            INSERT INTO parent_child_maps (user_id, doc_id, parent_id, parent_content, parent_metadata)
            VALUES (?, ?, ?, ?, ?)
        """
        
        # 转换参数格式（PostgreSQL 使用 %s，SQLite 使用 ?）
        query, _ = self.db._convert_params(query, ())
        
        # 准备所有插入数据
        values_list = []
        for parent_id, doc in parent_map.items():
            meta_json = json.dumps(doc.metadata or {}, ensure_ascii=False)
            # 清理 page_content 中的 NULL 字符（\x00），PostgreSQL 不允许字符串包含 NULL 字符
            cleaned_content = doc.page_content.replace('\x00', '') if doc.page_content else ''
            values_list.append((user_id, doc_id, parent_id, cleaned_content, meta_json))
        
        # 使用批量插入（在一个事务中完成所有插入）
        parent_count = len(values_list)
        logger.info(f"[ParentChildDAO] 批量插入 parent_map: doc_id={doc_id}, parent_count={parent_count}")
        
        with self.db.get_cursor() as cursor:
            cursor.executemany(query, values_list)
        # 事务自动提交（在 get_cursor 的 finally 中）
        
        logger.info(f"[ParentChildDAO] 批量插入完成: doc_id={doc_id}, 已插入 {parent_count} 条记录")

    def delete_parent_map(self, user_id: int, doc_id: str):
        query = "DELETE FROM parent_child_maps WHERE user_id = ? AND doc_id = ?"
        self.db.execute_update(query, (user_id, doc_id))

    def get_parent_map(self, user_id: int, doc_id: str) -> Dict[str, LCDocument]:
        """
        获取某个 doc_id 的 parent_map
        """
        query = """
            SELECT parent_id, parent_content, parent_metadata
            FROM parent_child_maps
            WHERE user_id = ? AND doc_id = ?
        """
        rows = self.db.execute_query(query, (user_id, doc_id))
        parent_map: Dict[str, LCDocument] = {}
        for row in rows:
            meta = {}
            # sqlite3.Row 不支持 .get()，使用字典式访问
            parent_metadata = row["parent_metadata"] if row["parent_metadata"] else None
            if parent_metadata:
                try:
                    meta = json.loads(parent_metadata)
                except Exception:
                    meta = {}
            parent_map[row["parent_id"]] = LCDocument(page_content=row["parent_content"], metadata=meta)
        return parent_map

    def get_parent_map_for_user(self, user_id: int) -> Dict[str, LCDocument]:
        """
        获取用户所有 parent_id -> parent_doc（用于检索时从 child 映射回 parent）
        """
        query = """
            SELECT parent_id, parent_content, parent_metadata
            FROM parent_child_maps
            WHERE user_id = ?
        """
        rows = self.db.execute_query(query, (user_id,))
        parent_map: Dict[str, LCDocument] = {}
        for row in rows:
            meta = {}
            # sqlite3.Row 不支持 .get()，使用字典式访问
            parent_metadata = row["parent_metadata"] if row["parent_metadata"] else None
            if parent_metadata:
                try:
                    meta = json.loads(parent_metadata)
                except Exception:
                    meta = {}
            parent_map[row["parent_id"]] = LCDocument(page_content=row["parent_content"], metadata=meta)
        return parent_map


