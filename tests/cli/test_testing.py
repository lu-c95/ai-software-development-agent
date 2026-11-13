"""pytest 测试执行命令测试。"""

from pathlib import Path

import pytest

from ai_software_dev_agent import cli
from ai_software_dev_agent.commands import testing
from ai_software_dev_agent.test_runner import (
    TestRunResult as RunnerResult,
)


@pytest.fixture
def pytest_demo(tmp_path: Path) -> Path:
    """准备一个用于 CLI 集成测试的临时仓库。"""

    (tmp_path / "tests").mkdir()
    return tmp_path


def write_demo_test(
    project: Path,
    filename: str,
    source: str,
) -> None:
    """创建临时 pytest 测试文件。"""

    (project / "tests" / filename).write_text(
        source,
        encoding="utf-8",
    )


def test_test_command_reports_passed(
    pytest_demo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """CLI 应正确展示成功测试的状态与退出码。"""

    write_demo_test(
        pytest_demo,
        "test_success.py",
        "def test_success():\n    assert 2 + 2 == 4\n",
    )

    result = cli.main(
        [
            "test",
            "--project",
            str(pytest_demo),
        ]
    )

    output = capsys.readouterr().out

    assert result == 0
    assert "测试状态：passed（通过）" in output
    assert "pytest 退出码：0" in output
    assert "执行耗时：" in output
    assert "1 passed" in output


def test_test_command_reports_failed(
    pytest_demo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """测试断言失败时，CLI 应返回非零退出码。"""

    write_demo_test(
        pytest_demo,
        "test_failure.py",
        "def test_failure():\n    assert 1 == 2\n",
    )

    result = cli.main(
        [
            "test",
            "--project",
            str(pytest_demo),
        ]
    )

    output = capsys.readouterr().out

    assert result == 1
    assert "测试状态：failed（测试失败）" in output
    assert "pytest 退出码：1" in output
    assert "1 failed" in output


def test_test_command_reports_no_tests(
    pytest_demo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """没有收集到测试不应该返回成功。"""

    result = cli.main(
        [
            "test",
            "--project",
            str(pytest_demo),
        ]
    )

    output = capsys.readouterr().out

    assert result == 1
    assert "测试状态：no_tests（未发现测试）" in output
    assert "pytest 退出码：5" in output


def test_test_command_runs_specific_file(
    pytest_demo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """指定单个测试文件时不运行其他失败测试。"""

    write_demo_test(
        pytest_demo,
        "test_success.py",
        "def test_success():\n    assert True\n",
    )

    write_demo_test(
        pytest_demo,
        "test_failure.py",
        "def test_failure():\n    assert False\n",
    )

    result = cli.main(
        [
            "test",
            "--project",
            str(pytest_demo),
            "--target",
            "tests/test_success.py",
            "--timeout",
            "30",
        ]
    )

    output = capsys.readouterr().out

    assert result == 0
    assert "1 passed" in output
    assert "测试状态：passed" in output


def test_test_command_rejects_unsafe_target(
    pytest_demo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """不允许通过 CLI 指定 tests 目录以外的目标。"""

    result = cli.main(
        [
            "test",
            "--project",
            str(pytest_demo),
            "--target",
            "../outside.py",
        ]
    )

    captured = capsys.readouterr()

    assert result == 2
    assert "测试参数或目标错误" in captured.err


def test_test_command_rejects_invalid_timeout(
    pytest_demo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """超时时间超出范围时不能启动 pytest。"""

    result = cli.main(
        [
            "test",
            "--project",
            str(pytest_demo),
            "--timeout",
            "121",
        ]
    )

    captured = capsys.readouterr()

    assert result == 2
    assert "超时时间" in captured.err


def test_test_command_reports_timeout(
    pytest_demo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """测试执行超时时，CLI 应显示超时状态。"""

    def fake_run(
        _self: object,
        target: str,
        timeout_seconds: int,
    ) -> RunnerResult:
        return RunnerResult(
            status="timeout",
            exit_code=None,
            stdout="已收集部分测试输出",
            stderr="模拟执行超时",
            duration_seconds=2.0,
            command=("python", "-m", "pytest", target),
        )

    monkeypatch.setattr(
        testing.TestRunner,
        "run",
        fake_run,
    )

    result = cli.main(
        [
            "test",
            "--project",
            str(pytest_demo),
            "--timeout",
            "2",
        ]
    )

    captured = capsys.readouterr()

    assert result == 1
    assert "测试状态：timeout（执行超时）" in captured.out
    assert "pytest 退出码：无" in captured.out
    assert "执行耗时：2.00 秒" in captured.out
    assert "已收集部分测试输出" in captured.out
    assert "模拟执行超时" in captured.err


def test_test_command_reports_execution_error(
    pytest_demo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """测试子进程无法运行时，CLI 应展示错误。"""

    def fake_run(
        _self: object,
        target: str,
        timeout_seconds: int,
    ) -> RunnerResult:
        return RunnerResult(
            status="error",
            exit_code=None,
            stdout="",
            stderr="模拟子进程启动失败",
            duration_seconds=0.1,
            command=("python", "-m", "pytest", target),
        )

    monkeypatch.setattr(
        testing.TestRunner,
        "run",
        fake_run,
    )

    result = cli.main(
        [
            "test",
            "--project",
            str(pytest_demo),
        ]
    )

    captured = capsys.readouterr()

    assert result == 1
    assert "测试状态：error（执行错误）" in captured.out
    assert "模拟子进程启动失败" in captured.err


def test_test_command_help_displays_options(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """test 帮助信息应列出目标与超时参数。"""

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["test", "--help"])

    assert exc_info.value.code == 0

    output = capsys.readouterr().out

    assert "--project" in output
    assert "--target" in output
    assert "--timeout" in output
