"""结构化开发计划 CLI 命令。"""

import argparse
import sys
from typing import Any

from langchain_core.exceptions import OutputParserException
from openai import APIStatusError, OpenAIError
from pydantic import ValidationError

from ai_software_dev_agent.commands._common import describe_api_error
from ai_software_dev_agent.model import (
    create_chat_model,
    load_model_settings,
)
from ai_software_dev_agent.planning import (
    PlanningError,
    generate_development_plan,
)


def run_plan(args: argparse.Namespace) -> int:
    """通过模型生成结构化软件开发计划。"""

    try:
        settings = load_model_settings()
        model = create_chat_model(settings)

        plan = generate_development_plan(
            model,
            args.task,
        )

        print(plan.model_dump_json(indent=2))

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


def register(subparsers: Any) -> None:
    """注册 plan 子命令。"""

    parser = subparsers.add_parser(
        "plan",
        help="生成结构化软件开发计划",
    )

    parser.add_argument(
        "--task",
        required=True,
        help="需要制定计划的软件开发任务",
    )

    parser.set_defaults(handler=run_plan)
