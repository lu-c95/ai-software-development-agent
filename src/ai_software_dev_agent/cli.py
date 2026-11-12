"""AI 软件开发智能体的命令行入口。"""

import argparse
import sys
from pathlib import Path

from langchain_core.exceptions import OutputParserException
from langchain_core.messages import BaseMessage, ToolMessage
from langchain_core.runnables import Runnable
from openai import APIStatusError, OpenAIError
from pydantic import ValidationError

from ai_software_dev_agent import __version__
from ai_software_dev_agent.agent import (
    AgentExecutionError,
    build_development_agent,
    run_agent_turn,
)
from ai_software_dev_agent.editor import CodeEditor, FileEditError
from ai_software_dev_agent.model import (
    ModelConfigError,
    create_chat_model,
    generate_answer,
    load_model_settings,
)
from ai_software_dev_agent.planning import (
    PlanningError,
    generate_development_plan,
)
from ai_software_dev_agent.repository import (
    RepositoryError,
    RepositoryExplorer,
)
from ai_software_dev_agent.test_runner import (
    DEFAULT_TIMEOUT_SECONDS,
    TestRunner,
    TestRunnerError,
)


def describe_api_error(status_code: int) -> str:
    """将常见 HTTP 错误转换为容易理解的提示。"""

    reasons = {
        400: "请求参数错误或模型不支持该功能",
        401: "API Key 无效或没有访问权限",
        404: "模型不存在或当前不可用",
        429: "平台限流或模型访问量过大",
    }

    return reasons.get(
        status_code,
        "请检查模型服务状态和请求配置",
    )


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

    ask_parser = subparsers.add_parser(
        "ask",
        help="使用 LangChain 调用聊天模型",
    )

    plan_parser = subparsers.add_parser(
        "plan",
        help="生成结构化软件开发计划",
    )

    chat_parser = subparsers.add_parser(
        "chat",
        help="与能够探索代码仓库的 Agent 持续对话",
    )

    edit_parser = subparsers.add_parser(
        "edit",
        help="预览并确认一次 Python 代码修改",
    )

    # Day 07：新增 pytest 测试执行命令。
    test_parser = subparsers.add_parser(
        "test",
        help="在指定项目中受控执行 pytest",
    )

    # 需要指定仓库的命令统一支持 --project。
    for command_parser in (
        doctor_parser,
        inspect_parser,
        read_parser,
        search_parser,
        chat_parser,
        edit_parser,
        test_parser,
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

    plan_parser.add_argument(
        "--task",
        required=True,
        help="需要制定计划的软件开发任务",
    )

    # Day 06：安全文件编辑参数。
    edit_parser.add_argument(
        "--path",
        required=True,
        help="相对项目根目录的 Python 文件路径",
    )

    edit_parser.add_argument(
        "--old",
        required=True,
        help="需要精确匹配的旧代码片段",
    )

    edit_parser.add_argument(
        "--new",
        required=True,
        help="替换后的新代码片段",
    )

    # Day 07：固定 pytest 目标与超时参数。
    test_parser.add_argument(
        "--target",
        default="tests",
        help="tests 目录或其中的 test_*.py 文件",
    )

    test_parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="执行超时秒数，范围 1～120，默认 30",
    )

    return parser


def run_test_command(
    project: Path,
    target: str,
    timeout_seconds: int,
) -> int:
    """调用 TestRunner，并展示结构化 pytest 执行结果。"""

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

    # 将内部状态转换为用户更容易理解的文字。
    status_labels = {
        "passed": "通过",
        "failed": "测试失败",
        "no_tests": "未发现测试",
        "error": "执行错误",
        "timeout": "执行超时",
    }

    status_label = status_labels[result.status]

    print(f"测试状态：{result.status}（{status_label}）")

    # 超时或进程启动失败时，可能没有 pytest 退出码。
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

    # 只有全部通过才向调用方返回 0。
    # 其他情况统一返回非零，便于后续工作流检测失败。
    return 0 if result.passed else 1


def run_edit_command(
    project: Path,
    file_path: str,
    old_text: str,
    new_text: str,
) -> int:
    """预览差异，获取用户确认，然后安全应用修改。"""

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


