"""仓库探索工具测试。"""

from pathlib import Path

import pytest

from ai_software_dev_agent.repository import RepositoryError, RepositoryExplorer


def test_list_files_ignores_cache_and_binary(tmp_path: Path) -> None:
    """扫描时应跳过虚拟环境与不支持的文件。"""

    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("print('ok')\n", encoding="utf-8")

    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "private.py").write_text("secret", encoding="utf-8")

    (tmp_path / "image.png").write_bytes(b"\x00\x01")

    assert RepositoryExplorer(tmp_path).list_files() == ["app/main.py"]


def test_read_file(tmp_path: Path) -> None:
    """应该正确读取 UTF-8 文件及中文内容。"""

    (tmp_path / "main.py").write_text("hello = '你好'\n", encoding="utf-8")

    assert RepositoryExplorer(tmp_path).read_file("main.py") == ("hello = '你好'\n")


def test_read_rejects_outside_path(tmp_path: Path) -> None:
    """不允许通过相对路径访问项目外部。"""

    with pytest.raises(
        RepositoryError,
        match="不在指定项目目录内",
    ):
        RepositoryExplorer(tmp_path).read_file("../outside.py")


def test_read_rejects_symlink_outside(tmp_path: Path) -> None:
    """符号链接指向项目外部时应被拒绝。"""

    outside = tmp_path.parent / "external.py"
    (tmp_path / "link.py").symlink_to(outside)

    with pytest.raises(
        RepositoryError,
        match="不在指定项目目录内",
    ):
        RepositoryExplorer(tmp_path).read_file("link.py")


def test_read_rejects_ignored_directory(tmp_path: Path) -> None:
    """不允许读取运行时数据目录。"""

    (tmp_path / ".runtime").mkdir()
    (tmp_path / ".runtime" / "record.json").write_text("{}", encoding="utf-8")

    with pytest.raises(
        RepositoryError,
        match="不允许访问已忽略的目录",
    ):
        RepositoryExplorer(tmp_path).read_file(".runtime/record.json")


def test_read_rejects_oversized_file(tmp_path: Path) -> None:
    """超过单文件大小限制时应拒绝读取。"""

    (tmp_path / "large.txt").write_text(
        "x" * (64 * 1024 + 1),
        encoding="utf-8",
    )

    with pytest.raises(RepositoryError, match="超过"):
        RepositoryExplorer(tmp_path).read_file("large.txt")


def test_search_returns_line_numbers(tmp_path: Path) -> None:
    """搜索应返回正确的文件、行号和内容。"""

    (tmp_path / "main.py").write_text(
        "hello\nDef Main():\npass\n",
        encoding="utf-8",
    )

    hits = RepositoryExplorer(tmp_path).search("def main")

    assert [(hit.path, hit.line_number, hit.line) for hit in hits] == [
        ("main.py", 2, "Def Main():")
    ]


def test_search_rejects_empty_keyword(tmp_path: Path) -> None:
    """空关键词不应该触发全仓库搜索。"""

    with pytest.raises(
        RepositoryError,
        match="不能为空",
    ):
        RepositoryExplorer(tmp_path).search("  ")


def test_hidden_directories_are_not_scanned_or_read(
    tmp_path: Path,
) -> None:
    """未显式允许的隐藏目录也应该受到保护。"""

    hidden_dir = tmp_path / ".private"
    hidden_dir.mkdir()

    (hidden_dir / "note.py").write_text(
        "private = True\n",
        encoding="utf-8",
    )

    explorer = RepositoryExplorer(tmp_path)

    assert explorer.list_files() == []

    with pytest.raises(
        RepositoryError,
        match="隐藏文件或目录",
    ):
        explorer.read_file(".private/note.py")
