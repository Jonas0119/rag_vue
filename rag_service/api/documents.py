"""
文档处理 API 路由
"""
import logging
from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from pydantic import BaseModel

from rag_service.services.document_processor import get_document_processor
from rag_service.database import DocumentDAO

logger = logging.getLogger(__name__)

router = APIRouter()


class ProcessDocumentRequest(BaseModel):
    doc_id: str
    user_id: int
    filepath: str
    file_type: str


def process_document_background(
    user_id: int,
    doc_id: str,
    filepath: str,
    file_type: str
):
    """
    后台处理文档：解析、分块、向量化
    
    这个函数在后台任务中运行，不阻塞 HTTP 响应。
    """
    processor = get_document_processor()
    doc_dao = DocumentDAO()
    
    try:
        logger.info(f"[后台任务] 开始处理文档 doc_id={doc_id}, user_id={user_id}")
        
        # 处理文档
        success, message = processor.process_document(
            user_id,
            doc_id,
            filepath,
            file_type
        )
        
        if success:
            chunk_count = int(message)
            logger.info(f"[后台任务] 文档 {doc_id} 处理成功: {chunk_count} 个文本块")
        else:
            # 标记文档为错误状态
            doc_dao.mark_document_error(doc_id, message)
            logger.error(f"[后台任务] 文档 {doc_id} 处理失败: {message}")
    
    except Exception as e:
        logger.error(f"[后台任务] 文档 {doc_id} 处理异常: {str(e)}", exc_info=True)
        try:
            doc_dao.mark_document_error(doc_id, f"处理异常: {str(e)}")
        except Exception as e2:
            logger.error(f"[后台任务] 标记文档错误状态失败: {str(e2)}")


@router.post("/api/documents/{doc_id}/process")
async def process_document(
    doc_id: str,
    request: ProcessDocumentRequest,
    background_tasks: BackgroundTasks
):
    """
    处理文档：解析、分块、向量化（异步处理）
    
    此接口立即返回，文档处理在后台进行。
    前端可以通过 /api/documents/{doc_id}/status 轮询处理状态。
    
    Args:
        doc_id: 文档ID
        request: 处理请求（包含user_id, filepath, file_type）
        background_tasks: FastAPI 后台任务管理器
    
    Returns:
        立即返回成功响应，实际处理在后台进行
    """
    # 验证doc_id匹配
    if doc_id != request.doc_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="路径中的doc_id与请求体不匹配"
        )
    
    doc_dao = DocumentDAO()
    
    try:
        # 验证文档存在且属于该用户
        doc = doc_dao.get_document(doc_id)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文档不存在"
            )
        
        if doc.user_id != request.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权处理该文档"
            )
        
        # 确保文档状态为 processing（如果还不是）
        if doc.status != 'processing':
            # 这里可以更新状态，但通常上传时已经设置为 processing
            pass
        
        # 将文档处理任务添加到后台任务队列
        background_tasks.add_task(
            process_document_background,
            request.user_id,
            doc_id,
            request.filepath,
            request.file_type
        )
        
        logger.info(f"[文档处理] 文档 {doc_id} 已加入后台处理队列")
        
        # 立即返回成功响应，不等待处理完成
        return {
            "success": True,
            "message": "文档处理任务已启动，正在后台处理中",
            "doc_id": doc_id,
            "status": "processing"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"启动文档处理任务异常: {str(e)}", exc_info=True)
        try:
            doc_dao.mark_document_error(doc_id, f"启动处理任务异常: {str(e)}")
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"启动文档处理任务异常: {str(e)}"
        )


@router.delete("/api/documents/{doc_id}/delete-vectors")
async def delete_document_vectors(
    doc_id: str,
    user_id: int
):
    """
    删除文档的向量数据（从Pinecone中删除）
    
    注意：此接口不要求文档在数据库中仍然存在，因为可能已经被删除。
    只要 user_id 匹配，就会尝试删除向量库中的向量数据。
    
    Args:
        doc_id: 文档ID
        user_id: 用户ID（从查询参数获取）
    
    Returns:
        删除结果
    """
    from rag_service.services.vector_store_service import get_vector_store_service
    
    vector_service = get_vector_store_service()
    doc_dao = DocumentDAO()
    
    try:
        # 可选：如果文档还存在，验证权限；如果不存在，也允许删除向量（因为可能已经被删除了）
        doc = doc_dao.get_document(doc_id)
        if doc:
            # 文档存在，验证权限
            if doc.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="无权删除该文档的向量"
            )
        else:
            # 文档不存在（可能已被删除），记录日志但继续删除向量
            logger.info(f"[删除向量] 文档 {doc_id} 在数据库中不存在，但仍尝试删除向量数据（user_id={user_id}）")
        
        # 删除向量数据（即使文档不存在也尝试删除，因为向量可能还存在）
        try:
            vector_service.delete_documents(user_id, doc_id)
            logger.info(f"[删除向量] 文档 {doc_id} 的向量数据删除成功（user_id={user_id}）")
        except Exception as vec_err:
                # 向量删除失败，记录警告但不抛出异常（因为可能向量已经不存在）
                logger.warning(f"[删除向量] 删除向量数据时发生错误（可能向量已不存在）: {str(vec_err)}")
        
        return {
            "success": True,
            "message": "向量数据删除完成（如果存在）"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除向量异常: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除向量异常: {str(e)}"
        )

