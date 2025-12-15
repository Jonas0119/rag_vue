"""
Graph 节点函数模块
定义 RAG Graph 中的各个节点函数
"""

from typing import Literal, Any, Optional
import logging
import uuid
from pydantic import BaseModel, Field
from langchain.messages import HumanMessage, ToolMessage, SystemMessage, AIMessage

from .rag_state import RAGState
from backend.utils.token_counter import token_counter
from backend.utils.config import config

logger = logging.getLogger(__name__)


def create_summarize_messages_node(summary_model: Any):
    """
    创建消息总结节点，当消息总 token 数超过阈值时自动总结
    
    Args:
        summary_model: 用于总结的模型
    
    Returns:
        节点函数
    """
    def summarize_messages(state: RAGState):
        """检查并总结消息历史"""
        messages = state["messages"]
        
        # 详细记录消息信息
        logger.info(f"[总结节点] 当前消息列表（共 {len(messages)} 条）:")
        for i, msg in enumerate(messages):
            msg_type = type(msg).__name__
            content_preview = str(getattr(msg, 'content', ''))[:100] if hasattr(msg, 'content') else 'N/A'
            tool_calls = getattr(msg, 'tool_calls', None)
            logger.info(f"  消息 {i+1}: {msg_type} - 内容预览: {content_preview}...")
            if tool_calls:
                logger.info(f"    工具调用: {len(tool_calls)} 个")
        
        # 1. 分离 SystemMessage（如果有）
        system_messages = [msg for msg in messages if isinstance(msg, SystemMessage)]
        non_system_messages = [msg for msg in messages if not isinstance(msg, SystemMessage)]
        
        # 2. 计算总 token 数（包括 SystemMessage）
        total_tokens = token_counter.get_messages_tokens(messages)
        threshold = config.MESSAGE_SUMMARIZATION_THRESHOLD
        
        if total_tokens <= threshold:
            # 不需要总结
            logger.info(f"[总结节点] 消息总 token 数 {int(total_tokens)} <= {threshold}，无需总结")
            logger.info(f"[总结节点] 消息数量: {len(messages)} 条")
            return {}
        
        logger.info(f"[总结节点] 消息总 token 数 {int(total_tokens)} > {threshold}，开始总结")
        
        # 3. 确定需要保留的消息数量
        keep_count = config.MESSAGE_SUMMARIZATION_KEEP_MESSAGES
        
        # 4. 分离需要总结的旧消息和需要保留的新消息
        if len(non_system_messages) <= keep_count:
            logger.info("[总结节点] 非系统消息数量不足，无需总结")
            return {}
        
        # 4.1 先简单分离，然后确保新消息的完整性
        old_messages = non_system_messages[:-keep_count]
        new_messages = non_system_messages[-keep_count:]
        
        # 4.2 确保新消息序列的完整性：检查是否有孤立的 ToolMessage
        # 如果第一条新消息是 ToolMessage，需要找到对应的 AIMessage
        if new_messages and isinstance(new_messages[0], ToolMessage):
            logger.warning("[总结节点] 发现新消息序列以 ToolMessage 开头，需要查找对应的 AIMessage")
            # 向前查找对应的 AIMessage
            tool_call_id = getattr(new_messages[0], 'tool_call_id', None)
            if tool_call_id:
                # 在旧消息中查找对应的 AIMessage
                found_ai_msg = None
                for msg in reversed(old_messages):
                    if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls') and msg.tool_calls:
                        for tc in msg.tool_calls:
                            tc_id = None
                            if isinstance(tc, dict):
                                tc_id = tc.get('id', tc.get('tool_call_id'))
                            else:
                                tc_id = getattr(tc, 'id', getattr(tc, 'tool_call_id', None))
                            if tc_id == tool_call_id:
                                found_ai_msg = msg
                                break
                    if found_ai_msg:
                        break
                
                if found_ai_msg:
                    # 将对应的 AIMessage 移到新消息列表的开头
                    logger.info("[总结节点] 找到对应的 AIMessage，将其移到新消息列表开头")
                    # 从旧消息中移除
                    old_messages = [msg for msg in old_messages if msg != found_ai_msg]
                    # 添加到新消息开头
                    new_messages = [found_ai_msg] + new_messages
                else:
                    # 找不到对应的 AIMessage，删除孤立的 ToolMessage
                    logger.warning(f"[总结节点] 找不到 ToolMessage (tool_call_id: {tool_call_id}) 对应的 AIMessage，删除孤立的 ToolMessage")
                    new_messages = new_messages[1:]
        
        # 4.3 确保新消息序列的完整性：检查是否有孤立的 ToolMessage（不在开头的情况）
        # 遍历新消息，确保每个 ToolMessage 都有对应的 AIMessage
        cleaned_new_messages = []
        i = 0
        while i < len(new_messages):
            msg = new_messages[i]
            if isinstance(msg, ToolMessage):
                tool_call_id = getattr(msg, 'tool_call_id', None)
                if tool_call_id:
                    # 检查前面是否有对应的 AIMessage
                    has_corresponding_ai = False
                    for prev_msg in cleaned_new_messages:
                        if isinstance(prev_msg, AIMessage) and hasattr(prev_msg, 'tool_calls') and prev_msg.tool_calls:
                            for tc in prev_msg.tool_calls:
                                tc_id = None
                                if isinstance(tc, dict):
                                    tc_id = tc.get('id', tc.get('tool_call_id'))
                                else:
                                    tc_id = getattr(tc, 'id', getattr(tc, 'tool_call_id', None))
                                if tc_id == tool_call_id:
                                    has_corresponding_ai = True
                                    break
                            if has_corresponding_ai:
                                break
                    
                    if not has_corresponding_ai:
                        # 在旧消息中查找
                        found_ai_msg = None
                        for old_msg in reversed(old_messages):
                            if isinstance(old_msg, AIMessage) and hasattr(old_msg, 'tool_calls') and old_msg.tool_calls:
                                for tc in old_msg.tool_calls:
                                    tc_id = None
                                    if isinstance(tc, dict):
                                        tc_id = tc.get('id', tc.get('tool_call_id'))
                                    else:
                                        tc_id = getattr(tc, 'id', getattr(tc, 'tool_call_id', None))
                                    if tc_id == tool_call_id:
                                        found_ai_msg = old_msg
                                        break
                                if found_ai_msg:
                                    break
                        
                        if found_ai_msg:
                            # 将对应的 AIMessage 移到新消息列表
                            logger.info(f"[总结节点] 找到 ToolMessage 对应的 AIMessage，将其移到新消息列表")
                            old_messages = [m for m in old_messages if m != found_ai_msg]
                            cleaned_new_messages.append(found_ai_msg)
                            cleaned_new_messages.append(msg)
                            i += 1
                            continue
                        else:
                            # 找不到对应的 AIMessage，删除孤立的 ToolMessage
                            logger.warning(f"[总结节点] 找不到 ToolMessage (tool_call_id: {tool_call_id}) 对应的 AIMessage，删除孤立的 ToolMessage")
                            i += 1
                            continue
                    else:
                        # 有对应的 AIMessage，保留
                        cleaned_new_messages.append(msg)
                        i += 1
                        continue
                else:
                    # ToolMessage 没有 tool_call_id，可能是无效的，删除
                    logger.warning("[总结节点] ToolMessage 没有 tool_call_id，删除")
                    i += 1
                    continue
            else:
                # 不是 ToolMessage，正常保留
                cleaned_new_messages.append(msg)
                i += 1
        
        new_messages = cleaned_new_messages
        
        # 4.4 确保旧消息序列的完整性：删除没有对应 ToolMessage 的 AIMessage（包含工具调用但工具调用未完成）
        # 注意：这里我们只检查旧消息，因为旧消息会被总结，所以可以删除不完整的消息
        cleaned_old_messages = []
        i = 0
        while i < len(old_messages):
            msg = old_messages[i]
            if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls') and msg.tool_calls:
                # 检查是否有对应的 ToolMessage（在旧消息或新消息中）
                has_corresponding_tool = False
                tool_call_ids = set()
                for tc in msg.tool_calls:
                    tc_id = None
                    if isinstance(tc, dict):
                        tc_id = tc.get('id', tc.get('tool_call_id'))
                    else:
                        tc_id = getattr(tc, 'id', getattr(tc, 'tool_call_id', None))
                    if tc_id:
                        tool_call_ids.add(tc_id)
                
                # 在旧消息的后续消息中查找
                for j in range(i + 1, len(old_messages)):
                    next_msg = old_messages[j]
                    if isinstance(next_msg, ToolMessage):
                        tool_call_id = getattr(next_msg, 'tool_call_id', None)
                        if tool_call_id in tool_call_ids:
                            has_corresponding_tool = True
                            break
                    elif isinstance(next_msg, AIMessage) or isinstance(next_msg, HumanMessage):
                        # 遇到新的 AIMessage 或 HumanMessage，停止查找
                        break
                
                # 如果旧消息中没有，在新消息中查找
                if not has_corresponding_tool:
                    for new_msg in new_messages:
                        if isinstance(new_msg, ToolMessage):
                            tool_call_id = getattr(new_msg, 'tool_call_id', None)
                            if tool_call_id in tool_call_ids:
                                has_corresponding_tool = True
                                break
                
                if not has_corresponding_tool:
                    # 没有对应的 ToolMessage，删除这条 AIMessage（如果它没有内容）
                    has_content = bool(getattr(msg, 'content', None))
                    if not has_content:
                        logger.warning("[总结节点] 删除没有对应 ToolMessage 的 AIMessage（无内容）")
                        i += 1
                        continue
                    else:
                        # 有内容，保留但移除工具调用
                        logger.info("[总结节点] 移除没有对应 ToolMessage 的工具调用，保留消息内容")
                        cleaned_msg = AIMessage(
                            content=msg.content,
                            tool_calls=[],
                            additional_kwargs=getattr(msg, 'additional_kwargs', {})
                        )
                        cleaned_old_messages.append(cleaned_msg)
                        i += 1
                        continue
                else:
                    # 有对应的 ToolMessage，保留
                    cleaned_old_messages.append(msg)
                    i += 1
            else:
                # 不是包含工具调用的 AIMessage，正常保留
                cleaned_old_messages.append(msg)
                i += 1
        
        old_messages = cleaned_old_messages
        
        # 5. 生成总结
        max_tokens = config.MESSAGE_SUMMARIZATION_MAX_TOKENS
        summary_prompt = f"""请总结以下对话历史，保留关键信息和上下文，以便后续对话能够继续。

对话历史：
{_format_messages_for_summary(old_messages)}

请生成一个简洁的总结，包含：
1. 讨论的主要话题
2. 用户的关键问题和需求
3. 已提供的重要信息或答案

**重要限制**：总结内容不能超过 {max_tokens} tokens（约 {max_tokens * 2} 个中文字符）。请确保总结简洁、精炼，只保留最关键的信息。

总结："""
        
        # 调用模型生成总结
        summary_messages_list = [{"role": "user", "content": summary_prompt}]
        input_tokens = token_counter.get_messages_tokens([HumanMessage(content=summary_prompt)])
        
        response = summary_model.invoke(summary_messages_list)
        summary_content=str(response.content)
        
        # 处理 response.content：可能是字符串、列表或其他格式
        # 如果是列表，提取 type='text' 的内容，忽略 type='thinking' 的内容
        raw_content = response.content
        if isinstance(raw_content, list):
            # 从列表中提取 type='text' 的内容
            text_parts = []
            for item in raw_content:
                if isinstance(item, dict):
                    item_type = item.get('type', '')
                    if item_type == 'text' and 'text' in item:
                        text_parts.append(item['text'])
                    elif item_type == 'thinking':
                        # 忽略 thinking 内容
                        logger.debug(f"[总结清理] 跳过 thinking 类型内容")
                elif isinstance(item, str):
                    # 如果是字符串，直接添加
                    text_parts.append(item)
            clean_summary_content = '\n'.join(text_parts) if text_parts else str(raw_content)
        else:
            # 如果是字符串或其他格式，直接转换
            clean_summary_content = str(raw_content)
        
        # 清理总结内容，移除 thinking 等无关内容（仅用于 SystemMessage 融合）
        #clean_summary_content = _clean_summary_content(no_thinking_summary)
        
        output_tokens = _safe_get_tokens_from_response(response)[1]
        token_counter.count_tokens(
            model_name="summary_model",
            node_name="summarize_messages",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        
        # 6. 创建或更新 SystemMessage，将总结合并到其中
        # 原因：SystemMessage 只能有一个，且应该在消息列表开头
        # 总结应该合并到 SystemMessage 中，而不是作为单独的 AIMessage
        if system_messages:
            # 合并到现有 SystemMessage
            existing_system = system_messages[0]
            existing_content = str(existing_system.content)
            # 检查是否已有总结标记
            if "[对话历史总结]" in existing_content:
                # 如果已有总结，替换旧的总结部分
                # 提取非总结部分（如果有其他系统提示）
                parts = existing_content.split("[对话历史总结]")
                base_content = parts[0].strip() if parts[0].strip() else ""
                if base_content:
                    updated_system_content = f"{base_content}\n\n[对话历史总结]\n{clean_summary_content}"
                else:
                    updated_system_content = f"[对话历史总结]\n{clean_summary_content}"
            else:
                # 没有总结，追加新总结
                if existing_content:
                    updated_system_content = f"{existing_content}\n\n[对话历史总结]\n{clean_summary_content}"
                else:
                    updated_system_content = f"[对话历史总结]\n{clean_summary_content}"
            updated_system_msg = SystemMessage(content=updated_system_content)
        else:
            # 创建新的 SystemMessage
            updated_system_msg = SystemMessage(content=f"[对话历史总结]\n{clean_summary_content}")
        
        # 7. 构建最终消息列表：SystemMessage（包含总结）+ 最近 N 条消息
        # 注意：返回完整的消息列表以替换现有消息（因为 add_messages reducer 会追加）
        updated_messages = [updated_system_msg] + new_messages
        
        # 清理未配对的工具调用（避免 Anthropic API 报错）
        updated_messages = _clean_orphaned_tool_calls(updated_messages)
        
        # 8. 验证总结效果
        new_total_tokens = token_counter.get_messages_tokens(updated_messages)
        logger.info(f"[总结节点] 总结前: {len(messages)} 条消息, {int(total_tokens)} tokens")
        logger.info(f"[总结节点] 总结后: {len(updated_messages)} 条消息, {int(new_total_tokens)} tokens")
        
        # 详细记录最终消息列表
        logger.info(f"[总结节点] 最终消息列表（共 {len(updated_messages)} 条）:")
        for i, msg in enumerate(updated_messages):
            msg_type = type(msg).__name__
            content_preview = str(getattr(msg, 'content', ''))[:100] if hasattr(msg, 'content') else 'N/A'
            logger.info(f"  最终消息 {i+1}: {msg_type} - {content_preview}...")
        
        if new_total_tokens > threshold:
            logger.warning(f"[总结节点] 警告：总结后 token 数 {int(new_total_tokens)} 仍超过阈值 {threshold}")
        
        logger.info(f"[总结节点] Token 统计 - 输入: {int(input_tokens)}, 输出: {int(output_tokens)}")
        logger.info(f"[总结节点] 总结内容预览: {summary_content[:200]}...")
        logger.info("=" * 80)
        
        # 重要：返回完整的消息列表以替换现有消息
        # 注意：由于 add_messages reducer 的行为，我们需要确保返回的是完整的替换列表
        # 但实际上，LangGraph 的 add_messages 会将返回的消息追加，所以我们需要特殊处理
        # 但根据用户反馈，旧消息仍然存在，说明可能需要不同的处理方式
        return {"messages": updated_messages}
    
    return summarize_messages


def _format_messages_for_summary(messages):
    """格式化消息用于总结"""
    formatted = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            role = "用户"
        elif isinstance(msg, AIMessage):
            role = "助手"
        elif isinstance(msg, SystemMessage):
            role = "系统"
        elif isinstance(msg, ToolMessage):
            role = "工具"
        else:
            role = "未知"
        
        content = str(getattr(msg, "content", ""))
        formatted.append(f"{role}: {content}")
    return "\n".join(formatted)


def _clean_summary_content(summary_content: str) -> str:
    """
    清理总结内容，移除 thinking 等无关内容，只保留纯粹的总结文本
    
    Args:
        summary_content: 原始总结内容（应该已经是提取出的文本内容）
        
    Returns:
        清理后的总结内容
    """
    import re
    import json
    
    if not summary_content:
        return ""
    
    cleaned_content = summary_content
    
    # 清理策略1: 如果内容看起来像 JSON 列表字符串，尝试解析并提取 text 类型
    # 处理类似 "[{'type': 'thinking', ...}, {'type': 'text', 'text': '...'}]" 的情况
    if cleaned_content.strip().startswith('[') and cleaned_content.strip().endswith(']'):
        try:
            parsed = json.loads(cleaned_content)
            if isinstance(parsed, list):
                text_parts = []
                for item in parsed:
                    if isinstance(item, dict):
                        item_type = item.get('type', '')
                        if item_type == 'text' and 'text' in item:
                            text_parts.append(item['text'])
                        elif item_type == 'thinking':
                            # 忽略 thinking 内容
                            logger.debug(f"[总结清理] 从 JSON 中跳过 thinking 类型内容")
                if text_parts:
                    cleaned_content = '\n'.join(text_parts)
                    logger.debug(f"[总结清理] 从 JSON 列表中提取了 {len(text_parts)} 个文本块")
        except (json.JSONDecodeError, ValueError):
            # 不是有效的 JSON，继续使用原始内容
            pass
    
    # 清理策略2: 移除明显的 thinking 标记块
    # 匹配类似 "思考过程:"、"Thinking:"、"推理:" 等开头的块
    thinking_patterns = [
        r'(?i)(思考过程|thinking|推理过程|reasoning)[:：]\s*\n.*?(?=\n\n|\n[^\s]|$)',
        r'(?i)(思考|thinking|推理|reasoning)[:：].*?(?=\n\n|\n[^\s]|$)',
        r'```thinking.*?```',
        r'```reasoning.*?```',
        r'<thinking>.*?</thinking>',
        r'<reasoning>.*?</reasoning>',
    ]
    
    for pattern in thinking_patterns:
        cleaned_content = re.sub(pattern, '', cleaned_content, flags=re.DOTALL)
    
    # 清理策略3: 移除包含工具调用相关的部分
    tool_patterns = [
        r'(?i)(工具调用|tool call|function call)[:：].*?(?=\n\n|\n[^\s]|$)',
        r'(?i)(调用工具|调用函数).*?(?=\n\n|\n[^\s]|$)',
    ]
    
    for pattern in tool_patterns:
        cleaned_content = re.sub(pattern, '', cleaned_content, flags=re.DOTALL)
    
    # 清理策略4: 移除多余的空行和空白
    cleaned_content = re.sub(r'\n{3,}', '\n\n', cleaned_content)  # 多个空行合并为两个
    cleaned_content = cleaned_content.strip()
    
    # 如果清理后内容为空或过短，使用原始内容（可能是格式不同）
    if len(cleaned_content) < len(summary_content) * 0.3:  # 如果清理后内容少于原内容的30%
        logger.warning(f"[总结清理] 清理后内容过短，使用原始内容。原始长度: {len(summary_content)}, 清理后长度: {len(cleaned_content)}")
        cleaned_content = summary_content.strip()
    
    logger.info(f"[总结清理] 原始内容长度: {len(summary_content)}, 清理后内容长度: {len(cleaned_content)}")
    logger.debug(f"[总结清理] 清理后内容预览: {cleaned_content[:200]}...")
    return cleaned_content


def _validate_and_fix_tool_calls(messages: list) -> list:
    """
    验证并修复工具调用格式，确保符合 Anthropic API 要求
    
    Anthropic API 严格要求：
    1. 如果 AIMessage 包含 tool_calls，每个 tool_call 必须有唯一的 id（字符串）
    2. 对应的 ToolMessage 必须有 tool_call_id，且必须与 tool_call 的 id 完全匹配
    3. ToolMessage 必须紧跟在包含 tool_calls 的 AIMessage 之后
    4. 如果 AIMessage 有 tool_calls，所有 tool_calls 都必须有对应的 ToolMessage
    
    Args:
        messages: 消息列表
        
    Returns:
        修复后的消息列表
    """
    if not messages:
        return messages
    
    fixed_messages = []
    i = 0
    
    while i < len(messages):
        msg = messages[i]
        
        # 检查是否是包含工具调用的 AIMessage
        if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls') and msg.tool_calls:
            # 验证并修复 tool_calls 的 id 格式
            fixed_tool_calls = []
            tool_call_ids = []
            
            for tc in msg.tool_calls:
                if isinstance(tc, dict):
                    tool_call_id = tc.get('id', tc.get('tool_call_id'))
                    # 确保 id 是字符串类型
                    if tool_call_id is not None:
                        tool_call_id = str(tool_call_id)
                        tc['id'] = tool_call_id
                        if 'tool_call_id' in tc:
                            del tc['tool_call_id']
                    else:
                        # 如果没有 id，生成一个（不应该发生，但为了安全）
                        tool_call_id = str(uuid.uuid4())
                        tc['id'] = tool_call_id
                        logger.warning(f"[修复工具调用] 为工具调用生成新的 ID: {tool_call_id}")
                    fixed_tool_calls.append(tc)
                    tool_call_ids.append(tool_call_id)
                else:
                    # ToolCall 对象
                    tool_call_id = getattr(tc, 'id', getattr(tc, 'tool_call_id', None))
                    if tool_call_id is not None:
                        tool_call_id = str(tool_call_id)
                        # 创建新的字典格式（Anthropic API 要求）
                        fixed_tc = {
                            'id': tool_call_id,
                            'name': getattr(tc, 'name', 'unknown'),
                            'args': getattr(tc, 'args', getattr(tc, 'arguments', {}))
                        }
                        fixed_tool_calls.append(fixed_tc)
                        tool_call_ids.append(tool_call_id)
                    else:
                        # 如果没有 id，生成一个
                        tool_call_id = str(uuid.uuid4())
                        fixed_tc = {
                            'id': tool_call_id,
                            'name': getattr(tc, 'name', 'unknown'),
                            'args': getattr(tc, 'args', getattr(tc, 'arguments', {}))
                        }
                        fixed_tool_calls.append(fixed_tc)
                        tool_call_ids.append(tool_call_id)
                        logger.warning(f"[修复工具调用] 为工具调用生成新的 ID: {tool_call_id}")
            
            # 创建修复后的 AIMessage
            fixed_ai_msg = AIMessage(
                content=msg.content,
                tool_calls=fixed_tool_calls,
                additional_kwargs=getattr(msg, 'additional_kwargs', {})
            )
            fixed_messages.append(fixed_ai_msg)
            i += 1
            
            # 检查后续的 ToolMessage 是否匹配
            tool_call_ids_set = set(tool_call_ids)
            found_tool_messages = set()
            
            # 查找匹配的 ToolMessage（必须紧跟在 AIMessage 之后）
            while i < len(messages):
                next_msg = messages[i]
                
                # 如果遇到新的 AIMessage 或 HumanMessage，停止查找
                if isinstance(next_msg, AIMessage) or isinstance(next_msg, HumanMessage):
                    break
                
                if isinstance(next_msg, ToolMessage):
                    tool_call_id = getattr(next_msg, 'tool_call_id', None)
                    if tool_call_id is not None:
                        tool_call_id = str(tool_call_id)  # 确保是字符串
                        if tool_call_id in tool_call_ids_set:
                            # 修复 ToolMessage 的 tool_call_id（确保是字符串）
                            fixed_tool_msg = ToolMessage(
                                content=next_msg.content,
                                tool_call_id=tool_call_id
                            )
                            fixed_messages.append(fixed_tool_msg)
                            found_tool_messages.add(tool_call_id)
                            i += 1
                        else:
                            # tool_call_id 不匹配，跳过这个 ToolMessage（可能是孤立的）
                            logger.warning(f"[修复工具调用] 跳过不匹配的 ToolMessage (tool_call_id: {tool_call_id})")
                            i += 1
                    else:
                        # ToolMessage 没有 tool_call_id，跳过
                        logger.warning("[修复工具调用] 跳过没有 tool_call_id 的 ToolMessage")
                        i += 1
                else:
                    # 其他类型的消息，保留
                    fixed_messages.append(next_msg)
                    i += 1
            
            # 检查是否所有工具调用都有对应的 ToolMessage
            missing_tool_messages = tool_call_ids_set - found_tool_messages
            if missing_tool_messages:
                logger.error(
                    f"[修复工具调用] ⚠️ 警告：部分工具调用没有对应的 ToolMessage: {missing_tool_messages}"
                )
                # 移除没有对应 ToolMessage 的工具调用
                remaining_tool_calls = [
                    tc for tc in fixed_tool_calls 
                    if str(tc.get('id', '')) in found_tool_messages
                ]
                if remaining_tool_calls:
                    # 更新 AIMessage，只保留有对应 ToolMessage 的工具调用
                    fixed_ai_msg = AIMessage(
                        content=fixed_ai_msg.content,
                        tool_calls=remaining_tool_calls,
                        additional_kwargs=fixed_ai_msg.additional_kwargs
                    )
                    fixed_messages[-1] = fixed_ai_msg
                else:
                    # 所有工具调用都没有对应的 ToolMessage，移除工具调用
                    if fixed_ai_msg.content:
                        fixed_ai_msg = AIMessage(
                            content=fixed_ai_msg.content,
                            tool_calls=[],
                            additional_kwargs=fixed_ai_msg.additional_kwargs
                        )
                        fixed_messages[-1] = fixed_ai_msg
                    else:
                        # 没有内容也没有有效的工具调用，移除这条消息
                        fixed_messages.pop()
                        logger.warning("[修复工具调用] 移除无效的 AIMessage（没有内容且没有有效的工具调用）")
        else:
            # 不是包含工具调用的 AIMessage，直接保留
            fixed_messages.append(msg)
            i += 1
    
    return fixed_messages


def _clean_orphaned_tool_calls(messages: list) -> list:
    """
    清理未配对的工具调用
    
    Anthropic API 要求：如果消息中有工具调用（tool_calls），
    必须紧接着有对应的 ToolMessage，且 tool_call_id 必须匹配。
    
    如果发现未配对的工具调用：
    - 如果消息有内容，移除未配对的工具调用但保留消息内容
    - 如果消息没有内容，移除整条消息
    
    Args:
        messages: 消息列表
        
    Returns:
        清理后的消息列表
    """
    if not messages:
        return messages
    
    # 先验证并修复工具调用格式
    messages = _validate_and_fix_tool_calls(messages)
    
    cleaned_messages = []
    i = 0
    
    while i < len(messages):
        msg = messages[i]
        
        # 检查是否是包含工具调用的 AIMessage
        if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls') and msg.tool_calls:
            # 收集所有工具调用的 ID
            tool_call_ids = set()
            for tc in msg.tool_calls:
                if isinstance(tc, dict):
                    tool_call_id = tc.get('id', tc.get('tool_call_id'))
                else:
                    tool_call_id = getattr(tc, 'id', getattr(tc, 'tool_call_id', None))
                if tool_call_id:
                    tool_call_ids.add(tool_call_id)
            
            # 检查后续消息中是否有对应的 ToolMessage
            found_tool_messages = set()
            j = i + 1
            while j < len(messages) and j < i + 10:  # 最多检查后续10条消息
                next_msg = messages[j]
                if isinstance(next_msg, ToolMessage):
                    tool_call_id = getattr(next_msg, 'tool_call_id', None)
                    if tool_call_id and tool_call_id in tool_call_ids:
                        found_tool_messages.add(tool_call_id)
                elif isinstance(next_msg, AIMessage) or isinstance(next_msg, HumanMessage):
                    # 遇到新的 AIMessage 或 HumanMessage，停止检查
                    break
                j += 1
            
            # 如果所有工具调用都有对应的 ToolMessage，保留这条消息
            if found_tool_messages == tool_call_ids:
                cleaned_messages.append(msg)
                i += 1
            else:
                # 有未配对的工具调用
                orphaned_ids = tool_call_ids - found_tool_messages
                logger.warning(
                    f"[清理工具调用] 发现未配对的工具调用 IDs: {orphaned_ids}，"
                    f"工具调用 IDs: {tool_call_ids}, 找到的 ToolMessage IDs: {found_tool_messages}"
                )
                
                # 检查消息是否有内容（不仅仅是工具调用）
                has_content = bool(getattr(msg, 'content', None))
                
                if has_content:
                    # 消息有内容，移除工具调用但保留消息内容
                    # 只保留已配对的工具调用
                    paired_tool_calls = []
                    for tc in msg.tool_calls:
                        if isinstance(tc, dict):
                            tool_call_id = tc.get('id', tc.get('tool_call_id'))
                        else:
                            tool_call_id = getattr(tc, 'id', getattr(tc, 'tool_call_id', None))
                        if tool_call_id and tool_call_id in found_tool_messages:
                            paired_tool_calls.append(tc)
                    
                    # 创建新的 AIMessage，只包含已配对的工具调用（或没有工具调用）
                    # 使用 copy 方法创建新消息，然后修改 tool_calls
                    cleaned_msg = AIMessage(
                        content=msg.content,
                        tool_calls=paired_tool_calls if paired_tool_calls else [],
                        additional_kwargs=getattr(msg, 'additional_kwargs', {})
                    )
                    cleaned_messages.append(cleaned_msg)
                    logger.info(f"[清理工具调用] 移除未配对的工具调用，保留消息内容。原始工具调用数: {len(msg.tool_calls)}, 保留: {len(paired_tool_calls)}")
                else:
                    # 消息没有内容，只有工具调用，移除整条消息
                    logger.warning(f"[清理工具调用] 移除包含未配对工具调用的 AIMessage（无内容）")
                
                i += 1
                # 同时移除后续可能相关的 ToolMessage（如果它们属于未配对的工具调用）
                while i < len(messages):
                    next_msg = messages[i]
                    if isinstance(next_msg, ToolMessage):
                        tool_call_id = getattr(next_msg, 'tool_call_id', None)
                        if tool_call_id and tool_call_id in orphaned_ids:
                            # 这个 ToolMessage 属于未配对的工具调用，也移除它
                            logger.warning(f"[清理工具调用] 移除未配对的 ToolMessage (tool_call_id: {tool_call_id})")
                            i += 1
                            continue
                    # 不是相关的 ToolMessage，停止移除
                    break
        else:
            # 不是包含未配对工具调用的消息，正常保留
            cleaned_messages.append(msg)
            i += 1
    
    if len(cleaned_messages) != len(messages):
        logger.info(f"[清理工具调用] 清理完成：{len(messages)} 条消息 -> {len(cleaned_messages)} 条消息")
    
    return cleaned_messages


# 提示词定义
GRADE_PROMPT = (
    "你是一个评估文档相关性的评分员。请评估检索到的文档是否与用户问题相关。\n\n"
    "检索到的文档内容：\n{context}\n\n"
    "用户问题：{question}\n\n"
    "**判断标准：**\n"
    "- 如果文档包含直接回答或与核心问题相关的信息，返回 'yes'，"
    "即使文档没有提到问题中的所有细节（例如，具体的人名）。\n"
    "- 如果文档涉及主要主题或提供相关信息，返回 'yes'。\n"
    "- 只有当文档与问题完全无关或不相关时，才返回 'no'。\n\n"
    "**示例：**\n"
    "- 问题：'张三对人工智能有什么看法？' 文档：'人工智能可以用于自动化。' → 'yes'（相关，回答了主题）\n"
    "- 问题：'X有哪些类型？' 文档：'X有两种类型：A和B。' → 'yes'（直接回答了问题）\n"
    "- 问题：'今天天气怎么样？' 文档：'烹饪食谱。' → 'no'（完全无关）\n\n"
    "请给出二元评分 'yes' 或 'no' 来表示相关性。"
)

REWRITE_PROMPT = (
    "你是一个问题重写助手。你的任务是将用户的问题重写为更具体、更易搜索的形式。\n\n"
    "原始问题："
    "\n ------- \n"
    "{question}"
    "\n ------- \n\n"
    "**重要提示**：只返回改进后的问题文本，不要包含其他内容。"
    "不要包含任何分析、解释或评论。"
    "不要包含类似'改进后的问题：'或'这是改进版本：'这样的短语。"
    "只返回重写后的问题本身，作为一个清晰、可搜索的查询。\n\n"
    "改进后的问题："
)

GENERATE_PROMPT = (
    "你是一个问答助手。请使用以下检索到的上下文内容来回答问题。\n\n"
    "**指令：**\n"
    "- 如果上下文包含足够的信息来回答问题，请提供清晰简洁的答案，不要有废话。\n"
    "- 如果上下文只包含标题、标题或目录而没有实际内容，你应该指出检索到的信息不足，并建议可能需要更具体的搜索。\n\n"
    #"- 最多使用三句话，保持答案简洁。\n\n"
    "问题：{question} \n\n"
    "上下文：{context}\n\n"
    "答案："
)


# 数据结构定义
class GradeDocuments(BaseModel):  # type: ignore[call-arg]
    """Grade documents using a binary score for relevance check."""

    binary_score: Literal["yes", "no"] = Field(
        description="Relevance score: 'yes' if relevant, or 'no' if not relevant"
    )


def _safe_get_tokens_from_response(response: Any) -> tuple[int, int]:
    """
    兼容不同模型/SDK的 token 统计字段。
    优先 usage_metadata，其次 response_metadata.usage，最后估算。
    """
    return token_counter.get_model_response_tokens(response)


# 节点函数
def create_generate_query_or_respond_node(response_model: Any, retrieve_tool):
    """
    创建生成查询或响应的节点函数
    
    Args:
        response_model: 响应模型
        retrieve_tool: 检索工具
        
    Returns:
        节点函数
    """
    def generate_query_or_respond(state: RAGState):
        """Call the model to generate a response based on the current state. 
        For RAG system, we ALWAYS require retrieval first before answering.
        """
        logger.info("=" * 80)
        logger.info("[LangGraph节点] generate_query_or_respond: 开始执行")
        messages = state["messages"]
        current_query = state.get("current_query", "")
        retry_count = state.get("retry_count", 0)
        logger.info(f"[输入] 当前查询: {current_query}")
        logger.info(f"[输入] retry_count: {retry_count} (单次请求内的重试计数，每次新请求应从 0 开始)")
        logger.info(f"[输入] messages 数量: {len(messages)}")
        
        logger.info(f"[输入] 消息列表详情:")
        for i, msg in enumerate(messages):
            msg_type = type(msg).__name__
            content_preview = str(getattr(msg, 'content', ''))[:100] if hasattr(msg, 'content') else 'N/A'
            tool_calls = getattr(msg, 'tool_calls', None)
            logger.info(f"  消息 {i+1}: {msg_type} - {content_preview}...")
            if tool_calls:
                logger.info(f"    工具调用: {len(tool_calls)} 个")
        if messages:
            last_msg = messages[-1]
            if hasattr(last_msg, 'content'):
                logger.info(f"[输入] 最后一条消息内容: {str(last_msg.content)[:200]}...")
        
        # 清理未配对的工具调用（避免 Anthropic API 报错）
        messages = _clean_orphaned_tool_calls(messages)
        
        # 确保 SystemMessage 在消息列表开头（如果存在）
        system_messages = [msg for msg in messages if isinstance(msg, SystemMessage)]
        non_system_messages = [msg for msg in messages if not isinstance(msg, SystemMessage)]
        
        if system_messages and len(system_messages) > 0:
            # 如果 SystemMessage 不在开头，重新排序
            if not isinstance(messages[0], SystemMessage):
                logger.warning("[输入] ⚠️ SystemMessage 不在消息列表开头，重新排序")
                messages = system_messages + non_system_messages
                # 验证 retry_count 重置：如果是新的用户消息（没有之前的工具调用），retry_count 应该是 0
        # 这是一个额外的安全检查，确保 retry_count 在每次新请求时正确重置
        is_new_user_message = False
        if len(messages) > 0:
            last_msg = messages[-1]
            if isinstance(last_msg, HumanMessage):
                # 检查是否有之前的工具调用
                has_previous_tool_call = False
                for msg in messages[:-1]:
                    if hasattr(msg, 'tool_calls') and msg.tool_calls:
                        has_previous_tool_call = True
                        break
                    if isinstance(msg, ToolMessage):
                        has_previous_tool_call = True
                        break
                
                if not has_previous_tool_call:
                    is_new_user_message = True
                    if retry_count != 0:
                        logger.warning(f"[LangGraph节点] 检测到新用户消息，但 retry_count={retry_count}（应该是 0），强制重置为 0")
                        retry_count = 0
                    else:
                        logger.info("[LangGraph节点] 检测到新用户消息，retry_count=0（正确重置）")
        
        # 检查是否是首次用户问题（没有之前的工具调用）
        # 注意：上面的验证已经检查过了，这里再次检查以确保逻辑正确
        has_previous_tool_call = False
        if len(messages) >= 2:
            # 检查是否有之前的工具调用
            for msg in messages[:-1]:  # 检查除最后一条外的所有消息
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    has_previous_tool_call = True
                    break
                if isinstance(msg, ToolMessage):
                    has_previous_tool_call = True
                    break
        
        # 对于 RAG 系统，总是强制先检索文档
        # 1. 首次用户问题：必须检索
        # 2. 重写后的问题：必须检索（继续尝试）
        # 只有在已经检索过且确认没有相关内容时，才允许不检索（这个逻辑在 generate_answer 中处理）
        
        # 检查是否已有 SystemMessage（可能包含总结）
        existing_system_msg = None
        system_msg_index = -1
        for i, msg in enumerate(messages):
            if isinstance(msg, SystemMessage):
                existing_system_msg = msg
                system_msg_index = i
                break
        
        # 构建系统提示
        # 统一提示：无论是首次问题还是重写后的问题，都需要先检索
        # 模型可以从历史消息中了解上下文，无需在 system prompt 中区分场景
        system_content = (
            "你是一个 RAG（检索增强生成）助手。"
            "在回答任何用户问题之前，你必须始终使用 retrieve_documents 工具来搜索信息。"
            "不要在没有检索的情况下直接回答。始终首先调用 retrieve_documents 工具来搜索知识库。"
        )
        
        # 如果已有 SystemMessage，追加新的指令（保留总结内容）
        if existing_system_msg is not None:
            existing_content = str(existing_system_msg.content)
            # 检查是否包含总结
            if "[对话历史总结]" in existing_content:
                # 保留总结，追加新指令
                merged_content = f"{existing_content}\n\n{system_content}"
            else:
                # 没有总结，直接合并
                merged_content = f"{existing_content}\n\n{system_content}"
            # 更新现有的 SystemMessage
            messages[system_msg_index] = SystemMessage(content=merged_content)
            # 确保 SystemMessage 在开头（Anthropic API 要求）
            if system_msg_index != 0:
                # 如果 SystemMessage 不在开头，移动到开头
                messages = [messages[system_msg_index]] + [msg for i, msg in enumerate(messages) if i != system_msg_index]
            messages_with_prompt = messages
        else:
            # 没有 SystemMessage，在开头添加新的
            system_msg = SystemMessage(content=system_content)
            messages_with_prompt = [system_msg] + messages
        
        # 调用模型并统计 token
        input_tokens = token_counter.get_messages_tokens(messages_with_prompt)
        
        # 检查工具绑定
        try:
            bound_model = response_model.bind_tools([retrieve_tool])  # type: ignore[attr-defined]
            logger.debug(f"[工具绑定] 工具绑定成功，工具名称: {getattr(retrieve_tool, 'name', 'unknown')}")
            logger.debug(f"[工具绑定] 工具对象类型: {type(retrieve_tool)}")
            if hasattr(retrieve_tool, 'args_schema'):
                logger.debug(f"[工具绑定] 工具参数模式: {retrieve_tool.args_schema}")
        except Exception as e:
            logger.error(f"[工具绑定] 工具绑定失败: {e}", exc_info=True)
            bound_model = response_model
        
        response = bound_model.invoke(messages_with_prompt)
        
        # 统计 token
        output_tokens = _safe_get_tokens_from_response(response)[1]
        token_counter.count_tokens(
            model_name="response_model",
            node_name="generate_query_or_respond",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        
        # 详细检查响应结构
        logger.info(f"[响应结构] 响应类型: {type(response)}")
        logger.info(f"[响应结构] 响应所有属性: {[attr for attr in dir(response) if not attr.startswith('_')]}")
        
        # 检查 additional_kwargs（某些模型可能在这里存储工具调用）
        if hasattr(response, "additional_kwargs"):
            logger.info(f"[响应结构] additional_kwargs: {response.additional_kwargs}")
            if isinstance(response.additional_kwargs, dict):
                # 检查是否有工具调用相关的键
                tool_related_keys = [k for k in response.additional_kwargs.keys() if 'tool' in k.lower() or 'function' in k.lower()]
                if tool_related_keys:
                    logger.info(f"[响应结构] additional_kwargs 中包含工具相关键: {tool_related_keys}")
                    for key in tool_related_keys:
                        logger.info(f"[响应结构] additional_kwargs['{key}']: {response.additional_kwargs[key]}")
        
        # 检查是否有工具调用（支持多种格式）
        has_tool_calls = False
        tool_calls_list = []
        
        # 标准格式：response.tool_calls
        if hasattr(response, "tool_calls"):
            logger.info(f"[工具调用检查] response.tool_calls 存在: {response.tool_calls}")
            if response.tool_calls:
                has_tool_calls = True
                tool_calls_list = response.tool_calls
                logger.info(f"[工具调用检查] 找到标准格式工具调用: {len(tool_calls_list)} 个")
        
        # 检查 invalid_tool_calls（某些模型可能在这里存储工具调用）
        if not has_tool_calls and hasattr(response, "invalid_tool_calls"):
            logger.info(f"[工具调用检查] 检查 invalid_tool_calls: {response.invalid_tool_calls}")
            if response.invalid_tool_calls:
                # invalid_tool_calls 可能包含工具调用信息，即使格式不正确
                logger.warning(f"[工具调用检查] 发现 invalid_tool_calls: {response.invalid_tool_calls}")
                # 尝试从 invalid_tool_calls 中提取工具调用信息
                for invalid_call in response.invalid_tool_calls:
                    logger.info(f"[工具调用检查] invalid_tool_call 详情: {invalid_call}")
                    # 如果 invalid_tool_calls 有正确的结构，我们可以尝试使用它
                    if isinstance(invalid_call, dict):
                        if invalid_call.get("name") == "retrieve_documents" or "retrieve" in str(invalid_call).lower():
                            logger.warning("[工具调用检查] 在 invalid_tool_calls 中发现 retrieve_documents，尝试使用")
                            # 尝试构造一个有效的工具调用
                            tool_calls_list.append(invalid_call)
                            has_tool_calls = True
        
        # 检查 content_blocks（某些模型可能使用此字段）
        if not has_tool_calls and hasattr(response, "content_blocks"):
            logger.info(f"[工具调用检查] 检查 content_blocks: {response.content_blocks}")
            if isinstance(response.content_blocks, list):
                for i, block in enumerate(response.content_blocks):
                    logger.info(f"[工具调用检查] content_blocks[{i}] 类型: {type(block)}, 内容: {str(block)[:300]}")
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        has_tool_calls = True
                        tool_calls_list.append(block)
                        logger.info(f"[工具调用检查] 在 content_blocks 中找到 tool_use: {block}")
                    elif hasattr(block, "type") and getattr(block, "type", None) == "tool_use":
                        has_tool_calls = True
                        tool_calls_list.append(block)
                        logger.info(f"[工具调用检查] 在 content_blocks 中找到 tool_use 对象: {block}")
        
        # MiniMax-M2 可能使用 content 中的 tool_use 块
        if not has_tool_calls and hasattr(response, "content"):
            content = response.content
            logger.info(f"[工具调用检查] 检查 content，类型: {type(content)}")
            if isinstance(content, list):
                logger.info(f"[工具调用检查] content 是列表，长度: {len(content)}")
                for i, block in enumerate(content):
                    logger.info(f"[工具调用检查] content[{i}] 类型: {type(block)}")
                    if isinstance(block, dict):
                        block_type = block.get("type")
                        all_keys = list(block.keys())
                        logger.info(f"[工具调用检查] content[{i}] 是字典，type 字段: {block_type}, 所有键: {all_keys}")
                        # 输出完整的 block 内容用于调试
                        logger.info(f"[工具调用检查] content[{i}] 完整内容: {block}")
                        if block_type == "tool_use":
                            has_tool_calls = True
                            tool_calls_list.append(block)
                            logger.info(f"[工具调用检查] ✅ 在 content 中找到 tool_use 字典: {block}")
                        # 检查是否有其他可能的工具调用格式
                        elif "retrieve" in str(block).lower() or "tool" in str(block).lower():
                            logger.warning(f"[工具调用检查] ⚠️ content[{i}] 可能包含工具调用信息: {block}")
                    elif hasattr(block, "type"):
                        block_type = getattr(block, "type", None)
                        logger.info(f"[工具调用检查] content[{i}] 有 type 属性: {block_type}")
                        if block_type == "tool_use":
                            has_tool_calls = True
                            tool_calls_list.append(block)
                            logger.info(f"[工具调用检查] ✅ 在 content 中找到 tool_use 对象: {block}")
            elif isinstance(content, str):
                logger.info(f"[工具调用检查] content 是字符串，长度: {len(content)}")
                # 检查字符串中是否包含工具调用的 JSON
                if "tool_use" in content.lower() or "retrieve_documents" in content.lower():
                    logger.warning(f"[工具调用检查] ⚠️ content 字符串中可能包含工具调用关键词")
                    logger.info(f"[工具调用检查] content 前500字符: {content[:500]}")
        
        logger.info(f"[输出] Token 统计 - 输入: {int(input_tokens)}, 输出: {int(output_tokens)}, 总计: {int(input_tokens + output_tokens)}")
        logger.info(f"[输出] 是否有工具调用: {has_tool_calls}")
        logger.info(f"[输出] 返回的消息类型: {type(response).__name__}")
        #logger.info(f"[输出] 响应对象属性: {[attr for attr in dir(response) if not attr.startswith('_')][:10]}")
        
        if has_tool_calls:
            logger.info(f"[输出] 工具调用数量: {len(tool_calls_list)}")
            tool_calls_info = []
            for tc in tool_calls_list:
                if isinstance(tc, dict):
                    tool_name = tc.get('name', tc.get('tool_name', 'unknown'))
                    tool_args = tc.get('args', tc.get('arguments', {}))
                    tool_calls_info.append(f"工具: {tool_name}, 参数: {str(tool_args)[:100]}")
                else:
                    tool_name = getattr(tc, 'name', getattr(tc, 'tool_name', 'unknown'))
                    tool_args = getattr(tc, 'args', getattr(tc, 'arguments', {}))
                    tool_calls_info.append(f"工具: {tool_name}, 参数: {str(tool_args)[:100]}")
            logger.info(f"[输出] 工具调用详情: {', '.join(tool_calls_info)}")
        else:
            if hasattr(response, 'content'):
                content_preview = str(response.content)[:200]
                logger.info(f"[输出] 响应内容预览: {content_preview}...")
                # 输出完整的 content 结构用于调试
                if isinstance(response.content, list):
                    logger.info(f"[输出] content 是列表，包含 {len(response.content)} 个元素")
                    for i, item in enumerate(response.content[:5]):  # 输出前5个
                        logger.info(f"[输出] content[{i}] 完整内容: {item}")
                logger.warning("[输出] ⚠️ 模型未调用工具，直接返回了内容。这可能导致检索步骤被跳过。")
                logger.warning("[输出] ⚠️ 可能原因：1) MiniMax-M2 工具调用格式不同 2) 工具绑定失败 3) 模型选择不调用工具")
                logger.warning("[输出] ⚠️ 建议：检查上面的 INFO 级别日志，查看响应结构的详细信息")
                
                # 如果模型没有调用工具，我们需要强制调用工具
                # 这是一个 fallback 机制，确保 RAG 系统始终先检索
                logger.warning("[输出] ⚠️ 由于模型未调用工具，将强制调用 retrieve_documents 工具")
                # 创建一个工具调用消息，强制调用检索工具
                from langchain_core.messages import AIMessage
                import uuid
                
                # 获取查询文本
                query_text = current_query if current_query else (messages[-1].content if messages and hasattr(messages[-1], 'content') else "")
                if not query_text:
                    # 如果还是没有查询文本，尝试从最后一条 HumanMessage 获取
                    for msg in reversed(messages):
                        if hasattr(msg, 'content') and isinstance(msg, HumanMessage):
                            query_text = str(msg.content)
                            break
                
                # 使用字典格式构造工具调用（更兼容）
                forced_tool_call_dict = {
                    "name": "retrieve_documents",
                    "args": {"query": query_text},
                    "id": str(uuid.uuid4())
                }
                
                # 尝试使用 ToolCall 对象，如果失败则使用字典
                try:
                    from langchain_core.messages.tool import ToolCall
                    forced_tool_call = ToolCall(
                        name="retrieve_documents",
                        args={"query": query_text},
                        id=forced_tool_call_dict["id"]
                    )
                except Exception as e:
                    logger.warning(f"[输出] 无法创建 ToolCall 对象，使用字典格式: {e}")
                    forced_tool_call = forced_tool_call_dict
                
                # 创建一个包含工具调用的 AIMessage
                forced_response = AIMessage(
                    content="",
                    tool_calls=[forced_tool_call]
                )
                
                # 安全地获取工具调用信息用于日志
                if isinstance(forced_tool_call, dict):
                    tool_name = forced_tool_call.get('name', 'retrieve_documents')
                    tool_args = forced_tool_call.get('args', {"query": query_text})
                else:
                    tool_name = getattr(forced_tool_call, 'name', 'retrieve_documents')
                    tool_args = getattr(forced_tool_call, 'args', {"query": query_text})
                logger.info(f"[输出] 强制工具调用: name={tool_name}, args={tool_args}")
                has_tool_calls = True
                tool_calls_list = [forced_tool_call]
                response = forced_response
        logger.info("[LangGraph节点] generate_query_or_respond: 完成")
        logger.info("=" * 80)

        # 使用 current_query 替换检索工具的 query 参数（保留 rewrite 后的优化查询）
        # 注意：需要同时支持标准 tool_calls 和 MiniMax-M2 的 tool_use 格式
        if current_query and has_tool_calls and tool_calls_list:
            try:
                for tc in tool_calls_list:
                    if isinstance(tc, dict):
                        # 支持标准格式和 MiniMax-M2 格式
                        if "args" in tc:
                            tc["args"]["query"] = current_query
                        elif "arguments" in tc:
                            tc["arguments"]["query"] = current_query
                    else:
                        # 兼容 ToolCall 对象
                        if hasattr(tc, "args"):
                            tc.args["query"] = current_query
                        elif hasattr(tc, "arguments"):
                            tc.arguments["query"] = current_query
            except Exception:
                logger.exception("覆盖工具调用 query 失败")

        return {"messages": [response]}
    
    return generate_query_or_respond


def create_grade_documents_node(grader_model: Any, debug: bool = False):
    """
    创建评估文档相关性的节点函数
    
    Args:
        grader_model: 评估模型
        debug: 是否输出调试信息
        
    Returns:
        节点函数
    """
    def grade_documents(
        state: RAGState,
    ) -> Literal["generate_answer", "rewrite_question"]:
        """Determine whether the retrieved documents are relevant to the question."""
        logger.info("=" * 80)
        logger.info("[LangGraph节点] grade_documents: 开始执行")
        current_query = state.get("current_query", "")
        retry_count = state.get("retry_count", 0)
        context = state["messages"][-1].content
        logger.info(f"[输入] 当前查询: {current_query}")
        logger.info(f"[输入] retry_count: {retry_count}")
        logger.info(f"[输入] 上下文长度: {len(str(context))} 字符")
        logger.info(f"[输入] 上下文内容预览: {str(context)[:300]}...")
        
        if debug:
            logger.debug("current_query: %s", current_query)
            logger.debug("retry_count: %s", retry_count)
            logger.debug("context: %s", context)

        prompt = GRADE_PROMPT.format(question=current_query, context=context)
        
        if debug:
            logger.debug("prompt: %s", prompt)
        
        # 调用模型并统计 token
        messages = [{"role": "user", "content": prompt}]
        input_tokens = token_counter.get_messages_tokens([HumanMessage(content=prompt)])
        
        response = (
            grader_model
            .with_structured_output(GradeDocuments).invoke(messages)  # type: ignore[attr-defined]
        )
        
        # 统计 token
        output_tokens = _safe_get_tokens_from_response(response)[1]
        token_counter.count_tokens(
            model_name="grader_model",
            node_name="grade_documents",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        
        logger.info(f"[输出] Token 统计 - 输入: {int(input_tokens)}, 输出: {int(output_tokens)}, 总计: {int(input_tokens + output_tokens)}")
        
        if debug:
            logger.debug("with_structured_output response: %s", response)
        
        # 检查 response 是否为 None
        if response is None:
            logger.warning("[输出] 模型返回 None，使用默认值 'no'")
            # 检查是否超过重试上限
            if retry_count >= 2:  # 已经重试2次，加上这次就是第3次
                logger.info("[输出] 路由决策: generate_answer (超过重试上限)")
                logger.info("[LangGraph节点] grade_documents: 完成")
                logger.info("=" * 80)
                return "generate_answer"
            else:
                logger.info("[输出] 路由决策: rewrite_question")
                logger.info("[LangGraph节点] grade_documents: 完成")
                logger.info("=" * 80)
                return "rewrite_question"
        
        score = response.binary_score
        logger.info(f"[输出] 评分结果: {score}")
        
        if score == "yes":
            # 找到相关文档
            logger.info("[输出] 路由决策: generate_answer (文档相关)")
            logger.info("[LangGraph节点] grade_documents: 完成")
            logger.info("=" * 80)
            return "generate_answer"
        else:
            # 文档不相关，检查是否超过重试上限
            if retry_count >= 2:  # 已经重试2次，加上这次就是第3次
                # 路由到 generate_answer，generate_answer 会检查 retry_count
                logger.info("[输出] 路由决策: generate_answer (文档不相关但超过重试上限)")
                logger.info("[LangGraph节点] grade_documents: 完成")
                logger.info("=" * 80)
                return "generate_answer"
            else:
                logger.info("[输出] 路由决策: rewrite_question (文档不相关)")
                logger.info("[LangGraph节点] grade_documents: 完成")
                logger.info("=" * 80)
                return "rewrite_question"
    
    return grade_documents


def create_rewrite_question_node(response_model: Any):
    """
    创建重写问题的节点函数
    
    Args:
        response_model: 响应模型
        
    Returns:
        节点函数
    """
    def rewrite_question(state: RAGState):
        """Rewrite the original user question."""
        logger.info("=" * 80)
        logger.info("[LangGraph节点] rewrite_question: 开始执行")
        current_query = state.get("current_query", "")
        retry_count = state.get("retry_count", 0)
        logger.info(f"[输入] 原始查询: {current_query}")
        logger.info(f"[输入] retry_count: {retry_count}")
        
        # 递增 retry_count
        new_retry_count = retry_count + 1
        
        prompt = REWRITE_PROMPT.format(question=current_query)
        messages = [{"role": "user", "content": prompt}]
        input_tokens = token_counter.get_messages_tokens([HumanMessage(content=prompt)])
        
        response = response_model.invoke(messages)
        
        # 统计 token
        output_tokens = _safe_get_tokens_from_response(response)[1]
        token_counter.count_tokens(
            model_name="response_model",
            node_name="rewrite_question",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        
        logger.info(f"[输出] Token 统计 - 输入: {int(input_tokens)}, 输出: {int(output_tokens)}, 总计: {int(input_tokens + output_tokens)}")
        
        # 提取重写后的问题（处理可能的列表格式）
        content = response.content
        logger.info(f"[输出] 模型原始响应: {str(content)[:200]}...")
        rewritten_query = ""
        
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get('type') == 'text':
                    text = item.get('text', '')
                    # 清理格式
                    text = text.replace('**Refined question:**', '').strip()
                    text = text.replace('*', '').strip()
                    # 提取第一行或第一个句子作为问题
                    lines = [line.strip() for line in text.split('\n') if line.strip()]
                    if lines:
                        # 取第一行，如果太长则取第一个句子
                        question_text = lines[0]
                        if len(question_text) > 200:
                            # 如果第一行太长，尝试取第一个句子
                            sentences = question_text.split('.')
                            if sentences:
                                question_text = sentences[0].strip() + '.'
                        rewritten_query = question_text
                        break
        
        if not rewritten_query:
            # 处理字符串格式的响应
            text = str(content).strip()
            # 清理常见的前缀
            prefixes_to_remove = [
                "Improved question:",
                "Refined question:",
                "Here is the improved question:",
                "The improved question is:",
                "**Improved question:**",
                "**Refined question:**"
            ]
            for prefix in prefixes_to_remove:
                if text.startswith(prefix):
                    text = text[len(prefix):].strip()
            
            # 提取第一行或第一个句子
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            if lines:
                question_text = lines[0]
                if len(question_text) > 200:
                    sentences = question_text.split('.')
                    if sentences:
                        question_text = sentences[0].strip() + '.'
                rewritten_query = question_text
            else:
                # 如果都失败了，使用原始内容（截断到合理长度）
                rewritten_query = text[:300]
        
        logger.info(f"[输出] 重写后的问题: {rewritten_query}")
        logger.info(f"[输出] 新的 retry_count: {new_retry_count}")
        logger.info("[LangGraph节点] rewrite_question: 完成")
        logger.info("=" * 80)
        
        # 更新 current_query 为重写后的问题，并递增 retry_count
        return {
            "messages": [HumanMessage(content=rewritten_query)],
            "current_query": rewritten_query,
            "retry_count": new_retry_count
        }
    
    return rewrite_question


def create_generate_answer_node(response_model: Any):
    """
    创建生成答案的节点函数
    
    Args:
        response_model: 响应模型
        
    Returns:
        节点函数
    """
    def generate_answer(state: RAGState):
        """Generate an answer."""
        logger.info("=" * 80)
        logger.info("[LangGraph节点] generate_answer: 开始执行")
        current_query = state.get("current_query", "")
        retry_count = state.get("retry_count", 0)
        messages_count = len(state.get("messages", []))
        logger.info(f"[输入] 当前查询: {current_query}")
        logger.info(f"[输入] retry_count: {retry_count}")
        logger.info(f"[输入] messages 数量: {messages_count}")
        
        # 提取上下文信息
        context_parts = []
        for i, msg in enumerate(state.get("messages", [])):
            if hasattr(msg, 'content'):
                content = str(msg.content)
                if len(content) > 100:
                    content = content[:100] + "..."
                context_parts.append(f"消息{i+1}: {content}")
        if context_parts:
            logger.info(f"[输入] 上下文预览: {' | '.join(context_parts[:3])}")
        
        # 如果超过重试上限（retry_count >= 3），生成"未找到相关内容"的答案
        if retry_count >= 3:
            no_content_prompt = (
                f"用户问题: {current_query}\n\n"
                "经过多次尝试，我无法在提供的文档中找到与用户问题相关的内容。"
                "请生成一个友好的回复，告知用户未找到相关内容，并建议用户重新表述问题或确认文档中是否包含相关信息。"
                "回复应该简洁、友好，不超过3句话。"
            )
            messages = [{"role": "user", "content": no_content_prompt}]
            input_tokens = token_counter.get_messages_tokens([HumanMessage(content=no_content_prompt)])
            
            full_content = ""
            response_chunks = []
            
            # 流式调用模型
            for chunk in response_model.stream(messages):
                # 处理不同类型的 chunk 格式
                content = None
                if hasattr(chunk, 'content'):
                    # AIMessageChunk 对象
                    content = chunk.content
                elif hasattr(chunk, 'text'):
                    # 某些版本使用 text 属性
                    content = chunk.text
                elif isinstance(chunk, dict):
                    # 字典格式
                    content = chunk.get('content') or chunk.get('text')
                else:
                    # 尝试转换为字符串
                    try:
                        content = str(chunk)
                    except Exception:
                        continue
                
                # 处理 content 可能是字符串或列表的情况
                if content:
                    if isinstance(content, list):
                        # 如果是列表，提取文本
                        text_parts = []
                        for item in content:
                            if isinstance(item, dict) and 'text' in item:
                                text_parts.append(item['text'])
                            elif isinstance(item, str):
                                text_parts.append(item)
                        content = ''.join(text_parts)
                    
                    if content and isinstance(content, str):
                        full_content += content
                        response_chunks.append(chunk)
            
            # 构建完整的响应对象
            if response_chunks:
                final_response = response_chunks[-1]
                if hasattr(final_response, 'content'):
                    final_response.content = full_content
                elif isinstance(final_response, dict):
                    final_response['content'] = full_content
                else:
                    final_response = AIMessage(content=full_content)
            else:
                final_response = response_model.invoke(messages)
            
            # 统计 token
            output_tokens = (
                token_counter.get_messages_tokens([HumanMessage(content=full_content)])
                if full_content else _safe_get_tokens_from_response(final_response)[1]
            )
            token_counter.count_tokens(
                model_name="response_model",
                node_name="generate_answer",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
            
            logger.info(f"[输出] Token 统计 - 输入: {int(input_tokens)}, 输出: {int(output_tokens)}, 总计: {int(input_tokens + output_tokens)}")
            logger.info(f"[输出] 答案长度: {len(full_content)} 字符")
            logger.info(f"[输出] 答案预览: {full_content[:200]}...")
            logger.info("[LangGraph节点] generate_answer: 完成 (未找到相关内容模式)")
            logger.info("=" * 80)
            
            return {
                "messages": [final_response],
                "retry_count": 0,
                "no_relevant_found": False  # 重置标记
            }
        
        # 正常情况：使用检索到的内容生成答案（流式输出）
        context = state["messages"][-1].content
        logger.info(f"[输入] 上下文长度: {len(str(context))} 字符")
        logger.info(f"[输入] 上下文预览: {str(context)[:300]}...")
        prompt = GENERATE_PROMPT.format(question=current_query, context=context)
        messages = [{"role": "user", "content": prompt}]
        input_tokens = token_counter.get_messages_tokens([HumanMessage(content=prompt)])
        logger.info(f"[输入] Prompt token 数: {int(input_tokens)}")
        
        full_content = ""
        response_chunks = []
        
        # 流式调用模型
        for chunk in response_model.stream(messages):
            # 处理不同类型的 chunk 格式
            content = None
            if hasattr(chunk, 'content'):
                # AIMessageChunk 对象
                content = chunk.content
            elif hasattr(chunk, 'text'):
                # 某些版本使用 text 属性
                content = chunk.text
            elif isinstance(chunk, dict):
                # 字典格式
                content = chunk.get('content') or chunk.get('text')
            else:
                # 尝试转换为字符串
                try:
                    content = str(chunk)
                except Exception:
                    continue
            
            # 处理 content 可能是字符串或列表的情况
            if content:
                if isinstance(content, list):
                    # 如果是列表，提取文本
                    text_parts = []
                    for item in content:
                        if isinstance(item, dict) and 'text' in item:
                            text_parts.append(item['text'])
                        elif isinstance(item, str):
                            text_parts.append(item)
                    content = ''.join(text_parts)
                
                if content and isinstance(content, str):
                    full_content += content
                    response_chunks.append(chunk)
        
        # 构建完整的响应对象（用于 token 统计和返回）
        # 尝试从最后一个 chunk 构建完整响应
        if response_chunks:
            # 使用最后一个 chunk 作为基础，更新 content
            final_response = response_chunks[-1]
            if hasattr(final_response, 'content'):
                final_response.content = full_content
            elif isinstance(final_response, dict):
                final_response['content'] = full_content
            else:
                # 如果无法修改，创建一个新的 AIMessage
                final_response = AIMessage(content=full_content)
        else:
            # 如果没有 chunks，回退到 invoke
            final_response = response_model.invoke(messages)
        
        # 统计 token（使用完整内容估算）
        output_tokens = (
            token_counter.get_messages_tokens([HumanMessage(content=full_content)])
            if full_content else _safe_get_tokens_from_response(final_response)[1]
        )
        token_counter.count_tokens(
            model_name="response_model",
            node_name="generate_answer",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        
        logger.info(f"[输出] Token 统计 - 输入: {int(input_tokens)}, 输出: {int(output_tokens)}, 总计: {int(input_tokens + output_tokens)}")
        logger.info(f"[输出] 答案长度: {len(full_content)} 字符")
        logger.info(f"[输出] 答案预览: {full_content[:200]}...")
        logger.info("[LangGraph节点] generate_answer: 完成")
        logger.info("=" * 80)
        
        # 重置 retry_count，因为已找到相关文档
        return {
            "messages": [final_response],
            "retry_count": 0,
            "no_relevant_found": False
        }
    
    return generate_answer


