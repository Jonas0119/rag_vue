"""
会话列表组件
"""
import streamlit as st
from services import get_session_service
from .chat_interface import load_session_messages


def show_session_list(user_id: int):
    """显示会话列表（侧边栏）"""
    
    session_service = get_session_service()
    
    st.sidebar.markdown("### 💬 我的会话")
    
    # 新建对话按钮
    if st.sidebar.button("➕ 新建对话", use_container_width=True):
        # 清空当前对话
        st.session_state.current_session_id = None
        st.session_state.chat_messages = []
        st.rerun()
    
    # 搜索框
    search_query = st.sidebar.text_input(
        "🔍 搜索会话",
        placeholder="输入关键词...",
        label_visibility="collapsed"
    )
    
    # 获取会话列表（按时间分组）
    sessions_grouped = session_service.get_user_sessions(user_id, limit=50)
    
    # 过滤搜索结果
    if search_query:
        sessions_grouped = _filter_sessions(sessions_grouped, search_query)
    
    # 显示会话分组
    _display_session_groups(sessions_grouped, session_service)


def _filter_sessions(sessions_grouped: dict, search_query: str) -> dict:
    """过滤会话"""
    filtered = {}
    for group_name, sessions in sessions_grouped.items():
        filtered_sessions = [
            s for s in sessions 
            if search_query.lower() in s['title'].lower()
        ]
        if filtered_sessions:
            filtered[group_name] = filtered_sessions
    return filtered


def _display_session_groups(sessions_grouped: dict, session_service):
    """显示会话分组"""
    
    # 定义分组显示顺序和标题
    group_labels = {
        'pinned': '📌 置顶',
        'today': '📅 今天',
        'yesterday': '📅 昨天',
        'this_week': '📅 本周',
        'this_month': '📅 本月',
        'older': '📅 更早'
    }
    
    for group_key in group_labels.keys():
        sessions = sessions_grouped.get(group_key, [])
        if not sessions:
            continue
        
        # 显示分组标题 - 使用更紧凑的样式
        st.sidebar.markdown(f"<p style='margin: 4px 0 2px 0; font-size: 11px; font-weight: 600; color: var(--text-tertiary); opacity: 0.8;'>{group_labels[group_key]}</p>", unsafe_allow_html=True)
        
        # 显示会话列表
        for session in sessions:
            _display_session_item(session, session_service)
        
        # 使用更紧凑的分隔线
        st.sidebar.markdown("<hr style='margin: 6px 0 4px 0; border: none; border-top: 1px solid var(--border); opacity: 0.2;'>", unsafe_allow_html=True)


def _display_session_item(session: dict, session_service):
    """显示单个会话项"""
    
    session_id = session['session_id']
    title = session['title']
    message_count = session['message_count']
    is_pinned = session['is_pinned']
    
    # 判断是否为当前会话
    is_current = st.session_state.get('current_session_id') == session_id
    
    # 使用两列布局：会话标题 + 操作菜单
    col1, col2 = st.sidebar.columns([5, 1])
    
    with col1:
        # 会话按钮（带高亮）
        button_label = f"{'📍' if is_pinned else '💬'} {title}"
        
        if st.button(
            button_label,
            key=f"session_{session_id}",
            use_container_width=True,
            type="primary" if is_current else "secondary",
            help=f"{message_count} 条消息"
        ):
            # 加载会话消息
            load_session_messages(session_id, session_service)
            st.rerun()
    
    with col2:
        # 三点菜单
        with st.popover("⋮", use_container_width=True):
            st.markdown(f"**操作菜单**")
            st.caption(f"{message_count} 条消息")
            st.markdown("---")
            
            # 置顶/取消置顶
            pin_label = "📌 置顶" if not is_pinned else "📍 取消置顶"
            if st.button(pin_label, key=f"pin_{session_id}", use_container_width=True):
                session_service.pin_session(session_id, not is_pinned)
                st.rerun()
            
            # 导出 - 直接下载
            markdown_content = session_service.export_session_markdown(session_id)
            if markdown_content:
                # 使用 on_click 回调来触发 rerun
                if st.download_button(
                    label="📥 导出会话",
                    data=markdown_content,
                    file_name=f"session_{session_id[:8]}.md",
                    mime="text/markdown",
                    key=f"export_{session_id}",
                    use_container_width=True
                ):
                    # download_button 被点击后，触发 rerun 关闭菜单
                    st.rerun()
            
            # 删除
            if st.button("🗑️ 删除会话", key=f"del_{session_id}", use_container_width=True):
                _confirm_delete_session(session_id, title, session_service)


def _confirm_delete_session(session_id: str, title: str, session_service):
    """确认删除会话"""
    
    @st.dialog("⚠️ 确认删除会话")
    def delete_dialog():
        st.warning(f"确定要删除会话「{title}」吗？\n\n**此操作不可恢复！**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("❌ 取消", use_container_width=True):
                st.rerun()
        
        with col2:
            if st.button("✅ 确认删除", use_container_width=True, type="primary"):
                session_service.delete_session(session_id)
                
                # 如果删除的是当前会话，清空
                if st.session_state.get('current_session_id') == session_id:
                    st.session_state.current_session_id = None
                    st.session_state.chat_messages = []
                
                st.success("会话已删除")
                st.rerun()
    
    delete_dialog()

