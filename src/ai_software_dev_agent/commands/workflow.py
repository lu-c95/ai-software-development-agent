"""LangGraph 开发工作流的 CLI 命令。"""

import argparse
import sys
from pathlib import Path
from typing import Any

from ai_software_dev_agent.commands._common import add_project_argument
from ai_software_dev_agent.repository import RepositoryError
from ai_software_dev_agent.test_runner import (
    DEFAULT_TIMEOUT_SECONDS,
    TestRunnerError,
    TestRunResult,
)
from ai_software_dev_agent.workflow import (
    DevelopmentWorkflowState,
    build_development_workflow,
)


def run_workflow_command(
    project: Path,
    target: str,
    timeout_seconds: int,
) -> int:
    """逐节点执行工作流，展示进度与最终测试状态。"""

    # 1. 准备 LangGraph 的初始共享状态。
    initial_state: DevelopmentWorkflowState = {
        "project": str(project.expanduser().resolve()),
        "target": target,
        "timeout_seconds": timeout_seconds,
        "completed_steps": [],
    }

    # 2. 构建已经在 Day 08 第一阶段实现的工作流。
    graph = build_development_workflow()

    completed_nodes: list[str] = []
    test_result: TestRunResult | None = None
    summary: str | None = None

    print("开始执行 LangGraph 开发工作流...")
    print(f"项目目录：{initial_state['project']}")
    print(f"测试目标：{target}")
    print()

    try:
        # updates 模式会在每个节点完成后，返回该节点的状态更新。
        for event in graph.stream(
            initial_state,
            stream_mode="updates",
        ):
            for node_name, update in event.items():
                # 本阶段的图固定有三个业务节点。
                if node_name not in {
                    "inspect_repository",
                    "run_tests",
                    "summarize",
                }:
                    continue

                completed_nodes.append(node_name)

                print(
                    f"[{len(completed_nodes)}/3] {node_name} 已完成",
                    flush=True,
                )

                if node_name == "inspect_repository":
                    files = update["files"]
                    print(f"      发现 {len(files)} 个可探索文件")

                elif node_name == "run_tests":
                    test_result = update["test_result"]
                    print(f"      pytest 状态：{test_result.status}")

                elif node_name == "summarize":
                    summary = update["summary"]

    except (RepositoryError, TestRunnerError) as exc:
        # 项目或测试目标不合法，属于输入/参数问题。
        print(
            f"工作流参数或目标错误：{exc}",
            file=sys.stderr,
        )
        return 2

    except OSError as exc:
        # 文件系统等执行错误，不应被报告为测试通过。
        print(
            f"工作流执行错误：{exc}",
            file=sys.stderr,
        )
        return 1

    # 3. 只有取得测试结果和摘要，才认为流程执行完整。
    if test_result is None or summary is None:
        print(
            "工作流执行不完整：缺少测试结果或总结。",
            file=sys.stderr,
        )
        return 1

    print("\n=== 工作流总结 ===")
    print(summary)

    print("\n=== 执行信息 ===")
    print(f"已完成节点：{len(completed_nodes)}/3")
    print(f"pytest 状态：{test_result.status}")

    exit_code = (
        str(test_result.exit_code) if test_result.exit_code is not None else "无"
    )

    print(f"pytest 退出码：{exit_code}")

    # 测试未通过时展示 pytest 输出，帮助分析失败原因。
    if not test_result.passed:
        if test_result.stdout:
            print("\n=== pytest 输出 ===")
            print(test_result.stdout)

        if test_result.stderr:
            print(
                "\n=== pytest 错误输出 ===",
                file=sys.stderr,
            )
            print(test_result.stderr, file=sys.stderr)

    # CLI 退出码必须能让未来的工作流识别测试失败。
    return 0 if test_result.passed else 1


def run_workflow(args: argparse.Namespace) -> int:
    """将 argparse 参数交给工作流命令。"""

    return run_workflow_command(
        project=args.project,
        target=args.target,
        timeout_seconds=args.timeout,
    )


def register(subparsers: Any) -> None:
    """向统一 CLI 注册 workflow 子命令。"""

    parser = subparsers.add_parser(
        "workflow",
        help="运行 LangGraph 仓库检查与测试工作流",
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
        help="pytest 超时秒数，范围 1～120，默认 30",
    )

    parser.set_defaults(handler=run_workflow)
