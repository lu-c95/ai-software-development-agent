"""普通模型问答 CLI 命令。"""

import argparse
import sys
from typing import Any

from openai import APIStatusError, OpenAIError

from ai_software_dev_agent.commands._common import describe_api_error
from ai_software_dev_agent.model import (
    create_chat_model,
    generate_answer,
    load_model_settings,
)


def run_ask(args: argparse.Namespace) -> int:
    """执行单轮模型问答。"""

    try:
        settings = load_model_settings()
        model = create_chat_model(settings)

        answer = generate_answer(
            model,
            args.question,
        )

        print(answer)

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


def register(subparsers: Any) -> None:
    """注册 ask 子命令。"""

    parser = subparsers.add_parser(
        "ask",
        help="使用 LangChain 调用聊天模型",
    )

    parser.add_argument(
        "--question",
        required=True,
        help="发送给模型的问题",
    )

    parser.set_defaults(handler=run_ask)
