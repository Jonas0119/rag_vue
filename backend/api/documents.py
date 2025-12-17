"""
文档管理 API 路由
"""
import os
import logging
import time
from pathlib import Path
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


class UploadUrlRequest(BaseModel):
    """前端请求生成直传 Supabase 的上传 URL"""
    filename: str
    file_size: int
    content_type: Optional[str] = None


class UploadUrlResponse(BaseModel):
    """返回给前端的上传 URL 信息"""
    upload_url: str
    doc_id: str
    status: str


class TusInitRequest(BaseModel):
    """前端请求初始化 TUS 大文件上传"""
    filename: str
    file_size: int
    content_type: Optional[str] = None


class TusInitResponse(BaseModel):
    """返回给前端的 TUS 上传配置"""
    endpoint: str
    bucket: str
    object_name: str
    doc_id: str
    max_file_size: int
    supabase_anon_key: Optional[str] = None


@router.get("/documents", response_model=List[DocumentResponse])
async def get_documents(
    user: User = Depends(get_current_user_dependency)
):
    """
    获取用户的文档列表（包括处理中的文档，排除已删除的文档）
    
    Returns:
        文档列表（只包含 active 和 processing 状态的文档）
    """
    start_ts = time.perf_counter()
    from backend.database import DocumentDAO
    from backend.utils.file_handler import format_file_size

    logger.info(
        "[perf][/api/documents] start | user_id=%s",
        getattr(user, "user_id", None),
    )

    # 直接查询数据库，只获取 active 和 processing 状态的文档
    # 排除 deleted 状态的文档（已硬删除，不应显示）
    db_start = time.perf_counter()
    doc_dao = DocumentDAO()
    docs = doc_dao.get_user_documents(user.user_id, status=None)
    db_end = time.perf_counter()

    # 转换为字典格式
    serialize_start = time.perf_counter()
    documents = []
    for doc in docs:
        doc_dict = doc.to_dict()
        doc_dict["file_size_formatted"] = format_file_size(doc.file_size)
        documents.append(doc_dict)
    serialize_end = time.perf_counter()

    # 统计并打印耗时
    total_ms = (time.perf_counter() - start_ts) * 1000
    db_ms = (db_end - db_start) * 1000
    serialize_ms = (serialize_end - serialize_start) * 1000

    logger.info(
        "[perf][/api/documents] done | user_id=%s, total=%.1fms, db=%.1fms, serialize=%.1fms, count=%d",
        getattr(user, "user_id", None),
        total_ms,
        db_ms,
        serialize_ms,
        len(documents),
    )

    # 返回响应
    return [
        DocumentResponse(
            doc_id=doc["doc_id"],
            user_id=doc["user_id"],
            filename=doc["filename"],
            original_filename=doc["original_filename"],
            file_size=doc["file_size"],
            file_type=doc["file_type"],
            page_count=doc.get("page_count"),
            chunk_count=doc.get("chunk_count", 0),
            upload_at=doc.get("upload_at"),
            status=doc.get("status", "active"),
            error_message=doc.get("error_message"),
        )
        for doc in documents
    ]


