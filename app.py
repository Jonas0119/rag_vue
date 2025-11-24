"""
RAG 智能问答系统 - 主应用
"""
# ==================== IPv4 强制（必须在所有导入之前）====================
# 解决 Streamlit Cloud IPv6 连接问题
# 必须在导入任何可能使用 socket 的模块之前执行
import socket
_original_getaddrinfo = socket.getaddrinfo

def _ipv4_getaddrinfo(*args, **kwargs):
    """强制使用 IPv4 的 getaddrinfo（解决 Streamlit Cloud IPv6 问题）"""
    try:
        responses = _original_getaddrinfo(*args, **kwargs)
        # 过滤掉 IPv6 地址，只返回 IPv4
        ipv4_responses = [r for r in responses if r[0] == socket.AF_INET]
        # 如果没有 IPv4 地址但有其他地址，返回原始响应（让系统处理）
        return ipv4_responses if ipv4_responses else responses
    except Exception:
        # 如果出错，回退到原始函数
        return _original_getaddrinfo(*args, **kwargs)

# 立即替换，确保所有后续的 socket 操作都使用 IPv4
socket.getaddrinfo = _ipv4_getaddrinfo
# ==================== IPv4 强制结束 ====================

import streamlit as st
import os
import logging
import sys

# 设置环境变量
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# 配置日志格式，包含文件名和行号
# 格式：时间戳 | 级别 | 文件名:行号 | 函数名 | 消息
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)-8s | %(filename)s:%(lineno)d | %(funcName)s() | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    stream=sys.stdout,
    force=True  # 强制重新配置，避免重复配置
)

logger = logging.getLogger(__name__)

from auth import AuthManager
from components import (
    show_login_page,
    show_logout_button,
    show_chat_interface,
    show_document_manager,
    show_session_list
)


