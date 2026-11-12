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


def describe_api_error(status_code: int) -> str:
    """将常见 HTTP 错误转换成可理解的提示。"""

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

    # Day 05：新增持续对话入口。
    chat_parser = subparsers.add_parser(
        "chat",
        help="与能够探索代码仓库的 Agent 持续对话",
    )

    # 需要指定目标仓库的命令，统一提供 --project。
    for command_parser in (
        doctor_parser,
        inspect_parser,
        read_parser,
        search_parser,
        chat_parser,
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

    return parser


def run_chat_session(
    agent: Runnable,
    project: Path,
) -> int:
    """启动持续对话，并在当前进程内维护消息历史。"""

    history: list[BaseMessage] = []

    print("AI Software Development Agent")
    print(f"当前项目：{project.expanduser().resolve()}")
    print("输入 /help 查看命令，输入 /exit 退出。")

    while True:
        try:
            question = input("\n你：").strip()

        except (EOFError, KeyboardInterrupt):
            # Ctrl+D 或 Ctrl+C：正常结束交互。
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
            # LangGraph 的 GraphRecursionError 继承 RecursionError。
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

        # 只展示本轮新增的工具消息，不重复展示历史消息。
        new_messages = updated_history[len(history) :]

        for message in new_messages:
            if isinstance(message, ToolMessage):
                tool_name = message.name or "未知工具"
                print(f"[工具返回] {tool_name}")

        # 只有本轮完整成功，才更新会话历史。
        history = updated_history

        print(f"Agent：{answer}")


def main(argv: list[str] | None = None) -> int:
    """解析命令并执行对应功能。"""

    parser = build_parser()
    args = parser.parse_args(argv)

    # Day 05：Agent 交互会话。
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
