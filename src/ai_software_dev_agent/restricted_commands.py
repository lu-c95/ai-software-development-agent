"""Day 13：固定命令白名单、临时工作副本与执行审计。"""

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal

from ai_software_dev_agent.audit_log import AuditLogger
from ai_software_dev_agent.security import (
    ALLOWED_READ_ROOTS,
    PermissionDenied,
    PermissionPolicy,
)

# 仅允许这些检查类型，不接受模型拼接的命令与额外参数。
ALLOWED_CHECKS: dict[str, tuple[str, ...]] = {
    "ruff_check": (
        "-m",
        "ruff",
        "check",
        ".",
    ),
    "ruff_format_check": (
        "-m",
        "ruff",
        "format",
        "--check",
        ".",
    ),
    "pytest": (
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
    ),
}

MAX_COPIED_FILES = 200
MAX_TOTAL_BYTES = 2 * 1024 * 1024
MAX_OUTPUT_CHARS = 4000


class CommandDenied(PermissionError):
    """命令不在白名单中，或缺少必要的人工批准。"""


@dataclass(frozen=True)
class CheckResult:
    """受控检查的执行结果。"""

    check: str
    status: Literal["passed", "failed", "timeout"]
    returncode: int | None
    stdout: str
    stderr: str


class RestrictedCheckRunner:
    """在临时工作副本中运行固定的本地检查。"""

    def __init__(
        self,
        project_root: Path,
        audit_path: Path,
        timeout_seconds: int = 30,
    ) -> None:
        """初始化可信项目路径、审计日志与时间限制。"""

        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, int)
            or not 1 <= timeout_seconds <= 120
        ):
            raise ValueError("超时时间必须是 1～120 秒的整数")

        self.policy = PermissionPolicy(project_root)
        self.audit = AuditLogger(
            audit_path,
            self.policy.project_root,
        )
        self.timeout_seconds = timeout_seconds

    def _candidate_files(self):
        """遍历候选文件，不跟随目录符号链接。"""

        root = self.policy.project_root

        for name in ALLOWED_READ_ROOTS:
            source = root / name

            if source.is_symlink():
                continue

            if source.is_file():
                yield source
                continue

            if not source.is_dir():
                continue

            for current_root, directories, filenames in os.walk(
                source,
                followlinks=False,
            ):
                current = Path(current_root)

                # 原地修改目录列表，阻止进入隐藏目录或符号链接。
                directories[:] = sorted(
                    directory
                    for directory in directories
                    if not directory.startswith(".")
                    and not (current / directory).is_symlink()
                )

                for filename in sorted(filenames):
                    candidate = current / filename

                    if candidate.is_symlink() or not candidate.is_file():
                        continue

                    yield candidate

    def _create_snapshot(self, destination: Path) -> int:
        """仅复制经过授权的文本文件到临时工作副本。"""

        root = self.policy.project_root
        copied = 0
        total_bytes = 0

        for source in self._candidate_files():
            relative_path = source.relative_to(root).as_posix()

            try:
                # 与 Day 13 第一阶段共用同一权限策略。
                content = self.policy.read_text(relative_path)

            except (PermissionDenied, FileNotFoundError):
                # 敏感、无授权或不适合读取的文件不进入副本。
                continue

            size = len(content.encode("utf-8"))

            # 超过副本资源预算时终止，不静默截断。
            if copied >= MAX_COPIED_FILES or total_bytes + size > MAX_TOTAL_BYTES:
                raise ValueError("临时工作副本超出文件数量或大小限制")

            target = destination / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

            copied += 1
            total_bytes += size

        if copied == 0:
            raise ValueError("没有可用于执行检查的授权文件")

        return copied

    @staticmethod
    def _child_environment(workspace: Path) -> dict[str, str]:
        """创建受控子进程环境，统一使用中国大陆时区。"""

        return {
            "PATH": (str(Path(sys.executable).parent) + os.pathsep + "/usr/bin:/bin"),
            # 临时工作目录，避免默认使用用户真实主目录。
            "HOME": str(workspace),
            "TMPDIR": str(workspace),
            # 统一采用北京时间。
            "TZ": "Asia/Shanghai",
            # 确保 Python 输出使用 UTF-8，正确处理简体中文。
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
            # 不生成 .pyc 文件。
            "PYTHONDONTWRITEBYTECODE": "1",
            # 禁止 pytest 自动加载第三方插件。
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        }

    def run_check(
        self,
        check_name: str,
        *,
        human_approved: bool = False,
    ) -> CheckResult:
        """按白名单运行检查，记录结果并清理临时副本。"""

        # 未知命令一律拒绝，也不把原始未知输入写入日志。
        if check_name not in ALLOWED_CHECKS:
            self.audit.record(
                "unknown",
                "denied",
                reason="not_allowlisted",
            )
            raise CommandDenied("检查类型不在命令白名单中")

        # pytest 会运行项目代码，不能自动开放给模型。
        if check_name == "pytest" and human_approved is not True:
            self.audit.record(
                check_name,
                "denied",
                reason="approval_required",
            )
            raise CommandDenied("pytest 需要人工明确批准")

        command = [
            sys.executable,
            *ALLOWED_CHECKS[check_name],
        ]

        try:
            with TemporaryDirectory(prefix="agent-day13-") as temp:
                workspace = Path(temp) / "workspace"
                workspace.mkdir()

                # 检查在副本上进行，不直接写入原项目。
                self._create_snapshot(workspace)

                self.audit.record(
                    check_name,
                    "started",
                )

                try:
                    completed = subprocess.run(
                        command,
                        cwd=workspace,
                        env=self._child_environment(workspace),
                        stdin=subprocess.DEVNULL,
                        capture_output=True,
                        text=True,
                        timeout=self.timeout_seconds,
                        check=False,
                        shell=False,
                    )

                except subprocess.TimeoutExpired:
                    self.audit.record(
                        check_name,
                        "timeout",
                        reason="time_limit",
                    )

                    return CheckResult(
                        check=check_name,
                        status="timeout",
                        returncode=None,
                        stdout="",
                        stderr="检查超时，已终止直接子进程。",
                    )

                # 非零返回码表示检查没有通过，不等于权限拒绝。
                status: Literal["passed", "failed"] = (
                    "passed" if completed.returncode == 0 else "failed"
                )

                self.audit.record(
                    check_name,
                    "finished",
                    returncode=completed.returncode,
                )

                return CheckResult(
                    check=check_name,
                    status=status,
                    returncode=completed.returncode,
                    stdout=completed.stdout[:MAX_OUTPUT_CHARS],
                    stderr=completed.stderr[:MAX_OUTPUT_CHARS],
                )

        except (OSError, ValueError) as exc:
            # 只记录异常类型，避免把异常文本中的路径或信息泄露。
            self.audit.record(
                check_name,
                "error",
                reason=type(exc).__name__,
            )
            raise
