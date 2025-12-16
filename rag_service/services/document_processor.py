"""
文档处理服务 - 文档解析、分块、向量化
从backend迁移的文档处理逻辑
"""
import os
import logging
from typing import List, Tuple
import tempfile

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document

from rag_service.database import DocumentDAO, ParentChildDAO
from rag_service.services.vector_store_service import get_vector_store_service
from rag_service.utils.config import config
from rag_service.utils.document_cleaner import clean_text
from rag_service.utils.text_splitter import split_by_paragraphs
from rag_service.utils.parent_child_splitter import split_to_parent_child
from rag_service.utils.supabase_storage import get_supabase_storage

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """文档处理器 - 负责文档解析、分块、向量化"""
    
    def __init__(self):
        self.doc_dao = DocumentDAO()
        self.parent_child_dao = ParentChildDAO()
        self.vector_service = get_vector_store_service()
    
    def process_document(self, user_id: int, doc_id: str, filepath: str, file_type: str) -> Tuple[bool, str]:
        """
        处理文档：解析、分块、向量化
        
        Args:
            user_id: 用户ID
            doc_id: 文档ID
            filepath: 文件路径（Supabase Storage路径或本地路径）
            file_type: 文件类型（如'.pdf'）
        
        Returns:
            (是否成功, 消息/块数量)
        """
        try:
            # 1. 解析文档
            # 根据存储模式读取文件
            if config.STORAGE_MODE == "cloud":
                # 云存储：先下载文件到临时位置
                storage = get_supabase_storage()
                if storage is None:
                    return False, "Supabase Storage 未初始化"
                
                file_data = storage.download_file(filepath)
                if file_data is None:
                    return False, "无法从云存储下载文件"
                
                # 创建临时文件
                with tempfile.NamedTemporaryFile(delete=False, suffix=file_type) as tmp_file:
                    tmp_file.write(file_data)
                    tmp_file_path = tmp_file.name
                
                try:
                    if file_type == '.pdf':
                        loader = PyPDFLoader(tmp_file_path)
                        pages = loader.load()
                        full_text = "\n\n".join([page.page_content for page in pages])
                        page_count = len(pages)
                    elif file_type in ['.txt', '.md']:
                        full_text = file_data.decode('utf-8', errors='ignore')
                        if not full_text:
                            return False, "无法读取文件内容"
                        page_count = None
                    else:
                        return False, f"不支持的文件类型：{file_type}"
                finally:
                    # 删除临时文件
                    if os.path.exists(tmp_file_path):
                        os.remove(tmp_file_path)
            else:
                # 本地文件系统
                if file_type == '.pdf':
                    loader = PyPDFLoader(filepath)
                    pages = loader.load()
                    full_text = "\n\n".join([page.page_content for page in pages])
                    page_count = len(pages)
                elif file_type in ['.txt', '.md']:
                    from rag_service.utils.file_handler import read_text_file
                    full_text = read_text_file(filepath)
                    if not full_text:
                        return False, "无法读取文件内容"
                    if not full_text:
                        return False, "无法读取文件内容"
                    page_count = None
                else:
                    return False, f"不支持的文件类型：{file_type}"
            
            # 2. 文档清理（先统一清理，再分块）
            full_text = clean_text(
                full_text,
                remove_multiple_newlines=True,
                remove_trailing_whitespace=True,
                remove_html_tags=True,
                normalize_whitespace=True,
                min_length=0,
            )

            # 3. 分块（支持 Parent-Child 策略）
            documents: List[Document] = []
            if config.USE_PARENT_CHILD_STRATEGY:
                raw_docs = [
                    Document(
                        page_content=full_text,
                        metadata={
                            "doc_id": doc_id,
                            "user_id": user_id,
                            "source": filepath,
                        },
                    )
                ]
                child_docs, parent_map = split_to_parent_child(
                    raw_docs,
                    parent_chunk_size=config.PARENT_CHUNK_SIZE,
                    child_chunk_size=config.CHILD_CHUNK_SIZE,
                )
                # parent_map 落库（按 doc_id 存储）
                self.parent_child_dao.save_parent_map(user_id, doc_id, parent_map)

                # 子文档补充 chunk_id
                for i, d in enumerate(child_docs):
                    d.metadata = dict(d.metadata or {})
                    d.metadata.update(
                        {
                            "doc_id": doc_id,
                            "chunk_id": i,
                            "user_id": user_id,
                            "source": filepath,
                        }
                    )
                documents = child_docs
            else:
                chunks = split_by_paragraphs(full_text)
                if not chunks:
                    return False, "文档内容为空或无法分块"
                
                logger.info(f"[文档处理] 文档 {doc_id} 分块完成: {len(chunks)} 个文本块")
                
                # 创建 Document 对象（带元数据）
                for i, chunk in enumerate(chunks):
                    doc = Document(
                        page_content=chunk,
                        metadata={
                            "doc_id": doc_id,
                            "chunk_id": i,
                            "user_id": user_id,
                            "source": filepath
                        }
                    )
                    documents.append(doc)
            
            # 4. 向量化并存入向量库
            total_chunks = len(documents)
            logger.info(f"[文档处理] 开始向量化文档 {doc_id}, 共 {total_chunks} 个文本块")
            
            # 分批处理，每50个文本块输出一次日志
            batch_size = 50
            all_ids = []
            for i in range(0, total_chunks, batch_size):
                batch = documents[i:i + batch_size]
                batch_num = i // batch_size + 1
                total_batches = (total_chunks + batch_size - 1) // batch_size
                
                logger.info(f"[文档处理] 正在向量化文档 {doc_id}: 第 {batch_num}/{total_batches} 批，处理第 {i+1}-{min(i+len(batch), total_chunks)} 个文本块（共 {len(batch)} 个）")
                
                batch_ids = self.vector_service.add_documents(user_id, batch)
                all_ids.extend(batch_ids)
                
                logger.info(f"[文档处理] 文档 {doc_id} 第 {batch_num}/{total_batches} 批向量化完成，已处理 {min(i+len(batch), total_chunks)}/{total_chunks} 个文本块")
            
            logger.info(f"[文档处理] 文档 {doc_id} 向量化完成，共处理 {total_chunks} 个文本块")
            
            # 5. 更新文档状态
            self.doc_dao.mark_document_active(doc_id, len(documents))
            
            # 更新页数（如果是 PDF）
            if page_count:
                self.doc_dao.update_document(doc_id, page_count=page_count)
            
            return True, str(len(documents))
        
        except Exception as e:
            logger.error(f"[文档处理] 文档 {doc_id} 处理失败: {str(e)}", exc_info=True)
            return False, str(e)


# 全局实例
_document_processor: DocumentProcessor = None


def get_document_processor() -> DocumentProcessor:
    """获取文档处理器实例（单例）"""
    global _document_processor
    if _document_processor is None:
        _document_processor = DocumentProcessor()
    return _document_processor

