"""Day 11：持久化开发 Agent 的业务测试。"""

from pathlib import Path
from typing import Any

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.sqlite import SqliteSaver

from ai_software_dev_agent import persistent_agent
from ai_software_dev_agent.persistent_agent import (
    build_persistent_development_agent,
    get_persistent_agent_history,
    run_persistent_agent_turn,
)


class EchoToolModel(BaseChatModel):
    """支持工具绑定、但不真正调用工具的测试模型。"""

    @property
    def _llm_type(self) -> str:
        return "day11-echo-model"

    def bind_tools(self, tools: Any, **kwargs: Any) -> Any:
        """使模拟模型兼容 LangChain Agent 的工具绑定接口。"""
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        """根据历史用户消息数返回确定性回答。"""

        user_messages = [
            message for message in messages if isinstance(message, HumanMessage)
        ]

        last_question = user_messages[-1].content

        answer = AIMessage(
            content=(f"第 {len(user_messages)} 轮，当前问题：{last_question}")
        )

        return ChatResult(
            generations=[
                ChatGeneration(message=answer),
            ]
        )


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    """创建可以被 RepositoryExplorer 识别的仓库。"""

    (tmp_path / "demo.py").write_text(
        "def hello():\n    return 'hello'\n",
        encoding="utf-8",
    )
    return tmp_path


def test_persistent_agent_survives_reopen(
    sample_project: Path,
) -> None:
    """重新打开 SQLite 后，工具 Agent 可以继续原会话。"""

    database = sample_project / "sessions.sqlite"

    with SqliteSaver.from_conn_string(str(database)) as saver:
        agent = build_persistent_development_agent(
            EchoToolModel(), sample_project, saver
        )

        answer, history = run_persistent_agent_turn(
            agent, sample_project, "learning", "第一轮"
        )

        assert "第 1 轮" in answer
        assert len(history) == 2

    # 重新建立数据库连接、Agent 与模型对象。
    with SqliteSaver.from_conn_string(str(database)) as saver:
        agent = build_persistent_development_agent(
            EchoToolModel(), sample_project, saver
        )

        saved = get_persistent_agent_history(agent, sample_project, "learning")

        assert len(saved) == 2
        assert saved[0].content == "第一轮"

        answer, history = run_persistent_agent_turn(
            agent, sample_project, "learning", "第二轮"
        )

        assert "第 2 轮" in answer
        assert len(history) == 4


def test_sessions_are_isolated(
    sample_project: Path,
) -> None:
    """不同会话名称不能相互读取消息。"""

    database = sample_project / "sessions.sqlite"

    with SqliteSaver.from_conn_string(str(database)) as saver:
        agent = build_persistent_development_agent(
            EchoToolModel(), sample_project, saver
        )

        run_persistent_agent_turn(agent, sample_project, "session-a", "A 的第一轮")

        answer, history = run_persistent_agent_turn(
            agent, sample_project, "session-b", "B 的第一轮"
        )

        assert "第 1 轮" in answer
        assert len(history) == 2
        assert history[0].content == "B 的第一轮"


def test_same_session_name_in_different_projects(
    tmp_path: Path,
) -> None:
    """不同仓库中相同的会话名应相互隔离。"""

    first = tmp_path / "project-a"
    second = tmp_path / "project-b"
    first.mkdir()
    second.mkdir()

    (first / "demo.py").write_text("x = 1\n", encoding="utf-8")
    (second / "demo.py").write_text("y = 2\n", encoding="utf-8")

    database = tmp_path / "sessions.sqlite"

    with SqliteSaver.from_conn_string(str(database)) as saver:
        first_agent = build_persistent_development_agent(EchoToolModel(), first, saver)
        second_agent = build_persistent_development_agent(
            EchoToolModel(), second, saver
        )

        run_persistent_agent_turn(first_agent, first, "learning", "项目 A 的消息")

        answer, history = run_persistent_agent_turn(
            second_agent, second, "learning", "项目 B 的消息"
        )

        assert "第 1 轮" in answer
        assert len(history) == 2
        assert history[0].content == "项目 B 的消息"


def test_original_repository_tools_are_registered(
    sample_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """持久化模式仍然注册 Day 05 的仓库工具。"""

    observed: dict[str, object] = {}

    def fake_create_agent(
        *,
        model: Any,
        tools: Any,
        system_prompt: str,
        checkpointer: Any,
    ) -> object:
        observed["tool_names"] = [tool.name for tool in tools]
        observed["system_prompt"] = system_prompt
        observed["checkpointer"] = checkpointer
        return object()

    monkeypatch.setattr(
        persistent_agent,
        "create_agent",
        fake_create_agent,
    )

    with SqliteSaver.from_conn_string(":memory:") as saver:
        persistent_agent.build_persistent_development_agent(
            EchoToolModel(),
            sample_project,
            saver,
        )

        tool_names = observed["tool_names"]

        assert "inspect_repository" in tool_names
        assert "read_repository_file" in tool_names
        assert observed["checkpointer"] is saver


@pytest.mark.parametrize(
    ("session_id", "question", "message"),
    [
        ("  ", "你好", "会话 ID 不能为空"),
        ("learning", "  ", "用户问题不能为空"),
    ],
)
def test_invalid_input(
    sample_project: Path,
    session_id: str,
    question: str,
    message: str,
) -> None:
    """空会话 ID 与空问题应该被拒绝。"""

    with SqliteSaver.from_conn_string(":memory:") as saver:
        agent = build_persistent_development_agent(
            EchoToolModel(), sample_project, saver
        )

        with pytest.raises(ValueError, match=message):
            run_persistent_agent_turn(
                agent,
                sample_project,
                session_id,
                question,
            )
