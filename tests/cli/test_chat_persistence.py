"""Day 11：chat CLI 会话持久化与恢复测试。"""

from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableLambda

from ai_software_dev_agent import cli
from ai_software_dev_agent.commands import chat as chat_command
from ai_software_dev_agent.persistent_chat import (
    build_persistent_chat_graph,
)


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    """创建独立仓库，不修改真实项目。"""

    (tmp_path / "demo.py").write_text(
        "value = 123\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def fake_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """模拟模型配置与聊天模型，不访问外部 API。"""

    def fake_model() -> RunnableLambda:
        def respond(messages: list) -> AIMessage:
            count = sum(isinstance(message, HumanMessage) for message in messages)
            return AIMessage(content=f"第 {count} 轮回答")

        return RunnableLambda(respond)

    monkeypatch.setattr(
        chat_command,
        "load_model_settings",
        lambda: object(),
    )

    monkeypatch.setattr(
        chat_command,
        "create_chat_model",
        lambda settings: fake_model(),
    )

    # CLI 测试使用第一阶段已验证的持久化对话图。
    # 业务测试另行验证仓库工具仍能注册。
    monkeypatch.setattr(
        chat_command,
        "build_persistent_development_agent",
        lambda model, project, saver: build_persistent_chat_graph(model, saver),
    )


def provide_inputs(
    monkeypatch: pytest.MonkeyPatch,
    *values: str,
) -> None:
    """模拟用户在交互式 CLI 中依次输入命令。"""

    items = iter(values)

    monkeypatch.setattr(
        "builtins.input",
        lambda prompt="": next(items),
    )


def test_cli_restores_session_after_restart(
    sample_project: Path,
    fake_dependencies: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """两次启动 chat，使用相同数据库和会话恢复历史。"""

    db_path = sample_project / "sessions.sqlite"

    args = [
        "chat",
        "--project",
        str(sample_project),
        "--session",
        "python-learning",
        "--db",
        str(db_path),
    ]

    provide_inputs(monkeypatch, "第一次提问", "/exit")
    assert cli.main(args) == 0
    first_output = capsys.readouterr().out
    assert "第 1 轮回答" in first_output

    # 模拟退出后重新启动 CLI。
    provide_inputs(monkeypatch, "第二次提问", "/exit")
    assert cli.main(args) == 0
    second_output = capsys.readouterr().out

    assert "已恢复用户消息：1 轮" in second_output
    assert "第 2 轮回答" in second_output
    assert db_path.is_file()


def test_cli_switches_between_sessions(
    sample_project: Path,
    fake_dependencies: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """使用 /session 切换后，应恢复各自的消息。"""

    db_path = sample_project / "sessions.sqlite"

    provide_inputs(
        monkeypatch,
        "主会话第一轮",
        "/session other",
        "其他会话第一轮",
        "/session main",
        "主会话第二轮",
        "/exit",
    )

    result = cli.main(
        [
            "chat",
            "--project",
            str(sample_project),
            "--session",
            "main",
            "--db",
            str(db_path),
        ]
    )

    output = capsys.readouterr().out

    assert result == 0
    assert "已切换会话：other" in output
    assert "已切换会话：main" in output
    assert "第 1 轮回答" in output
    assert "第 2 轮回答" in output


def test_new_session_does_not_delete_old_history(
    sample_project: Path,
    fake_dependencies: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """执行 /new 后原会话应能再次恢复。"""

    db_path = sample_project / "sessions.sqlite"

    args = [
        "chat",
        "--project",
        str(sample_project),
        "--session",
        "original",
        "--db",
        str(db_path),
    ]

    provide_inputs(
        monkeypatch,
        "旧会话第一轮",
        "/new",
        "新会话第一轮",
        "/exit",
    )

    assert cli.main(args) == 0
    output = capsys.readouterr().out
    assert "已开始新会话" in output

    # 重新使用旧会话 ID，仍然应该接着原历史继续。
    provide_inputs(monkeypatch, "旧会话第二轮", "/exit")
    assert cli.main(args) == 0

    restored_output = capsys.readouterr().out

    assert "已恢复用户消息：1 轮" in restored_output
    assert "第 2 轮回答" in restored_output


def test_legacy_chat_without_session(
    sample_project: Path,
    fake_dependencies: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """不传 --session 时，继续使用原有内存历史方式。"""

    def fake_build_agent(model: object, project: Path) -> RunnableLambda:
        def respond(data: dict) -> dict:
            messages = data["messages"]
            count = sum(isinstance(message, HumanMessage) for message in messages)
            return {
                "messages": [
                    *messages,
                    AIMessage(content=f"第 {count} 轮回答"),
                ]
            }

        return RunnableLambda(respond)

    monkeypatch.setattr(
        chat_command,
        "build_development_agent",
        fake_build_agent,
    )

    provide_inputs(
        monkeypatch,
        "第一次",
        "第二次",
        "/new",
        "重新开始",
        "/exit",
    )

    result = cli.main(
        [
            "chat",
            "--project",
            str(sample_project),
        ]
    )

    output = capsys.readouterr().out

    assert result == 0
    assert "临时聊天模式" in output
    assert "第 2 轮回答" in output
    assert "已清空当前对话历史" in output


def test_db_requires_session(
    sample_project: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """单独传 --db 而不指定会话，应拒绝执行。"""

    result = cli.main(
        [
            "chat",
            "--project",
            str(sample_project),
            "--db",
            str(sample_project / "sessions.sqlite"),
        ]
    )

    captured = capsys.readouterr()

    assert result == 2
    assert "--db 需要与 --session 一起使用" in captured.err


def test_chat_help_contains_persistence_options(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """chat 帮助信息应包含持久化参数。"""

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["chat", "--help"])

    assert exc_info.value.code == 0

    output = capsys.readouterr().out

    assert "--session" in output
    assert "--db" in output
