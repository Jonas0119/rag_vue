"""
会话管理 API 路由（与 chat.py 中的会话端点重复，但保持 RESTful 风格）
"""
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
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
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user_dependency)
):
    """
    删除会话（异步删除，立即返回）
    
    与 /chat/sessions/{session_id} 使用相同的优化策略
    """
    from backend.database import SessionDAO
    session_dao = SessionDAO()
    
    # 优化验证：直接查询单个会话（O(1) 而不是 O(n)）
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
    
    # 异步删除会话（数据库 CASCADE 会自动删除消息）
    background_tasks.add_task(
        _delete_session_background,
        session_id
    )
    
    # 立即返回成功（乐观更新）
    return {"success": True, "message": "会话已删除"}


def _delete_session_background(session_id: str):
    """
    后台删除会话（数据库 CASCADE 会自动删除消息）
    
    Args:
        session_id: 会话 ID
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"[会话删除] 后台删除会话: session_id={session_id}")
        from backend.database import SessionDAO
        session_dao = SessionDAO()
        session_dao.delete_session(session_id)
        logger.info(f"[会话删除] 会话删除成功: session_id={session_id}")
    except Exception as e:
        logger.error(f"[会话删除] 会话删除失败: session_id={session_id}, error={str(e)}", exc_info=True)
