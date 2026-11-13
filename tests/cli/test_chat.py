"""交互式 Agent 命令测试。"""

from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from ai_software_dev_agent import cli
from ai_software_dev_agent.agent import AgentExecutionError
from ai_software_dev_agent.commands import chat
from ai_software_dev_agent.model import ModelSettings


def test_chat_command_builds_agent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = ModelSettings(
        api_key="test-key",
        model_name="test-model",
        base_url="https://example.com/v1",
    )

    fake_model = object()
    fake_agent = object()
    captured = {}

    def fake_build_agent(
        model: object,
        project: Path,
    ) -> object:
        captured["model"] = model
        captured["project"] = project
        return fake_agent

    def fake_session(
        agent: object,
        project: Path,
    ) -> int:
        captured["agent"] = agent
        captured["session_project"] = project
        return 0

    monkeypatch.setattr(
        chat,
        "load_model_settings",
        lambda: settings,
    )
    monkeypatch.setattr(
        chat,
        "create_chat_model",
        lambda _settings: fake_model,
    )
    monkeypatch.setattr(
        chat,
        "build_development_agent",
        fake_build_agent,
    )
    monkeypatch.setattr(
        chat,
        "run_chat_session",
        fake_session,
    )

    result = cli.main(
        [
            "chat",
            "--project",
            str(tmp_path),
        ]
    )

    assert result == 0
    assert captured["model"] is fake_model
    assert captured["agent"] is fake_agent
    assert captured["project"] == tmp_path
    assert captured["session_project"] == tmp_path


def test_chat_preserves_history_and_shows_tool(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    inputs = iter(
        [
            "读取 demo.py",
            "继续解释这个函数",
            "/exit",
        ]
    )

    monkeypatch.setattr(
        "builtins.input",
        lambda _prompt: next(inputs),
    )

    observed = []

    def fake_run_turn(
        _agent: object,
        history: list,
        question: str,
    ) -> tuple[str, list]:
        observed.append((question, len(history)))

        if question == "读取 demo.py":
            new_messages = [
                HumanMessage(content=question),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "read_repository_file",
                            "args": {"path": "demo.py"},
                            "id": "call-1",
                            "type": "tool_call",
                        }
                    ],
                ),
                ToolMessage(
                    content="def greet(): return 'hello'",
                    tool_call_id="call-1",
                    name="read_repository_file",
                ),
                AIMessage(content="已读取 demo.py"),
            ]
            return "已读取 demo.py", history + new_messages

        new_messages = [
            HumanMessage(content=question),
            AIMessage(content="这个函数返回 hello"),
        ]
        return "这个函数返回 hello", history + new_messages

    monkeypatch.setattr(
        chat,
        "run_agent_turn",
        fake_run_turn,
    )

    result = chat.run_chat_session(object(), tmp_path)
    output = capsys.readouterr().out

    assert result == 0
    assert observed == [
        ("读取 demo.py", 0),
        ("继续解释这个函数", 4),
    ]

    assert "[工具返回] read_repository_file" in output
    assert "这个函数返回 hello" in output


def test_chat_new_clears_history(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    inputs = iter(
        [
            "第一个问题",
            "/new",
            "第二个问题",
            "/exit",
        ]
    )

    monkeypatch.setattr(
        "builtins.input",
        lambda _prompt: next(inputs),
    )

    history_lengths = []

    def fake_run_turn(
        _agent: object,
        history: list,
        question: str,
    ) -> tuple[str, list]:
        history_lengths.append(len(history))

        updated = history + [
            HumanMessage(content=question),
            AIMessage(content="测试回答"),
        ]
        return "测试回答", updated

    monkeypatch.setattr(
        chat,
        "run_agent_turn",
        fake_run_turn,
    )

    result = chat.run_chat_session(object(), tmp_path)

    assert result == 0
    assert history_lengths == [0, 0]
    assert "已清空当前对话历史" in capsys.readouterr().out


def test_chat_help_and_unknown_command(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    inputs = iter(
        [
            "   ",
            "/help",
            "/unknown",
            "/exit",
        ]
    )

    monkeypatch.setattr(
        "builtins.input",
        lambda _prompt: next(inputs),
    )

    def unexpected_agent_call(
        _agent: object,
        _history: list,
        _question: str,
    ) -> None:
        raise AssertionError("不应该调用 Agent")

    monkeypatch.setattr(
        chat,
        "run_agent_turn",
        unexpected_agent_call,
    )

    result = chat.run_chat_session(object(), tmp_path)
    output = capsys.readouterr().out

    assert result == 0
    assert "/help" in output
    assert "/new" in output
    assert "/exit" in output
    assert "未知命令" in output


def test_chat_keeps_running_after_agent_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    inputs = iter(
        [
            "这次失败",
            "这次成功",
            "/exit",
        ]
    )

    monkeypatch.setattr(
        "builtins.input",
        lambda _prompt: next(inputs),
    )

    history_lengths = []

    def fake_run_turn(
        _agent: object,
        history: list,
        question: str,
    ) -> tuple[str, list]:
        history_lengths.append(len(history))

        if question == "这次失败":
            raise AgentExecutionError("模拟执行失败")

        updated = history + [
            HumanMessage(content=question),
            AIMessage(content="成功回答"),
        ]
        return "成功回答", updated

    monkeypatch.setattr(
        chat,
        "run_agent_turn",
        fake_run_turn,
    )

    result = chat.run_chat_session(object(), tmp_path)
    captured = capsys.readouterr()

    assert result == 0
    assert history_lengths == [0, 0]
    assert "模拟执行失败" in captured.err
    assert "成功回答" in captured.out


def test_chat_exits_on_eof(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def raise_eof(_prompt: str) -> str:
        raise EOFError

    monkeypatch.setattr(
        "builtins.input",
        raise_eof,
    )

    result = chat.run_chat_session(object(), tmp_path)

    assert result == 0
    assert "再见" in capsys.readouterr().out
