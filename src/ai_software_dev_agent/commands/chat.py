"""交互式开发 Agent CLI，支持临时会话和 SQLite 持久化。"""

import argparse
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    ToolMessage,
)
from langchain_core.runnables import Runnable
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.errors import GraphRecursionError
from openai import OpenAIError

from ai_software_dev_agent.agent import (
    AgentExecutionError,
    build_development_agent,
    run_agent_turn,
)
from ai_software_dev_agent.commands._common import add_project_argument
from ai_software_dev_agent.model import (
    ModelConfigError,
    create_chat_model,
    load_model_settings,
)
from ai_software_dev_agent.persistent_agent import (
    build_persistent_development_agent,
    get_persistent_agent_history,
    run_persistent_agent_turn,
)
from ai_software_dev_agent.repository import (
    RepositoryError,
    RepositoryExplorer,
)

# 默认存储位置位于用户主目录，而不是项目的 Git 仓库中。
DEFAULT_DB_PATH = Path.home() / ".ai-software-development-agent" / "sessions.sqlite"


def print_help(persistent: bool) -> None:
    """显示当前聊天模式支持的命令。"""

    print("\n可用指令：")
    print("  /help       显示帮助")
    print("  /new        开始新会话")
    print("  /history    显示最近的对话消息")
    print("  /exit       退出聊天")

    if persistent:
        print("  /session ID 切换或恢复指定会话")

    print()


def print_recent_history(
    history: list[BaseMessage],
    limit: int = 8,
) -> None:
    """显示最近的用户及最终 AI 消息，不展示工具内部消息。"""

    visible_messages = [
        message
        for message in history
        if isinstance(message, HumanMessage)
        or (isinstance(message, AIMessage) and not message.tool_calls)
    ]

    if not visible_messages:
        print("当前没有对话历史。")
        return

    for message in visible_messages[-limit:]:
        role = "你" if isinstance(message, HumanMessage) else "AI"
        print(f"{role}：{str(message.text)[:300]}")


def interactive_chat(
    agent: Runnable,
    project: Path,
    session_id: str | None = None,
) -> int:
    """运行持续交互的 CLI 对话循环。"""

    # 临时模式仍然使用 Day 05 的内存历史。
    history: list[BaseMessage] = []

    if session_id is None:
        print("已进入临时聊天模式，退出后不保留历史。")
    else:
        saved = get_persistent_agent_history(agent, project, session_id)

        turns = sum(isinstance(message, HumanMessage) for message in saved)

        print(f"当前会话：{session_id}")
        print(f"已恢复用户消息：{turns} 轮")

    print("输入 /help 查看指令，输入 /exit 退出。")

    while True:
        try:
            question = input("\n你：").strip()

        except EOFError:
            print("\n再见，聊天已结束。")
            return 0

        except KeyboardInterrupt:
            print("\n聊天已中断。")
            return 130

        if not question:
            continue

        if question in {"/exit", "/quit"}:
            print("已退出聊天。")
            return 0

        if question == "/help":
            print_help(session_id is not None)
            continue

        if question == "/new":
            if session_id is None:
                history = []
                print("已清空当前对话历史。")
            else:
                # 切换新 thread_id，不删除原 SQLite 历史。
                session_id = f"session-{uuid4().hex}"
                print(f"已开始新会话：{session_id}")
            continue

        if question == "/history":
            current_history = (
                history
                if session_id is None
                else get_persistent_agent_history(agent, project, session_id)
            )

            print_recent_history(current_history)
            continue

        if question == "/session" or question.startswith("/session "):
            if session_id is None:
                print("请使用 --session ID 启动持久化聊天。")
                continue

            parts = question.split(maxsplit=1)

            if len(parts) != 2 or not parts[1].strip():
                print("使用方法：/session 会话ID")
                continue

            session_id = parts[1].strip()

            saved = get_persistent_agent_history(agent, project, session_id)

            turns = sum(isinstance(message, HumanMessage) for message in saved)

            print(f"已切换会话：{session_id}")
            print(f"已恢复用户消息：{turns} 轮")
            continue

        if question.startswith("/"):
            print("未知命令。输入 /help 查看帮助。")
            continue

        try:
            if session_id is None:
                # 记录执行本轮 Agent 前的历史长度。
                previous_count = len(history)

                answer, updated_history = run_agent_turn(
                    agent,
                    history,
                    question,
                )

                # 仅处理本轮新增的消息。
                for message in updated_history[previous_count:]:
                    if isinstance(message, AIMessage):
                        # 展示本轮的工具调用。
                        for tool_call in message.tool_calls:
                            print(f"[工具调用] {tool_call['name']}")

                    elif isinstance(message, ToolMessage):
                        # 恢复 Day 05 原有的工具返回格式。
                        tool_name = message.name or message.tool_call_id

                        print(f"[工具返回] {tool_name}")
                        print(message.text)

                history = updated_history

            else:
                # Day 11 持久化模式保留原有逻辑。
                answer, history = run_persistent_agent_turn(
                    agent,
                    project,
                    session_id,
                    question,
                )

            print(f"\nAI：{answer}")

        except (
            AgentExecutionError,
            ModelConfigError,
            RepositoryError,
            OpenAIError,
            httpx.HTTPError,
            GraphRecursionError,
        ) as exc:
            print(
                f"本轮对话失败：{type(exc).__name__}：{exc}",
                file=sys.stderr,
            )
            print("可以重新提问，或输入 /exit 结束。")

        except KeyboardInterrupt:
            print("\n用户已中断模型请求。")
            return 130


