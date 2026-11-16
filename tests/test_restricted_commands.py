"""Day 13：命令限制、操作副本与审计日志测试。"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from ai_software_dev_agent.restricted_commands import (
    CommandDenied,
    RestrictedCheckRunner,
)


@pytest.fixture
def workspace(tmp_path: Path) -> tuple[Path, Path]:
    """准备项目目录和仓库外的审计日志路径。"""

    project = tmp_path / "project"
    project.mkdir()

    (project / "src").mkdir()
    (project / "tests").mkdir()

    (project / "src" / "app.py").write_text(
        "answer = 42\n",
        encoding="utf-8",
    )

    (project / "tests" / "test_app.py").write_text(
        "def test_answer():\n    assert 42 == 42\n",
        encoding="utf-8",
    )

    (project / "README.md").write_text(
        "# Demo\n",
        encoding="utf-8",
    )

    # 构造虚假的敏感信息，不能使用真实 Token。
    (project / ".env").write_text(
        "API_KEY=demo-secret\n",
        encoding="utf-8",
    )

    (project / "src" / "credentials.json").write_text(
        '{"token": "demo-secret"}',
        encoding="utf-8",
    )

    audit_path = tmp_path / "audit" / "events.jsonl"

    return project, audit_path


def read_audit(path: Path) -> list[dict[str, Any]]:
    """读取 JSONL 审计事件。"""

    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_unknown_command_is_denied(
    workspace: tuple[Path, Path],
) -> None:
    """没有列入白名单的命令必须拒绝。"""

    project, audit_path = workspace

    runner = RestrictedCheckRunner(project, audit_path)

    with pytest.raises(
        CommandDenied,
        match="命令白名单",
    ):
        runner.run_check("rm -rf /")

    events = read_audit(audit_path)

    assert len(events) == 1
    assert events[0]["operation"] == "unknown"
    assert events[0]["outcome"] == "denied"
    assert events[0]["reason"] == "not_allowlisted"


def test_pytest_requires_approval(
    workspace: tuple[Path, Path],
) -> None:
    """没有人工批准的 pytest 必须拒绝。"""

    project, audit_path = workspace

    runner = RestrictedCheckRunner(project, audit_path)

    with pytest.raises(
        CommandDenied,
        match="人工明确批准",
    ):
        runner.run_check("pytest")

    events = read_audit(audit_path)

    assert events[0]["operation"] == "pytest"
    assert events[0]["outcome"] == "denied"
    assert events[0]["reason"] == "approval_required"


def test_ruff_runs_inside_temporary_snapshot(
    workspace: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ruff 的工作目录必须是临时副本，而非原项目。"""

    project, audit_path = workspace

    observed: dict[str, Any] = {}

    def fake_run(command: list[str], **kwargs: Any) -> Any:
        cwd = Path(kwargs["cwd"])

        observed["cwd"] = cwd
        observed["command"] = command
        observed["shell"] = kwargs["shell"]

        assert cwd != project
        assert (cwd / "src" / "app.py").is_file()
        assert (cwd / "README.md").is_file()

        # 敏感文件没有被复制到临时工作副本。
        assert not (cwd / ".env").exists()
        assert not (cwd / "src" / "credentials.json").exists()

        # 模拟检查命令在副本中发生写入。
        (cwd / "src" / "app.py").write_text(
            "answer = 999\n",
            encoding="utf-8",
        )

        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout="All checks passed!\n",
            stderr="",
        )

    monkeypatch.setattr(
        "ai_software_dev_agent.restricted_commands.subprocess.run",
        fake_run,
    )

    runner = RestrictedCheckRunner(project, audit_path)

    result = runner.run_check("ruff_check")

    assert result.status == "passed"
    assert result.returncode == 0
    assert "All checks passed" in result.stdout

    assert observed["shell"] is False
    assert observed["command"] == [
        sys.executable,
        "-m",
        "ruff",
        "check",
        ".",
    ]

    # 原始项目文件必须保持不变。
    assert (project / "src" / "app.py").read_text(encoding="utf-8") == "answer = 42\n"

    # run_check 返回时，TemporaryDirectory 已经清理。
    assert not observed["cwd"].exists()

    events = read_audit(audit_path)
    assert [event["outcome"] for event in events] == [
        "started",
        "finished",
    ]


