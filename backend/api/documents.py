"""
文档管理 API 路由
"""
import os
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, BackgroundTasks
from pydantic import BaseModel

from backend.core.dependencies import get_current_user_dependency
from backend.core.config import settings
from backend.database.models import User
from backend.services import get_document_service
from backend.utils.file_handler import is_allowed_file, validate_file_size

logger = logging.getLogger(__name__)

router = APIRouter()


# Pydantic 模型
class DocumentResponse(BaseModel):
    doc_id: str
    user_id: int
    filename: str
    original_filename: str
    file_size: int
    file_type: str
    page_count: Optional[int] = None
    chunk_count: int = 0
    upload_at: Optional[str] = None
    status: str = 'active'
    error_message: Optional[str] = None


class DocumentStatusResponse(BaseModel):
    doc_id: str
    status: str
    chunk_count: int = 0
    error_message: Optional[str] = None


@router.get("/documents", response_model=List[DocumentResponse])
async def get_documents(
    user: User = Depends(get_current_user_dependency)
):
    """
    获取用户的文档列表（包括处理中的文档，排除已删除的文档）
    
    Returns:
        文档列表（只包含 active 和 processing 状态的文档）
    """
    # 直接查询数据库，只获取 active 和 processing 状态的文档
    # 排除 deleted 状态的文档（已硬删除，不应显示）
    from backend.database import DocumentDAO
    doc_dao = DocumentDAO()
    
    # 获取所有状态的文档（排除 deleted），传入 None 会自动过滤 deleted
    docs = doc_dao.get_user_documents(user.user_id, status=None)
    
    # 转换为字典格式
    from backend.utils.file_handler import format_file_size
    documents = []
    for doc in docs:
        doc_dict = doc.to_dict()
        doc_dict['file_size_formatted'] = format_file_size(doc.file_size)
        documents.append(doc_dict)
    
    # 返回响应
    return [
        DocumentResponse(
            doc_id=doc['doc_id'],
            user_id=doc['user_id'],
            filename=doc['filename'],
            original_filename=doc['original_filename'],
            file_size=doc['file_size'],
            file_type=doc['file_type'],
            page_count=doc.get('page_count'),
            chunk_count=doc.get('chunk_count', 0),
            upload_at=doc.get('upload_at'),
            status=doc.get('status', 'active'),
            error_message=doc.get('error_message')
        )
        for doc in documents
    ]


@router.post("/documents/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user_dependency)
):
    """
    上传文档（异步处理）
    
    立即返回文档ID，文档处理在后台进行。
    使用 /api/documents/{doc_id}/status 查询处理状态。
    
    Returns:
        上传结果（包含 doc_id）
    """
    doc_service = get_document_service()
    
    # 验证文件类型（当前仅支持 PDF）
    if not is_allowed_file(file.filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不支持的文件类型。当前仅支持 PDF 文件（.pdf）"
        )
    
    # 验证文件大小
    file_content = await file.read()
    file_size = len(file_content)
    
    from backend.utils.config import config as app_config
    valid, error_msg = validate_file_size(file_size, app_config.MAX_FILE_SIZE)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    
    # 重置文件指针
    await file.seek(0)
    
    # 创建类似 Streamlit UploadedFile 的对象
    class FastAPIUploadedFile:
        def __init__(self, file: UploadFile, content: bytes):
            self.name = file.filename
            self.size = len(content)
            self.type = file.content_type
            self._content = content
            self._file = file
            self._position = 0
        
        def read(self, size: int = -1):
            """读取文件内容"""
            if size == -1:
                result = self._content[self._position:]
                self._position = len(self._content)
            else:
                result = self._content[self._position:self._position + size]
                self._position = min(self._position + size, len(self._content))
            return result
        
        def seek(self, position: int):
            """移动文件指针"""
            self._position = max(0, min(position, len(self._content)))
        
        def getvalue(self):
            """获取所有内容"""
            return self._content
        
        def getbuffer(self):
            """获取内存视图（用于本地文件保存）"""
            import io
            return io.BytesIO(self._content).getbuffer()
    
    uploaded_file = FastAPIUploadedFile(file, file_content)
    
    # 只保存文件并创建文档记录，不立即处理
    # 返回 doc_id，处理在后台进行
    try:
        from pathlib import Path
        from backend.utils.file_handler import (
            generate_safe_filename,
            save_uploaded_file,
            format_file_size
        )
        
        # 生成安全文件名
        safe_filename = generate_safe_filename(file.filename)
        
        # 根据存储模式设置文件路径
        if app_config.STORAGE_MODE == "cloud":
            filepath = f"user_{user.user_id}/{safe_filename}"
        else:
            user_dir = f"{app_config.USER_DATA_DIR}/user_{user.user_id}/uploads"
            filepath = os.path.join(user_dir, safe_filename)
        
        # 保存文件
        if not save_uploaded_file(uploaded_file, filepath, user_id=user.user_id):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="文件保存失败"
            )
        
        # 获取文件扩展名
        file_ext = Path(file.filename).suffix.lower()
        
        # 创建文档记录（状态为 processing）
        from backend.database import DocumentDAO
        doc_dao = DocumentDAO()
        vector_collection = f"user_{user.user_id}_docs"
        
        doc_id = doc_dao.create_document(
            user_id=user.user_id,
            filename=safe_filename,
            original_filename=file.filename,
            filepath=filepath,
            file_size=file_size,
            file_type=file_ext,
            vector_collection=vector_collection
        )
        
        logger.info(f"[文档上传] 用户 {user.user_id} 上传文件: {file.filename}, doc_id={doc_id}, 大小={format_file_size(file_size)}")
        
        # 添加后台任务处理文档
        background_tasks.add_task(
            process_document_background,
            user.user_id,
            doc_id,
            filepath,
            file_ext
        )
        
        return {
            "success": True,
            "message": "文档上传成功，正在后台处理中...",
            "doc_id": doc_id,
            "status": "processing"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[文档上传] 上传失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"上传失败：{str(e)}"
        )


