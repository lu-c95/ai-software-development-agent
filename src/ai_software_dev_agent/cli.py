"""AI 软件开发智能体的命令行入口。"""

import argparse
from pathlib import Path

from ai_software_dev_agent import __version__


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

    # 使用子命令组织功能，方便后续扩展 inspect、plan、run 等命令。
    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="检查目标项目目录",
    )

    doctor_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="目标项目目录，默认使用当前工作目录",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """解析命令并执行对应功能。"""

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "doctor":
        # 统一转换为绝对路径，避免后续工具使用路径时产生歧义。
        project_path = args.project.expanduser().resolve()

        # 当前只检查目录有效性，不读取或修改项目代码。
        if not project_path.is_dir():
            parser.error(f"项目目录不存在或不是文件夹：{project_path}")

        print(f"项目目录检查通过：{project_path}")
        print("当前模式：仅进行目录检查，不修改任何文件。")

        return 0

    return 2
