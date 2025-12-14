"""
会话管理 API 路由（与 chat.py 中的会话端点重复，但保持 RESTful 风格）
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from backend.core.dependencies import get_current_user_dependency
from backend.database.models import User
from backend.services import get_session_service
from backend.api.chat import SessionResponse, MessageResponse

router = APIRouter()


@router.get("/sessions", response_model=List[SessionResponse])
async def get_sessions(
    user: User = Depends(get_current_user_dependency)
):
    """
    获取用户的会话列表（与 /chat/sessions 相同）
    """
    session_service = get_session_service()
    sessions_dict = session_service.get_user_sessions(user.user_id, limit=100)
    
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


@router.get("/sessions/{session_id}/messages", response_model=List[MessageResponse])
async def get_session_messages(
    session_id: str,
    user: User = Depends(get_current_user_dependency)
):
    """
    获取会话的所有消息（与 /chat/sessions/{session_id}/messages 相同）
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


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    user: User = Depends(get_current_user_dependency)
):
    """
    删除会话（与 /chat/sessions/{session_id} 相同）
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
    
    # 删除会话
    from backend.database import SessionDAO
    session_dao = SessionDAO()
    session_dao.delete_session(session_id)
    
    return {"success": True, "message": "会话已删除"}
