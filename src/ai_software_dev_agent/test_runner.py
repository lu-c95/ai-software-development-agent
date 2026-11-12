"""受控执行 pytest，并返回结构化测试结果。"""

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

# 默认运行时间为 30 秒，最多允许 120 秒。
DEFAULT_TIMEOUT_SECONDS = 30
MAX_TIMEOUT_SECONDS = 120

# 控制最终展示的输出长度，保留结尾的 pytest 汇总。
MAX_OUTPUT_CHARS = 16_000

TestStatus = Literal[
    "passed",
    "failed",
    "no_tests",
    "error",
    "timeout",
]


class TestRunnerError(ValueError):
    """测试执行参数或目标仓库不符合要求。"""


@dataclass(frozen=True)
class TestRunResult:
    """一次 pytest 执行产生的结构化结果。"""

    status: TestStatus
    exit_code: int | None
    stdout: str
    stderr: str
    duration_seconds: float
    command: tuple[str, ...]

    @property
    def passed(self) -> bool:
        """只有 pytest 退出码为 0 才表示通过。"""

        return self.status == "passed"


class TestRunner:
    """只允许在指定项目的 tests 目录内执行 pytest。"""

    def __init__(self, project: Path) -> None:
        root = project.expanduser().resolve()

        if not root.is_dir():
            raise TestRunnerError("项目目录不存在或不是目录")

        tests_root = root / "tests"

        if tests_root.is_symlink() or not tests_root.is_dir():
            raise TestRunnerError("项目必须包含非符号链接的 tests 目录")

        self.root = root
        self.tests_root = tests_root

    def _validate_target(self, target: str) -> str:
        """仅允许选择 tests 目录内的测试文件或子目录。"""

        if not target.strip():
            raise TestRunnerError("测试目标路径不能为空")

        relative = Path(target)

        if (
            relative.is_absolute()
            or ".." in relative.parts
            or not relative.parts
            or relative.parts[0] != "tests"
            or any(part.startswith(".") for part in relative.parts)
        ):
            raise TestRunnerError("测试目标必须是 tests 目录内的相对路径")

        current = self.root

        # 拒绝路径任意组成部分为符号链接。
        for part in relative.parts:
            current = current / part

            if current.is_symlink():
                raise TestRunnerError("测试目标路径不允许包含符号链接")

        resolved = current.resolve()

        if not resolved.is_relative_to(self.tests_root):
            raise TestRunnerError("测试目标超出 tests 目录")

        if not resolved.exists():
            raise TestRunnerError("指定的测试目标不存在")

        if resolved.is_file():
            # 当前只允许直接选择 pytest 命名规范的测试文件。
            if not resolved.name.startswith("test_") or resolved.suffix != ".py":
                raise TestRunnerError("仅允许选择 test_*.py 测试文件")

        elif not resolved.is_dir():
            raise TestRunnerError("测试目标必须是普通文件或目录")

        return relative.as_posix()

    @staticmethod
    def _limit_output(output: str | bytes | None) -> str:
        """规范化输出，并保留过长输出的末尾部分。"""

        if output is None:
            return ""

        # TimeoutExpired 捕获的输出可能仍然是 bytes。
        if isinstance(output, bytes):
            output = output.decode(
                "utf-8",
                errors="replace",
            )

        if len(output) <= MAX_OUTPUT_CHARS:
            return output

        omitted = len(output) - MAX_OUTPUT_CHARS

        return f"[输出已截断，省略前 {omitted} 个字符]\n{output[-MAX_OUTPUT_CHARS:]}"

    def run(
        self,
        target: str = "tests",
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> TestRunResult:
        """运行指定 pytest 目标，返回结果而非直接抛出测试失败。"""

        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, int)
            or not 1 <= timeout_seconds <= MAX_TIMEOUT_SECONDS
        ):
            raise TestRunnerError("超时时间必须是 1～120 秒之间的整数")

        safe_target = self._validate_target(target)

        # 固定命令格式，不允许用户传入任意 Shell 命令。
        command = (
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "--",
            safe_target,
        )

        # 去掉会额外改变 pytest 命令行行为的环境选项。
        # 这不是完整的进程或环境隔离。
        env = os.environ.copy()
        env.pop("PYTEST_ADDOPTS", None)
        env.pop("PYTEST_PLUGINS", None)

        started = time.perf_counter()

        try:
            completed = subprocess.run(
                command,
                cwd=self.root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
                stdin=subprocess.DEVNULL,
                check=False,
                shell=False,
                env=env,
            )

        except subprocess.TimeoutExpired as exc:
            elapsed = time.perf_counter() - started

            return TestRunResult(
                status="timeout",
                exit_code=None,
                stdout=self._limit_output(exc.stdout),
                stderr=self._limit_output(exc.stderr),
                duration_seconds=elapsed,
                command=command,
            )

        except OSError as exc:
            elapsed = time.perf_counter() - started

            return TestRunResult(
                status="error",
                exit_code=None,
                stdout="",
                stderr=str(exc),
                duration_seconds=elapsed,
                command=command,
            )

        elapsed = time.perf_counter() - started

        # pytest 的退出码与结果状态明确对应。
        if completed.returncode == 0:
            status: TestStatus = "passed"
        elif completed.returncode == 1:
            status = "failed"
        elif completed.returncode == 5:
            status = "no_tests"
        else:
            status = "error"

        return TestRunResult(
            status=status,
            exit_code=completed.returncode,
            stdout=self._limit_output(completed.stdout),
            stderr=self._limit_output(completed.stderr),
            duration_seconds=elapsed,
            command=command,
        )
