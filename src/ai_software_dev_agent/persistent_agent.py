"""Day 11：为现有开发 Agent 添加检查点与会话持久化。"""

from pathlib import Path

from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph

from ai_software_dev_agent.agent import (
    AGENT_SYSTEM_PROMPT,
    AgentExecutionError,
    create_repository_tools,
)
from ai_software_dev_agent.model import ModelConfigError

# 与 Day 05 原有 Agent 保持一致的内部执行步数限制。
AGENT_RECURSION_LIMIT = 12


def build_persistent_development_agent(
    model: BaseChatModel,
    project: Path,
    checkpointer: BaseCheckpointSaver,
) -> CompiledStateGraph:
    """使用原有系统提示词和仓库工具，创建可持久化 Agent。"""

    # 直接复用 Day 05 的工具定义，不创建另一套工具。
    tools = create_repository_tools(project)

    return create_agent(
        model=model,
        tools=tools,
        system_prompt=AGENT_SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )


def make_session_config(
    project: Path,
    session_id: str,
) -> dict:
    """按项目和会话 ID 生成 LangGraph 执行配置。"""

    clean_session_id = session_id.strip()

    if not clean_session_id:
        raise ValueError("会话 ID 不能为空")

    # 防止不同项目使用相同会话名时共享聊天记录。
    project_key = project.expanduser().resolve().as_posix()

    thread_id = f"{project_key}::{clean_session_id}"

    return {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": AGENT_RECURSION_LIMIT,
    }


def get_persistent_agent_history(
    agent: CompiledStateGraph,
    project: Path,
    session_id: str,
) -> list[BaseMessage]:
    """从 Checkpoint 读取指定项目、指定会话的消息历史。"""

    config = make_session_config(project, session_id)
    snapshot = agent.get_state(config)

    return list(snapshot.values.get("messages", []))


def run_persistent_agent_turn(
    agent: CompiledStateGraph,
    project: Path,
    session_id: str,
    question: str,
) -> tuple[str, list[BaseMessage]]:
    """执行一轮持久化工具 Agent 对话。"""

    clean_question = question.strip()

    if not clean_question:
        raise ModelConfigError("用户问题不能为空")

    config = make_session_config(project, session_id)

    # 只传入这一轮的新消息。
    # LangGraph 会通过 thread_id 恢复已有消息。
    result = agent.invoke(
        {
            "messages": [
                HumanMessage(content=clean_question),
            ]
        },
        config=config,
    )

    messages = list(result["messages"])

    if not messages:
        raise AgentExecutionError("Agent 没有返回任何消息")

    last_message = messages[-1]

    # 工具调用已经结束，才能视为完成一轮对话。
    if not isinstance(last_message, AIMessage) or last_message.tool_calls:
        raise AgentExecutionError("Agent 未返回有效的最终回答")

    return str(last_message.text), messages
