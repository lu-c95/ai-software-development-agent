"""安全代码编辑 CLI 命令。"""

import argparse
import sys
from pathlib import Path
from typing import Any

from ai_software_dev_agent.commands._common import add_project_argument
from ai_software_dev_agent.editor import CodeEditor, FileEditError
from ai_software_dev_agent.repository import RepositoryError


def run_edit_command(
    project: Path,
    file_path: str,
    old_text: str,
    new_text: str,
) -> int:
    """预览 Diff，确认后安全应用修改。"""

    try:
        editor = CodeEditor(project)

        preview = editor.preview_replace(
            file_path,
            old_text,
            new_text,
        )

    except (FileEditError, RepositoryError, OSError) as exc:
        print(
            f"无法生成修改预览：{exc}",
            file=sys.stderr,
        )
        return 1

    print(f"目标文件：{preview.path}")
    print("=== 修改预览（尚未写入）===")

    print(
        preview.diff,
        end="" if preview.diff.endswith("\n") else "\n",
    )

    try:
        confirmation = input("\n输入 yes 确认写入，其他任意输入取消：").strip()

    except (EOFError, KeyboardInterrupt):
        print("\n已取消修改，文件未写入。")
        return 0

    if confirmation != "yes":
        print("已取消修改，文件未写入。")
        return 0

    try:
        editor.apply(preview)

    except (FileEditError, RepositoryError, OSError) as exc:
        print(
            f"应用补丁失败：{exc}",
            file=sys.stderr,
        )
        return 1

    print(f"修改完成：{preview.path}")

    return 0


def run_edit(args: argparse.Namespace) -> int:
    """适配 argparse 参数与编辑器调用。"""

    return run_edit_command(
        project=args.project,
        file_path=args.path,
        old_text=args.old,
        new_text=args.new,
    )


def register(subparsers: Any) -> None:
    """注册 edit 子命令。"""

    parser = subparsers.add_parser(
        "edit",
        help="预览并确认一次 Python 代码修改",
    )

    add_project_argument(parser)

    parser.add_argument(
        "--path",
        required=True,
        help="相对项目根目录的 Python 文件路径",
    )

    parser.add_argument(
        "--old",
        required=True,
        help="需要精确匹配的旧代码片段",
    )

    parser.add_argument(
        "--new",
        required=True,
        help="替换后的新代码片段",
    )

    parser.set_defaults(handler=run_edit)
