"""AI 软件开发智能体的命令行入口。"""

import argparse
import sys
from pathlib import Path

from openai import APIStatusError, OpenAIError

from ai_software_dev_agent import __version__
from ai_software_dev_agent.model import (
    ModelConfigError,
    create_chat_model,
    generate_answer,
    load_model_settings,
)
from ai_software_dev_agent.repository import RepositoryError, RepositoryExplorer


def build_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器。"""

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

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="检查目标项目目录",
    )

    inspect_parser = subparsers.add_parser(
        "inspect",
        help="列出项目中的代码文件",
    )

    read_parser = subparsers.add_parser(
        "read",
        help="读取指定代码文件",
    )

    search_parser = subparsers.add_parser(
        "search",
        help="搜索代码关键词",
    )

    # Day 03：新增模型问答命令。
    ask_parser = subparsers.add_parser(
        "ask",
        help="使用 LangChain 调用聊天模型",
    )

    # 仓库相关命令共用项目目录参数。
    for command_parser in (
        doctor_parser,
        inspect_parser,
        read_parser,
        search_parser,
    ):
        command_parser.add_argument(
            "--project",
            type=Path,
            default=Path.cwd(),
            help="目标项目目录",
        )

    read_parser.add_argument(
        "--path",
        required=True,
        help="相对项目根目录的文件路径",
    )

    search_parser.add_argument(
        "--query",
        required=True,
        help="搜索关键词",
    )

    search_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="最多返回的结果数",
    )

    ask_parser.add_argument(
        "--question",
        required=True,
        help="发送给模型的问题",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """解析命令，调用对应的业务功能。"""

    parser = build_parser()
    args = parser.parse_args(argv)

    # 模型问答目前不需要访问目标仓库，因此单独处理。
    if args.command == "ask":
        try:
            settings = load_model_settings()
            model = create_chat_model(settings)
            answer = generate_answer(model, args.question)

        except ModelConfigError as exc:
            parser.error(str(exc))

        except APIStatusError as exc:
            if exc.status_code == 404:
                reason = "模型不存在或当前不可用，请检查模型 ID"
            elif exc.status_code == 429:
                reason = "平台限流或模型访问量过大"
            elif exc.status_code == 401:
                reason = "API Key 无效或没有访问权限"
            else:
                reason = "请检查模型服务状态及请求配置"

            print(
                f"模型请求失败：HTTP {exc.status_code}，{reason}。",
                file=sys.stderr,
            )
            return 1

        except OpenAIError as exc:
            print(
                f"模型请求失败：{type(exc).__name__}。",
                file=sys.stderr,
            )
            return 1

        print(answer)
        return 0

    try:
        explorer = RepositoryExplorer(args.project)

        if args.command == "doctor":
            print(f"项目目录检查通过：{explorer.root}")
            print("当前模式：仅进行目录检查，不修改任何文件。")

        elif args.command == "inspect":
            files = explorer.list_files()

            print(f"找到 {len(files)} 个可探索文件：")

            for path in files:
                print(path)

        elif args.command == "read":
            content = explorer.read_file(args.path)
            print(content, end="")

        elif args.command == "search":
            hits = explorer.search(
                args.query,
                limit=args.limit,
            )

            print(f"找到 {len(hits)} 条匹配结果：")

            for hit in hits:
                print(f"{hit.path}:{hit.line_number}: {hit.line}")

    except RepositoryError as exc:
        parser.error(str(exc))

    return 0
