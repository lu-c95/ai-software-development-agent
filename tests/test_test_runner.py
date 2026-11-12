"""Test Runner 的执行结果、路径限制与超时测试。"""

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from ai_software_dev_agent.test_runner import (
    MAX_OUTPUT_CHARS,
)
from ai_software_dev_agent.test_runner import (
    TestRunner as Runner,
)
from ai_software_dev_agent.test_runner import (
    TestRunnerError as RunnerError,
)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """创建一个带 tests 目录的独立项目。"""

    (tmp_path / "tests").mkdir()
    return tmp_path


def write_test(
    project: Path,
    filename: str,
    source: str,
) -> Path:
    """在临时项目中创建测试文件。"""

    target = project / "tests" / filename
    target.write_text(source, encoding="utf-8")
    return target


def test_runner_reports_passed(project: Path) -> None:
    """pytest 成功时，返回 passed 和退出码 0。"""

    write_test(
        project,
        "test_math.py",
        "def test_add():\n    assert 1 + 1 == 2\n",
    )

    runner = Runner(project)
    result = runner.run()

    assert result.status == "passed"
    assert result.passed is True
    assert result.exit_code == 0
    assert "1 passed" in result.stdout
    assert result.duration_seconds >= 0


def test_runner_reports_failed(project: Path) -> None:
    """断言失败时，应返回 failed 而不是抛出异常。"""

    write_test(
        project,
        "test_math.py",
        "def test_add():\n    assert 1 + 1 == 3\n",
    )

    runner = Runner(project)
    result = runner.run()

    assert result.status == "failed"
    assert result.passed is False
    assert result.exit_code == 1
    assert "1 failed" in result.stdout


def test_runner_reports_no_tests(project: Path) -> None:
    """没有测试时，不能错误地报告通过。"""

    runner = Runner(project)
    result = runner.run()

    assert result.status == "no_tests"
    assert result.passed is False
    assert result.exit_code == 5


def test_runner_runs_specific_test_file(project: Path) -> None:
    """指定测试文件时，不应运行其他测试文件。"""

    write_test(
        project,
        "test_success.py",
        "def test_success():\n    assert True\n",
    )

    write_test(
        project,
        "test_failure.py",
        "def test_failure():\n    assert False\n",
    )

    runner = Runner(project)

    result = runner.run(
        target="tests/test_success.py",
    )

    assert result.passed is True
    assert result.exit_code == 0
    assert result.command[-1] == "tests/test_success.py"


@pytest.mark.parametrize(
    "target",
    [
        "../outside.py",
        "/tmp/outside.py",
        "tests/../outside.py",
        "src/test_other.py",
        "",
    ],
)
def test_runner_rejects_unsafe_target(
    project: Path,
    target: str,
) -> None:
    """拒绝仓库外路径和不属于 tests 的目标。"""

    runner = Runner(project)

    with pytest.raises(RunnerError):
        runner.run(target=target)


def test_runner_rejects_missing_target(
    project: Path,
) -> None:
    """测试目标不存在时，不应启动 pytest。"""

    runner = Runner(project)

    with pytest.raises(
        RunnerError,
        match="测试目标不存在",
    ):
        runner.run(target="tests/test_missing.py")


def test_runner_rejects_non_test_file(
    project: Path,
) -> None:
    """不能将普通 Python 文件直接作为测试目标。"""

    write_test(
        project,
        "helper.py",
        "value = 42\n",
    )

    runner = Runner(project)

    with pytest.raises(
        RunnerError,
        match="test_",
    ):
        runner.run(target="tests/helper.py")


def test_runner_rejects_symlink(
    project: Path,
) -> None:
    """测试目标路径不能经过符号链接。"""

    real_file = write_test(
        project,
        "test_real.py",
        "def test_real():\n    assert True\n",
    )

    link = project / "tests" / "test_link.py"
    link.symlink_to(real_file)

    runner = Runner(project)

    with pytest.raises(
        RunnerError,
        match="符号链接",
    ):
        runner.run(target="tests/test_link.py")