@router.post("/documents/upload-url", response_model=UploadUrlResponse)
async def create_upload_url(
    request: UploadUrlRequest,
    user: User = Depends(get_current_user_dependency),
):
    """
    创建 Supabase Storage 的签名上传 URL，让前端可以直接将大文件上传到 Supabase，
    避免经过 Vercel 的 Body 限制。

    流程：
    1. 前端提交文件名、大小、类型到该接口；
    2. 后端校验类型 & 大小，生成安全文件名和存储路径；
    3. 在数据库中创建文档记录（status=processing / uploading）；
    4. 使用 Service Key 调用 Supabase，生成签名上传 URL；
    5. 将 upload_url + doc_id 返回给前端；
    6. 前端使用 upload_url 直传文件，上传完成后再调用 confirm-upload 接口触发后台处理。
    """
    from backend.utils.config import config as app_config
    from backend.utils.file_handler import generate_safe_filename
    from backend.utils.supabase_storage import get_supabase_storage
    from backend.database import DocumentDAO

    # 仅在云存储模式下支持直传
    if app_config.STORAGE_MODE != "cloud":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前存储模式不支持直传，请将 STORAGE_MODE 设置为 cloud",
        )

    # 验证文件类型（当前仅支持 PDF）
    if not is_allowed_file(request.filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不支持的文件类型。当前仅支持 PDF 文件（.pdf）",
        )

    # 验证文件大小（业务层面限制，例如 30MB）
    valid, error_msg = validate_file_size(request.file_size, app_config.MAX_FILE_SIZE)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )

    storage = get_supabase_storage()
    if storage is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase Storage 未配置或初始化失败，无法生成上传链接",
        )

    # 生成安全文件名与存储路径（保持与原有逻辑一致）
    safe_filename = generate_safe_filename(request.filename)
    filepath = f"user_{user.user_id}/{safe_filename}"
    file_ext = Path(request.filename).suffix.lower()

    # 先创建文档记录，状态为 processing（与原 create_document 一致）
    from backend.database import DocumentDAO

    doc_dao = DocumentDAO()
    vector_collection = f"user_{user.user_id}_docs"

    try:
        doc_id = doc_dao.create_document(
            user_id=user.user_id,
            filename=safe_filename,
            original_filename=request.filename,
            filepath=filepath,
            file_size=request.file_size,
            file_type=file_ext,
            page_count=None,
            vector_collection=vector_collection,
        )
    except Exception as e:
        logger.error(f"[文档上传] 创建文档记录失败: {request.filename}, error={e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建文档记录失败：{e}",
        )

    # 创建签名上传 URL
    ok, url_or_error = storage.create_signed_upload_url(filepath)
    if not ok:
        # 回滚文档记录
        try:
            doc_dao.hard_delete_document(doc_id)
        except Exception:
            logger.warning(f"[文档上传] 回滚文档记录失败: doc_id={doc_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建上传链接失败：{url_or_error}",
        )

    logger.info(
        f"[文档上传] 用户 {user.user_id} 请求直传文件: {request.filename}, "
        f"doc_id={doc_id}, size={request.file_size} bytes, path={filepath}"
    )

    return UploadUrlResponse(
        upload_url=url_or_error,
        doc_id=doc_id,
        status="uploading",
    )


@router.post("/documents/tus-init", response_model=TusInitResponse)
async def tus_init(
    request: TusInitRequest,
    user: User = Depends(get_current_user_dependency),
):
    """
    初始化 Supabase TUS 大文件上传配置。

    流程：
    1. 前端提交文件元数据（名称、大小、类型）；
    2. 后端校验类型 & 大小，生成安全文件名和存储路径；
    3. 在数据库中创建文档记录（status=processing）；
    4. 返回 Supabase TUS 端点、bucket 名称、objectName、doc_id、最大文件大小等；
    5. 前端使用 tus-js-client 直接将文件上传到 Supabase。
    """
    from backend.utils.config import config as app_config
    from backend.utils.file_handler import generate_safe_filename
    from backend.database import DocumentDAO

    # 仅在云存储模式下支持直传
    if app_config.STORAGE_MODE != "cloud":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前存储模式不支持直传，请将 STORAGE_MODE 设置为 cloud",
        )

    # 验证文件类型（当前仅支持 PDF）
    if not is_allowed_file(request.filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不支持的文件类型。当前仅支持 PDF 文件（.pdf）",
        )

    # 验证文件大小（业务层面限制，例如 30MB）
    valid, error_msg = validate_file_size(request.file_size, app_config.MAX_FILE_SIZE)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )

    # 生成安全文件名与存储路径（保持与原有逻辑一致）
    safe_filename = generate_safe_filename(request.filename)
    object_name = f"user_{user.user_id}/{safe_filename}"
    file_ext = Path(request.filename).suffix.lower()

    # 在数据库中创建文档记录
    doc_dao = DocumentDAO()
    vector_collection = f"user_{user.user_id}_docs"

    try:
        doc_id = doc_dao.create_document(
            user_id=user.user_id,
            filename=safe_filename,
            original_filename=request.filename,
            filepath=object_name,
            file_size=request.file_size,
            file_type=file_ext,
            page_count=None,
            vector_collection=vector_collection,
        )
    except Exception as e:
        logger.error(f"[文档上传] 创建文档记录失败(tus-init): {request.filename}, error={e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建文档记录失败：{e}",
        )

    # Supabase TUS 端点
    supabase_url = app_config.SUPABASE_URL.rstrip("/")
    endpoint = f"{supabase_url}/storage/v1/upload/resumable"

    logger.info(
        f"[文档上传] TUS 初始化: user_id={user.user_id}, doc_id={doc_id}, "
        f"object_name={object_name}, size={request.file_size}"
    )

    return TusInitResponse(
        endpoint=endpoint,
        bucket=app_config.SUPABASE_STORAGE_BUCKET,
        object_name=object_name,
        doc_id=doc_id,
        max_file_size=app_config.MAX_FILE_SIZE,
        # 传递 anon key 给前端用于 TUS 认证（权限由 Supabase Policy 控制）
        supabase_anon_key=app_config.SUPABASE_KEY or None,
    )


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


