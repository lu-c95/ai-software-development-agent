"""Day 13：最小权限策略与越权访问测试。"""

from pathlib import Path

import pytest

from ai_software_dev_agent.security import (
    PermissionDenied,
    PermissionPolicy,
)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """建立包含正常文件和敏感文件的临时仓库。"""

    root = tmp_path / "project"
    root.mkdir()

    for directory in ("src", "tests", "docs", "notes"):
        (root / directory).mkdir()

    (root / "src" / "app.py").write_text(
        "answer = 42\n",
        encoding="utf-8",
    )

    (root / "tests" / "test_app.py").write_text(
        "def test_app():\n    assert True\n",
        encoding="utf-8",
    )

    (root / "docs" / "guide.md").write_text(
        "# 开发指南\n",
        encoding="utf-8",
    )

    (root / "README.md").write_text(
        "# 示例项目\n",
        encoding="utf-8",
    )

    (root / "pyproject.toml").write_text(
        "[project]\nname = 'demo'\n",
        encoding="utf-8",
    )

    (root / "notes" / "private.py").write_text(
        "secret = 'internal'\n",
        encoding="utf-8",
    )

    # 用于测试默认拒绝策略。
    (root / ".env").write_text(
        "API_KEY=demo-secret\n",
        encoding="utf-8",
    )

    (root / "src" / "credentials.json").write_text(
        '{"token": "secret"}',
        encoding="utf-8",
    )

    (root / "src" / "private.pem").write_text(
        "PRIVATE KEY DATA\n",
        encoding="utf-8",
    )

    (root / "src" / "data.sqlite").write_bytes(b"SQLite data")

    return root


@pytest.fixture
def policy(project: Path) -> PermissionPolicy:
    """以该临时仓库创建真实权限策略。"""

    return PermissionPolicy(project_root=project)


@pytest.mark.parametrize(
    "relative_path",
    [
        "src/app.py",
        "tests/test_app.py",
        "docs/guide.md",
        "README.md",
        "pyproject.toml",
    ],
)
def test_allowed_files_can_be_read(
    policy: PermissionPolicy,
    relative_path: str,
) -> None:
    """明确允许的项目文件可以读取。"""

    target = policy.authorize(
        "read_file",
        relative_path,
    )

    assert target.is_file()
    assert policy.read_text(relative_path)


@pytest.mark.parametrize(
    "relative_path",
    [
        "",
        ".",
        "../outside.py",
        "/etc/passwd",
        "src/../README.md",
        "src-private/secret.py",
        "notes/private.py",
    ],
)
def test_invalid_or_unlisted_paths_are_denied(
    policy: PermissionPolicy,
    relative_path: str,
) -> None:
    """绝对路径、路径穿越与未授权目录都必须拒绝。"""

    with pytest.raises(PermissionDenied):
        policy.authorize(
            "read_file",
            relative_path,
        )


@pytest.mark.parametrize(
    "relative_path",
    [
        ".env",
        ".git/config",
        ".venv/lib/site.py",
        "src/.env.local",
        "src/.hidden.py",
        "src/credentials.json",
        "src/private.pem",
        "src/data.sqlite",
        "src/secrets.toml",
    ],
)
def test_sensitive_paths_are_denied(
    policy: PermissionPolicy,
    relative_path: str,
) -> None:
    """隐藏路径、凭据和数据库不能被受限工具读取。"""

    with pytest.raises(
        PermissionDenied,
    ):
        policy.read_text(relative_path)


@pytest.mark.parametrize(
    ("action", "path"),
    [
        ("edit_file", "src/app.py"),
        ("create_file", "src/new.py"),
        ("run_command", "python -m pytest"),
        ("unknown_operation", "src/app.py"),
    ],
)
def test_non_read_operations_are_denied_by_default(
    policy: PermissionPolicy,
    action: str,
    path: str,
) -> None:
    """写入、命令执行和未知操作默认不授权。"""

    with pytest.raises(
        PermissionDenied,
        match="操作未授权",
    ):
        policy.authorize(action, path)


def test_none_path_is_denied(
    policy: PermissionPolicy,
) -> None:
    """工具没有提供合法路径时不能读取。"""

    with pytest.raises(PermissionDenied):
        policy.authorize("read_file", None)


def test_symlink_to_outside_is_denied(
    project: Path,
    policy: PermissionPolicy,
    tmp_path: Path,
) -> None:
    """符号链接不能用来读取仓库外的内容。"""

    outside = tmp_path / "outside.py"
    outside.write_text(
        "password = 'outside'\n",
        encoding="utf-8",
    )

    (project / "src" / "external.py").symlink_to(outside)

    with pytest.raises(
        PermissionDenied,
        match="符号链接",
    ):
        policy.read_text("src/external.py")


def test_symlink_to_inside_is_also_denied(
    project: Path,
    policy: PermissionPolicy,
) -> None:
    """第一阶段采取保守策略，连内部符号链接也拒绝。"""

    (project / "src" / "alias.py").symlink_to(project / "src" / "app.py")

    with pytest.raises(
        PermissionDenied,
        match="符号链接",
    ):
        policy.read_text("src/alias.py")


def test_symlinked_directory_is_denied(
    project: Path,
    policy: PermissionPolicy,
) -> None:
    """路径中间的符号链接目录也不能绕过检查。"""

    (project / "src" / "linked").symlink_to(
        project / "tests",
        target_is_directory=True,
    )

    with pytest.raises(
        PermissionDenied,
        match="符号链接",
    ):
        policy.read_text("src/linked/test_app.py")


def test_read_size_limit_is_enforced(
    project: Path,
) -> None:
    """不能通过工具一次读取超过配置上限的文件。"""

    policy = PermissionPolicy(
        project_root=project,
        max_read_bytes=8,
    )

    with pytest.raises(
        PermissionDenied,
        match="最大读取限制",
    ):
        policy.read_text("src/app.py")


def test_non_utf8_file_is_denied(
    project: Path,
    policy: PermissionPolicy,
) -> None:
    """不把无法解码的二进制内容直接返回给模型。"""

    (project / "src" / "binary.py").write_bytes(b"\xff\xfe\x00")

    with pytest.raises(
        PermissionDenied,
        match="UTF-8",
    ):
        policy.read_text("src/binary.py")


def test_missing_file_is_not_read(
    policy: PermissionPolicy,
) -> None:
    """路径合法，但文件不存在时应明确报错。"""

    with pytest.raises(FileNotFoundError):
        policy.read_text("src/not_exists.py")


def test_invalid_project_root_is_rejected(
    tmp_path: Path,
) -> None:
    """不能为不存在的项目目录创建有效策略。"""

    with pytest.raises(
        ValueError,
        match="项目目录不存在",
    ):
        PermissionPolicy(tmp_path / "missing")


@pytest.mark.parametrize(
    "limit",
    [
        0,
        -1,
        True,
    ],
)
def test_invalid_read_limit_is_rejected(
    project: Path,
    limit: int,
) -> None:
    """读取上限必须是正整数，不能误用布尔值。"""

    with pytest.raises(
        ValueError,
        match="正整数",
    ):
        PermissionPolicy(
            project_root=project,
            max_read_bytes=limit,
        )
