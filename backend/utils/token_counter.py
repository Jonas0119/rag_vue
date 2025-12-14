"""
Token 统计模块
用于统计模型调用的输入和输出 token 数量
"""

from typing import Dict, Any
from collections import defaultdict
from langchain_core.messages import BaseMessage


class TokenCounter:
    """Token 统计器，用于跟踪模型调用的 token 使用情况"""
    
    def __init__(self):
        """初始化 Token 统计器"""
        # 按模型类型统计：model, response_model, grader_model
        self.model_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "call_count": 0
        })
        
        # 按节点统计：generate_query_or_respond, grade_documents, rewrite_question, generate_answer
        self.node_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "call_count": 0
        })
        
        # 总体统计
        self.total_stats = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "call_count": 0
        }
    
    def count_tokens(
        self,
        model_name: str,
        node_name: str,
        input_tokens: int,
        output_tokens: int,
    ):
        """
        统计 token 使用情况
        
        Args:
            model_name: 模型名称（model, response_model, grader_model）
            node_name: 节点名称（generate_query_or_respond, grade_documents, rewrite_question, generate_answer）
            input_tokens: 输入 token 数量
            output_tokens: 输出 token 数量
        """
        total_tokens = input_tokens + output_tokens
        
        # 更新模型统计
        self.model_stats[model_name]["input_tokens"] += input_tokens
        self.model_stats[model_name]["output_tokens"] += output_tokens
        self.model_stats[model_name]["total_tokens"] += total_tokens
        self.model_stats[model_name]["call_count"] += 1
        
        # 更新节点统计
        self.node_stats[node_name]["input_tokens"] += input_tokens
        self.node_stats[node_name]["output_tokens"] += output_tokens
        self.node_stats[node_name]["total_tokens"] += total_tokens
        self.node_stats[node_name]["call_count"] += 1
        
        # 更新总体统计
        self.total_stats["input_tokens"] += input_tokens
        self.total_stats["output_tokens"] += output_tokens
        self.total_stats["total_tokens"] += total_tokens
        self.total_stats["call_count"] += 1
    
    def get_model_response_tokens(self, response: Any) -> tuple[int, int]:
        """
        从模型响应中提取 token 数量
        
        优先级：
        1. usage_metadata（LangChain 1.0+）
        2. response_metadata['usage'] 或 response_metadata['token_usage']
        3. 估算
        """
        input_tokens = 0
        output_tokens = 0
        
        # 1) 尝试 usage_metadata（支持对象和字典两种格式）
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            usage = response.usage_metadata
            # 支持字典格式
            if isinstance(usage, dict):
                input_tokens = usage.get("input_tokens", 0) or 0
                output_tokens = usage.get("output_tokens", 0) or 0
            else:
                # 支持对象格式（使用 getattr 安全访问）
                input_tokens = getattr(usage, "input_tokens", 0) or 0
                output_tokens = getattr(usage, "output_tokens", 0) or 0
        
        # 2) 尝试 response_metadata
        if (input_tokens == 0 and output_tokens == 0) and hasattr(response, 'response_metadata'):
            metadata = response.response_metadata
            if metadata:
                # 尝试多种可能的 token 统计字段
                input_tokens = (
                    metadata.get('input_tokens') or
                    metadata.get('usage', {}).get('input_tokens') or
                    metadata.get('token_usage', {}).get('input_tokens') or
                    0
                )
                output_tokens = (
                    metadata.get('output_tokens') or
                    metadata.get('usage', {}).get('output_tokens') or
                    metadata.get('token_usage', {}).get('output_tokens') or
                    0
                )
        
        # 3) 如果没有找到 token 信息，尝试从消息中估算
        if input_tokens == 0 and output_tokens == 0:
            if hasattr(response, 'content'):
                content = str(response.content)
                # 更准确的中文 token 估算
                estimated_tokens = self._estimate_tokens_chinese(content)
                output_tokens = int(estimated_tokens)
        
        return int(input_tokens), int(output_tokens)
    
    def _estimate_tokens_chinese(self, text: str) -> float:
        """
        更准确地估算中文文本的 token 数量
        
        对于中文文本：
        - 中文字符：通常 1 个中文字符 ≈ 1.5-2 tokens（取决于 tokenizer）
        - 英文/数字：通常 1 个字符 ≈ 0.25-0.5 tokens
        - 标点符号：通常 1 个标点 ≈ 0.5-1 token
        
        这里使用混合估算方法：
        - 中文字符（CJK统一汉字）：按 1.8 tokens/字符
        - 其他字符：按 0.4 tokens/字符
        
        Args:
            text: 待估算的文本
            
        Returns:
            估算的 token 数量
        """
        if not text:
            return 0.0
        
        # 统计中文字符数量（CJK统一汉字范围）
        chinese_chars = 0
        other_chars = 0
        
        for char in text:
            # CJK统一汉字范围：\u4e00-\u9fff
            # 还包括扩展A：\u3400-\u4dbf
            if '\u4e00' <= char <= '\u9fff' or '\u3400' <= char <= '\u4dbf':
                chinese_chars += 1
            elif char.strip():  # 非空白字符
                other_chars += 1
        
        # 中文字符按 1.8 tokens/字符，其他字符按 0.4 tokens/字符
        estimated_tokens = chinese_chars * 1.8 + other_chars * 0.4
        return estimated_tokens
    
    def get_messages_tokens(self, messages: list[BaseMessage]) -> int:
        """
        估算消息列表的 token 数量
        
        Args:
            messages: 消息列表
            
        Returns:
            估算的 token 数量
        """
        total_chars = 0
        for msg in messages:
            if hasattr(msg, 'content'):
                total_chars += len(str(msg.content))
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                # 工具调用也会消耗 token
                total_chars += len(str(msg.tool_calls)) * 2
        
        # 使用更准确的中文 token 估算
        content_str = ""
        for msg in messages:
            if hasattr(msg, 'content'):
                content_str += str(msg.content)
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                content_str += str(msg.tool_calls)
        
        return self._estimate_tokens_chinese(content_str)
    
    def print_stats(self):
        """打印统计结果"""
        print("\n" + "=" * 80)
        print("📊 Token 使用统计")
        print("=" * 80)
        
        # 总体统计
        print("\n【总体统计】")
        print(f"  总调用次数: {self.total_stats['call_count']}")
        print(f"  总输入 Token: {self.total_stats['input_tokens']:,}")
        print(f"  总输出 Token: {self.total_stats['output_tokens']:,}")
        print(f"  总 Token: {self.total_stats['total_tokens']:,}")
        
        # 按模型统计
        if self.model_stats:
            print("\n【按模型统计】")
            for model_name, stats in self.model_stats.items():
                print(f"  {model_name}:")
                print(f"    调用次数: {stats['call_count']}")
                print(f"    输入 Token: {stats['input_tokens']:,}")
                print(f"    输出 Token: {stats['output_tokens']:,}")
                print(f"    总 Token: {stats['total_tokens']:,}")
        
        # 按节点统计
        if self.node_stats:
            print("\n【按节点统计】")
            for node_name, stats in self.node_stats.items():
                print(f"  {node_name}:")
                print(f"    调用次数: {stats['call_count']}")
                print(f"    输入 Token: {stats['input_tokens']:,}")
                print(f"    输出 Token: {stats['output_tokens']:,}")
                print(f"    总 Token: {stats['total_tokens']:,}")
        
        print("=" * 80 + "\n")
    
    def reset(self):
        """重置所有统计"""
        self.model_stats.clear()
        self.node_stats.clear()
        self.total_stats = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "call_count": 0
        }


# 全局 Token 统计器实例
token_counter = TokenCounter()


