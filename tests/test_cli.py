"""CLI 命令行功能测试。"""

import json
from pathlib import Path

import pytest
from langchain_core.language_models import FakeListChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from ai_software_dev_agent import cli
from ai_software_dev_agent.agent import AgentExecutionError
from ai_software_dev_agent.model import ModelConfigError, ModelSettings
from ai_software_dev_agent.planning import (
    DevelopmentPlan,
    PlanningError,
    PlanStep,
)

# ==========================================================
# Day 01：项目检查
# ==========================================================


def test_doctor_accepts_existing_directory(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = cli.main(["doctor", "--project", str(tmp_path)])
    output = capsys.readouterr().out

    assert result == 0
    assert "项目目录检查通过" in output
    assert str(tmp_path.resolve()) in output


def test_doctor_rejects_missing_directory(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    missing_path = tmp_path / "missing"

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["doctor", "--project", str(missing_path)])

    assert exc_info.value.code == 2
    assert "项目目录不存在" in capsys.readouterr().err


def test_doctor_uses_current_directory_by_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)

    result = cli.main(["doctor"])
    output = capsys.readouterr().out

    assert result == 0
    assert str(tmp_path.resolve()) in output


def test_help_displays_doctor_command(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--help"])

    assert exc_info.value.code == 0
    assert "doctor" in capsys.readouterr().out


# ==========================================================
# Day 02：仓库探索
# ==========================================================


def test_inspect_lists_files(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "a.py").write_text(
        "pass\n",
        encoding="utf-8",
    )

    result = cli.main(
        [
            "inspect",
            "--project",
            str(tmp_path),
        ]
    )

    assert result == 0
    assert "a.py" in capsys.readouterr().out


def test_read_displays_file(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "a.py").write_text(
        "value = 42\n",
        encoding="utf-8",
    )

    result = cli.main(
        [
            "read",
            "--project",
            str(tmp_path),
            "--path",
            "a.py",
        ]
    )

    assert result == 0
    assert "value = 42" in capsys.readouterr().out


def test_search_displays_matches(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "a.py").write_text(
        "def main():\n    pass\n",
        encoding="utf-8",
    )

    result = cli.main(
        [
            "search",
            "--project",
            str(tmp_path),
            "--query",
            "def main",
        ]
    )

    assert result == 0
    assert "a.py:1: def main():" in capsys.readouterr().out


# ==========================================================
# Day 03：模型问答
# ==========================================================


def test_ask_uses_fake_model(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = ModelSettings(
        api_key="test-key",
        model_name="test-model",
        base_url="https://example.com/v1",
    )

    fake_model = FakeListChatModel(responses=["这是来自假模型的回答"])

    monkeypatch.setattr(
        cli,
        "load_model_settings",
        lambda: settings,
    )
    monkeypatch.setattr(
        cli,
        "create_chat_model",
        lambda _settings: fake_model,
    )

    result = cli.main(
        [
            "ask",
            "--question",
            "你好",
        ]
    )

    assert result == 0
    assert "这是来自假模型的回答" in capsys.readouterr().out


def test_ask_requires_question() -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["ask"])

    assert exc_info.value.code == 2


def test_ask_reports_missing_config(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def broken_settings() -> ModelSettings:
        raise ModelConfigError("缺少 API Key")

    monkeypatch.setattr(
        cli,
        "load_model_settings",
        broken_settings,
    )

    with pytest.raises(SystemExit) as exc_info:
        cli.main(
            [
                "ask",
                "--question",
                "你好",
            ]
        )

    assert exc_info.value.code == 2
    assert "缺少 API Key" in capsys.readouterr().err


# ==========================================================
# Day 04：结构化任务规划
# ==========================================================


def test_plan_outputs_structured_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = ModelSettings(
        api_key="test-key",
        model_name="test-model",
        base_url="https://example.com/v1",
    )

    expected_plan = DevelopmentPlan(
        goal="增加用户登录功能",
        steps=[
            PlanStep(
                title="检查项目",
                action="了解现有代码结构",
                verification="确认认证相关文件",
            ),
            PlanStep(
                title="实现功能",
                action="编写登录接口",
                verification="运行 pytest",
            ),
        ],
    )

    monkeypatch.setattr(
        cli,
        "load_model_settings",
        lambda: settings,
    )
    monkeypatch.setattr(
        cli,
        "create_chat_model",
        lambda _settings: object(),
    )
    monkeypatch.setattr(
        cli,
        "generate_development_plan",
        lambda _model, _task: expected_plan,
    )

    result = cli.main(
        [
            "plan",
            "--task",
            "增加用户登录功能",
        ]
    )

    assert result == 0

    output = json.loads(capsys.readouterr().out)

    assert output["goal"] == "增加用户登录功能"
    assert len(output["steps"]) == 2
    assert output["steps"][1]["verification"] == "运行 pytest"


def test_plan_requires_task() -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["plan"])

    assert exc_info.value.code == 2


def test_plan_reports_structured_output_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = ModelSettings(
        api_key="test-key",
        model_name="test-model",
        base_url="https://example.com/v1",
    )

    def broken_plan(_model: object, _task: str) -> None:
        raise PlanningError("模型没有返回开发计划")

    monkeypatch.setattr(
        cli,
        "load_model_settings",
        lambda: settings,
    )
    monkeypatch.setattr(
        cli,
        "create_chat_model",
        lambda _settings: object(),
    )
    monkeypatch.setattr(
        cli,
        "generate_development_plan",
        broken_plan,
    )

    result = cli.main(
        [
            "plan",
            "--task",
            "增加用户登录功能",
        ]
    )

    assert result == 1
    assert "结构化生成失败" in capsys.readouterr().err


# ==========================================================
# Day 05：Interactive CLI
# ==========================================================


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
        cli,
        "load_model_settings",
        lambda: settings,
    )
    monkeypatch.setattr(
        cli,
        "create_chat_model",
        lambda _settings: fake_model,
    )
    monkeypatch.setattr(
        cli,
        "build_development_agent",
        fake_build_agent,
    )
    monkeypatch.setattr(
        cli,
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
        cli,
        "run_agent_turn",
        fake_run_turn,
    )

    result = cli.run_chat_session(object(), tmp_path)
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
        cli,
        "run_agent_turn",
        fake_run_turn,
    )

    result = cli.run_chat_session(object(), tmp_path)

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
        cli,
        "run_agent_turn",
        unexpected_agent_call,
    )

    result = cli.run_chat_session(object(), tmp_path)
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
        cli,
        "run_agent_turn",
        fake_run_turn,
    )

    result = cli.run_chat_session(object(), tmp_path)
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

    result = cli.run_chat_session(object(), tmp_path)

    assert result == 0
    assert "再见" in capsys.readouterr().out


