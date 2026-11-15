"""Day 12：已有文件修改的人工审批 CLI。"""

import argparse
import sqlite3
import sys
from pathlib import Path
from shlex import quote
from typing import Any
from uuid import uuid4

from langgraph.checkpoint.sqlite import SqliteSaver

from ai_software_dev_agent.edit_approval_workflow import (
    build_edit_approval_graph,
    make_edit_approval_config,
    resume_edit_approval,
    start_edit_approval,
)
from ai_software_dev_agent.editor import FileEditError

# 与 Day 11 的聊天数据库分离，避免不同类型的线程混用。
DEFAULT_APPROVAL_DB = (
    Path.home() / ".ai-software-development-agent" / "edit-approvals.sqlite"
)


def resolve_db_path(path: Path | None) -> Path:
    """获取本地审批数据库的绝对路径。"""

    selected = path if path is not None else DEFAULT_APPROVAL_DB
    return selected.expanduser().resolve()


def run_prepare(args: argparse.Namespace) -> int:
    """创建一条待审批修改请求，不修改目标文件。"""

    db_path = resolve_db_path(args.db)
    thread_id = args.thread_id or uuid4().hex

    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # 数据库连接只在本命令执行期间保持打开。
        with SqliteSaver.from_conn_string(str(db_path)) as saver:
            graph = build_edit_approval_graph(saver)

            result = start_edit_approval(
                graph=graph,
                project=args.project,
                relative_path=args.relative_path,
                old_text=args.old_text,
                new_text=args.new_text,
                thread_id=thread_id,
            )

            interrupts = result.get("__interrupt__", ())

            if not interrupts:
                print(
                    "工作流没有进入待审批状态。",
                    file=sys.stderr,
                )
                return 1

            request = interrupts[0].value

            print("\n===== 文件修改预览 =====")
            print(f"项目目录：{args.project.resolve()}")
            print(f"目标文件：{request['relative_path']}")
            print(f"原文件哈希：{request['original_sha256']}")

            print("\n===== Diff =====")
            print(request["diff"])

            print("审批状态：等待人工确认")
            print(f"审批 ID：{thread_id}")
            print(f"数据库：{db_path}")

            # 打印可复制的恢复命令，正确处理路径中的空格。
            command = (
                "ai-dev-agent edit-approval review"
                f" --thread-id {quote(thread_id)}"
                f" --db {quote(str(db_path))}"
            )

            print("\n之后运行以下命令进行审批：")
            print(command)

            return 0

    except (FileEditError, ValueError, OSError, sqlite3.Error) as exc:
        print(
            f"准备审批失败：{type(exc).__name__}：{exc}",
            file=sys.stderr,
        )
        return 1


def run_review(args: argparse.Namespace) -> int:
    """恢复审批任务，显示 Diff 后读取人工决定。"""

    db_path = resolve_db_path(args.db)

    if not db_path.is_file():
        print(
            f"审批数据库不存在：{db_path}",
            file=sys.stderr,
        )
        return 2

    try:
        config = make_edit_approval_config(args.thread_id)

        with SqliteSaver.from_conn_string(str(db_path)) as saver:
            graph = build_edit_approval_graph(saver)

            snapshot = graph.get_state(config)

            # 只有真正暂停在审批节点的任务才能被恢复。
            if snapshot.next != ("request_edit_approval",):
                print(
                    "没有找到等待处理的文件修改审批。",
                    file=sys.stderr,
                )
                return 2

            state = snapshot.values

            print("\n===== 待审批的修改 =====")
            print(f"审批 ID：{args.thread_id}")
            print(f"项目目录：{state['project']}")
            print(f"目标文件：{state['relative_path']}")
            print(f"原文件哈希：{state['original_sha256']}")

            print("\n===== Diff =====")
            print(state["diff"])

            print("请确认以上项目路径与代码修改内容。")
            print("yes：批准修改")
            print("no ：拒绝修改")
            print("其他输入：取消本次操作，保留待审批状态")

            try:
                answer = input("\n请输入决定（yes/no）：")
            except EOFError:
                # 没有人工输入，不能擅自批准或拒绝。
                print("\n未收到审批输入，任务仍处于待审批状态。")
                return 2
            except KeyboardInterrupt:
                print("\n用户取消审批，任务仍处于待审批状态。")
                return 130

            decision = answer.strip().lower()

            if decision not in {"yes", "no"}:
                print("本次未提交决定，任务仍处于待审批状态。")
                return 0

            # 只有明确输入 yes 才会传入布尔 True。
            approved = decision == "yes"

            result = resume_edit_approval(
                graph=graph,
                thread_id=args.thread_id,
                approved=approved,
            )

            print(f"\n最终状态：{result['status']}")
            print(f"执行说明：{result['summary']}")

            if result["status"] in {"applied", "rejected"}:
                return 0

            # 包括文件版本冲突等未成功应用的情况。
            return 1

    except (
        FileEditError,
        ValueError,
        OSError,
        sqlite3.Error,
        KeyError,
    ) as exc:
        print(
            f"审批处理失败：{type(exc).__name__}：{exc}",
            file=sys.stderr,
        )
        return 1


def register(subparsers: Any) -> None:
    """注册 edit-approval 及其两个子命令。"""

    parser = subparsers.add_parser(
        "edit-approval",
        help="预览代码修改，并通过人工审批决定是否执行",
    )

    actions = parser.add_subparsers(
        dest="approval_action",
        required=True,
    )

    # 准备审批：只预览，不执行写入。
    prepare = actions.add_parser(
        "prepare",
        help="生成 Diff 并保存待审批任务",
    )

    prepare.add_argument(
        "--project",
        type=Path,
        required=True,
        help="项目根目录",
    )
    prepare.add_argument(
        "--file",
        dest="relative_path",
        required=True,
        help="相对项目根目录的 Python 文件路径",
    )
    prepare.add_argument(
        "--old",
        dest="old_text",
        required=True,
        help="需要唯一匹配的原始文本",
    )
    prepare.add_argument(
        "--new",
        dest="new_text",
        required=True,
        help="用于替换的新文本",
    )
    prepare.add_argument(
        "--thread-id",
        default=None,
        help="自定义审批 ID；默认自动生成",
    )
    prepare.add_argument(
        "--db",
        type=Path,
        default=None,
        help="SQLite 审批数据库路径",
    )
    prepare.set_defaults(handler=run_prepare)

    # 恢复审批：显示 Diff 后，读取人工输入。
    review = actions.add_parser(
        "review",
        help="恢复待审批任务，交互式批准或拒绝",
    )

    review.add_argument(
        "--thread-id",
        required=True,
        help="prepare 阶段生成的审批 ID",
    )
    review.add_argument(
        "--db",
        type=Path,
        default=None,
        help="与 prepare 相同的 SQLite 数据库路径",
    )
    review.set_defaults(handler=run_review)
