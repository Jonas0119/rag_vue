"""
Parent-Child 映射 DAO
用于存储/读取 parent_id -> parent_doc 的映射
"""

import json
from typing import Dict, Optional

from langchain_core.documents import Document as LCDocument

from .db_manager import DatabaseManager, get_db_manager


class ParentChildDAO:
    """Parent-Child 映射数据访问对象"""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or get_db_manager()

    def save_parent_map(self, user_id: int, doc_id: str, parent_map: Dict[str, LCDocument]):
        """
        保存某个 doc_id 的 parent_map（全量写入，先删后插）
        """
        # 先删除旧映射
        self.delete_parent_map(user_id, doc_id)

        query = """
            INSERT INTO parent_child_maps (user_id, doc_id, parent_id, parent_content, parent_metadata)
            VALUES (?, ?, ?, ?, ?)
        """
        for parent_id, doc in parent_map.items():
            meta_json = json.dumps(doc.metadata or {}, ensure_ascii=False)
            self.db.execute_insert(query, (user_id, doc_id, parent_id, doc.page_content, meta_json))

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


