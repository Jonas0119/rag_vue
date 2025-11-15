"""
对话界面组件
"""
import streamlit as st
from typing import Optional
import uuid

from services import get_rag_service, get_session_service


def show_chat_interface(user_id: int):
    """显示对话界面"""
    
    st.title("💬 智能问答")
    
    rag_service = get_rag_service()
    session_service = get_session_service()
    
    # 初始化当前会话
    if 'current_session_id' not in st.session_state:
        st.session_state.current_session_id = None
    
    # 初始化消息列表
    if 'chat_messages' not in st.session_state:
        st.session_state.chat_messages = []
    
    # 显示消息历史
    _display_messages()
    
    # 输入框
    _show_input_box(user_id, rag_service, session_service)


def _display_messages():
    """显示消息历史"""
    
    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            
            # 显示检索结果（仅 assistant）
            if message["role"] == "assistant" and message.get("retrieved_docs"):
                _show_retrieved_docs(message["retrieved_docs"])
            
            # 显示思考过程（仅 assistant）
            if message["role"] == "assistant" and message.get("thinking_process"):
                _show_thinking_process(message["thinking_process"])


def _show_input_box(user_id: int, rag_service, session_service):
    """显示输入框"""
    
    # 使用 chat_input
    if prompt := st.chat_input("输入您的问题..."):
        # 添加用户消息
        st.session_state.chat_messages.append({
            "role": "user",
            "content": prompt
        })
        
        # 显示用户消息
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # 生成回复
        with st.chat_message("assistant"):
            with st.spinner("🤔 思考中..."):
                # 执行 RAG 查询
                result = rag_service.query(user_id, prompt)
                
                # 显示答案
                st.markdown(result['answer'])
                
                # 显示检索结果
                if result['retrieved_docs']:
                    _show_retrieved_docs(result['retrieved_docs'])
                
                # 显示思考过程
                if result['thinking_process']:
                    _show_thinking_process(result['thinking_process'])
                
                # 添加到消息列表
                st.session_state.chat_messages.append({
                    "role": "assistant",
                    "content": result['answer'],
                    "retrieved_docs": result['retrieved_docs'],
                    "thinking_process": result['thinking_process']
                })
                
                # 保存到数据库
                _save_to_database(user_id, prompt, result, session_service)
        
        st.rerun()


def _save_to_database(user_id: int, question: str, result: dict, session_service):
    """保存对话到数据库"""
    
    # 创建或使用现有会话
    if not st.session_state.current_session_id:
        # 创建新会话
        session_id = session_service.create_session(user_id, question)
        st.session_state.current_session_id = session_id
    else:
        session_id = st.session_state.current_session_id
    
    # 保存用户消息
    session_service.save_message(
        session_id=session_id,
        role='user',
        content=question
    )
    
    # 保存 AI 回复
    session_service.save_message(
        session_id=session_id,
        role='assistant',
        content=result['answer'],
        retrieved_docs=result.get('retrieved_docs'),
        thinking_process=result.get('thinking_process'),
        tokens_used=result.get('tokens_used', 0)
    )


def _show_retrieved_docs(retrieved_docs):
    """显示检索结果"""
    
    with st.expander("📄 检索到的文档片段", expanded=False):
        for i, doc in enumerate(retrieved_docs, 1):
            similarity = doc.get('similarity', 0)
            content = doc.get('content', '')
            
            # 显示相似度进度条
            st.markdown(f"**[片段 {i}]** 相似度: {similarity:.0%}")
            st.progress(similarity)
            
            # 显示内容（可折叠）
            with st.expander(f"查看内容 ({len(content)} 字符)", expanded=False):
                st.text(content)
            
            if i < len(retrieved_docs):
                st.markdown("---")


def _show_thinking_process(thinking_process):
    """显示思考过程"""
    
    with st.expander("💭 AI 思考过程", expanded=False):
        for step in thinking_process:
            step_num = step.get('step', 0)
            action = step.get('action', '')
            description = step.get('description', '')
            details = step.get('details', '')
            
            st.markdown(f"**步骤 {step_num}: {action}**")
            st.caption(description)
            
            if details:
                st.code(details, language=None)
            
            if step_num < len(thinking_process):
                st.markdown("↓")


def show_new_chat_button():
    """显示新建对话按钮"""
    
    if st.button("➕ 新建对话", use_container_width=True):
        # 清空当前对话
        st.session_state.current_session_id = None
        st.session_state.chat_messages = []
        st.rerun()


def load_session_messages(session_id: str, session_service):
    """加载历史会话"""
    
    messages = session_service.get_session_messages(session_id)
    
    # 转换为chat格式
    chat_messages = []
    for msg in messages:
        chat_messages.append({
            "role": msg['role'],
            "content": msg['content'],
            "retrieved_docs": msg.get('retrieved_docs'),
            "thinking_process": msg.get('thinking_process')
        })
    
    st.session_state.chat_messages = chat_messages
    st.session_state.current_session_id = session_id

