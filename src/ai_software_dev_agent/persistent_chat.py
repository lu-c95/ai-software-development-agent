"""Day 11：使用 LangGraph Checkpoint 持久化对话历史。"""

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)
from langchain_core.runnables import Runnable
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph

SYSTEM_PROMPT = (
    "你是一名 Python 软件开发学习助手。"
    "请结合当前会话中已经出现的历史消息回答问题。"
    "如果历史中没有相关信息，请明确说明不知道。"
    "不要声称已经调用工具、运行测试或修改文件。"
    "使用简体中文回答。"
)


def build_persistent_chat_graph(
    model: Runnable,
    checkpointer: BaseCheckpointSaver,
) -> CompiledStateGraph:
    """创建支持 Checkpoint 的对话工作流。"""

    def respond_node(
        state: MessagesState,
    ) -> dict[str, list[AIMessage]]:
        """读取当前会话历史，并让模型生成下一条回答。"""

        # SystemMessage 每轮发送给模型，但不重复写入持久化历史。
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            *state["messages"],
        ]

        response = model.invoke(messages)

        # 当前是无工具对话节点，不接受未完成的工具调用请求。
        if not isinstance(response, AIMessage) or response.tool_calls:
            raise ValueError("模型没有返回有效的最终 AI 消息")

        # MessagesState 自动将新回答合并到历史消息中。
        return {"messages": [response]}

    builder = StateGraph(MessagesState)

    builder.add_node("respond", respond_node)

    builder.add_edge(START, "respond")
    builder.add_edge("respond", END)

    # 核心：编译时绑定 Checkpointer。
    return builder.compile(checkpointer=checkpointer)


def run_persistent_turn(
    graph: CompiledStateGraph,
    thread_id: str,
    question: str,
) -> tuple[str, list[BaseMessage]]:
    """在指定会话中执行一轮对话，返回回答及完整历史。"""

    clean_thread_id = thread_id.strip()
    clean_question = question.strip()

    if not clean_thread_id:
        raise ValueError("会话 ID 不能为空")

    if not clean_question:
        raise ValueError("用户问题不能为空")

    # thread_id 决定从哪一条会话历史恢复 State。
    config = {
        "configurable": {
            "thread_id": clean_thread_id,
        }
    }

    # 这里只传入本轮新增的 HumanMessage。
    # 历史消息由 Checkpointer 自动恢复。
    result = graph.invoke(
        {
            "messages": [
                HumanMessage(content=clean_question),
            ]
        },
        config=config,
    )

    history = list(result["messages"])
    last_message = history[-1]

    if not isinstance(last_message, AIMessage) or last_message.tool_calls:
        raise ValueError("工作流未返回有效的最终 AI 消息")

    return str(last_message.text), history
