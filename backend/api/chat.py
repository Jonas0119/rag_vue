"""
对话 API 路由 - 代理转发到 RAG Service
"""
import json
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import httpx

from backend.core.dependencies import get_current_user_dependency
from backend.database.models import User
from backend.services import get_session_service
from backend.utils.config import config

logger = logging.getLogger(__name__)

router = APIRouter()


# Pydantic 模型
class ChatMessageRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class CreateSessionRequest(BaseModel):
    title: Optional[str] = None


class SessionResponse(BaseModel):
    session_id: str
    title: str
    created_at: Optional[str] = None
    message_count: int = 0


class MessageResponse(BaseModel):
    message_id: Optional[int] = None
    session_id: str
    role: str
    content: str
    created_at: Optional[str] = None
    retrieved_docs: Optional[list] = None
    thinking_process: Optional[list] = None


@router.post("/chat/message")
async def send_message(
    request: ChatMessageRequest,
    user: User = Depends(get_current_user_dependency),
):
    """
    发送消息：backend 负责保存用户消息，并以普通 HTTP 方式调用 RAG Service。

    Returns:
        简单 JSON：
        {
            "success": true,
            "session_id": "...",
        }
    """
    if not config.RAG_SERVICE_URL:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="RAG Service URL 未配置",
        )

    session_service = get_session_service()

    # 获取或创建 session_id（在 backend 处理）
    session_id = request.session_id
    if not session_id:
        # 创建新会话
        session_id = session_service.create_session(user.user_id, request.message)

    # 无论新会话还是旧会话，都在 backend 保存一条用户消息
    session_service.save_message(
        session_id=session_id,
        role="user",
        content=request.message,
    )

    # 转发请求到 RAG Service（普通 POST）
    rag_service_url = config.RAG_SERVICE_URL.rstrip("/")
    target_url = f"{rag_service_url}/api/chat/message"

    forward_request = {
        "message": request.message,
        "session_id": session_id,
        "user_id": user.user_id,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                target_url,
                json=forward_request,
                headers={"Content-Type": "application/json"},
            )
    except httpx.RequestError as exc:
        logger.error(f"调用 RAG Service 失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="无法连接 RAG Service，请稍后重试",
        )

    if response.status_code != 200:
        logger.error(
            "RAG Service 返回错误: status=%s, body=%s",
            response.status_code,
            response.text,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"RAG Service 错误: {response.text}",
        )

    try:
        data = response.json()
    except ValueError:
        data = {}

    if not data.get("success", True):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=data.get("message", "RAG Service 处理失败"),
        )

    return {
        "success": True,
        "session_id": session_id,
    }


@router.get("/chat/sessions", response_model=list[SessionResponse])
async def get_sessions(
    user: User = Depends(get_current_user_dependency)
):
    """
    获取用户的会话列表
    
    Returns:
        会话列表
    """
    session_service = get_session_service()
    sessions_dict = session_service.get_user_sessions(user.user_id, limit=100)
    
    # 将字典格式转换为列表
    sessions_list = []
    for date_group, sessions in sessions_dict.items():
        for session in sessions:
            sessions_list.append(SessionResponse(
                session_id=session['session_id'],
                title=session['title'],
                created_at=session.get('created_at'),
                message_count=session.get('message_count', 0)
            ))
    
    return sessions_list


@router.post("/chat/sessions", response_model=SessionResponse)
async def create_session(
    request: CreateSessionRequest,
    user: User = Depends(get_current_user_dependency)
):
    """
    创建新会话
    
    Returns:
        新创建的会话
    """
    session_service = get_session_service()
    
    # 如果没有提供标题，使用默认标题
    title = request.title or "新建对话"
    
    # 创建会话（需要提供一个初始问题来生成标题）
    session_id = session_service.create_session(user.user_id, title)
    
    # 获取会话信息
    sessions_dict = session_service.get_user_sessions(user.user_id, limit=1)
    session = None
    for date_group, sessions in sessions_dict.items():
        for s in sessions:
            if s['session_id'] == session_id:
                session = s
                break
        if session:
            break
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="创建会话失败"
        )
    
    return SessionResponse(
        session_id=session['session_id'],
        title=session['title'],
        created_at=session.get('created_at'),
        message_count=session.get('message_count', 0)
    )


@router.delete("/chat/sessions/{session_id}")
async def delete_session(
    session_id: str,
    user: User = Depends(get_current_user_dependency)
):
    """
    删除会话
    
    Returns:
        成功消息
    """
    from backend.database import SessionDAO
    session_dao = SessionDAO()
    
    # 验证会话存在且属于当前用户
    session = session_dao.get_session(session_id)
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在"
        )
    
    # 验证权限
    if session.user_id != user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权删除该会话"
        )
    
    # 删除会话
    session_dao.delete_session(session_id)
    
    return {"success": True, "message": "会话已删除"}


@router.get("/chat/sessions/{session_id}/messages", response_model=list[MessageResponse])
async def get_session_messages(
    session_id: str,
    user: User = Depends(get_current_user_dependency)
):
    """
    获取会话的所有消息
    
    Returns:
        消息列表
    """
    session_service = get_session_service()
    
    # 验证会话属于当前用户
    sessions_dict = session_service.get_user_sessions(user.user_id, limit=1000)
    session_exists = False
    for date_group, sessions in sessions_dict.items():
        for session in sessions:
            if session['session_id'] == session_id:
                session_exists = True
                break
        if session_exists:
            break
    
    if not session_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在或无权限"
        )
    
    # 获取消息
    messages = session_service.get_session_messages(session_id)
    
    return [
        MessageResponse(
            message_id=msg.get('message_id'),
            session_id=msg['session_id'],
            role=msg['role'],
            content=msg['content'],
            created_at=msg.get('created_at'),
            retrieved_docs=msg.get('retrieved_docs'),
            thinking_process=msg.get('thinking_process')
        )
        for msg in messages
    ]


@router.delete("/chat/messages/{message_id}")
async def delete_message(
    message_id: int,
    user: User = Depends(get_current_user_dependency)
):
    """
    删除单条消息（需验证归属）
    """
    session_service = get_session_service()
    try:
        session_id = session_service.delete_message(message_id, user.user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="消息不存在"
        )
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权删除该消息"
        )
    
    return {"success": True, "session_id": session_id}


@router.delete("/chat/sessions/{session_id}/messages/{message_id}")
async def delete_message_with_session(
    session_id: str,
    message_id: int,
    user: User = Depends(get_current_user_dependency)
):
    """
    删除单条消息（带 session_id 路径，便于路由匹配）
    """
    session_service = get_session_service()
    try:
        session_id_checked = session_service.delete_message(message_id, user.user_id)
        if session_id_checked != session_id:
            raise PermissionError("消息不属于该会话")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="消息不存在"
        )
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权删除该消息"
        )
    
    return {"success": True, "session_id": session_id_checked}
