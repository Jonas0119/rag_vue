"""
Parent-Child 分块工具
用于将文档拆分为父文档和子文档
"""

import logging
import uuid
from typing import List, Dict, Tuple

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)


def split_to_parent_child(
    documents: List[Document],
    parent_chunk_size: int = 1200,
    child_chunk_size: int = 300,
) -> Tuple[List[Document], Dict[str, Document]]:
    """
    将文档拆分为父文档和子文档。
    
    Args:
        documents: 原始文档列表（每个 Document 对象包含 page_content）
        parent_chunk_size: 父文档大小（字符数）
        child_chunk_size: 子文档大小（字符数）
        
    Returns:
        (child_docs, parent_map)
        child_docs: 子文档列表（用于向量化）
        parent_map: parent_id -> 父文档 Document
    """
    # 创建父文档（大块，约 800-1600 字符）
    parent_splitter = RecursiveCharacterTextSplitter(
        separators=[
            "\n\n\n",      # 多个空行（段落分隔）
            "\n\n",        # 双换行（段落分隔）
            "\n",          # 单换行
            "。", ".",     # 句号
        ],
        keep_separator=False,
        chunk_size=parent_chunk_size,
        chunk_overlap=int(parent_chunk_size * 0.2),  # 中文需要更多上下文，从 15% 调整为 20%
    )

    parent_docs = parent_splitter.split_documents(documents)

    # 过滤过短的父文档
    filtered_parents: List[Document] = []
    for d in parent_docs:
        content = d.page_content.strip()
        if len(content) < 200:  # 父文档最小长度
            continue
        lines = [ln.strip() for ln in content.split("\n") if ln.strip()]
        if lines and all(len(ln) < 60 and ln.endswith("#") for ln in lines):
            continue
        filtered_parents.append(d)

    logger.info("[ParentChildSplitter] 父文档创建完成: %d", len(filtered_parents))

    # 为每个父文档创建子文档（小块，约 200-400 字符）
    child_splitter = RecursiveCharacterTextSplitter(
        separators=[
            "\n\n",        # 双换行
            "\n",          # 单换行
            "。", ".",     # 句号
            "！", "!",     # 感叹号
            "？", "?",     # 问号
            "；", ";",     # 分号
            "，", ",",     # 逗号
            " ",           # 空格
        ],
        keep_separator=False,
        chunk_size=child_chunk_size,
        chunk_overlap=int(child_chunk_size * 0.25),  # 中文需要更多上下文，从 20% 调整为 25%
    )

    child_docs: List[Document] = []
    parent_map: Dict[str, Document] = {}

    for parent_doc in filtered_parents:
        parent_id = str(uuid.uuid4())

        # 保存父文档
        parent_doc_copy = Document(
            page_content=parent_doc.page_content,
            metadata={
                **parent_doc.metadata,
                "parent_id": parent_id,
                "doc_type": "parent",
            }
        )
        parent_map[parent_id] = parent_doc_copy

        # 拆分子文档
        child_splits = child_splitter.split_documents([parent_doc])
        for child_doc in child_splits:
            content = child_doc.page_content.strip()
            if len(content) < 50:  # 子文档最小长度
                continue

            child_doc_with_metadata = Document(
                page_content=content,
                metadata={
                    **child_doc.metadata,
                    "parent_id": parent_id,
                    "doc_type": "child",
                }
            )
            child_docs.append(child_doc_with_metadata)

    logger.info(
        "[ParentChildSplitter] 子文档创建完成: 父文档=%d, 子文档=%d",
        len(filtered_parents),
        len(child_docs),
    )

    return child_docs, parent_map


