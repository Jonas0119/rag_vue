"""
文档清理工具模块
提供用于清理和预处理文档内容的函数
"""

import re
from typing import List, Optional
from langchain_core.documents import Document


# 噪声行/块过滤的关键词与模式
NAVIGATION_KEYWORDS = [
    "posts", "archive", "search", "tags", "faq", "home", "previous", "next",
    "©", "copyright", "all rights reserved",
    # 中文导航关键词
    "上一页", "下一页", "返回", "首页", "搜索", "标签", "归档"
]
METADATA_KEYWORDS = [
    "date:", "author:", "reading time", "estimated reading time", "published on",
    # 中文元数据关键词
    "日期：", "作者：", "发布时间：", "出版日期：", "阅读时间：", "字数：",
    "日期:", "作者:", "发布时间:", "出版日期:", "阅读时间:", "字数:"
]
TOC_KEYWORDS = [
    "table of contents", "contents", "目录",
    # 中文目录关键词
    "目 录", "目录页", "目录表", "章节索引", "内容索引"
]
if True: # dummy to keep noqa tools quiet
    CITATION_KEYWORDS = [
        "citation", "cited as", "references", "reference", "参考文献",
        # 中文引用关键词
        "参考书目", "参考资料", "引用文献", "文献索引", "注释"
    ]

# 中文书籍特有的噪声模式
CHINESE_BOOK_NOISE_PATTERNS = [
    # 章节标题模式（如"第X章"、"第X节"）
    r"^第[一二三四五六七八九十\d]+章\s*$",
    r"^第[一二三四五六七八九十\d]+节\s*$",
    r"^第[一二三四五六七八九十\d]+部分\s*$",
    # 页码标记
    r"^第\d+页\s*$",
    r"^P\.\d+\s*$",
    r"^p\.\d+\s*$",
    r"^页码：\d+\s*$",
    r"^页码:\d+\s*$",
    # 版权信息
    r"^版权所有\s*$",
    r"^©\s*\d{4}\s*$",
    r"^Copyright\s*\d{4}\s*$",
    # 目录项（单独一行）
    r"^目\s*录\s*$",
    r"^Contents\s*$",
]


def clean_text(
    text: str,
    remove_multiple_newlines: bool = True,
    remove_trailing_whitespace: bool = True,
    remove_html_tags: bool = True,
    normalize_whitespace: bool = True,
    min_length: int = 0
) -> str:
    """
    清理文本内容
    
    Args:
        text: 原始文本
        remove_multiple_newlines: 是否去除多个连续空行（保留最多2个换行）
        remove_trailing_whitespace: 是否去除行尾空白
        remove_html_tags: 是否去除 HTML 标签
        normalize_whitespace: 是否规范化空白字符（多个空格替换为单个）
        min_length: 最小长度，如果清理后长度小于此值，返回空字符串
        
    Returns:
        清理后的文本
    """
    if not text:
        return ""
    
    # 去除首尾空白
    text = text.strip()
    
    # 去除 HTML 标签
    if remove_html_tags:
        text = re.sub(r'<[^>]+>', '', text)
    
    # 去除多个连续空行（保留最多2个换行）
    if remove_multiple_newlines:
        text = re.sub(r'\n{3,}', '\n\n', text)
    
    # 去除行尾空白（空格和制表符）
    if remove_trailing_whitespace:
        text = re.sub(r'[ \t]+$', '', text, flags=re.MULTILINE)
    
    # 规范化空白字符
    if normalize_whitespace:
        # 多个空格替换为单个空格
        text = re.sub(r' +', ' ', text)
        # 规范化换行符周围的空格（去除换行前后的空格）
        text = re.sub(r' ?\n ?', '\n', text)
        # 去除制表符
        text = text.replace('\t', ' ')
    
    # 最终去除首尾空白
    text = text.strip()
    
    # 检查最小长度
    if len(text) < min_length:
        return ""
    
    return text


def clean_document(
    document: Document,
    remove_multiple_newlines: bool = True,
    remove_trailing_whitespace: bool = True,
    remove_html_tags: bool = True,
    normalize_whitespace: bool = True,
    min_length: int = 0,
    remove_navigation: bool = False,
    remove_toc: bool = False,
    remove_metadata: bool = False,
    remove_citation: bool = False,
    remove_headers_only: bool = False,
    remove_chinese_book_noise: bool = True,  # 默认启用中文书籍噪声过滤
) -> Optional[Document]:
    """
    清理单个文档
    
    Args:
        document: LangChain Document 对象
        remove_multiple_newlines: 是否去除多个连续空行
        remove_trailing_whitespace: 是否去除行尾空白
        remove_html_tags: 是否去除 HTML 标签
        normalize_whitespace: 是否规范化空白字符
        min_length: 最小长度，如果清理后长度小于此值，返回 None
        
    Returns:
        清理后的文档，如果清理后内容为空或过短，返回 None
    """
    cleaned_content = clean_text(
        document.page_content,
        remove_multiple_newlines=remove_multiple_newlines,
        remove_trailing_whitespace=remove_trailing_whitespace,
        remove_html_tags=remove_html_tags,
        normalize_whitespace=normalize_whitespace,
        min_length=min_length
    )
    
    if not cleaned_content:
        return None

    # 行级过滤：去掉导航/目录/元数据/引用等噪声行
    lines = []
    for line in cleaned_content.split("\n"):
        low = line.lower().strip()
        if not low:
            continue
        if remove_navigation and any(k in low for k in NAVIGATION_KEYWORDS):
            continue
        if remove_metadata and any(k in low for k in METADATA_KEYWORDS):
            continue
        if remove_toc and any(k in low for k in TOC_KEYWORDS):
            continue
        if remove_citation and any(k in low for k in CITATION_KEYWORDS):
            continue
        # 中文书籍特有的噪声模式过滤
        if remove_chinese_book_noise:
            import re
            if any(re.match(pattern, line.strip()) for pattern in CHINESE_BOOK_NOISE_PATTERNS):
                continue
        lines.append(line)

    cleaned_content = "\n".join(lines).strip()

    if not cleaned_content:
        return None

    # 如果只有标题（很短且包含多行以 # 或极短短语组成），则丢弃
    if remove_headers_only:
        header_like = True
        for line in cleaned_content.split("\n"):
            l = line.strip()
            if len(l) > 80:
                header_like = False
                break
            # 含有句号/问号视为有正文
            if any(p in l for p in [".", "?", "!", "。", "！", "？"]):
                header_like = False
                break
        if header_like:
            return None
    
    # 创建新文档或更新现有文档
    document.page_content = cleaned_content
    return document


def clean_documents(
    documents: List[Document],
    remove_multiple_newlines: bool = True,
    remove_trailing_whitespace: bool = True,
    remove_html_tags: bool = True,
    normalize_whitespace: bool = True,
    min_length: int = 10,
    remove_navigation: bool = False,
    remove_toc: bool = False,
    remove_metadata: bool = False,
    remove_citation: bool = False,
    remove_headers_only: bool = False,
    remove_chinese_book_noise: bool = True,  # 默认启用中文书籍噪声过滤
) -> List[Document]:
    """
    清理文档列表
    
    Args:
        documents: 文档列表
        remove_multiple_newlines: 是否去除多个连续空行
        remove_trailing_whitespace: 是否去除行尾空白
        remove_html_tags: 是否去除 HTML 标签
        normalize_whitespace: 是否规范化空白字符
        min_length: 最小长度，过滤掉少于指定字符数的文档
        
    Returns:
        清理后的文档列表（已过滤掉空文档和过短文档）
    """
    cleaned_docs = []
    for doc in documents:
        cleaned_doc = clean_document(
            doc,
            remove_multiple_newlines=remove_multiple_newlines,
            remove_trailing_whitespace=remove_trailing_whitespace,
            remove_html_tags=remove_html_tags,
            normalize_whitespace=normalize_whitespace,
            min_length=min_length,
            remove_navigation=remove_navigation,
            remove_toc=remove_toc,
            remove_metadata=remove_metadata,
            remove_citation=remove_citation,
            remove_headers_only=remove_headers_only,
            remove_chinese_book_noise=remove_chinese_book_noise,
        )
        if cleaned_doc is not None:
            cleaned_docs.append(cleaned_doc)
    
    return cleaned_docs


def clean_text_advanced(
    text: str,
    remove_multiple_newlines: bool = True,
    remove_trailing_whitespace: bool = True,
    remove_html_tags: bool = True,
    normalize_whitespace: bool = True,
    remove_special_chars: bool = False,
    min_length: int = 0
) -> str:
    """
    高级文本清理（包含更多选项）
    
    Args:
        text: 原始文本
        remove_multiple_newlines: 是否去除多个连续空行
        remove_trailing_whitespace: 是否去除行尾空白
        remove_html_tags: 是否去除 HTML 标签
        normalize_whitespace: 是否规范化空白字符
        remove_special_chars: 是否去除特殊字符（保留字母、数字、标点、空格、换行）
        min_length: 最小长度
        
    Returns:
        清理后的文本
    """
    # 先执行基础清理
    text = clean_text(
        text,
        remove_multiple_newlines=remove_multiple_newlines,
        remove_trailing_whitespace=remove_trailing_whitespace,
        remove_html_tags=remove_html_tags,
        normalize_whitespace=normalize_whitespace,
        min_length=0  # 先不检查长度
    )
    
    # 去除特殊字符（可选）
    if remove_special_chars:
        # 保留字母、数字、常见标点、空格、换行
        text = re.sub(r'[^\w\s.,!?;:()\[\]{}\'"-]', '', text)
    
    # 最终检查长度
    if len(text.strip()) < min_length:
        return ""
    
    return text.strip()


