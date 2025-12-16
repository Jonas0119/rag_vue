"""
RAG State 定义模块
定义 LangGraph 工作流使用的自定义 State 类型
"""

from typing import Annotated, List, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages


def replace_messages(left: List[BaseMessage], right: List[BaseMessage]) -> List[BaseMessage]:
    """
    自定义 reducer：替换整个消息列表
    
    当右侧消息列表的第一个消息是 SystemMessage 且包含 "[对话历史总结]" 标记时，
    说明这是总结后的消息列表，应该替换而不是追加。
    
    Args:
        left: 现有的消息列表
        right: 新返回的消息列表
        
    Returns:
        替换后的消息列表
    """
    # 检查是否是总结操作：右侧消息列表的第一个消息是 SystemMessage 且包含总结标记
    if right and len(right) > 0:
        first_msg = right[0]
        # 检查是否是 SystemMessage
        from langchain_core.messages import SystemMessage
        if isinstance(first_msg, SystemMessage):
            content = str(getattr(first_msg, 'content', ''))
            # 如果第一个消息是 SystemMessage 且包含总结标记，说明这是总结后的完整列表，应该替换
            if "[对话历史总结]" in content:
                # 这是总结操作，替换整个消息列表
                return right
    
    # 默认行为：追加消息（使用 add_messages 的逻辑）
    return add_messages(left, right)


class RAGState(TypedDict):
    """
    RAG Graph 的 State 类型定义
    
    字段说明:
    - messages: 消息列表，使用自定义 reducer 自动合并（总结时替换，其他时候追加）
    - retry_count: 重试计数，用于跟踪文档检索重试次数
    - current_query: 当前查询文本，初始为原始问题，rewrite 后更新为重写问题
    - no_relevant_found: 标记是否已超过重试上限，用于 generate_answer 判断
    """

    messages: Annotated[List[BaseMessage], replace_messages]
    retry_count: int
    current_query: str
    no_relevant_found: bool

