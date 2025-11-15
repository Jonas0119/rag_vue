"""
文本分块工具 - 段落级别分块策略
智能分块算法，保留段落语义完整性
"""
import re
from typing import List
from utils.config import config


def split_by_paragraphs(text: str, 
                       max_chunk_size: int = None,
                       min_chunk_size: int = None) -> List[str]:
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
    if max_chunk_size is None:
        max_chunk_size = config.MAX_CHUNK_SIZE
    if min_chunk_size is None:
        min_chunk_size = config.MIN_CHUNK_SIZE
    
    chunks = []
    
    # 首先按双换行符分割（段落分隔）
    paragraphs = re.split(r'\n\s*\n', text)
    
    current_chunk = ""
    current_size = 0
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
            
        para_size = len(para)
        
        # 如果当前段落太长，需要进一步分割
        if para_size > max_chunk_size:
            # 如果有积累的内容，先保存
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""
                current_size = 0
            
            # 对超长段落按句子分割
            sentences = re.split(r'([。！？；\n])', para)
            temp_chunk = ""
            for i in range(0, len(sentences), 2):
                if i + 1 < len(sentences):
                    sentence = sentences[i] + sentences[i + 1]
                else:
                    sentence = sentences[i]
                
                if len(temp_chunk) + len(sentence) > max_chunk_size:
                    if temp_chunk:
                        chunks.append(temp_chunk.strip())
                    temp_chunk = sentence
                else:
                    temp_chunk += sentence
            
            if temp_chunk:
                chunks.append(temp_chunk.strip())
        else:
            # 如果添加这个段落会超出大小限制
            if current_size + para_size > max_chunk_size and current_size >= min_chunk_size:
                chunks.append(current_chunk.strip())
                current_chunk = para + "\n\n"
                current_size = para_size
            else:
                current_chunk += para + "\n\n"
                current_size += para_size
    
    # 保存最后的块
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    return chunks

