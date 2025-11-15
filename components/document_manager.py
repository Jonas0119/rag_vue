"""
文档管理组件
"""
import streamlit as st
from services import get_document_service


def show_document_manager(user_id: int):
    """显示文档管理界面"""
    
    st.title("📁 知识库管理")
    
    doc_service = get_document_service()
    
    # 显示统计信息
    _show_statistics(user_id, doc_service)
    
    st.markdown("---")
    
    # 文档上传区域
    _show_upload_section(user_id, doc_service)
    
    st.markdown("---")
    
    # 文档列表
    _show_document_list(user_id, doc_service)


def _show_statistics(user_id: int, doc_service):
    """显示统计信息"""
    stats = doc_service.get_user_stats(user_id)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("📄 文档数量", stats['document_count'])
    
    with col2:
        st.metric("🧩 向量块数", stats['vector_count'])
    
    with col3:
        st.metric("💾 存储空间", stats['storage_used_formatted'])


def _show_upload_section(user_id: int, doc_service):
    """显示上传区域"""
    st.subheader("📤 上传文档")
    
    # 使用 session_state 管理文件上传器的 key
    if 'uploader_key' not in st.session_state:
        st.session_state.uploader_key = 0
    
    uploaded_file = st.file_uploader(
        "选择文件",
        type=['pdf', 'txt', 'md', 'docx'],
        help="支持 PDF、TXT、Markdown、Word 文档，最大 10MB",
        key=f"file_uploader_{st.session_state.uploader_key}"
    )
    
    if uploaded_file:
        st.info(f"📄 已选择: {uploaded_file.name} ({uploaded_file.size // 1024} KB)")
        
        col1, col2 = st.columns([1, 4])
        
        with col1:
            if st.button("🚀 开始上传", use_container_width=True):
                with st.spinner("正在处理文档..."):
                    success, message = doc_service.upload_document(user_id, uploaded_file)
                    
                    if success:
                        st.success(f"✅ {message}")
                        # 上传成功后，更新 key 以清空文件选择器
                        st.session_state.uploader_key += 1
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")
        
        with col2:
            st.caption("上传后将自动解析、分块并生成向量索引")


def _show_document_list(user_id: int, doc_service):
    """显示文档列表"""
    # 使用更紧凑的标题样式
    st.markdown("<h3 style='margin: 4px 0 6px 0; font-size: 1.1rem;'>📋 我的文档</h3>", unsafe_allow_html=True)
    
    # 获取文档列表
    documents = doc_service.get_user_documents(user_id)
    
    if not documents:
        st.info("暂无文档。请上传文档以开始使用智能问答功能。")
        return
    
    # 搜索功能
    search_query = st.text_input("🔍 搜索文档", placeholder="输入文件名关键词...")
    
    if search_query:
        documents = [doc for doc in documents if search_query.lower() in doc['original_filename'].lower()]
    
    # 排序选项
    sort_by = st.selectbox(
        "排序方式",
        ["上传时间（最新）", "上传时间（最早）", "文件大小（大到小）", "文件大小（小到大）"],
        label_visibility="collapsed"
    )
    
    if "最新" in sort_by:
        documents = sorted(documents, key=lambda x: x['upload_at'], reverse=True)
    elif "最早" in sort_by:
        documents = sorted(documents, key=lambda x: x['upload_at'])
    elif "大到小" in sort_by:
        documents = sorted(documents, key=lambda x: x['file_size'], reverse=True)
    elif "小到大" in sort_by:
        documents = sorted(documents, key=lambda x: x['file_size'])
    
    st.caption(f"共 {len(documents)} 个文档")
    
    # 显示文档卡片
    for doc in documents:
        _show_document_card(user_id, doc, doc_service)


def _show_document_card(user_id: int, doc: dict, doc_service):
    """显示单个文档卡片"""
    
    # 使用两列布局：文档信息 + 操作菜单
    col1, col2 = st.columns([10, 1])
    
    with col1:
        # 文件图标和名称 - 使用更紧凑的样式
        icon = _get_file_icon(doc['file_type'])
        st.markdown(f"<p style='margin: 2px 0; font-size: 0.95rem;'><strong>{icon} {doc['original_filename']}</strong></p>", unsafe_allow_html=True)
        
        # 文件信息
        info_parts = []
        info_parts.append(f"📏 {doc['file_size_formatted']}")
        
        if doc.get('page_count'):
            info_parts.append(f"📄 {doc['page_count']} 页")
        
        info_parts.append(f"🧩 {doc['chunk_count']} 块")
        info_parts.append(f"🕐 {doc['upload_at'][:16]}")
        
        st.markdown(f"<p style='margin: 2px 0; font-size: 0.85rem; opacity: 0.7;'>{' • '.join(info_parts)}</p>", unsafe_allow_html=True)
    
    with col2:
        # 三点菜单
        with st.popover("⋮", use_container_width=True):
            st.markdown(f"**操作菜单**")
            st.caption(doc['original_filename'])
            st.markdown("---")
            
            # 预览按钮
            if st.button("👁️ 预览文档", key=f"preview_{doc['doc_id']}", use_container_width=True):
                _show_document_preview(user_id, doc['doc_id'], doc['original_filename'], doc_service)
            
            # 删除按钮
            if st.button("🗑️ 删除文档", key=f"delete_{doc['doc_id']}", use_container_width=True):
                _confirm_delete_document(user_id, doc['doc_id'], doc['original_filename'], doc_service)
    
    # 使用更紧凑的分隔线
    st.markdown("<hr style='margin: 5px 0; border: none; border-top: 1px solid var(--border); opacity: 0.3;'>", unsafe_allow_html=True)


