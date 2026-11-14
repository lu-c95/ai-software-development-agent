"""Day 10：conditional-workflow CLI 命令测试。"""

from pathlib import Path

import pytest

from ai_software_dev_agent import cli
from ai_software_dev_agent.commands import (
    conditional_workflow as command,
)


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    """创建测试用项目目录。"""

    (tmp_path / "demo.py").write_text(
        "print('hello')\n",
        encoding="utf-8",
    )

    return tmp_path


def test_cli_passes_arguments(
    sample_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """验证 CLI 将参数完整传给工作流。"""

    observed: dict[str, object] = {}

    def fake_run(
        project: Path,
        target: str,
        timeout_seconds: int,
        max_retries: int,
    ) -> dict:
        observed.update(
            {
                "project": project,
                "target": target,
                "timeout_seconds": timeout_seconds,
                "max_retries": max_retries,
            }
        )

        return {
            "project": str(project),
            "target": target,
            "status": "passed",
            "retry_count": 1,
            "completed_steps": [
                "inspect_repository",
                "run_tests",
                "retry_tests",
                "run_tests",
                "summarize_passed",
            ],
            "summary": "重试后测试通过",
        }

    monkeypatch.setattr(
        command,
        "run_conditional_workflow",
        fake_run,
    )

    result = cli.main(
        [
            "conditional-workflow",
            "--project",
            str(sample_project),
            "--target",
            "tests/test_demo.py",
            "--timeout",
            "30",
            "--max-retries",
            "1",
        ]
    )

    output = capsys.readouterr().out

    assert result == 0
    assert observed["project"] == sample_project.resolve()
    assert observed["target"] == "tests/test_demo.py"
    assert observed["timeout_seconds"] == 30
    assert observed["max_retries"] == 1

    assert "测试状态：passed" in output
    assert "已重试：1 次" in output
    assert "重试后测试通过" in output


@pytest.mark.parametrize(
    "status",
    ["failed", "no_tests", "timeout", "error"],
)
def test_cli_non_success_status_returns_failure(
    sample_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    status: str,
) -> None:
    """非 passed 状态都必须返回非零退出码。"""

    def fake_run(
        project: Path,
        target: str,
        timeout_seconds: int,
        max_retries: int,
    ) -> dict:
        return {
            "project": str(project),
            "target": target,
            "status": status,
            "retry_count": 0,
            "completed_steps": [
                "inspect_repository",
                "run_tests",
                "summarize_error",
            ],
            "summary": "模拟工作流未成功",
        }

    monkeypatch.setattr(
        command,
        "run_conditional_workflow",
        fake_run,
    )

    result = cli.main(
        [
            "conditional-workflow",
            "--project",
            str(sample_project),
        ]
    )

    output = capsys.readouterr().out

    assert result == 1
    assert f"测试状态：{status}" in output


def test_cli_rejects_invalid_retry_choice() -> None:
    """超过允许范围的 CLI 参数应被 argparse 拒绝。"""

    with pytest.raises(SystemExit) as exc_info:
        cli.main(
            [
                "conditional-workflow",
                "--max-retries",
                "10",
            ]
        )

    assert exc_info.value.code == 2


def test_cli_reports_invalid_input(
    sample_project: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """无效测试目标应返回参数错误退出码。"""

    result = cli.main(
        [
            "conditional-workflow",
            "--project",
            str(sample_project),
            "--target",
            "   ",
        ]
    )

    captured = capsys.readouterr()

    assert result == 2
    assert "测试目标不能为空" in captured.err


def test_cli_reports_unexpected_error(
    sample_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """未知程序错误不能被误报为成功。"""

    def fake_run(**kwargs: object) -> None:
        raise RuntimeError("模拟未知程序错误")

    monkeypatch.setattr(
        command,
        "run_conditional_workflow",
        fake_run,
    )

    result = cli.main(
        [
            "conditional-workflow",
            "--project",
            str(sample_project),
        ]
    )

    captured = capsys.readouterr()

    assert result == 1
    assert "RuntimeError" in captured.err
    assert "模拟未知程序错误" in captured.err


def test_cli_help(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """验证新子命令帮助信息。"""

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["conditional-workflow", "--help"])

    assert exc_info.value.code == 0

    output = capsys.readouterr().out

    assert "--project" in output
    assert "--target" in output
    assert "--timeout" in output
    assert "--max-retries" in output


def test_top_level_help_contains_command(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """顶层帮助应包含 conditional-workflow。"""

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--help"])

    assert exc_info.value.code == 0
    assert "conditional-workflow" in capsys.readouterr().out