# ==================== 主题相关 ====================
THEME_CSS = {
    "dark": """
    :root {
        /* 背景色系 - 统一深灰 */
        --bg-primary: #121212;
        --bg-secondary: #1E1E1E;
        --bg-card: #2D2D2D;
        --bg-hover: #383838;
        --bg-input: #252525;
        
        /* 文字色系 - 高对比度 */
        --text-primary: #FFFFFF;
        --text-secondary: #B3B3B3;
        --text-tertiary: #808080;
        --text-disabled: #666666;
        
        /* 强调色 - 更浅更明亮的蓝色 */
        --accent: #64B5F6;
        --accent-hover: #42A5F5;
        --accent-active: #2196F3;
        --success: #4CAF50;
        --warning: #FFA726;
        --error: #EF5350;
        --info: #42A5F5;
        
        /* 边框 */
        --border: #404040;
        --border-light: #505050;
        --border-focus: #64B5F6;
    }
    
    /* ===== 全局样式 ===== */
    body, html {
        background-color: var(--bg-primary) !important;
        color: var(--text-primary) !important;
    }
    
    * {
        color: var(--text-secondary) !important;
    }
    
    /* ===== 主容器 ===== */
    [data-testid="stAppViewContainer"] {
        background-color: var(--bg-primary) !important;
    }
    
    .main .block-container {
        background-color: var(--bg-primary) !important;
        padding-bottom: 0 !important;
    }
    
    /* 底部区域 - 移除白色背景 */
    [data-testid="stBottom"],
    .stBottom,
    [data-testid="stBottomBlockContainer"],
    section[data-testid="stBottom"] {
        background-color: var(--bg-primary) !important;
    }
    
    /* 统一所有容器的背景为主背景色 */
    .element-container,
    .stChatFloatingInputContainer {
        background-color: var(--bg-primary) !important;
    }
    
    /* ===== 标题文字 ===== */
    h1, h2, h3, h4, h5, h6 {
        color: var(--text-primary) !important;
    }
    
    /* 减少标题的上下间距 - 紧凑显示 */
    h3 {
        margin-top: 8px !important;
        margin-bottom: 6px !important;
        font-size: 1.1rem !important;
    }
    
    /* 减少容器的上下间距 - 紧凑显示 */
    .element-container {
        margin: 4px 0 !important;
    }
    
    /* 主内容区容器 - 更紧凑 */
    .main .block-container {
        padding-top: 2rem !important;
        padding-bottom: 1rem !important;
    }
    
    /* 主内容区内的元素容器 - 减少间距 */
    .main .element-container {
        margin: 2px 0 !important;
        padding: 2px 0 !important;
    }
    
    /* 输入框、选择框等的容器 */
    .stTextInput, .stSelectbox {
        margin-bottom: 6px !important;
    }
    
    /* caption 文字的间距 */
    .main p[data-testid="stCaptionContainer"] {
        margin: 2px 0 !important;
        padding: 2px 0 !important;
    }
    
    /* column 布局的间距 */
    .main div[data-testid="column"] {
        padding: 2px 4px !important;
    }
    
    /* ===== 标题栏 ===== */
    [data-testid="stHeader"] {
        background-color: var(--bg-secondary) !important;
        border-bottom: 1px solid var(--border);
    }
    
    /* 隐藏整个顶部工作区 */
    [data-testid="stToolbar"],
    #MainMenu,
    header[data-testid="stHeader"],
    header[data-testid="stHeader"] *,
    header[data-testid="stHeader"] > div,
    button[kind="header"],
    [data-testid="stDecoration"] {
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
        padding: 0 !important;
        margin: 0 !important;
    }
    
    /* ===== 侧边栏 ===== */
    [data-testid="stSidebar"] {
        background-color: var(--bg-secondary) !important;
        border-right: 1px solid var(--border) !important;
        padding-top: 4px !important;
    }
    
    /* 侧边栏内的所有容器 - 统一缩小间距 */
    [data-testid="stSidebar"] .element-container,
    [data-testid="stSidebar"] .stMarkdown,
    [data-testid="stSidebar"] div[data-testid="column"] {
        background-color: transparent !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    
    /* 侧边栏的所有 block 容器 */
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] > div {
        gap: 2px !important;
    }
    
    /* 侧边栏输入框 */
    [data-testid="stSidebar"] input {
        background-color: var(--bg-card) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border) !important;
        border-radius: 8px;
    }
    
    /* 侧边栏标题 h3 */
    [data-testid="stSidebar"] h3 {
        margin-top: 4px !important;
        margin-bottom: 2px !important;
        font-size: 1rem !important;
    }
    
    /* 侧边栏分组标题（如"今天"、"昨天"）*/
    [data-testid="stSidebar"] strong,
    [data-testid="stSidebar"] .stMarkdown strong {
        color: var(--text-tertiary) !important;
        font-size: 11px !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        display: block;
        margin-top: 3px !important;
        margin-bottom: 2px !important;
    }
    
    /* 侧边栏按钮 - 统一深色背景（使用最高优先级选择器）*/
    [data-testid="stSidebar"] .stButton>button,
    [data-testid="stSidebar"] button,
    [data-testid="stSidebar"] .stButton button,
    [data-testid="stSidebar"] button[kind="secondary"],
    section[data-testid="stSidebar"] button {
        background-color: var(--bg-card) !important;
        color: var(--text-secondary) !important;
        border: 1px solid var(--border) !important;
        border-radius: 5px !important;
        transition: all 0.2s ease !important;
        font-weight: 400 !important;
        padding: 5px 10px !important;
        margin: 0 !important;
        font-size: 13px !important;
        line-height: 1.4 !important;
    }
    
    /* 侧边栏分隔线 */
    [data-testid="stSidebar"] hr {
        margin: 3px 0 !important;
        border: none !important;
        border-top: 1px solid var(--border) !important;
        opacity: 0.3 !important;
    }
    
    /* 侧边栏按钮悬停 */
    [data-testid="stSidebar"] .stButton>button:hover,
    [data-testid="stSidebar"] button:hover,
    [data-testid="stSidebar"] .stButton button:hover,
    [data-testid="stSidebar"] button[kind="secondary"]:hover,
    section[data-testid="stSidebar"] button:hover {
        background-color: var(--bg-hover) !important;
        border-color: var(--accent) !important;
        color: var(--text-primary) !important;
    }
    
    /* 侧边栏选中按钮（深蓝色高亮）*/
    [data-testid="stSidebar"] .stButton>button[kind="primary"],
    [data-testid="stSidebar"] button[kind="primary"],
    [data-testid="stSidebar"] .stButton button[kind="primary"],
    section[data-testid="stSidebar"] button[kind="primary"] {
        background-color: #1976D2 !important;
        color: #FFFFFF !important;
        border: none !important;
        font-weight: 600 !important;
    }
    
    /* 侧边栏选中按钮悬停 */
    [data-testid="stSidebar"] .stButton>button[kind="primary"]:hover,
    [data-testid="stSidebar"] button[kind="primary"]:hover,
    [data-testid="stSidebar"] .stButton button[kind="primary"]:hover,
    section[data-testid="stSidebar"] button[kind="primary"]:hover {
        background-color: #1565C0 !important;
        color: #FFFFFF !important;
    }
    
    /* ===== 主按钮 ===== */
    .stButton>button {
        background-color: #1976D2 !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 10px;
        font-weight: 600 !important;
        transition: all 0.2s ease;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4);
    }
    
    .stButton>button:hover {
        background-color: #1565C0 !important;
        color: #FFFFFF !important;
        transform: translateY(-1px);
        box-shadow: 0 4px 16px rgba(25, 118, 210, 0.3);
    }
    
    /* ===== 表单提交按钮（登录注册）===== */
    button[kind="formSubmit"],
    .stForm button[type="submit"],
    [data-testid="stFormSubmitButton"] > button {
        background-color: #1976D2 !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4) !important;
    }
    
    button[kind="formSubmit"]:hover,
    .stForm button[type="submit"]:hover,
    [data-testid="stFormSubmitButton"] > button:hover {
        background-color: #1565C0 !important;
        color: #FFFFFF !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 16px rgba(25, 118, 210, 0.3) !important;
    }
    
    /* ===== 输入框 ===== */
    .stTextInput>div>div>input,
    .stTextArea>div>div>textarea,
    .stSelectbox>div>div>div,
    input[type="text"],
    input[type="password"],
    input[type="email"],
    textarea {
        background-color: var(--bg-card) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border) !important;
        border-radius: 8px;
    }
    
    /* 禁用状态的输入框 - 确保文字可见 */
    input:disabled,
    textarea:disabled,
    .stTextInput>div>div>input:disabled,
    .stTextArea>div>div>textarea:disabled,
    input[type="text"]:disabled,
    input[type="password"]:disabled,
    input[type="email"]:disabled,
    .stTextInput input[disabled],
    .stTextInput input:disabled {
        background-color: var(--bg-card) !important;
        color: var(--text-primary) !important;
        opacity: 1 !important;
        -webkit-text-fill-color: var(--text-primary) !important;
    }
    
    /* Streamlit 输入框内部文字颜色 */
    .stTextInput input,
    .stTextInput input:not(:disabled),
    .stTextInput input:disabled {
        color: var(--text-primary) !important;
        -webkit-text-fill-color: var(--text-primary) !important;
    }
    
    /* 强制移除所有输入框的所有状态边框 */
    input,
    textarea,
    input:hover,
    textarea:hover,
    input:focus,
    textarea:focus,
    input:active,
    textarea:active,
    input:focus-visible,
    textarea:focus-visible,
    input:invalid,
    textarea:invalid,
    input:valid,
    textarea:valid,
    input:disabled,
    textarea:disabled {
        border-color: var(--border) !important;
        outline: none !important;
        outline-width: 0 !important;
        outline-style: none !important;
        outline-offset: 0 !important;
        box-shadow: none !important;
    }
    
    input::placeholder,
    textarea::placeholder {
        color: var(--text-disabled) !important;
    }
    
    .stTextInput label,
    .stTextArea label,
    .stSelectbox label {
        color: var(--text-secondary) !important;
    }
    
    /* 处理浏览器自动填充的背景与文字颜色 */
    input:-webkit-autofill,
    input:-webkit-autofill:focus,
    input:-webkit-autofill:hover,
    textarea:-webkit-autofill,
    textarea:-webkit-autofill:focus,
    textarea:-webkit-autofill:hover {
        -webkit-box-shadow: 0 0 0 1000px var(--bg-card) inset !important;
        -webkit-text-fill-color: var(--text-primary) !important;
        caret-color: var(--text-primary) !important;
        transition: background-color 5000s ease-in-out 0s;
    }

    /* 处理浏览器自动填充的背景与文字颜色 */
    input:-webkit-autofill,
    input:-webkit-autofill:focus,
    input:-webkit-autofill:hover,
    textarea:-webkit-autofill,
    textarea:-webkit-autofill:focus,
    textarea:-webkit-autofill:hover {
        -webkit-box-shadow: 0 0 0 1000px var(--bg-card) inset !important;
        -webkit-text-fill-color: var(--text-primary) !important;
        caret-color: var(--text-primary) !important;
        transition: background-color 5000s ease-in-out 0s;
    }
    
    /* ===== 聊天输入框 - 简洁统一设计 ===== */
    /* 容器背景统一 */
    .stChatInput,
    [data-testid="stChatInput"],
    .stChatFloatingInputContainer,
    [data-testid="InputInstructions"] {
        background-color: var(--bg-primary) !important;
        background: var(--bg-primary) !important;
    }
    
    /* 确保输入框容器无padding */
    .stChatInput>div,
    [data-testid="stChatInput"]>div {
        background-color: var(--bg-primary) !important;
        padding: 0 !important;
    }
    
    .stChatInput>div>div,
    [data-testid="stChatInput"]>div>div {
        background-color: var(--bg-primary) !important;
        padding: 0 !important;
    }
    
    /* 输入框本体 - 简洁统一 */
    .stChatInput>div>div>textarea,
    [data-testid="stChatInput"] textarea,
    .stChatInput textarea {
        /* 背景：统一纯色，与主背景协调 */
        background-color: var(--bg-card) !important;
        background-image: none !important;
        
        /* 文字 */
        color: var(--text-primary) !important;
        font-size: 15px !important;
        line-height: 1.6 !important;
        
        /* 光标颜色 - 确保可见 */
        caret-color: var(--text-primary) !important;
        
        /* 边框：柔和的边框 */
        border: 1px solid var(--border) !important;
        border-radius: 12px !important;
        
        /* 内边距 */
        padding: 12px 16px !important;
        
        /* 无阴影，保持简洁 */
        box-shadow: none !important;
        
        /* 平滑过渡 */
        transition: border-color 0.2s ease, background-color 0.2s ease !important;
    }
    
    /* Placeholder */
    .stChatInput>div>div>textarea::placeholder,
    [data-testid="stChatInput"] textarea::placeholder,
    .stChatInput textarea::placeholder {
        color: var(--text-disabled) !important;
        opacity: 1 !important;
        font-weight: 400 !important;
    }
    
    /* Hover状态 - 轻微变化 */
    .stChatInput>div>div>textarea:hover,
    [data-testid="stChatInput"] textarea:hover,
    .stChatInput textarea:hover {
        border-color: var(--border-light) !important;
        background-color: var(--bg-card) !important;
        outline: none !important;
    }
    
    /* Focus状态 - 柔和反馈 */
    .stChatInput>div>div>textarea:focus,
    [data-testid="stChatInput"] textarea:focus,
    .stChatInput textarea:focus,
    .stChatInput>div>div>textarea:focus-visible,
    [data-testid="stChatInput"] textarea:focus-visible,
    .stChatInput textarea:focus-visible,
    .stChatInput>div>div>textarea:active,
    [data-testid="stChatInput"] textarea:active,
    .stChatInput textarea:active {
        border-color: var(--border-light) !important;
        background-color: var(--bg-card) !important;
        outline: none !important;
        box-shadow: none !important;
        /* 确保焦点时光标可见 */
        caret-color: var(--text-primary) !important;
    }
    
    /* 其他状态 */
    .stChatInput>div>div>textarea:invalid,
    [data-testid="stChatInput"] textarea:invalid,
    .stChatInput textarea:invalid,
    .stChatInput>div>div>textarea:valid,
    [data-testid="stChatInput"] textarea:valid,
    .stChatInput textarea:valid {
        outline: none !important;
    }
    
    /* 发送按钮区域 - 统一背景 */
    .stChatInput button,
    [data-testid="stChatInput"] button {
        background-color: transparent !important;
        border: none !important;
        color: var(--text-secondary) !important;
    }
    
    .stChatInput button:hover,
    [data-testid="stChatInput"] button:hover {
        background-color: transparent !important;
        color: var(--text-primary) !important;
    }
    
    /* ===== 聊天消息 ===== */
    [data-testid="stChatMessage"] {
        background-color: transparent !important;
        background: transparent !important;
        border: none !important;
        border-radius: 0 !important;
        box-shadow: none !important;
        padding: 8px 0 !important;
    }
    
    [data-testid="stChatMessage"] * {
        color: var(--text-secondary) !important;
    }
    
    /* ===== Radio 按钮 ===== */
    .stRadio label,
    .stRadio > div {
        color: var(--text-secondary) !important;
    }
    
    /* ===== 指标卡片 ===== */
    div[data-testid="stMetricValue"] {
        color: var(--text-primary) !important;
        font-weight: 600;
    }
    
    div[data-testid="stMetricLabel"] {
        color: var(--text-tertiary) !important;
    }
    
    /* Metric 容器 - 统一样式，无边框无背景 */
    div[data-testid="stMetricContainer"],
    [data-testid="stMetric"] {
        background-color: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 8px 0 !important;
        margin: 0 !important;
    }
    
    /* ===== 辅助文字 ===== */
    .stCaption,
    small {
        color: var(--text-tertiary) !important;
    }
    
    /* ===== 提示框 ===== */
    .stSuccess {
        background-color: var(--bg-card) !important;
        color: var(--success) !important;
        border-left: 4px solid var(--success);
    }
    
    .stInfo {
        background-color: var(--bg-card) !important;
        color: var(--info) !important;
        border-left: 4px solid var(--info);
    }
    
    .stWarning {
        background-color: var(--bg-card) !important;
        color: var(--warning) !important;
        border-left: 4px solid var(--warning);
    }
    
    .stError {
        background-color: var(--bg-card) !important;
        color: var(--error) !important;
        border-left: 4px solid var(--error);
    }
    
    /* ===== Expander 折叠面板 ===== */
    .streamlit-expanderHeader {
        background-color: var(--bg-card) !important;
        color: var(--text-secondary) !important;
        border: 1px solid var(--border);
        border-radius: 8px;
    }
    
    .streamlit-expanderContent {
        background-color: var(--bg-card) !important;
        border: 1px solid var(--border);
        border-top: none;
    }
    
    /* ===== 分隔线 ===== */
    hr {
        border-color: var(--border) !important;
    }
    
    /* ===== 容器 ===== */
    .stContainer,
    [data-testid="stVerticalBlock"],
    [data-testid="stHorizontalBlock"],
    div[data-testid="column"] {
        background-color: transparent !important;
    }
    
    /* ===== Popover 弹窗 ===== */
    [data-testid="stPopover"],
    [data-baseweb="popover"] {
        background-color: var(--bg-card) !important;
        border: 1px solid var(--border) !important;
        border-radius: 8px;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
    }
    
    /* Popover 内的所有元素背景 */
    [data-testid="stPopover"] *,
    [data-baseweb="popover"] * {
        background-color: transparent !important;
    }
    
    /* Popover 内的文字 */
    [data-testid="stPopover"] p,
    [data-testid="stPopover"] span,
    [data-testid="stPopover"] div {
        color: var(--text-secondary) !important;
    }
    
    /* Popover 内的按钮 - 统一深色风格 */
    [data-testid="stPopover"] button,
    [data-baseweb="popover"] button {
        background-color: var(--bg-card) !important;
        color: var(--text-secondary) !important;
        border: 1px solid var(--border) !important;
        border-radius: 6px !important;
        transition: all 0.2s ease !important;
        font-weight: 400 !important;
        padding: 8px 16px !important;
    }
    
    /* Popover 内按钮悬停 */
    [data-testid="stPopover"] button:hover,
    [data-baseweb="popover"] button:hover {
        background-color: var(--bg-hover) !important;
        color: var(--text-primary) !important;
        border-color: var(--accent) !important;
    }
    
    /* Popover 标题 */
    [data-testid="stPopover"] strong {
        color: var(--text-primary) !important;
    }
    
    /* ===== 下拉菜单 ===== */
    [data-baseweb="select"],
    [role="listbox"],
    [data-baseweb="menu"] {
        background-color: var(--bg-card) !important;
    }
    
    [data-baseweb="menu"] li {
        background-color: var(--bg-card) !important;
        color: var(--text-secondary) !important;
    }
    
    [data-baseweb="menu"] li:hover {
        background-color: var(--bg-hover) !important;
    }
    
    /* ===== 文件上传器 ===== */
    [data-testid="stFileUploader"] section {
        background-color: var(--bg-card) !important;
        border: 2px dashed var(--border) !important;
        border-radius: 12px;
    }
    
    [data-testid="stFileUploader"] section:hover {
        border-color: var(--accent) !important;
    }
    
    /* ===== Tab 标签页 ===== */
    .stTabs [data-baseweb="tab-list"] {
        background-color: transparent !important;
        border-bottom: 1px solid var(--border);
    }
    
    .stTabs [data-baseweb="tab"] {
        color: var(--text-tertiary) !important;
    }
    
    .stTabs [aria-selected="true"] {
        color: var(--accent) !important;
        border-bottom: 2px solid var(--accent) !important;
    }
    
    /* ===== 进度条 ===== */
    .stProgress > div > div {
        background-color: var(--accent) !important;
    }
    """,
    "light": """
    :root {
        /* 背景色系 - 统一浅灰白 */
        --bg-primary: #F5F5F5;
        --bg-secondary: #FAFAFA;
        --bg-card: #FFFFFF;
        --bg-hover: #EEEEEE;
        --bg-input: #FAFAFA;
        
        /* 文字色系 - 深色清晰 */
        --text-primary: #212121;
        --text-secondary: #616161;
        --text-tertiary: #9E9E9E;
        --text-disabled: #AAAAAA;
        
        /* 强调色 - 更浅更明亮的蓝色 */
        --accent: #42A5F5;
        --accent-hover: #2196F3;
        --accent-active: #1976D2;
        --success: #66BB6A;
        --warning: #FFA726;
        --error: #EF5350;
        --info: #29B6F6;
        
        /* 边框 */
        --border: #E0E0E0;
        --border-light: #D0D0D0;
        --border-focus: #42A5F5;
    }
    
    /* ===== 全局样式 ===== */
    body, html {
        background-color: var(--bg-primary) !important;
        color: var(--text-primary) !important;
    }
    
    * {
        color: var(--text-secondary) !important;
    }
    
    /* ===== 主容器 ===== */
    [data-testid="stAppViewContainer"] {
        background-color: var(--bg-primary) !important;
    }
    
    .main .block-container {
        background-color: var(--bg-primary) !important;
        padding-bottom: 0 !important;
    }
    
    /* 底部区域 - 移除白色背景 */
    [data-testid="stBottom"],
    .stBottom,
    [data-testid="stBottomBlockContainer"],
    section[data-testid="stBottom"] {
        background-color: var(--bg-primary) !important;
    }
    
    /* 统一所有容器的背景为主背景色 */
    .element-container,
    .stChatFloatingInputContainer {
        background-color: var(--bg-primary) !important;
    }
    
    /* ===== 标题文字 ===== */
    h1, h2, h3, h4, h5, h6 {
        color: var(--text-primary) !important;
    }
    
    /* 减少标题的上下间距 - 紧凑显示 */
    h3 {
        margin-top: 8px !important;
        margin-bottom: 6px !important;
        font-size: 1.1rem !important;
    }
    
    /* 减少容器的上下间距 - 紧凑显示 */
    .element-container {
        margin: 4px 0 !important;
    }
    
    /* 主内容区容器 - 更紧凑 */
    .main .block-container {
        padding-top: 2rem !important;
        padding-bottom: 1rem !important;
    }
    
    /* 主内容区内的元素容器 - 减少间距 */
    .main .element-container {
        margin: 2px 0 !important;
        padding: 2px 0 !important;
    }
    
    /* 输入框、选择框等的容器 */
    .stTextInput, .stSelectbox {
        margin-bottom: 6px !important;
    }
    
    /* caption 文字的间距 */
    .main p[data-testid="stCaptionContainer"] {
        margin: 2px 0 !important;
        padding: 2px 0 !important;
    }
    
    /* column 布局的间距 */
    .main div[data-testid="column"] {
        padding: 2px 4px !important;
    }
    
    /* ===== 标题栏 ===== */
    [data-testid="stHeader"] {
        background-color: var(--bg-secondary) !important;
        border-bottom: 1px solid var(--border);
    }
    
    /* 隐藏整个顶部工作区 */
    [data-testid="stToolbar"],
    #MainMenu,
    header[data-testid="stHeader"],
    header[data-testid="stHeader"] *,
    header[data-testid="stHeader"] > div,
    button[kind="header"],
    [data-testid="stDecoration"] {
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
        padding: 0 !important;
        margin: 0 !important;
    }
    
    /* ===== 侧边栏 ===== */
    [data-testid="stSidebar"] {
        background-color: var(--bg-secondary) !important;
        border-right: 1px solid var(--border) !important;
        padding-top: 4px !important;
    }
    
    /* 侧边栏内的所有容器 - 统一缩小间距 */
    [data-testid="stSidebar"] .element-container,
    [data-testid="stSidebar"] .stMarkdown,
    [data-testid="stSidebar"] div[data-testid="column"] {
        background-color: transparent !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    
    /* 侧边栏的所有 block 容器 */
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] > div {
        gap: 2px !important;
    }
    
    /* 侧边栏输入框 */
    [data-testid="stSidebar"] input {
        background-color: var(--bg-card) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border) !important;
        border-radius: 8px;
    }
    
    /* 侧边栏标题 h3 */
    [data-testid="stSidebar"] h3 {
        margin-top: 4px !important;
        margin-bottom: 2px !important;
        font-size: 1rem !important;
    }
    
    /* 侧边栏分组标题（如"今天"、"昨天"）*/
    [data-testid="stSidebar"] strong,
    [data-testid="stSidebar"] .stMarkdown strong {
        color: var(--text-tertiary) !important;
        font-size: 11px !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        display: block;
        margin-top: 3px !important;
        margin-bottom: 2px !important;
    }
    
    /* 侧边栏按钮 - 统一浅色背景（使用最高优先级选择器）*/
    [data-testid="stSidebar"] .stButton>button,
    [data-testid="stSidebar"] button,
    [data-testid="stSidebar"] .stButton button,
    [data-testid="stSidebar"] button[kind="secondary"],
    section[data-testid="stSidebar"] button {
        background-color: var(--bg-card) !important;
        color: var(--text-secondary) !important;
        border: 1px solid var(--border) !important;
        border-radius: 6px !important;
        transition: all 0.2s ease !important;
        font-weight: 400 !important;
        padding: 6px 12px !important;
        margin: 0 !important;
        font-size: 14px !important;
    }
    
    /* 侧边栏分隔线 */
    [data-testid="stSidebar"] hr {
        margin: 3px 0 !important;
        border: none !important;
        border-top: 1px solid var(--border) !important;
        opacity: 0.3 !important;
    }
    
    /* 侧边栏按钮悬停 */
    [data-testid="stSidebar"] .stButton>button:hover,
    [data-testid="stSidebar"] button:hover,
    [data-testid="stSidebar"] .stButton button:hover,
    [data-testid="stSidebar"] button[kind="secondary"]:hover,
    section[data-testid="stSidebar"] button:hover {
        background-color: var(--bg-hover) !important;
        border-color: var(--accent) !important;
        color: var(--text-primary) !important;
    }
    
    /* 侧边栏选中按钮（深蓝色高亮）*/
    [data-testid="stSidebar"] .stButton>button[kind="primary"],
    [data-testid="stSidebar"] button[kind="primary"],
    [data-testid="stSidebar"] .stButton button[kind="primary"],
    section[data-testid="stSidebar"] button[kind="primary"] {
        background-color: #1976D2 !important;
        color: #FFFFFF !important;
        border: none !important;
        font-weight: 600 !important;
    }
    
    /* 侧边栏选中按钮悬停 */
    [data-testid="stSidebar"] .stButton>button[kind="primary"]:hover,
    [data-testid="stSidebar"] button[kind="primary"]:hover,
    [data-testid="stSidebar"] .stButton button[kind="primary"]:hover,
    section[data-testid="stSidebar"] button[kind="primary"]:hover {
        background-color: #1565C0 !important;
        color: #FFFFFF !important;
    }
    
    /* ===== 主按钮 ===== */
    .stButton>button {
        background-color: #1565C0 !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 10px;
        font-weight: 600 !important;
        transition: all 0.2s ease;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
    }
    
    .stButton>button:hover {
        background-color: #0D47A1 !important;
        color: #FFFFFF !important;
        transform: translateY(-1px);
        box-shadow: 0 4px 16px rgba(13, 71, 161, 0.3);
    }
    
    /* ===== 表单提交按钮（登录注册）===== */
    button[kind="formSubmit"],
    .stForm button[type="submit"],
    [data-testid="stFormSubmitButton"] > button {
        background-color: #1565C0 !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15) !important;
    }
    
    button[kind="formSubmit"]:hover,
    .stForm button[type="submit"]:hover,
    [data-testid="stFormSubmitButton"] > button:hover {
        background-color: #0D47A1 !important;
        color: #FFFFFF !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 16px rgba(13, 71, 161, 0.3) !important;
    }
    
    /* ===== 输入框 ===== */
    .stTextInput>div>div>input,
    .stTextArea>div>div>textarea,
    .stSelectbox>div>div>div,
    input[type="text"],
    input[type="password"],
    input[type="email"],
    textarea {
        background-color: var(--bg-card) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border) !important;
        border-radius: 8px;
    }
    
    /* 禁用状态的输入框 - 确保文字可见 */
    input:disabled,
    textarea:disabled,
    .stTextInput>div>div>input:disabled,
    .stTextArea>div>div>textarea:disabled,
    input[type="text"]:disabled,
    input[type="password"]:disabled,
    input[type="email"]:disabled,
    .stTextInput input[disabled],
    .stTextInput input:disabled {
        background-color: var(--bg-card) !important;
        color: var(--text-primary) !important;
        opacity: 1 !important;
        -webkit-text-fill-color: var(--text-primary) !important;
    }
    
    /* Streamlit 输入框内部文字颜色 */
    .stTextInput input,
    .stTextInput input:not(:disabled),
    .stTextInput input:disabled {
        color: var(--text-primary) !important;
        -webkit-text-fill-color: var(--text-primary) !important;
    }
    
    /* 强制移除所有输入框的所有状态边框 */
    input,
    textarea,
    input:hover,
    textarea:hover,
    input:focus,
    textarea:focus,
    input:active,
    textarea:active,
    input:focus-visible,
    textarea:focus-visible,
    input:invalid,
    textarea:invalid,
    input:valid,
    textarea:valid,
    input:disabled,
    textarea:disabled {
        border-color: var(--border) !important;
        outline: none !important;
        outline-width: 0 !important;
        outline-style: none !important;
        outline-offset: 0 !important;
        box-shadow: none !important;
    }
    
    input::placeholder,
    textarea::placeholder {
        color: var(--text-disabled) !important;
    }
    
    .stTextInput label,
    .stTextArea label,
    .stSelectbox label {
        color: var(--text-secondary) !important;
    }
    
    /* ===== 聊天输入框 - 简洁统一设计 ===== */
    /* 容器背景统一 */
    .stChatInput,
    [data-testid="stChatInput"],
    .stChatFloatingInputContainer,
    [data-testid="InputInstructions"] {
        background-color: var(--bg-primary) !important;
        background: var(--bg-primary) !important;
    }
    
    /* 确保输入框容器无padding */
    .stChatInput>div,
    [data-testid="stChatInput"]>div {
        background-color: var(--bg-primary) !important;
        padding: 0 !important;
    }
    
    .stChatInput>div>div,
    [data-testid="stChatInput"]>div>div {
        background-color: var(--bg-primary) !important;
        padding: 0 !important;
    }
    
    /* 输入框本体 - 简洁统一 */
    .stChatInput>div>div>textarea,
    [data-testid="stChatInput"] textarea,
    .stChatInput textarea {
        /* 背景：统一纯色，与主背景协调 */
        background-color: var(--bg-card) !important;
        background-image: none !important;
        
        /* 文字 */
        color: var(--text-primary) !important;
        font-size: 15px !important;
        line-height: 1.6 !important;
        
        /* 光标颜色 - 确保可见 */
        caret-color: var(--text-primary) !important;
        
        /* 边框：柔和的边框 */
        border: 1px solid var(--border) !important;
        border-radius: 12px !important;
        
        /* 内边距 */
        padding: 12px 16px !important;
        
        /* 无阴影，保持简洁 */
        box-shadow: none !important;
        
        /* 平滑过渡 */
        transition: border-color 0.2s ease, background-color 0.2s ease !important;
    }
    
    /* Placeholder */
    .stChatInput>div>div>textarea::placeholder,
    [data-testid="stChatInput"] textarea::placeholder,
    .stChatInput textarea::placeholder {
        color: var(--text-disabled) !important;
        opacity: 1 !important;
        font-weight: 400 !important;
    }
    
    /* Hover状态 - 轻微变化 */
    .stChatInput>div>div>textarea:hover,
    [data-testid="stChatInput"] textarea:hover,
    .stChatInput textarea:hover {
        border-color: var(--border-light) !important;
        background-color: var(--bg-card) !important;
        outline: none !important;
    }
    
    /* Focus状态 - 柔和反馈 */
    .stChatInput>div>div>textarea:focus,
    [data-testid="stChatInput"] textarea:focus,
    .stChatInput textarea:focus,
    .stChatInput>div>div>textarea:focus-visible,
    [data-testid="stChatInput"] textarea:focus-visible,
    .stChatInput textarea:focus-visible,
    .stChatInput>div>div>textarea:active,
    [data-testid="stChatInput"] textarea:active,
    .stChatInput textarea:active {
        border-color: var(--border-light) !important;
        background-color: var(--bg-card) !important;
        outline: none !important;
        box-shadow: none !important;
        /* 确保焦点时光标可见 */
        caret-color: var(--text-primary) !important;
    }
    
    /* 其他状态 */
    .stChatInput>div>div>textarea:invalid,
    [data-testid="stChatInput"] textarea:invalid,
    .stChatInput textarea:invalid,
    .stChatInput>div>div>textarea:valid,
    [data-testid="stChatInput"] textarea:valid,
    .stChatInput textarea:valid {
        outline: none !important;
    }
    
    /* 发送按钮区域 - 统一背景 */
    .stChatInput button,
    [data-testid="stChatInput"] button {
        background-color: transparent !important;
        border: none !important;
        color: var(--text-secondary) !important;
    }
    
    .stChatInput button:hover,
    [data-testid="stChatInput"] button:hover {
        background-color: transparent !important;
        color: var(--text-primary) !important;
    }
    
    /* ===== 聊天消息 ===== */
    [data-testid="stChatMessage"] {
        background-color: transparent !important;
        background: transparent !important;
        border: none !important;
        border-radius: 0 !important;
        box-shadow: none !important;
        padding: 8px 0 !important;
    }
    
    [data-testid="stChatMessage"] * {
        color: var(--text-secondary) !important;
    }
    
    /* ===== Radio 按钮 ===== */
    .stRadio label,
    .stRadio > div {
        color: var(--text-secondary) !important;
    }
    
    /* ===== 指标卡片 ===== */
    div[data-testid="stMetricValue"] {
        color: var(--text-primary) !important;
        font-weight: 600;
    }
    
    div[data-testid="stMetricLabel"] {
        color: var(--text-tertiary) !important;
    }
    
    /* Metric 容器 - 统一样式，无边框无背景 */
    div[data-testid="stMetricContainer"],
    [data-testid="stMetric"] {
        background-color: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 8px 0 !important;
        margin: 0 !important;
    }
    
    /* ===== 辅助文字 ===== */
    .stCaption,
    small {
        color: var(--text-tertiary) !important;
    }
    
    /* ===== 提示框 ===== */
    .stSuccess {
        background-color: var(--bg-card) !important;
        color: var(--success) !important;
        border-left: 4px solid var(--success);
    }
    
    .stInfo {
        background-color: var(--bg-card) !important;
        color: var(--info) !important;
        border-left: 4px solid var(--info);
    }
    
    .stWarning {
        background-color: var(--bg-card) !important;
        color: var(--warning) !important;
        border-left: 4px solid var(--warning);
    }
    
    .stError {
        background-color: var(--bg-card) !important;
        color: var(--error) !important;
        border-left: 4px solid var(--error);
    }
    
    /* ===== Expander 折叠面板 ===== */
    .streamlit-expanderHeader {
        background-color: var(--bg-card) !important;
        color: var(--text-secondary) !important;
        border: 1px solid var(--border);
        border-radius: 8px;
    }
    
    .streamlit-expanderContent {
        background-color: var(--bg-card) !important;
        border: 1px solid var(--border);
        border-top: none;
    }
    
    /* ===== 分隔线 ===== */
    hr {
        border-color: var(--border) !important;
    }
    
    /* ===== 容器 ===== */
    .stContainer,
    [data-testid="stVerticalBlock"],
    [data-testid="stHorizontalBlock"],
    div[data-testid="column"] {
        background-color: transparent !important;
    }
    
    /* ===== Popover 弹窗 ===== */
    [data-testid="stPopover"],
    [data-baseweb="popover"] {
        background-color: var(--bg-card) !important;
        border: 1px solid var(--border) !important;
        border-radius: 8px;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
    }
    
    /* Popover 内的所有元素背景 */
    [data-testid="stPopover"] *,
    [data-baseweb="popover"] * {
        background-color: transparent !important;
    }
    
    /* Popover 内的文字 */
    [data-testid="stPopover"] p,
    [data-testid="stPopover"] span,
    [data-testid="stPopover"] div {
        color: var(--text-secondary) !important;
    }
    
    /* Popover 内的按钮 - 统一浅色风格 */
    [data-testid="stPopover"] button,
    [data-baseweb="popover"] button {
        background-color: var(--bg-card) !important;
        color: var(--text-secondary) !important;
        border: 1px solid var(--border) !important;
        border-radius: 6px !important;
        transition: all 0.2s ease !important;
        font-weight: 400 !important;
        padding: 8px 16px !important;
    }
    
    /* Popover 内按钮悬停 */
    [data-testid="stPopover"] button:hover,
    [data-baseweb="popover"] button:hover {
        background-color: var(--bg-hover) !important;
        color: var(--text-primary) !important;
        border-color: var(--accent) !important;
    }
    
    /* Popover 标题 */
    [data-testid="stPopover"] strong {
        color: var(--text-primary) !important;
    }
    
    /* ===== 下拉菜单 ===== */
    [data-baseweb="select"],
    [role="listbox"],
    [data-baseweb="menu"] {
        background-color: var(--bg-card) !important;
    }
    
    [data-baseweb="menu"] li {
        background-color: var(--bg-card) !important;
        color: var(--text-secondary) !important;
    }
    
    [data-baseweb="menu"] li:hover {
        background-color: var(--bg-hover) !important;
    }
    
    /* ===== 文件上传器 ===== */
    [data-testid="stFileUploader"] section {
        background-color: var(--bg-card) !important;
        border: 2px dashed var(--border) !important;
        border-radius: 12px;
    }
    
    [data-testid="stFileUploader"] section:hover {
        border-color: var(--accent) !important;
    }
    
    /* ===== Tab 标签页 ===== */
    .stTabs [data-baseweb="tab-list"] {
        background-color: transparent !important;
        border-bottom: 1px solid var(--border);
    }
    
    .stTabs [data-baseweb="tab"] {
        color: var(--text-tertiary) !important;
    }
    
    .stTabs [aria-selected="true"] {
        color: var(--accent) !important;
        border-bottom: 2px solid var(--accent) !important;
    }
    
    /* ===== 进度条 ===== */
    .stProgress > div > div {
        background-color: var(--accent) !important;
    }
    """
}