def run_chat_session(
    agent: Runnable,
    project: Path,
) -> int:
    """保留 Day 05 的聊天接口，兼容原有调用方和测试。"""

    return interactive_chat(
        agent=agent,
        project=project,
        session_id=None,
    )


def run_chat(args: argparse.Namespace) -> int:
    """根据 CLI 参数选择临时或持久化聊天模式。"""

    project = args.project.expanduser().resolve()

    if args.db is not None and args.session is None:
        print(
            "--db 需要与 --session 一起使用。",
            file=sys.stderr,
        )
        return 2

    if args.session is not None and not args.session.strip():
        print("会话 ID 不能为空。", file=sys.stderr)
        return 2

    try:
        # 先检查仓库，避免无效路径仍然初始化模型。
        RepositoryExplorer(project)

        settings = load_model_settings()
        model = create_chat_model(settings)

        if args.session is None:
            # 保留原有接口，避免破坏 Day 05 的调用方和测试。
            agent = build_development_agent(model, project)

            return run_chat_session(agent, project)

        db_path = (
            (args.db if args.db is not None else DEFAULT_DB_PATH).expanduser().resolve()
        )

        db_path.parent.mkdir(parents=True, exist_ok=True)

        # 必须确保 Agent 的整个交互过程位于数据库连接生命周期内。
        with SqliteSaver.from_conn_string(str(db_path)) as saver:
            agent = build_persistent_development_agent(
                model,
                project,
                saver,
            )

            return interactive_chat(
                agent,
                project,
                session_id=args.session.strip(),
            )

    except (RepositoryError, ModelConfigError) as exc:
        print(f"项目或模型配置错误：{exc}", file=sys.stderr)
        return 2

    except (OSError, OpenAIError, httpx.HTTPError) as exc:
        print(
            f"聊天初始化失败：{type(exc).__name__}：{exc}",
            file=sys.stderr,
        )
        return 1


def register(subparsers: Any) -> None:
    """注册原有 chat 命令，并增加持久化参数。"""

    parser = subparsers.add_parser(
        "chat",
        help="多轮开发 Agent 聊天，可选 SQLite 会话持久化",
    )

    add_project_argument(parser)

    parser.add_argument(
        "--session",
        default=None,
        help="会话 ID；传入后启用历史持久化",
    )

    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="SQLite 数据库路径，默认保存到用户主目录",
    )

    parser.set_defaults(handler=run_chat)
