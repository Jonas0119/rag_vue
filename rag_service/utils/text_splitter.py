"""
文本分块工具 - 段落级别分块策略
智能分块算法，保留段落语义完整性
"""
import re
from typing import List
from rag_service.utils.config import config

def split_by_paragraphs(
    text: str, 
    max_chunk_size: int = None,
    min_chunk_size: int = None
) -> List[str]:
    """
    按照段落进行分块，保留语义完整性
    识别中文文档的段落结构

    Args:
        text: 待分块的文本
        max_chunk_size: 每个块的最大字符数
        min_chunk_size: 最小块大小

    Returns:
        分块后的文本列表
    """
    # 如果未指定最大/最小块大小，则从配置信息中获取默认值
    if max_chunk_size is None:
        max_chunk_size = config.MAX_CHUNK_SIZE
    if min_chunk_size is None:
        min_chunk_size = config.MIN_CHUNK_SIZE

    chunks = []  # 用于存放分好的文本块

    # 按双换行符分割，得到段落列表（兼容不同段落空行格式）
    paragraphs = re.split(r'\n\s*\n', text)

    current_chunk = ""  # 当前正在累计的文本块
    current_size = 0    # 当前累计块的字符数

    # 遍历每一个段落
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue  # 跳过空段落

        para_size = len(para)

        # 如果该段落长度超过最大块大小，需要对其再细致拆解
        if para_size > max_chunk_size:
            # 如果之前已累积有内容，则先保存为一个块
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""
                current_size = 0

            # 对超长段落按照句子级分割（支持中英文），保语义完整
            # 按中英文句子标点（。！？；. ! ? ;）以及换行符拆句，仍然保留分隔符
            sentences = re.split(r'([。！？；\.!?;\n])', para)
            temp_chunk = ""
            # 两两合并，构造完整句
            for i in range(0, len(sentences), 2):
                if i + 1 < len(sentences):
                    sentence = sentences[i] + sentences[i + 1]
                else:
                    sentence = sentences[i]

                # 超出max_chunk_size时，先保存当前已累积的句子
                if len(temp_chunk) + len(sentence) > max_chunk_size:
                    if temp_chunk:
                        chunks.append(temp_chunk.strip())
                    temp_chunk = sentence
                else:
                    temp_chunk += sentence

            # 保存剩下的部分
            if temp_chunk:
                chunks.append(temp_chunk.strip())
        else:
            # 当前段落可以接受
            # 判断如果新加这个段落后超过最大块长，并且当前块已达最小块长，则先保存旧块再累计新块
            if current_size + para_size > max_chunk_size and current_size >= min_chunk_size:
                chunks.append(current_chunk.strip())
                current_chunk = para + "\n\n"  # 当前段落作为新块开始累积
                current_size = para_size
            else:
                # 继续拼接到当前块
                current_chunk += para + "\n\n"
                current_size += para_size

    # 循环结束后，把最后还未保存的内容保存至chunks
    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks

