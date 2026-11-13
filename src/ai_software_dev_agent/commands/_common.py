"""多个 CLI 命令共享的参数与提示工具。"""

import argparse
from pathlib import Path


def add_project_argument(parser: argparse.ArgumentParser) -> None:
    """为需要操作项目的命令注册 --project 参数。"""

    parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="目标项目目录",
    )


def describe_api_error(status_code: int) -> str:
    """将常见模型服务 HTTP 错误转换为中文提示。"""

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
