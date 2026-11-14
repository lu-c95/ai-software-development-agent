"""Day 10：条件路由与错误恢复工作流的 CLI 命令。"""

import argparse
import sys
from typing import Any

from ai_software_dev_agent.commands._common import add_project_argument
from ai_software_dev_agent.conditional_workflow import (
    MAX_ALLOWED_RETRIES,
    run_conditional_workflow,
)


def run_conditional_workflow_command(
    args: argparse.Namespace,
) -> int:
    """运行条件工作流，并根据最终状态返回退出码。"""

    try:
        result = run_conditional_workflow(
            project=args.project,
            target=args.target,
            timeout_seconds=args.timeout,
            max_retries=args.max_retries,
        )

    except ValueError as exc:
        print(f"参数错误：{exc}", file=sys.stderr)
        return 2

    except KeyboardInterrupt:
        print("\n用户已中断工作流。", file=sys.stderr)
        return 130

    except Exception as exc:
        # CLI 边界允许统一报告异常，但不能把异常伪装成测试通过。
        print(
            f"条件工作流执行失败：{type(exc).__name__}：{exc}",
            file=sys.stderr,
        )
        return 1

    status = result["status"]
    completed_steps = result["completed_steps"]

    print("\n=== Day 10 条件工作流结果 ===")
    print(f"项目：{result['project']}")
    print(f"测试目标：{result['target']}")
    print(f"测试状态：{status}")
    print(f"已重试：{result['retry_count']} 次")
    print(f"执行路径：{' → '.join(completed_steps)}")
    print()
    print(result["summary"])

    # 发生失败时，提供有限长度的 pytest 输出辅助排查。
    test_result = result.get("test_result")

    if status != "passed" and test_result is not None:
        for stream_name in ("stdout", "stderr"):
            content = getattr(test_result, stream_name, "")

            if content:
                print(f"\n--- pytest {stream_name}（末尾 1500 字符）---")
                print(str(content)[-1500:])

    if status == "passed":
        return 0

    # 未通过、无测试、超时及错误都不能返回成功退出码。
    return 1


def register(subparsers: Any) -> None:
    """注册 conditional-workflow 子命令。"""

    parser = subparsers.add_parser(
        "conditional-workflow",
        help="执行带条件路由和有界超时重试的 pytest 工作流",
    )

    add_project_argument(parser)

    parser.add_argument(
        "--target",
        default="tests",
        help="pytest 测试目标，默认 tests",
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="每次 pytest 执行的超时时间（秒），默认 60",
    )

    parser.add_argument(
        "--max-retries",
        type=int,
        choices=range(MAX_ALLOWED_RETRIES + 1),
        default=0,
        help="超时后额外重试次数，可选 0、1、2，默认 0",
    )

    parser.set_defaults(handler=run_conditional_workflow_command)
