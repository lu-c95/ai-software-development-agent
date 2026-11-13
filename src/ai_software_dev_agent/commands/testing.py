"""pytest 测试执行 CLI 命令。"""

import argparse
import sys
from pathlib import Path
from typing import Any

from ai_software_dev_agent.commands._common import add_project_argument
from ai_software_dev_agent.test_runner import (
    DEFAULT_TIMEOUT_SECONDS,
    TestRunner,
    TestRunnerError,
)


def run_test_command(
    project: Path,
    target: str,
    timeout_seconds: int,
) -> int:
    """执行 pytest 并展示结构化结果。"""

    try:
        runner = TestRunner(project)

        result = runner.run(
            target=target,
            timeout_seconds=timeout_seconds,
        )

    except (TestRunnerError, OSError) as exc:
        print(
            f"测试参数或目标错误：{exc}",
            file=sys.stderr,
        )
        return 2

    status_labels = {
        "passed": "通过",
        "failed": "测试失败",
        "no_tests": "未发现测试",
        "error": "执行错误",
        "timeout": "执行超时",
    }

    status_label = status_labels[result.status]

    print(f"测试状态：{result.status}（{status_label}）")

    exit_code = str(result.exit_code) if result.exit_code is not None else "无"

    print(f"pytest 退出码：{exit_code}")
    print(f"执行耗时：{result.duration_seconds:.2f} 秒")

    if result.stdout:
        print("\n=== pytest 标准输出 ===")
        print(
            result.stdout,
            end="" if result.stdout.endswith("\n") else "\n",
        )

    if result.stderr:
        print("\n=== pytest 错误输出 ===", file=sys.stderr)
        print(
            result.stderr,
            end="" if result.stderr.endswith("\n") else "\n",
            file=sys.stderr,
        )

    return 0 if result.passed else 1


def run_test(args: argparse.Namespace) -> int:
    """适配 argparse 参数与 TestRunner 调用。"""

    return run_test_command(
        project=args.project,
        target=args.target,
        timeout_seconds=args.timeout,
    )


def register(subparsers: Any) -> None:
    """注册 test 子命令。"""

    parser = subparsers.add_parser(
        "test",
        help="在指定项目中受控执行 pytest",
    )

    add_project_argument(parser)

    parser.add_argument(
        "--target",
        default="tests",
        help="tests 目录或其中的 test_*.py 文件",
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="执行超时秒数，范围 1～120，默认 30",
    )

    parser.set_defaults(handler=run_test)
