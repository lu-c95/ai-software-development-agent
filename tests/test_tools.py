"""LangChain 仓库工具测试。"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from ai_software_dev_agent.repository import RepositoryError
from ai_software_dev_agent.tools import create_repository_tools


def test_create_repository_tools(tmp_path: Path) -> None:
    """应该创建三个名称明确的 LangChain 工具。"""

    tools = create_repository_tools(tmp_path)

    assert len(tools) == 3

    assert [item.name for item in tools] == [
        "inspect_repository",
        "read_repository_file",
        "search_repository",
    ]

    # 工具描述会帮助模型选择合适的工具。
    assert all(item.description for item in tools)


def test_inspect_repository_tool(tmp_path: Path) -> None:
    """工具能够列出仓库文件。"""

    (tmp_path / "main.py").write_text(
        "print('hello')\n",
        encoding="utf-8",
    )

    tools = create_repository_tools(tmp_path)
    inspect_tool = tools[0]

    result = inspect_tool.invoke({})

    assert "main.py" in result


def test_read_repository_file_tool(tmp_path: Path) -> None:
    """工具能够读取允许访问的文件。"""

    (tmp_path / "app.py").write_text(
        "answer = 42\n",
        encoding="utf-8",
    )

    tools = create_repository_tools(tmp_path)
    read_tool = tools[1]

    result = read_tool.invoke(
        {
            "path": "app.py",
        }
    )

    assert result == "answer = 42\n"


def test_search_repository_tool(tmp_path: Path) -> None:
    """工具能够搜索关键词并返回行号。"""

    (tmp_path / "app.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n",
        encoding="utf-8",
    )

    tools = create_repository_tools(tmp_path)
    search_tool = tools[2]

    result = search_tool.invoke(
        {
            "query": "FastAPI",
            "limit": 5,
        }
    )

    assert "app.py:1:" in result
    assert "app.py:2:" in result


def test_search_tool_rejects_invalid_limit(
    tmp_path: Path,
) -> None:
    """Pydantic 应拒绝超出范围的参数。"""

    tools = create_repository_tools(tmp_path)
    search_tool = tools[2]

    with pytest.raises(ValidationError):
        search_tool.invoke(
            {
                "query": "FastAPI",
                "limit": 100,
            }
        )


def test_read_tool_rejects_parent_directory(
    tmp_path: Path,
) -> None:
    """不允许通过 .. 读取仓库之外的文件。"""

    tools = create_repository_tools(tmp_path)
    read_tool = tools[1]

    with pytest.raises(RepositoryError):
        read_tool.invoke(
            {
                "path": "../private.py",
            }
        )
