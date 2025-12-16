"""
RAG对话 API 路由 - 支持 SSE 流式输出
"""
import json
import logging
import time
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Header, BackgroundTasks
from pydantic import BaseModel

from rag_service.services.rag_service import RAGService
from rag_service.database import SessionDAO, MessageDAO

logger = logging.getLogger(__name__)

router = APIRouter()

# 全局RAG服务实例
_rag_service: Optional[RAGService] = None


def get_rag_service() -> RAGService:
    """获取RAG服务实例（单例）"""
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service


# Pydantic 模型
class ChatMessageRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    user_id: int  # 从backend转发时传入


def _process_chat_task(user_id: int, session_id: str, question: str, thread_id: Optional[str]) -> None:
    """
    后台任务：执行 RAG 推理并将助手回复写入数据库。
    """
    rag_service = get_rag_service()
    message_dao = MessageDAO()
    logger.info(
        "[RAG Service][chat][task] 开始处理用户问题, user_id=%s, session_id=%s",
        user_id,
        session_id,
    )
    try:
        result = rag_service.query(user_id=user_id, question=question, thread_id=thread_id)
        answer = result.get("answer", "")
        retrieved_docs = result.get("retrieved_docs", [])
        thinking_process = result.get("thinking_process", [])
        tokens_used = result.get("tokens_used", 0)

        message_dao.create_message(
            session_id=session_id,
            role="assistant",
            content=answer,
            retrieved_docs=retrieved_docs,
            thinking_process=thinking_process,
            tokens_used=tokens_used,
        )
        logger.info(
            "[RAG Service][chat][task] 处理完成并写入数据库, session_id=%s, answer_len=%s",
            session_id,
            len(answer),
        )
    except Exception as e:
        logger.error(
            "[RAG Service][chat][task] 处理用户问题时出错: %s", str(e), exc_info=True
        )
        # 可选：写入错误消息，方便前端轮询结果时给出提示
        try:
            message_dao.create_message(
                session_id=session_id,
                role="assistant",
                content=f"抱歉，本次回答失败：{str(e)}",
            )
        except Exception:
            # 避免后台任务因为二次错误崩溃
            logger.exception("[RAG Service][chat][task] 写入错误消息失败")


@router.post("/api/chat/message")
async def send_message(
    request: ChatMessageRequest,
    background_tasks: BackgroundTasks,
    authorization: Optional[str] = Header(None),
):
    """
    发送消息（由 backend 转发），立即返回“已接收”，实际 RAG 推理在后台任务中执行。

    Args:
        request: 聊天消息请求（包含 user_id、session_id、message）
        background_tasks: FastAPI 后台任务管理器
        authorization: JWT token（可选）

    Returns:
        简单 JSON，表示请求已被接受：
        {
            "success": true,
            "status": "accepted",
            "session_id": "...",
            "message": "已开始处理"
        }
    """
    session_dao = SessionDAO()

    user_id = request.user_id

    # 获取或创建 session_id（仅作兜底，正常情况下应由 backend 创建）
    session_id = request.session_id
    if not session_id:
        title = request.message[:20] if len(request.message) > 20 else request.message
        session_id = session_dao.create_session(user_id, title)
        logger.info(
            "[RAG Service][chat] 未收到 session_id，已在 RAG Service 内部创建会话: %s",
            session_id,
        )

    # 构造 thread_id（用于 LangGraph checkpoint）
    thread_id = None
    if session_id:
        thread_id = f"user_{user_id}_session_{session_id}"

    # 将实际 RAG 推理放入后台任务
    background_tasks.add_task(
        _process_chat_task,
        user_id,
        session_id,
        request.message,
        thread_id,
    )

    return {
        "success": True,
        "status": "accepted",
        "session_id": session_id,
        "message": "已开始处理",
    }