def test_format_check_uses_fixed_arguments(
    workspace: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ruff 格式检查不能携带额外修改参数。"""

    project, audit_path = workspace

    observed: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: Any) -> Any:
        observed.append(command)

        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(
        "ai_software_dev_agent.restricted_commands.subprocess.run",
        fake_run,
    )

    runner = RestrictedCheckRunner(project, audit_path)

    result = runner.run_check("ruff_format_check")

    assert result.status == "passed"
    assert observed == [
        [
            sys.executable,
            "-m",
            "ruff",
            "format",
            "--check",
            ".",
        ]
    ]


def test_approved_pytest_uses_fixed_arguments(
    workspace: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """只有显式批准后才能调用固定的 pytest 检查。"""

    project, audit_path = workspace

    observed: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: Any) -> Any:
        observed.append(command)

        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout="1 passed\n",
            stderr="",
        )

    monkeypatch.setattr(
        "ai_software_dev_agent.restricted_commands.subprocess.run",
        fake_run,
    )

    runner = RestrictedCheckRunner(project, audit_path)

    result = runner.run_check(
        "pytest",
        human_approved=True,
    )

    assert result.status == "passed"

    assert observed == [
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
        ]
    ]


def test_failed_check_is_audited(
    workspace: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """检查返回非零退出码时必须记录失败结果。"""

    project, audit_path = workspace

    def fake_run(command: list[str], **kwargs: Any) -> Any:
        return subprocess.CompletedProcess(
            args=command,
            returncode=1,
            stdout="Found errors\n",
            stderr="",
        )

    monkeypatch.setattr(
        "ai_software_dev_agent.restricted_commands.subprocess.run",
        fake_run,
    )

    runner = RestrictedCheckRunner(project, audit_path)

    result = runner.run_check("ruff_check")

    assert result.status == "failed"
    assert result.returncode == 1

    events = read_audit(audit_path)

    assert events[-1]["outcome"] == "finished"
    assert events[-1]["returncode"] == 1


def test_timeout_is_audited(
    workspace: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """超时必须返回明确状态并写入审计日志。"""

    project, audit_path = workspace

    def fake_run(command: list[str], **kwargs: Any) -> Any:
        raise subprocess.TimeoutExpired(
            cmd=command,
            timeout=kwargs["timeout"],
        )

    monkeypatch.setattr(
        "ai_software_dev_agent.restricted_commands.subprocess.run",
        fake_run,
    )

    runner = RestrictedCheckRunner(
        project,
        audit_path,
        timeout_seconds=5,
    )

    result = runner.run_check("ruff_check")

    assert result.status == "timeout"
    assert result.returncode is None

    events = read_audit(audit_path)

    assert events[-1]["outcome"] == "timeout"
    assert events[-1]["reason"] == "time_limit"


def test_child_environment_excludes_api_keys(
    workspace: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """不把父进程的 API Key 传给检查进程。"""

    project, audit_path = workspace

    monkeypatch.setenv(
        "OPENAI_API_KEY",
        "demo-secret-value",
    )

    def fake_run(command: list[str], **kwargs: Any) -> Any:
        environment = kwargs["env"]

        assert "OPENAI_API_KEY" not in environment
        assert "PYTHONPATH" not in environment
        assert environment["PYTHONDONTWRITEBYTECODE"] == "1"

        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(
        "ai_software_dev_agent.restricted_commands.subprocess.run",
        fake_run,
    )

    runner = RestrictedCheckRunner(project, audit_path)

    assert runner.run_check("ruff_check").status == "passed"


def test_audit_does_not_contain_sensitive_content(
    workspace: tuple[Path, Path],
) -> None:
    """审计记录不应保存凭据、源码或任意原始命令。"""

    project, audit_path = workspace

    runner = RestrictedCheckRunner(project, audit_path)

    with pytest.raises(CommandDenied):
        runner.run_check("secret-token-123")

    content = audit_path.read_text(encoding="utf-8")

    assert "secret-token-123" not in content
    assert "demo-secret" not in content
    assert "answer = 42" not in content


def test_audit_cannot_be_written_inside_project(
    workspace: tuple[Path, Path],
) -> None:
    """审计日志路径必须位于项目目录外。"""

    project, _ = workspace

    with pytest.raises(
        ValueError,
        match="项目目录之外",
    ):
        RestrictedCheckRunner(
            project,
            project / "src" / "audit.jsonl",
        )


@pytest.mark.parametrize(
    "timeout_seconds",
    [
        0,
        -1,
        True,
        121,
    ],
)
def test_invalid_timeout_is_rejected(
    workspace: tuple[Path, Path],
    timeout_seconds: int,
) -> None:
    """超时时间必须位于允许范围内。"""

    project, audit_path = workspace

    with pytest.raises(
        ValueError,
        match="1～120 秒",
    ):
        RestrictedCheckRunner(
            project,
            audit_path,
            timeout_seconds=timeout_seconds,
        )


def test_audit_timestamp_uses_beijing_time(
    workspace: tuple[Path, Path],
) -> None:
    """验证审计日志采用北京时间，并精确到三位毫秒。"""

    project, audit_path = workspace

    runner = RestrictedCheckRunner(project, audit_path)

    with pytest.raises(CommandDenied):
        runner.run_check("unknown-operation")

    events = read_audit(audit_path)

    assert len(events) == 1

    timestamp = events[0]["timestamp"]

    # 必须符合 YYYY-MM-DD HH:MM:SS.SSS 格式。
    assert len(timestamp) == 23
    assert timestamp[19] == "."
    assert timestamp[20:23].isdigit()

    # 验证时间字符串能够被 Python 正确解析。
    parsed_time = datetime.strptime(
        timestamp,
        "%Y-%m-%d %H:%M:%S.%f",
    )

    assert parsed_time.year > 2000
    assert events[0]["timezone"] == "Asia/Shanghai"
