"""Day 13：受权限策略保护的 LangChain 仓库工具。"""

from pathlib import Path

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

from ai_software_dev_agent.repository import RepositoryExplorer
from ai_software_dev_agent.security import (
    ALLOWED_READ_ROOTS,
    PermissionDenied,
    PermissionPolicy,
)

MAX_VISIBLE_FILES = 80


class ReadFileArgs(BaseModel):
    """读取文件工具的输入参数。"""

    path: str = Field(description="相对于项目根目录的文件路径，例如 src/app.py")


def list_allowed_files(
    policy: PermissionPolicy,
    limit: int = MAX_VISIBLE_FILES,
) -> list[str]:
    """只展示经过权限策略检查的可读取文件路径。"""

    if limit <= 0:
        raise ValueError("文件列表上限必须大于零")

    root = policy.project_root
    visible: list[str] = []

    for allowed_root in ALLOWED_READ_ROOTS:
        location = root / allowed_root

        # 符号链接根目录不能作为扫描入口。
        if location.is_symlink():
            continue

        if location.is_file():
            candidates = (location,)
        elif location.is_dir():
            # 默认不递归跟随符号链接目录。
            candidates = location.rglob("*")
        else:
            continue

        for candidate in candidates:
            # 排除目录、符号链接和其他非普通文件。
            if candidate.is_symlink() or not candidate.is_file():
                continue

            relative_path = candidate.relative_to(root).as_posix()

            try:
                # 文件发现同样必须通过第一阶段的授权规则。
                policy.authorize("read_file", relative_path)
            except (PermissionDenied, FileNotFoundError):
                continue

            visible.append(relative_path)

            # 限制返回给模型的文件路径数量。
            if len(visible) >= limit:
                return sorted(visible)

    return sorted(visible)


def create_secure_repository_tools(
    project: Path,
) -> list[BaseTool]:
    """为 Agent 创建仅具备受限读取能力的仓库工具。"""

    # 复用旧项目的仓库校验，保持已有异常约定。
    RepositoryExplorer(project)

    # 在此基础上启用新的最小权限策略。
    policy = PermissionPolicy(project_root=project)

    @tool("inspect_repository")
    def inspect_repository() -> str:
        """列出项目中允许读取的文件，不包含隐藏或敏感文件。"""

        visible_files = list_allowed_files(policy)

        if not visible_files:
            return "当前权限策略下没有可读取的项目文件。"

        lines = [
            "当前项目允许读取的文件：",
            *visible_files,
        ]

        return "\n".join(lines)

    @tool(
        "read_repository_file",
        args_schema=ReadFileArgs,
    )
    def read_repository_file(path: str) -> str:
        """读取项目中已授权的 UTF-8 文本文件，拒绝敏感路径。"""

        try:
            # 这里不再调用原有 RepositoryExplorer.read_file()。
            # 从工具执行入口到文件读取，统一经过权限策略。
            return policy.read_text(path)

        except (PermissionDenied, FileNotFoundError) as exc:
            # 向 Agent 返回清晰的拒绝信息，而不是读取文件。
            return f"[权限拒绝] {exc}"

    return [
        inspect_repository,
        read_repository_file,
    ]
