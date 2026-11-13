"""LangGraph workflow CLI 命令的集成测试。"""

from pathlib import Path

import pytest

from ai_software_dev_agent import cli
from ai_software_dev_agent.commands import workflow as workflow_command
from ai_software_dev_agent.test_runner import (
    TestRunResult as RunnerResult,
)


@pytest.fixture
def demo_project(tmp_path: Path) -> Path:
    """创建带有一个正常测试的临时 Python 项目。"""

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()

    (tmp_path / "demo.py").write_text(
        "def add(a, b):\n    return a + b\n",
        encoding="utf-8",
    )

    (tests_dir / "test_demo.py").write_text(
        "def test_add():\n    assert 1 + 1 == 2\n",
        encoding="utf-8",
    )

    return tmp_path


def test_workflow_cli_reports_success(
    demo_project: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """整个真实工作流运行通过，CLI 应返回 0。"""

    result = cli.main(
        [
            "workflow",
            "--project",
            str(demo_project),
        ]
    )

    output = capsys.readouterr().out

    assert result == 0

    assert "[1/3] inspect_repository 已完成" in output
    assert "[2/3] run_tests 已完成" in output
    assert "[3/3] summarize 已完成" in output

    assert "=== 工作流总结 ===" in output
    assert "pytest 状态：passed" in output
    assert "pytest 退出码：0" in output
    assert "已完成节点：3/3" in output


def test_workflow_cli_reports_failed_tests(
    demo_project: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """测试断言失败时，仍然执行总结并返回 1。"""

    (demo_project / "tests" / "test_bad.py").write_text(
        "def test_bad():\n    assert 1 == 2\n",
        encoding="utf-8",
    )

    result = cli.main(
        [
            "workflow",
            "--project",
            str(demo_project),
        ]
    )

    output = capsys.readouterr().out

    assert result == 1
    assert "[3/3] summarize 已完成" in output
    assert "pytest 状态：failed" in output
    assert "pytest 退出码：1" in output
    assert "=== pytest 输出 ===" in output
    assert "1 failed" in output


def test_workflow_cli_reports_no_tests(
    demo_project: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """没有测试时应输出 no_tests，不能误报成功。"""

    (demo_project / "tests" / "test_demo.py").unlink()

    result = cli.main(
        [
            "workflow",
            "--project",
            str(demo_project),
        ]
    )

    output = capsys.readouterr().out

    assert result == 1
    assert "pytest 状态：no_tests" in output
    assert "pytest 退出码：5" in output
    assert "=== 工作流总结 ===" in output


def test_workflow_cli_runs_selected_file(
    demo_project: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """指定正常测试文件时，不执行其他失败测试。"""

    (demo_project / "tests" / "test_bad.py").write_text(
        "def test_bad():\n    assert False\n",
        encoding="utf-8",
    )

    result = cli.main(
        [
            "workflow",
            "--project",
            str(demo_project),
            "--target",
            "tests/test_demo.py",
            "--timeout",
            "30",
        ]
    )

    output = capsys.readouterr().out

    assert result == 0
    assert "pytest 状态：passed" in output
    assert "pytest 退出码：0" in output


def test_workflow_cli_rejects_unsafe_target(
    demo_project: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """不允许通过 workflow CLI 绕过测试路径限制。"""

    result = cli.main(
        [
            "workflow",
            "--project",
            str(demo_project),
            "--target",
            "../outside.py",
        ]
    )

    captured = capsys.readouterr()

    assert result == 2
    assert "工作流参数或目标错误" in captured.err


def test_workflow_cli_rejects_invalid_timeout(
    demo_project: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """超时时间超出范围时，返回参数错误。"""

    result = cli.main(
        [
            "workflow",
            "--project",
            str(demo_project),
            "--timeout",
            "121",
        ]
    )

    captured = capsys.readouterr()

    assert result == 2
    assert "超时时间" in captured.err


def test_workflow_cli_rejects_missing_project(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """仓库不存在时，工作流不应报告成功。"""

    result = cli.main(
        [
            "workflow",
            "--project",
            str(tmp_path / "missing"),
        ]
    )

    captured = capsys.readouterr()

    assert result == 2
    assert "工作流参数或目标错误" in captured.err


def test_workflow_cli_help_shows_arguments(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """工作流命令应展示自己的参数说明。"""

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["workflow", "--help"])

    assert exc_info.value.code == 0

    output = capsys.readouterr().out

    assert "--project" in output
    assert "--target" in output
    assert "--timeout" in output


def test_workflow_cli_streams_node_updates(
    demo_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """确认 CLI 使用 updates 模式，而不是 invoke()。"""

    observed: dict[str, object] = {}

    fake_result = RunnerResult(
        status="passed",
        exit_code=0,
        stdout="1 passed",
        stderr="",
        duration_seconds=0.5,
        command=("python", "-m", "pytest", "tests"),
    )

    class FakeGraph:
        """模拟三个节点逐步返回更新的 LangGraph。"""

        def stream(
            self,
            state: dict,
            stream_mode: str,
        ):
            observed["state"] = state
            observed["stream_mode"] = stream_mode

            yield {
                "inspect_repository": {
                    "files": ["demo.py"],
                    "completed_steps": ["inspect_repository"],
                }
            }

            yield {
                "run_tests": {
                    "test_result": fake_result,
                    "completed_steps": ["run_tests"],
                }
            }

            yield {
                "summarize": {
                    "summary": "模拟工作流总结",
                    "completed_steps": ["summarize"],
                }
            }

    monkeypatch.setattr(
        workflow_command,
        "build_development_workflow",
        lambda: FakeGraph(),
    )

    result = workflow_command.run_workflow_command(
        demo_project,
        target="tests",
        timeout_seconds=30,
    )

    output = capsys.readouterr().out

    assert result == 0
    assert observed["stream_mode"] == "updates"
    assert observed["state"]["target"] == "tests"

    assert output.index("inspect_repository 已完成") < (
        output.index("run_tests 已完成")
    )
    assert output.index("run_tests 已完成") < (output.index("summarize 已完成"))

    assert "模拟工作流总结" in output


def test_workflow_cli_rejects_incomplete_result(
    demo_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """节点没有产生完整结果时，CLI 不能返回成功。"""

    class IncompleteGraph:
        def stream(
            self,
            state: dict,
            stream_mode: str,
        ):
            yield {
                "inspect_repository": {
                    "files": ["demo.py"],
                    "completed_steps": ["inspect_repository"],
                }
            }

    monkeypatch.setattr(
        workflow_command,
        "build_development_workflow",
        lambda: IncompleteGraph(),
    )

    result = workflow_command.run_workflow_command(
        demo_project,
        target="tests",
        timeout_seconds=30,
    )

    captured = capsys.readouterr()

    assert result == 1
    assert "工作流执行不完整" in captured.err


def test_workflow_cli_reports_execution_error(
    demo_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """工作流执行出现文件系统错误时返回非零退出码。"""

    class BrokenGraph:
        def stream(
            self,
            state: dict,
            stream_mode: str,
        ):
            raise OSError("模拟磁盘读取失败")
            yield

    monkeypatch.setattr(
        workflow_command,
        "build_development_workflow",
        lambda: BrokenGraph(),
    )

    result = workflow_command.run_workflow_command(
        demo_project,
        target="tests",
        timeout_seconds=30,
    )

    captured = capsys.readouterr()

    assert result == 1
    assert "模拟磁盘读取失败" in captured.err