# ==========================================================
# Day 06：File Editing & Git Diff
# ==========================================================


def test_edit_applies_after_exact_confirmation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """输入精确的 yes 后，才允许执行实际写入。"""

    target = tmp_path / "demo.py"
    target.write_text(
        "def add(a, b):\n    return a+b\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "builtins.input",
        lambda _prompt: "yes",
    )

    result = cli.main(
        [
            "edit",
            "--project",
            str(tmp_path),
            "--path",
            "demo.py",
            "--old",
            "return a+b",
            "--new",
            "return a + b",
        ]
    )

    output = capsys.readouterr().out

    assert result == 0
    assert "修改预览" in output
    assert "-    return a+b" in output
    assert "+    return a + b" in output
    assert "修改完成" in output

    assert target.read_text(encoding="utf-8") == ("def add(a, b):\n    return a + b\n")


@pytest.mark.parametrize(
    "confirmation",
    ["", "no", "YES"],
)
def test_edit_cancels_without_exact_yes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    confirmation: str,
) -> None:
    """没有输入精确的 yes 时不能修改文件。"""

    target = tmp_path / "demo.py"
    target.write_text(
        "value = 1\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "builtins.input",
        lambda _prompt: confirmation,
    )

    result = cli.main(
        [
            "edit",
            "--project",
            str(tmp_path),
            "--path",
            "demo.py",
            "--old",
            "value = 1",
            "--new",
            "value = 2",
        ]
    )

    output = capsys.readouterr().out

    assert result == 0
    assert "修改预览" in output
    assert "已取消修改" in output
    assert target.read_text(encoding="utf-8") == "value = 1\n"