def _get_file_icon(file_type: str) -> str:
    """获取文件类型图标"""
    icons = {
        '.pdf': '📕',
        '.txt': '📄',
        '.md': '📝',
        '.docx': '📘'
    }
    return icons.get(file_type, '📄')


def _show_document_preview(user_id: int, doc_id: str, filename: str, doc_service):
    """显示文档预览对话框"""
    
    @st.dialog(f"📄 {filename}", width="large")
    def preview_dialog():
        # 获取文档信息
        from database import DocumentDAO
        doc_dao = DocumentDAO()
        doc = doc_dao.get_document(doc_id)
        
        preview_content = doc_service.get_document_preview(user_id, doc_id, max_length=2000)
        
        if preview_content:
            # 格式化文件大小
            def format_file_size(size_bytes):
                if size_bytes < 1024:
                    return f"{size_bytes} B"
                elif size_bytes < 1024 * 1024:
                    return f"{size_bytes / 1024:.1f} KB"
                else:
                    return f"{size_bytes / (1024 * 1024):.1f} MB"
            
            # 文档信息栏
            col1, col2, col3 = st.columns(3)
            with col1:
                file_size_str = format_file_size(doc.file_size) if doc else "未知"
                st.metric("📏 文件大小", file_size_str)
            with col2:
                st.metric("📝 字数", f"{len(preview_content):,}")
            with col3:
                file_type = doc.file_type if doc else ""
                type_name = {"pdf": "PDF", ".pdf": "PDF", ".docx": "Word", ".txt": "文本", ".md": "Markdown"}.get(file_type, file_type)
                st.metric("📑 类型", type_name)
            
            st.markdown("---")
            
            # 文档内容显示区域 - 使用美化的样式
            st.markdown("""
                <div style="
                    background: linear-gradient(to bottom, var(--bg-card), var(--bg-secondary));
                    border: 1px solid var(--border);
                    border-radius: 12px;
                    padding: 24px;
                    margin: 16px 0;
                    box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.1);
                    max-height: 500px;
                    overflow-y: auto;
                ">
                    <pre style="
                        font-family: 'SF Mono', 'Consolas', 'Monaco', monospace;
                        font-size: 14px;
                        line-height: 1.8;
                        color: var(--text-primary);
                        white-space: pre-wrap;
                        word-wrap: break-word;
                        margin: 0;
                    ">{}</pre>
                </div>
            """.format(preview_content.replace("<", "&lt;").replace(">", "&gt;")), unsafe_allow_html=True)
            
            # 操作按钮
            col1, col2 = st.columns(2)
            with col1:
                if st.button("📋 复制内容", use_container_width=True, type="secondary"):
                    # Streamlit 不支持直接复制到剪贴板，显示提示
                    st.toast("💡 请手动选择文本进行复制", icon="ℹ️")
            with col2:
                if st.button("✅ 关闭", use_container_width=True, type="primary"):
                    st.rerun()
        else:
            st.error("❌ 无法加载文档预览")
            if st.button("关闭", use_container_width=True):
                st.rerun()
    
    preview_dialog()


def _confirm_delete_document(user_id: int, doc_id: str, filename: str, doc_service):
    """确认删除文档"""
    
    @st.dialog("⚠️ 确认删除", width="medium")
    def delete_dialog():
        # 使用美化的警告框
        st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, rgba(239, 83, 80, 0.1), rgba(229, 57, 53, 0.05));
                border: 2px solid #EF5350;
                border-radius: 12px;
                padding: 20px;
                margin: 16px 0;
            ">
                <div style="
                    font-size: 16px;
                    font-weight: 600;
                    color: var(--text-primary);
                    margin-bottom: 12px;
                ">
                    确定要删除文档「{filename}」吗？
                </div>
                <div style="
                    font-size: 14px;
                    color: var(--text-secondary);
                    line-height: 1.8;
                ">
                    此操作将同时删除：<br>
                    • 文档文件<br>
                    • 所有文本块<br>
                    • 向量索引<br><br>
                    <strong style="color: #EF5350;">⚠️ 此操作不可恢复！</strong>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("↩️ 取消", use_container_width=True, type="secondary"):
                st.rerun()
        
        with col2:
            if st.button("🗑️ 确认删除", use_container_width=True, type="primary"):
                with st.spinner("正在删除..."):
                    success, message = doc_service.delete_document(user_id, doc_id)
                    
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
    
    delete_dialog()

