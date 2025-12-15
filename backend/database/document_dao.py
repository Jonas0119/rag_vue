"""
文档数据访问对象 (Document DAO)
"""
from typing import Optional, List
import uuid

from .db_manager import DatabaseManager, get_db_manager
from .models import Document


class DocumentDAO:
    """文档数据访问对象"""
    
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or get_db_manager()
    
    def create_document(self, user_id: int, filename: str, original_filename: str,
                       filepath: str, file_size: int, file_type: str,
                       page_count: Optional[int] = None,
                       vector_collection: Optional[str] = None) -> str:
        """
        创建文档记录
        
        Returns:
            doc_id: 新创建文档的 ID (UUID)
        """
        doc_id = str(uuid.uuid4())
        query = """
            INSERT INTO documents (
                doc_id, user_id, filename, original_filename,
                filepath, file_size, file_type, page_count,
                vector_collection, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'processing')
        """
        self.db.execute_insert(
            query,
            (doc_id, user_id, filename, original_filename, filepath, 
             file_size, file_type, page_count, vector_collection)
        )
        return doc_id
    
    def get_document(self, doc_id: str) -> Optional[Document]:
        """获取单个文档"""
        query = "SELECT * FROM documents WHERE doc_id = ?"
        row = self.db.execute_one(query, (doc_id,))
        return Document.from_db_row(row) if row else None
    
    def get_user_documents(self, user_id: int, status: Optional[str] = 'active') -> List[Document]:
        """
        获取用户的所有文档
        
        Args:
            user_id: 用户 ID
            status: 文档状态，None 表示查询所有状态（但排除 deleted）
        """
        if status is None:
            # 查询所有状态的文档，但排除 deleted 状态（已硬删除，不应显示）
            query = """
                SELECT * FROM documents 
                WHERE user_id = ? AND status != 'deleted'
                ORDER BY upload_at DESC
            """
            rows = self.db.execute_query(query, (user_id,))
        else:
            # 查询指定状态的文档
            query = """
                SELECT * FROM documents 
                WHERE user_id = ? AND status = ?
                ORDER BY upload_at DESC
            """
            rows = self.db.execute_query(query, (user_id, status))
        return [Document.from_db_row(row) for row in rows]
    
    def update_document(self, doc_id: str, **kwargs):
        """更新文档信息"""
        allowed_fields = ['chunk_count', 'status', 'error_message', 'metadata']
        updates = []
        params = []
        
        for field, value in kwargs.items():
            if field in allowed_fields:
                updates.append(f"{field} = ?")
                # 对于文本字段，清理 NULL 字符（PostgreSQL 不允许字符串包含 NULL 字符）
                if field in ['error_message'] and isinstance(value, str):
                    value = value.replace('\x00', '')
                params.append(value)
        
        if not updates:
            return 0
        
        params.append(doc_id)
        query = f"UPDATE documents SET {', '.join(updates)} WHERE doc_id = ?"
        return self.db.execute_update(query, tuple(params))
    
    def mark_document_active(self, doc_id: str, chunk_count: int):
        """标记文档为已完成"""
        return self.update_document(doc_id, status='active', chunk_count=chunk_count)
    
    def mark_document_error(self, doc_id: str, error_message: str):
        """标记文档处理失败"""
        return self.update_document(doc_id, status='error', error_message=error_message)
    
    def delete_document(self, doc_id: str):
        """删除文档（软删除）"""
        return self.update_document(doc_id, status='deleted')
    
    def hard_delete_document(self, doc_id: str):
        """硬删除文档记录"""
        query = "DELETE FROM documents WHERE doc_id = ?"
        return self.db.execute_update(query, (doc_id,))
    
    def get_document_count(self, user_id: int, status: str = 'active') -> int:
        """获取用户文档数量"""
        query = "SELECT COUNT(*) as count FROM documents WHERE user_id = ? AND status = ?"
        row = self.db.execute_one(query, (user_id, status))
        return row['count'] if row else 0
    
    def get_total_storage(self, user_id: int, status: str = 'active') -> int:
        """获取用户总存储空间（字节）"""
        query = "SELECT SUM(file_size) as total FROM documents WHERE user_id = ? AND status = ?"
        row = self.db.execute_one(query, (user_id, status))
        return row['total'] if row and row['total'] else 0
    
    def get_total_chunk_count(self, user_id: int, status: str = 'active') -> int:
        """获取用户总块数（从数据库获取，比查询向量库快）"""
        query = "SELECT SUM(chunk_count) as total FROM documents WHERE user_id = ? AND status = ?"
        row = self.db.execute_one(query, (user_id, status))
        return row['total'] if row and row['total'] else 0
    
    def get_user_stats_combined(self, user_id: int, status: str = 'active') -> dict:
        """一次查询获取所有统计数据（优化：3次查询→1次查询）"""
        query = """
            SELECT 
                COUNT(*) as document_count,
                COALESCE(SUM(file_size), 0) as storage_used,
                COALESCE(SUM(chunk_count), 0) as vector_count
            FROM documents 
            WHERE user_id = ? AND status = ?
        """
        row = self.db.execute_one(query, (user_id, status))
        return {
            'document_count': row['document_count'] if row else 0,
            'storage_used': row['storage_used'] if row else 0,
            'vector_count': row['vector_count'] if row else 0
        }
    
    def search_documents(self, user_id: int, keyword: str, limit: int = 20) -> List[Document]:
        """搜索文档"""
        query = """
            SELECT * FROM documents 
            WHERE user_id = ? AND status = 'active'
            AND original_filename LIKE ?
            ORDER BY upload_at DESC
            LIMIT ?
        """
        keyword_pattern = f"%{keyword}%"
        rows = self.db.execute_query(query, (user_id, keyword_pattern, limit))
        return [Document.from_db_row(row) for row in rows]

