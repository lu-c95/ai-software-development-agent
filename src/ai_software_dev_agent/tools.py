"""将已有仓库探索功能封装为 LangChain 工具。"""

from pathlib import Path

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

from ai_software_dev_agent.repository import RepositoryExplorer


class ReadFileArgs(BaseModel):
    """读取文件工具的参数结构。"""

    path: str = Field(
        min_length=1,
        description="相对于项目根目录的文件路径，例如 src/main.py",
    )


class SearchRepositoryArgs(BaseModel):
    """搜索仓库工具的参数结构。"""

    query: str = Field(
        min_length=1,
        description="要搜索的代码关键词，例如 FastAPI",
    )

    limit: int = Field(
        default=10,
        ge=1,
        le=20,
        description="最多返回的搜索结果数，范围 1～20",
    )


def create_repository_tools(project: Path) -> list[BaseTool]:
    """为指定项目创建一组只读的 LangChain 工具。"""

    explorer = RepositoryExplorer(project)

    @tool("inspect_repository")
    def inspect_repository() -> str:
        """列出代码仓库中可探索的文件，用于了解项目结构。"""

        files = explorer.list_files()

        if not files:
            return "没有找到可探索的文件。"

        return "\n".join(files)

    @tool("read_repository_file", args_schema=ReadFileArgs)
    def read_repository_file(path: str) -> str:
        """读取仓库中的指定文本文件，用于查看代码实现。"""

        return explorer.read_file(path)

    @tool("search_repository", args_schema=SearchRepositoryArgs)
    def search_repository(query: str, limit: int = 10) -> str:
        """在仓库中搜索代码关键词，返回文件路径、行号和内容。"""

        hits = explorer.search(query, limit=limit)

        if not hits:
            return "没有找到匹配的代码。"

        return "\n".join(f"{hit.path}:{hit.line_number}: {hit.line}" for hit in hits)

    return [
        inspect_repository,
        read_repository_file,
        search_repository,
    ]