def test_edit_rejects_unmatched_content(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """找不到指定旧代码时，不能进入确认或写入阶段。"""

    target = tmp_path / "demo.py"
    target.write_text(
        "value = 1\n",
        encoding="utf-8",
    )

    result = cli.main(
        [
            "edit",
            "--project",
            str(tmp_path),
            "--path",
            "demo.py",
            "--old",
            "value = 999",
            "--new",
            "value = 2",
        ]
    )

    captured = capsys.readouterr()

    assert result == 1
    assert "实际匹配 0 次" in captured.err
    assert target.read_text(encoding="utf-8") == "value = 1\n"


def test_edit_rejects_unsafe_path(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """CLI 不能绕过 CodeEditor 的文件路径限制。"""

    result = cli.main(
        [
            "edit",
            "--project",
            str(tmp_path),
            "--path",
            "../outside.py",
            "--old",
            "old",
            "--new",
            "new",
        ]
    )

    assert result == 1
    assert "无法生成修改预览" in capsys.readouterr().err


def test_edit_rejects_stale_preview(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """预览后文件被外部修改时，应拒绝覆盖。"""

    target = tmp_path / "demo.py"
    target.write_text(
        "value = 1\n",
        encoding="utf-8",
    )

    def change_file_before_confirmation(_prompt: str) -> str:
        # 模拟用户查看预览期间，其他程序修改了文件。
        target.write_text(
            "value = 99\n",
            encoding="utf-8",
        )
        return "yes"

    monkeypatch.setattr(
        "builtins.input",
        change_file_before_confirmation,
    )

    result = cli.main(
        [
            "edit",
            "--project",
            str(tmp_path),
            "--path",
            "demo.py",
            "--old",
            "value = 1",
            "--new",
            "value = 2",
        ]
    )

    captured = capsys.readouterr()

    assert result == 1
    assert "文件在预览后已发生变化" in captured.err
    assert target.read_text(encoding="utf-8") == "value = 99\n"


def test_edit_cancels_on_eof(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """确认阶段输入流结束时，文件必须保持不变。"""

    target = tmp_path / "demo.py"
    target.write_text(
        "value = 1\n",
        encoding="utf-8",
    )

    def raise_eof(_prompt: str) -> str:
        raise EOFError

    monkeypatch.setattr(
        "builtins.input",
        raise_eof,
    )

    result = cli.main(
        [
            "edit",
            "--project",
            str(tmp_path),
            "--path",
            "demo.py",
            "--old",
            "value = 1",
            "--new",
            "value = 2",
        ]
    )

    assert result == 0
    assert target.read_text(encoding="utf-8") == "value = 1\n"
    assert "已取消修改" in capsys.readouterr().out


@pytest.mark.parametrize(
    "arguments",
    [
        ["--path", "demo.py", "--new", "changed"],
        ["--path", "demo.py", "--old", "original"],
    ],
)
def test_edit_requires_old_and_new_arguments(
    tmp_path: Path,
    arguments: list[str],
) -> None:
    """--old、--new 均是必填参数。"""

    with pytest.raises(SystemExit) as exc_info:
        cli.main(
            [
                "edit",
                "--project",
                str(tmp_path),
                *arguments,
            ]
        )

    assert exc_info.value.code == 2


def test_edit_help_displays_arguments(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """edit 帮助信息必须说明全部编辑参数。"""

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["edit", "--help"])

    assert exc_info.value.code == 0

    output = capsys.readouterr().out

    assert "--project" in output
    assert "--path" in output
    assert "--old" in output
    assert "--new" in output