def test_runner_rejects_missing_tests_directory(
    tmp_path: Path,
) -> None:
    """没有 tests 目录时，创建执行器就应失败。"""

    with pytest.raises(
        RunnerError,
        match="tests 目录",
    ):
        Runner(tmp_path)


@pytest.mark.parametrize(
    "timeout",
    [0, -1, 121, True],
)
def test_runner_rejects_invalid_timeout(
    project: Path,
    timeout: Any,
) -> None:
    """超时时间必须是规定范围内的整数。"""

    runner = Runner(project)

    with pytest.raises(
        RunnerError,
        match="超时时间",
    ):
        runner.run(timeout_seconds=timeout)


def test_runner_reports_timeout(
    project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """超时时应返回 timeout，并保留已有输出。"""

    def fake_run(
        *args: Any,
        **kwargs: Any,
    ) -> None:
        raise subprocess.TimeoutExpired(
            cmd=args[0],
            timeout=kwargs["timeout"],
            output=b"partial output",
            stderr=b"execution timed out",
        )

    monkeypatch.setattr(
        "ai_software_dev_agent.test_runner.subprocess.run",
        fake_run,
    )

    runner = Runner(project)
    result = runner.run(timeout_seconds=2)

    assert result.status == "timeout"
    assert result.passed is False
    assert result.exit_code is None
    assert "partial output" in result.stdout
    assert "execution timed out" in result.stderr


def test_runner_reports_process_start_error(
    project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """子进程无法启动时应返回 error。"""

    def fake_run(
        *args: Any,
        **kwargs: Any,
    ) -> None:
        raise OSError("模拟子进程启动失败")

    monkeypatch.setattr(
        "ai_software_dev_agent.test_runner.subprocess.run",
        fake_run,
    )

    runner = Runner(project)
    result = runner.run()

    assert result.status == "error"
    assert result.exit_code is None
    assert "模拟子进程启动失败" in result.stderr


def test_runner_uses_fixed_pytest_command(
    project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """使用固定的命令参数，不经过 Shell。"""

    captured: dict[str, Any] = {}

    def fake_run(
        command: tuple[str, ...],
        **kwargs: Any,
    ) -> subprocess.CompletedProcess[str]:
        captured["command"] = command
        captured["kwargs"] = kwargs

        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout="1 passed",
            stderr="",
        )

    monkeypatch.setenv(
        "PYTEST_ADDOPTS",
        "--maxfail=1",
    )
    monkeypatch.setenv(
        "PYTEST_PLUGINS",
        "some_plugin",
    )

    monkeypatch.setattr(
        "ai_software_dev_agent.test_runner.subprocess.run",
        fake_run,
    )

    runner = Runner(project)
    result = runner.run()

    assert result.passed is True

    assert captured["command"] == (
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "--",
        "tests",
    )

    options = captured["kwargs"]

    assert options["shell"] is False
    assert options["cwd"] == project.resolve()
    assert options["stdin"] == subprocess.DEVNULL
    assert "PYTEST_ADDOPTS" not in options["env"]
    assert "PYTEST_PLUGINS" not in options["env"]


def test_runner_truncates_large_output(
    project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """输出过长时，保留结尾的 pytest 总结。"""

    def fake_run(
        command: tuple[str, ...],
        **kwargs: Any,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout="x" * 20_000 + "\n1 passed\n",
            stderr="",
        )

    monkeypatch.setattr(
        "ai_software_dev_agent.test_runner.subprocess.run",
        fake_run,
    )

    runner = Runner(project)
    result = runner.run()

    assert result.status == "passed"
    assert result.stdout.startswith("[输出已截断")
    assert result.stdout.endswith("1 passed\n")
    assert len(result.stdout) < MAX_OUTPUT_CHARS + 100
