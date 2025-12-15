"""
对话 API 路由 - 支持 SSE 流式输出
"""
import json
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.core.dependencies import get_current_user_dependency
from backend.database.models import User
from backend.services import get_rag_service, get_session_service

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
    user: User = Depends(get_current_user_dependency)
):
    """
    发送消息并返回 SSE 流式响应
    
    Returns:
        SSE 流，包含 chunk、complete、error 事件
    """
    rag_service = get_rag_service()
    session_service = get_session_service()
    
    # 获取或创建 session_id
    session_id = request.session_id
    if not session_id:
        # 创建新会话
        session_id = session_service.create_session(user.user_id, request.message)
        # 保存用户消息
        session_service.save_message(
            session_id=session_id,
            role='user',
            content=request.message
        )
    else:
        # 继续现有会话，保存用户消息
        session_service.save_message(
            session_id=session_id,
            role='user',
            content=request.message
        )
    
    # 获取 thread_id（用于多轮对话 checkpoint）
    thread_id = None
    if session_id:
        thread_id = f"user_{user.user_id}_session_{session_id}"
    
    async def generate_sse_stream():
        """生成 SSE 流"""
        try:
            current_answer = ""
            retrieved_docs = []
            thinking_process = []
            
            # 调用 RAG 服务的流式查询
            for response in rag_service.query_stream(
                user.user_id,
                request.message,
                thread_id=thread_id
            ):
                response_type = response.get('type')
                
                if response_type == 'chunk':
                    # 流式文本块
                    content = response.get('content', '')
                    if content:
                        current_answer += content
                        # 发送 chunk 事件
                        data = {
                            "type": "chunk",
                            "content": content,
                            "session_id": session_id
                        }
                        yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                
                elif response_type == 'thinking':
                    # 思考过程更新
                    thinking_steps = response.get('thinking_process', [])
                    if thinking_steps:
                        thinking_process.extend(thinking_steps)
                        data = {
                            "type": "thinking",
                            "data": thinking_steps,
                            "session_id": session_id
                        }
                        yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                
                elif response_type == 'complete':
                    # 生成完成
                    answer = response.get('answer', current_answer)
                    retrieved_docs = response.get('retrieved_docs', [])
                    thinking_process = response.get('thinking_process', thinking_process)
                    
                    # 保存 AI 回复到数据库
                    session_service.save_message(
                        session_id=session_id,
                        role='assistant',
                        content=answer,
                        retrieved_docs=retrieved_docs,
                        thinking_process=thinking_process,
                        tokens_used=response.get('tokens_used', 0)
                    )
                    
                    # 发送 complete 事件
                    data = {
                        "type": "complete",
                        "answer": answer,
                        "session_id": session_id,
                        "retrieved_docs": retrieved_docs,
                        "thinking_process": thinking_process,
                        "tokens_used": response.get('tokens_used', 0)
                    }
                    yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                    break
                
                elif response_type == 'error':
                    # 错误处理
                    error_msg = response.get('error', '未知错误')
                    data = {
                        "type": "error",
                        "message": error_msg,
                        "session_id": session_id
                    }
                    yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                    break
        
        except Exception as e:
            logger.error(f"流式生成错误: {str(e)}", exc_info=True)
            error_data = {
                "type": "error",
                "message": f"生成回答时发生错误: {str(e)}",
                "session_id": session_id
            }
            yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        generate_sse_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # 禁用 Nginx 缓冲
        }
    )


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
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user_dependency)
):
    """
    删除会话（异步删除，立即返回）
    
    使用乐观更新策略：
    1. 快速验证会话存在且属于当前用户（O(1) 查询）
    2. 立即返回成功，后台异步删除
    3. 数据库 CASCADE 会自动删除相关消息
    
    Returns:
        成功消息
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
    try:
        logger.info(f"[会话删除] 后台删除会话: session_id={session_id}")
        from backend.database import SessionDAO
        session_dao = SessionDAO()
        session_dao.delete_session(session_id)
        logger.info(f"[会话删除] 会话删除成功: session_id={session_id}")
    except Exception as e:
        logger.error(f"[会话删除] 会话删除失败: session_id={session_id}, error={str(e)}", exc_info=True)


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
