"""Day 13：受限仓库工具与真实 Agent 工具注册测试。"""

from pathlib import Path
from typing import Any

import pytest

from ai_software_dev_agent import agent as agent_module
from ai_software_dev_agent import persistent_agent
from ai_software_dev_agent.secure_tools import (
    create_secure_repository_tools,
    list_allowed_files,
)
from ai_software_dev_agent.security import PermissionPolicy


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """创建同时包含正常文件和敏感文件的测试项目。"""

    root = tmp_path / "project"
    root.mkdir()

    (root / "src").mkdir()
    (root / "tests").mkdir()
    (root / "docs").mkdir()
    (root / "notes").mkdir()

    (root / "src" / "app.py").write_text(
        "answer = 42\n",
        encoding="utf-8",
    )

    (root / "tests" / "test_app.py").write_text(
        "assert True\n",
        encoding="utf-8",
    )

    (root / "README.md").write_text(
        "# Demo\n",
        encoding="utf-8",
    )

    (root / "pyproject.toml").write_text(
        "[project]\nname = 'demo'\n",
        encoding="utf-8",
    )

    (root / ".env").write_text(
        "API_KEY=demo-secret\n",
        encoding="utf-8",
    )

    (root / "src" / "credentials.json").write_text(
        '{"token": "demo-secret"}',
        encoding="utf-8",
    )

    (root / "src" / "private.pem").write_text(
        "PRIVATE KEY DATA\n",
        encoding="utf-8",
    )

    (root / "notes" / "private.py").write_text(
        "private_value = 123\n",
        encoding="utf-8",
    )

    return root


def get_tools(project: Path) -> dict[str, Any]:
    """按名称整理安全工具，方便调用。"""

    return {item.name: item for item in create_secure_repository_tools(project)}


def test_only_expected_tools_are_registered(
    project: Path,
) -> None:
    """不能向模型提供不在允许范围内的工具。"""

    tools = get_tools(project)

    assert set(tools) == {
        "inspect_repository",
        "read_repository_file",
    }

    assert "execute_shell" not in tools
    assert "write_file" not in tools
    assert "delete_file" not in tools


def test_read_tool_can_read_allowed_file(
    project: Path,
) -> None:
    """真实 LangChain Tool 可以读取获授权的文件。"""

    tools = get_tools(project)

    result = tools["read_repository_file"].invoke({"path": "src/app.py"})

    assert result == "answer = 42\n"


@pytest.mark.parametrize(
    "path",
    [
        ".env",
        "src/credentials.json",
        "src/private.pem",
        "notes/private.py",
        "../outside.py",
        "/etc/passwd",
    ],
)
def test_read_tool_denies_sensitive_paths(
    project: Path,
    path: str,
) -> None:
    """模型传入越权路径时，工具必须拒绝。"""

    tools = get_tools(project)

    result = tools["read_repository_file"].invoke({"path": path})

    assert "[权限拒绝]" in result
    assert "demo-secret" not in result
    assert "PRIVATE KEY DATA" not in result


def test_inspect_tool_hides_sensitive_files(
    project: Path,
) -> None:
    """文件发现工具不能列出敏感路径。"""

    tools = get_tools(project)

    result = tools["inspect_repository"].invoke({})

    assert "src/app.py" in result
    assert "tests/test_app.py" in result
    assert "README.md" in result

    assert ".env" not in result
    assert "credentials.json" not in result
    assert "private.pem" not in result
    assert "notes/private.py" not in result


def test_inspect_does_not_follow_outside_symlink(
    project: Path,
    tmp_path: Path,
) -> None:
    """符号链接不能把仓库外路径引入文件列表。"""

    outside = tmp_path / "outside.py"

    outside.write_text(
        "outside_secret = 99\n",
        encoding="utf-8",
    )

    (project / "src" / "linked.py").symlink_to(outside)

    tools = get_tools(project)

    listing = tools["inspect_repository"].invoke({})

    assert "linked.py" not in listing

    result = tools["read_repository_file"].invoke({"path": "src/linked.py"})

    assert "[权限拒绝]" in result
    assert "outside_secret" not in result


def test_inspect_respects_file_limit(
    project: Path,
) -> None:
    """仓库文件发现结果必须受数量上限限制。"""

    policy = PermissionPolicy(project)

    files = list_allowed_files(policy, limit=2)

    assert len(files) == 2


def test_read_tool_respects_byte_limit(
    project: Path,
) -> None:
    """工具不能返回超过策略限制的整份文件。"""

    (project / "src" / "large.py").write_text(
        "a" * (65 * 1024),
        encoding="utf-8",
    )

    tools = get_tools(project)

    result = tools["read_repository_file"].invoke({"path": "src/large.py"})

    assert "[权限拒绝]" in result
    assert "最大读取限制" in result


def test_normal_agent_uses_secure_tools(
    project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """普通 Agent 构建时必须注册受限工具。"""

    captured: dict[str, Any] = {}

    def fake_create_agent(*args: Any, **kwargs: Any) -> object:
        tools = kwargs.get("tools")

        if tools is None and len(args) >= 2:
            tools = args[1]

        captured["tools"] = tools
        return object()

    monkeypatch.setattr(
        agent_module,
        "create_agent",
        fake_create_agent,
    )

    # 不调用真实模型，仅检查 Agent 的工具注册行为。
    agent_module.build_development_agent(
        object(),
        project,
    )

    tools = {item.name: item for item in captured["tools"]}

    result = tools["read_repository_file"].invoke({"path": ".env"})

    assert "[权限拒绝]" in result


def test_persistent_agent_uses_secure_tools(
    project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """持久化 Agent 也必须使用同一套受限工具。"""

    captured: dict[str, Any] = {}

    def fake_create_agent(*args: Any, **kwargs: Any) -> object:
        tools = kwargs.get("tools")

        if tools is None and len(args) >= 2:
            tools = args[1]

        captured["tools"] = tools
        return object()

    monkeypatch.setattr(
        persistent_agent,
        "create_agent",
        fake_create_agent,
    )

    persistent_agent.build_persistent_development_agent(
        model=object(),
        project=project,
        checkpointer=object(),
    )

    tools = {item.name: item for item in captured["tools"]}

    assert set(tools) == {
        "inspect_repository",
        "read_repository_file",
    }

    result = tools["read_repository_file"].invoke({"path": "src/credentials.json"})

    assert "[权限拒绝]" in result