def run_chat_session(
    agent: Runnable,
    project: Path,
) -> int:
    """启动持续对话，并维护当前进程内的消息历史。"""

    history: list[BaseMessage] = []

    print("AI Software Development Agent")
    print(f"当前项目：{project.expanduser().resolve()}")
    print("输入 /help 查看命令，输入 /exit 退出。")

    while True:
        try:
            question = input("\n你：").strip()

        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            return 0

        if not question:
            continue

        if question == "/exit":
            print("再见！")
            return 0

        if question == "/help":
            print("/help  查看帮助")
            print("/new   清空当前对话历史")
            print("/exit  退出交互式 CLI")
            continue

        if question == "/new":
            history = []
            print("已清空当前对话历史。")
            continue

        if question.startswith("/"):
            print("未知命令，请输入 /help 查看可用命令。")
            continue

        try:
            answer, updated_history = run_agent_turn(
                agent,
                history,
                question,
            )

        except APIStatusError as exc:
            print(
                f"模型请求失败：HTTP {exc.status_code}，"
                f"{describe_api_error(exc.status_code)}。",
                file=sys.stderr,
            )
            continue

        except OpenAIError as exc:
            print(
                f"模型请求失败：{type(exc).__name__}。",
                file=sys.stderr,
            )
            continue

        except RecursionError:
            print(
                "Agent 达到执行步数上限，本轮历史未保存，请尝试简化问题。",
                file=sys.stderr,
            )
            continue

        except (
            AgentExecutionError,
            ModelConfigError,
            RepositoryError,
            ValidationError,
        ) as exc:
            print(
                f"Agent 执行失败：{exc}",
                file=sys.stderr,
            )
            continue

        except KeyboardInterrupt:
            print("\n本轮请求已中断，可以继续输入。")
            continue

        # 仅展示本轮新增的工具执行消息。
        new_messages = updated_history[len(history) :]

        for message in new_messages:
            if isinstance(message, ToolMessage):
                tool_name = message.name or "未知工具"
                print(f"[工具返回] {tool_name}")

        history = updated_history

        print(f"Agent：{answer}")


def main(argv: list[str] | None = None) -> int:
    """解析命令并执行对应功能。"""

    parser = build_parser()
    args = parser.parse_args(argv)

    # Day 07：独立执行 pytest，不依赖模型 API。
    if args.command == "test":
        return run_test_command(
            project=args.project,
            target=args.target,
            timeout_seconds=args.timeout,
        )

    # Day 06：安全文件修改。
    if args.command == "edit":
        return run_edit_command(
            project=args.project,
            file_path=args.path,
            old_text=args.old,
            new_text=args.new,
        )

    # Day 05：交互式 Agent。
    if args.command == "chat":
        try:
            settings = load_model_settings()
            model = create_chat_model(settings)

            agent = build_development_agent(
                model,
                args.project,
            )

        except (ModelConfigError, RepositoryError) as exc:
            parser.error(str(exc))

        return run_chat_session(agent, args.project)

    # Day 03、Day 04：普通问答和结构化规划。
    if args.command in ("ask", "plan"):
        try:
            settings = load_model_settings()
            model = create_chat_model(settings)

            if args.command == "ask":
                answer = generate_answer(
                    model,
                    args.question,
                )
                print(answer)

            else:
                plan = generate_development_plan(
                    model,
                    args.task,
                )
                print(plan.model_dump_json(indent=2))

        except ModelConfigError as exc:
            parser.error(str(exc))

        except (
            PlanningError,
            ValidationError,
            OutputParserException,
        ) as exc:
            print(
                f"开发计划结构化生成失败：{type(exc).__name__}。",
                file=sys.stderr,
            )
            return 1

        except APIStatusError as exc:
            print(
                f"模型请求失败：HTTP {exc.status_code}，"
                f"{describe_api_error(exc.status_code)}。",
                file=sys.stderr,
            )
            return 1

        except OpenAIError as exc:
            print(
                f"模型请求失败：{type(exc).__name__}。",
                file=sys.stderr,
            )
            return 1

        return 0

    # Day 01、Day 02：仓库探索命令。
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