def process_document_background(user_id: int, doc_id: str, filepath: str, file_ext: str):
    """
    后台处理文档（解析、分块、向量化）
    
    这个函数在后台任务中运行，不阻塞 API 响应。
    """
    logger.info(f"[后台任务] 开始处理文档 doc_id={doc_id}, user_id={user_id}")
    
    try:
        # 在后台任务中重新获取服务实例
        from backend.services import get_document_service
        doc_service = get_document_service()
        
        # 调用处理文档的方法（私有方法，但可以通过实例访问）
        success, message = doc_service._process_document(user_id, doc_id, filepath, file_ext)
        
        if success:
            chunk_count = int(message)
            logger.info(f"[后台任务] 文档 {doc_id} 处理成功: {chunk_count} 个文本块")
        else:
            # 标记文档为错误状态
            from backend.database import DocumentDAO
            doc_dao = DocumentDAO()
            doc_dao.mark_document_error(doc_id, message)
            logger.error(f"[后台任务] 文档 {doc_id} 处理失败: {message}")
    except Exception as e:
        logger.error(f"[后台任务] 文档 {doc_id} 处理异常: {str(e)}", exc_info=True)
        # 标记文档为错误状态
        try:
            from backend.database import DocumentDAO
            doc_dao = DocumentDAO()
            doc_dao.mark_document_error(doc_id, f"处理异常: {str(e)}")
        except Exception as e2:
            logger.error(f"[后台任务] 标记文档错误状态失败: {str(e2)}")


@router.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: str,
    user: User = Depends(get_current_user_dependency)
):
    """
    删除文档（支持删除任何状态的文档，包括处理失败和处理中的文档）
    
    Returns:
        成功消息
    """
    doc_service = get_document_service()
    
    # 直接查询文档（不限制状态，支持删除 error 和 processing 状态的文档）
    from backend.database import DocumentDAO
    doc_dao = DocumentDAO()
    doc = doc_dao.get_document(doc_id)
    
    # 验证文档存在且属于当前用户
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档不存在"
        )
    
    if doc.user_id != user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权删除该文档"
        )
    
    # 删除文档（支持删除任何状态的文档）
    success, message = doc_service.delete_document(user.user_id, doc_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=message
        )
    
    return {
        "success": True,
        "message": "文档已删除"
    }


@router.get("/documents/{doc_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(
    doc_id: str,
    user: User = Depends(get_current_user_dependency)
):
    """
    获取文档处理状态
    
    Returns:
        文档状态信息
    """
    # 直接查询数据库，不限制状态（包括 processing 状态的文档）
    from backend.database import DocumentDAO
    doc_dao = DocumentDAO()
    
    # 获取文档（不限制状态）
    doc = doc_dao.get_document(doc_id)
    
    # 验证文档存在且属于当前用户
    if not doc or doc.user_id != user.user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档不存在或无权限"
        )
    
    return DocumentStatusResponse(
        doc_id=doc.doc_id,
        status=doc.status,
        chunk_count=doc.chunk_count,
        error_message=doc.error_message
    )
