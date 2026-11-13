"""仓库检查、文件列表、读取及搜索的 CLI 命令。"""

import argparse
from typing import Any

from ai_software_dev_agent.commands._common import add_project_argument
from ai_software_dev_agent.repository import RepositoryExplorer


def run_doctor(args: argparse.Namespace) -> int:
    """检查目标仓库。"""

    explorer = RepositoryExplorer(args.project)

    print(f"项目目录检查通过：{explorer.root}")
    print("当前模式：仅进行目录检查，不修改任何文件。")

    return 0


def run_inspect(args: argparse.Namespace) -> int:
    """列出仓库中的可探索文件。"""

    explorer = RepositoryExplorer(args.project)
    files = explorer.list_files()

    print(f"找到 {len(files)} 个可探索文件：")

    for path in files:
        print(path)

    return 0


def run_read(args: argparse.Namespace) -> int:
    """读取指定代码文件。"""

    explorer = RepositoryExplorer(args.project)
    content = explorer.read_file(args.path)

    print(content, end="")

    return 0


def run_search(args: argparse.Namespace) -> int:
    """搜索仓库中的代码关键词。"""

    explorer = RepositoryExplorer(args.project)

    hits = explorer.search(
        args.query,
        limit=args.limit,
    )

    print(f"找到 {len(hits)} 条匹配结果：")

    for hit in hits:
        print(f"{hit.path}:{hit.line_number}: {hit.line}")

    return 0


def register(subparsers: Any) -> None:
    """注册四个仓库管理子命令。"""

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="检查目标项目目录",
    )
    add_project_argument(doctor_parser)
    doctor_parser.set_defaults(handler=run_doctor)

    inspect_parser = subparsers.add_parser(
        "inspect",
        help="列出项目中的代码文件",
    )
    add_project_argument(inspect_parser)
    inspect_parser.set_defaults(handler=run_inspect)

    read_parser = subparsers.add_parser(
        "read",
        help="读取指定代码文件",
    )
    add_project_argument(read_parser)
    read_parser.add_argument(
        "--path",
        required=True,
        help="相对项目根目录的文件路径",
    )
    read_parser.set_defaults(handler=run_read)

    search_parser = subparsers.add_parser(
        "search",
        help="搜索代码关键词",
    )
    add_project_argument(search_parser)
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
    search_parser.set_defaults(handler=run_search)