@router.post("/documents/{doc_id}/confirm-upload")
async def confirm_upload(
    doc_id: str,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user_dependency),
):
    """
    前端在成功将文件直传到 Supabase 之后调用该接口，
    用于触发后台文档处理流程（解析 + 分块 + 向量化）。

    注意：如果上传失败但仍然调用了该接口，后台任务在下载文件时会失败，
    并将文档标记为 error 状态。
    """
    from backend.database import DocumentDAO
    from backend.utils.config import config as app_config

    doc_dao = DocumentDAO()
    doc = doc_dao.get_document(doc_id)

    # 验证文档存在且属于当前用户
    if not doc or doc.user_id != user.user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档不存在或无权限",
        )

    # 仅在云存储模式下允许该流程
    if app_config.STORAGE_MODE != "cloud":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前存储模式不支持该操作，请将 STORAGE_MODE 设置为 cloud",
        )

    file_ext = doc.file_type or Path(doc.filepath).suffix.lower()

    logger.info(
        f"[文档上传] 接收到确认上传请求: doc_id={doc_id}, user_id={user.user_id}, filepath={doc.filepath}"
    )

    # 触发后台处理任务（与原 /documents/upload 逻辑保持一致）
    background_tasks.add_task(
        process_document_background,
        user.user_id,
        doc_id,
        doc.filepath,
        file_ext,
    )

    return {
        "success": True,
        "message": "已确认上传，文档处理中...",
        "doc_id": doc_id,
        "status": "processing",
    }


def process_document_background(user_id: int, doc_id: str, filepath: str, file_ext: str):
    """
    后台处理文档（转发到 RAG Service）
    
    这个函数在后台任务中运行，不阻塞 API 响应。
    """
    logger.info(f"[后台任务] 开始处理文档 doc_id={doc_id}, user_id={user_id}")
    
    from backend.utils.config import config as app_config
    
    if not app_config.RAG_SERVICE_URL:
        logger.error("[后台任务] RAG_SERVICE_URL 未配置，无法处理文档")
        from backend.database import DocumentDAO
        doc_dao = DocumentDAO()
        doc_dao.mark_document_error(doc_id, "RAG Service URL 未配置")
        return
    
    try:
        import httpx
        
        rag_service_url = app_config.RAG_SERVICE_URL.rstrip("/")
        target_url = f"{rag_service_url}/api/documents/{doc_id}/process"
        
        # 构建请求体
        request_body = {
            "doc_id": doc_id,
            "user_id": user_id,
            "filepath": filepath,
            "file_type": file_ext
        }
        
        # 转发请求到 RAG Service（异步处理模式：立即返回，不等待处理完成）
        with httpx.Client(timeout=30.0) as client:  # 减少超时时间，因为现在应该立即返回
            response = client.post(
                target_url,
                json=request_body,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            
            result = response.json()
            if result.get("success"):
                # 异步处理模式：rag_service 立即返回，实际处理在后台进行
                # 前端可以通过轮询 /api/documents/{doc_id}/status 获取处理状态
                logger.info(f"[后台任务] 文档 {doc_id} 处理任务已启动，正在后台处理中")
                # 不需要等待处理完成，状态会通过数据库更新
            else:
                error_msg = result.get("detail", "未知错误")
                from backend.database import DocumentDAO
                doc_dao = DocumentDAO()
                doc_dao.mark_document_error(doc_id, error_msg)
                logger.error(f"[后台任务] 文档 {doc_id} 启动处理任务失败: {error_msg}")
    
    except httpx.TimeoutException:
        logger.error(f"[后台任务] 文档 {doc_id} 处理超时")
        from backend.database import DocumentDAO
        doc_dao = DocumentDAO()
        doc_dao.mark_document_error(doc_id, "处理超时")
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
    
    # 删除文档元数据
    success, message = doc_service.delete_document(user.user_id, doc_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=message
        )
    
    # 转发删除向量请求到 RAG Service
    from backend.utils.config import config as app_config
    if app_config.RAG_SERVICE_URL:
        try:
            import httpx
            rag_service_url = app_config.RAG_SERVICE_URL.rstrip("/")
            target_url = f"{rag_service_url}/api/documents/{doc_id}/delete-vectors"
            
            # 异步删除向量（不阻塞响应）
            with httpx.Client(timeout=30.0) as client:
                response = client.delete(
                    target_url,
                    params={"user_id": user.user_id}
                )
                # 即使删除向量失败，也不影响删除元数据的成功
                if response.status_code != 200:
                    logger.warning(f"删除向量失败: {response.text}")
        except Exception as e:
            logger.warning(f"删除向量时发生错误（不影响文档删除）: {str(e)}")
    
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
