"""交互式 Agent 聊天命令。"""

import argparse
import sys
from pathlib import Path
from typing import Any

from langchain_core.messages import BaseMessage, ToolMessage
from langchain_core.runnables import Runnable
from openai import APIStatusError, OpenAIError
from pydantic import ValidationError

from ai_software_dev_agent.agent import (
    AgentExecutionError,
    build_development_agent,
    run_agent_turn,
)
from ai_software_dev_agent.commands._common import (
    add_project_argument,
    describe_api_error,
)
from ai_software_dev_agent.model import (
    ModelConfigError,
    create_chat_model,
    load_model_settings,
)
from ai_software_dev_agent.repository import RepositoryError


def run_chat_session(
    agent: Runnable,
    project: Path,
) -> int:
    """持续接收问题并维护当前进程中的会话历史。"""

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

        new_messages = updated_history[len(history) :]

        for message in new_messages:
            if isinstance(message, ToolMessage):
                tool_name = message.name or "未知工具"
                print(f"[工具返回] {tool_name}")

        # 只有本轮成功，才更新会话历史。
        history = updated_history

        print(f"Agent：{answer}")


def run_chat(args: argparse.Namespace) -> int:
    """创建 Agent 并进入交互会话。"""

    settings = load_model_settings()
    model = create_chat_model(settings)

    agent = build_development_agent(
        model,
        args.project,
    )

    return run_chat_session(agent, args.project)


def register(subparsers: Any) -> None:
    """注册 chat 子命令。"""

    parser = subparsers.add_parser(
        "chat",
        help="与能够探索代码仓库的 Agent 持续对话",
    )

    add_project_argument(parser)
    parser.set_defaults(handler=run_chat)
