"""AI 软件开发智能体统一命令行入口。"""

import argparse

from ai_software_dev_agent import __version__
from ai_software_dev_agent.commands import (
    agent_workflow,
    ask,
    chat,
    edit,
    plan,
    repository,
    testing,
    workflow,
)
from ai_software_dev_agent.model import ModelConfigError
from ai_software_dev_agent.repository import RepositoryError


def build_parser() -> argparse.ArgumentParser:
    """创建顶层解析器，并注册全部命令。"""

    parser = argparse.ArgumentParser(
        prog="ai-dev-agent",
        description="AI Software Development Agent",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    repository.register(subparsers)
    ask.register(subparsers)
    plan.register(subparsers)
    chat.register(subparsers)
    edit.register(subparsers)
    testing.register(subparsers)
    workflow.register(subparsers)

    # Day 09：新增 LangChain Agent + LangGraph 集成命令。
    agent_workflow.register(subparsers)

    return parser


def main(argv: list[str] | None = None) -> int:
    """解析参数并分发给对应的命令处理函数。"""

    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return args.handler(args)

    except (ModelConfigError, RepositoryError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