def apply_theme():
    """根据 session_state 中的主题设置应用样式"""
    theme = st.session_state.get("theme_mode", "dark")
    css = THEME_CSS.get(theme, THEME_CSS["dark"])
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


# 页面配置
st.set_page_config(
    page_title="RAG 智能问答系统",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 初始化主题设置
if "theme_mode" not in st.session_state:
    st.session_state.theme_mode = "dark"

apply_theme()

# 初始化认证管理器（每次脚本运行都重新创建，确保请求级缓存被重置）
auth_manager = AuthManager()

# 在应用启动时预加载 Embedding 模型（异步，不阻塞）
# 使用 st.cache_resource 确保只触发一次（即使页面刷新）
@st.cache_resource
def init_embedding_model():
    try:
        from services import get_vector_store_service
        # 获取服务实例会触发后台模型加载
        _ = get_vector_store_service()
        logger.debug("[脚本初始化] 已触发 Embedding 模型后台加载 (Cached)")
    except Exception as e:
        logger.warning(f"[脚本初始化] 触发 Embedding 模型加载失败: {str(e)}")

init_embedding_model()


def main():
    """主函数"""
    
    # 获取当前用户（内存优先，Cookie兜底）
    user = auth_manager.get_current_user()
    
    if not user:
        # 未登录，显示登录页面
        logger.info("[主应用] 用户未认证，显示登录页面")
        show_login_page(auth_manager)
        return
    
    # 已登录，显示主应用
    logger.info(f"[主应用] 用户已认证: user_id={user.user_id}, username={user.username}")
    show_main_app(user)


def show_main_app(user):
    """显示主应用界面"""
    
    user_id = user.user_id
    
    # 初始化页面状态
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "💬 智能问答"
    
    # 侧边栏
    with st.sidebar:
        # 用户信息和登出
        show_logout_button(auth_manager)
        
        st.markdown("---")
        
        # 导航菜单 - 按钮样式
        st.markdown("### 📑 导航")
        
        # 智能问答按钮
        if st.button(
            "💬 智能问答",
            use_container_width=True,
            type="primary" if st.session_state.current_page == "💬 智能问答" else "secondary"
        ):
            st.session_state.current_page = "💬 智能问答"
            st.rerun()
        
        # 知识库管理按钮
        if st.button(
            "📁 知识库管理",
            use_container_width=True,
            type="primary" if st.session_state.current_page == "📁 知识库管理" else "secondary"
        ):
            st.session_state.current_page = "📁 知识库管理"
            st.rerun()
        
        # 系统设置按钮
        if st.button(
            "⚙️ 系统设置",
            use_container_width=True,
            type="primary" if st.session_state.current_page == "⚙️ 系统设置" else "secondary"
        ):
            st.session_state.current_page = "⚙️ 系统设置"
            st.rerun()
        
        page = st.session_state.current_page
        
        st.markdown("---")
        
        # 根据页面显示会话列表
        if page == "💬 智能问答":
            show_session_list(user_id)
    
    # 主内容区
    if page == "💬 智能问答":
        show_chat_page(user_id)
    elif page == "📁 知识库管理":
        show_knowledge_base_page(user_id)
    elif page == "⚙️ 系统设置":
        show_settings_page(user_id)


def show_chat_page(user_id: int):
    """智能问答页面"""
    show_chat_interface(user_id)


def show_knowledge_base_page(user_id: int):
    """知识库管理页面"""
    show_document_manager(user_id)


def show_settings_page(user_id: int):
    """系统设置页面"""
    st.title("⚙️ 系统设置")
    
    # 显示 Embedding 模型加载状态
    from services import get_vector_store_service
    vector_service = get_vector_store_service()
    status = vector_service.get_embeddings_loading_status()
    
    st.subheader("🤖 模型状态")
    if status['ready']:
        st.success(f"✅ Embedding 模型已就绪: {status['model_name']}")
    elif status['loading']:
        st.info(f"⏳ 正在后台加载 Embedding 模型: {status['model_name']}，请稍候...")
        st.caption("💡 模型加载完成后即可使用向量检索功能")
    else:
        st.warning(f"⚠️ Embedding 模型未加载: {status['model_name']}")
    
    st.markdown("---")
    
    # 用户信息
    st.subheader("👤 用户信息")
    
    from database import UserDAO
    from utils.db_error_handler import safe_db_operation, show_db_error_ui
    
    user_dao = UserDAO()
    try:
        user = safe_db_operation(
            lambda: user_dao.get_user_by_id(user_id),
            default_value=None,
            error_context="获取用户信息"
        )
    except Exception as e:
        show_db_error_ui(e, "获取用户信息")
        user = None
    
    if user:
        col1, col2 = st.columns(2)
        
        with col1:
            st.text_input("用户名", value=user.username, disabled=True)
            st.text_input("显示名称", value=user.display_name or "")
        
        with col2:
            st.text_input("邮箱", value=user.email or "")
            st.text_input("注册时间", value=str(user.created_at)[:19] if user.created_at else "", disabled=True)
    
    st.markdown("---")
    
    # 使用统计
    st.subheader("📊 使用统计")
    
    # 从各个 DAO 获取实时统计
    from database import SessionDAO, MessageDAO, DocumentDAO
    from services import get_document_service
    from utils.db_error_handler import safe_db_operation, show_db_error_ui
    
    session_dao = SessionDAO()
    message_dao = MessageDAO()
    doc_dao = DocumentDAO()
    doc_service = get_document_service()
    
    # 获取实时数据（使用安全操作包装）
    try:
        sessions = safe_db_operation(
            lambda: session_dao.get_user_sessions(user_id),
            default_value=[],
            error_context="获取会话列表"
        )
        total_sessions = len(sessions)
        
        total_messages = 0
        for session in sessions:
            messages = safe_db_operation(
                lambda s=session: message_dao.get_session_messages(s.session_id),
                default_value=[],
                error_context="获取消息列表"
            )
            total_messages += len(messages)
        
        doc_stats = safe_db_operation(
            lambda: doc_service.get_user_stats(user_id),
            default_value={'document_count': 0, 'storage_used': 0},
            error_context="获取文档统计"
        )
        total_documents = doc_stats.get('document_count', 0)
        storage_used = doc_stats.get('storage_used', 0)
    except Exception as e:
        show_db_error_ui(e, "获取使用统计")
        total_sessions = 0
        total_messages = 0
        total_documents = 0
        storage_used = 0
    
    # 显示统计
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("📊 会话数", total_sessions)
        st.metric("💬 消息数", total_messages)
    
    with col2:
        st.metric("📄 文档数", total_documents)
        from utils.file_handler import format_file_size
        st.metric("💾 存储空间", format_file_size(storage_used))
    
    with col3:
        st.metric("🧩 向量块数", doc_stats['vector_count'])
        user = user_dao.get_user_by_id(user_id)
        if user and user.last_login:
            last_login_str = user.last_login if isinstance(user.last_login, str) else user.last_login.strftime('%Y-%m-%d %H:%M:%S')
            st.metric("🕐 最后登录", last_login_str[:19])
    
    st.markdown("---")
    
    # 界面设置
    st.subheader("🎨 界面设置")
    
    current_theme = st.session_state.get("theme_mode", "dark")
    theme_option = st.radio(
        "主题模式，切换后立即生效",
        ["深色模式", "浅色模式"],
        index=0 if current_theme == "dark" else 1,
        horizontal=True
    )
    
    selected_theme = "dark" if theme_option == "深色模式" else "light"
    if selected_theme != current_theme:
        st.session_state.theme_mode = selected_theme
        st.success(f"✅ 已切换至{theme_option}，无需刷新。")
        st.rerun()
    
    # st.caption(f"🎨 当前主题：**{'深色模式' if st.session_state.theme_mode == 'dark' else '浅色模式'}**")
    # st.caption("💡 主题切换会立即生效，并自动保持在当前会话中。")



if __name__ == "__main__":
    main()

