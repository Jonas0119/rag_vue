"""
Graph 构建模块
负责构建和配置 RAG Graph
"""

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition

from rag_service.services.rag_state import RAGState


def build_rag_graph(
    retrieve_tool,
    generate_query_or_respond_node,
    grade_documents_node,
    rewrite_question_node,
    generate_answer_node,
    summarize_messages_node=None,
    checkpointer=None
):
    """
    构建 RAG Graph
    
    Args:
        retrieve_tool: 检索工具函数
        generate_query_or_respond_node: 生成查询或响应的节点函数
        grade_documents_node: 评估文档相关性的节点函数
        rewrite_question_node: 重写问题的节点函数
        generate_answer_node: 生成答案的节点函数
        summarize_messages_node: 可选的总结消息节点函数
        checkpointer: 可选的 checkpoint 实例，用于状态持久化
        
    Returns:
        编译好的 Graph 对象
    """
    workflow = StateGraph(RAGState)

    # 定义节点
    workflow.add_node("generate_query_or_respond", generate_query_or_respond_node)
    workflow.add_node("retrieve", ToolNode([retrieve_tool]))
    workflow.add_node("rewrite_question", rewrite_question_node)
    workflow.add_node("generate_answer", generate_answer_node)
    
    # 如果提供了总结节点，在所有进入 generate_query_or_respond 的路径之前都检查总结
    if summarize_messages_node:
        workflow.add_node("summarize_messages", summarize_messages_node)
        # START -> summarize_messages -> generate_query_or_respond
        workflow.add_edge(START, "summarize_messages")
        workflow.add_edge("summarize_messages", "generate_query_or_respond")
    else:
        # 设置入口
        workflow.add_edge(START, "generate_query_or_respond")

    # 决定是否检索
    workflow.add_conditional_edges(
        # 这一段的作用是为 "generate_query_or_respond" 节点添加条件边。
        # tools_condition 用于判断当前节点输出是否需要调用工具（即进行检索）：
        # - 如果满足条件（即返回值包含 "tools"），则跳转到 "retrieve" 节点（即调用检索工具进行信息搜索）
        # - 否则，直接进入 END，说明无需检索，可直接终止流程
        "generate_query_or_respond",         # 当前节点
        tools_condition,                     # 条件函数（判定是否触发工具调用）
        {
            "tools": "retrieve",             # 返回值含 "tools"，进入 "retrieve" 节点（调用检索工具）
            END: END,                        # 否则直接结束流程
        },
    )

    # 检索后的条件边：评估文档相关性（两路：相关/重写）
    # 当 retry >= 3 时，grade_documents 会设置 no_relevant_found 并路由到 generate_answer
    workflow.add_conditional_edges(
        "retrieve",
        grade_documents_node,
        {
            "generate_answer": "generate_answer",
            "rewrite_question": "rewrite_question",
        },
    )
    
    # 最终边
    workflow.add_edge("generate_answer", END)
    
    # rewrite_question 后，如果启用了总结，先检查总结再进入 generate_query_or_respond
    # 这样每次进入 generate_query_or_respond 之前都会检查是否需要总结
    if summarize_messages_node:
        workflow.add_edge("rewrite_question", "summarize_messages")
    else:
        workflow.add_edge("rewrite_question", "generate_query_or_respond")

    # 编译（如果提供了 checkpointer，则使用它）
    if checkpointer:
        graph = workflow.compile(checkpointer=checkpointer)
    else:
        graph = workflow.compile()
    
    return graph


