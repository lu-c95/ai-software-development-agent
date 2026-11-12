"""LangChain Agent 工具循环与对话历史测试。"""

from pathlib import Path
from typing import Any

import pytest
from langchain_core.language_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from ai_software_dev_agent.agent import (
    build_development_agent,
    run_agent_turn,
)
from ai_software_dev_agent.model import ModelConfigError
from ai_software_dev_agent.repository import RepositoryError


class ToolAwareFakeModel(FakeMessagesListChatModel):
    """能够配合 create_agent 测试的假聊天模型。"""

    def bind_tools(
        self,
        tools: Any,
        **kwargs: Any,
    ) -> "ToolAwareFakeModel":
        # 返回自身即可，因为测试回复中已经预设了 tool_calls。
        return self


def test_agent_executes_repository_tool(tmp_path: Path) -> None:
    """Agent 应自动执行工具，并将结果返回模型。"""

    (tmp_path / "demo.py").write_text(
        "def greet():\n    return 'hello'\n",
        encoding="utf-8",
    )

    fake_model = ToolAwareFakeModel(
        responses=[
            # 第一次模型回复：请求读取文件。
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "read_repository_file",
                        "args": {"path": "demo.py"},
                        "id": "call-read-1",
                        "type": "tool_call",
                    }
                ],
            ),
            # 第二次模型回复：收到文件内容后回答。
            AIMessage(
                content="greet() 函数返回字符串 hello。",
            ),
        ]
    )

    agent = build_development_agent(fake_model, tmp_path)

    answer, history = run_agent_turn(
        agent,
        [],
        "请读取 demo.py 并解释 greet() 函数。",
    )

    assert "hello" in answer

    # 确认工具确实执行过，而不仅仅生成了 tool_calls。
    tool_messages = [message for message in history if isinstance(message, ToolMessage)]

    assert len(tool_messages) == 1
    assert "return 'hello'" in tool_messages[0].content
    assert tool_messages[0].tool_call_id == "call-read-1"

    # 最后一条消息应为面向用户的最终回答。
    assert isinstance(history[-1], AIMessage)
    assert not history[-1].tool_calls


def test_agent_preserves_conversation_history(tmp_path: Path) -> None:
    """第二轮对话应该保留第一轮的用户与 AI 消息。"""

    fake_model = ToolAwareFakeModel(
        responses=[
            AIMessage(content="第一次回答"),
            AIMessage(content="第二次回答"),
        ]
    )

    agent = build_development_agent(fake_model, tmp_path)

    answer1, history1 = run_agent_turn(
        agent,
        [],
        "这是第一个问题",
    )

    answer2, history2 = run_agent_turn(
        agent,
        history1,
        "这是第二个问题",
    )

    assert answer1 == "第一次回答"
    assert answer2 == "第二次回答"

    assert len(history1) == 2
    assert len(history2) == 4

    assert isinstance(history2[0], HumanMessage)
    assert history2[0].content == "这是第一个问题"
    assert history2[1].content == "第一次回答"

    assert isinstance(history2[2], HumanMessage)
    assert history2[2].content == "这是第二个问题"
    assert history2[3].content == "第二次回答"


def test_agent_rejects_empty_question(tmp_path: Path) -> None:
    """空白问题不应该触发模型调用。"""

    fake_model = ToolAwareFakeModel(responses=[AIMessage(content="不会被调用")])

    agent = build_development_agent(fake_model, tmp_path)

    with pytest.raises(
        ModelConfigError,
        match="用户问题不能为空",
    ):
        run_agent_turn(agent, [], "   ")


def test_agent_rejects_invalid_project(tmp_path: Path) -> None:
    """绑定不存在的项目目录时应该报错。"""

    fake_model = ToolAwareFakeModel(responses=[AIMessage(content="不会被调用")])

    with pytest.raises(RepositoryError):
        build_development_agent(
            fake_model,
            tmp_path / "missing",
        )
