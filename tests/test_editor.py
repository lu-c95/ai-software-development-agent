"""代码修改、Diff 预览与安全写入测试。"""

from dataclasses import replace
from pathlib import Path

import pytest

from ai_software_dev_agent.editor import (
    CodeEditor,
    FileEditError,
)


@pytest.fixture
def sample_file(tmp_path: Path) -> Path:
    """创建每个测试使用的独立 Python 文件。"""

    target = tmp_path / "demo.py"
    target.write_text(
        "def add(a, b):\n    return a+b\n",
        encoding="utf-8",
    )
    return target


def test_preview_does_not_modify_file(
    tmp_path: Path,
    sample_file: Path,
) -> None:
    """预览时只能生成差异，不能修改文件。"""

    editor = CodeEditor(tmp_path)
    before = sample_file.read_bytes()

    preview = editor.preview_replace(
        "demo.py",
        "return a+b",
        "return a + b",
    )

    assert sample_file.read_bytes() == before
    assert preview.path == "demo.py"
    assert "-    return a+b" in preview.diff
    assert "+    return a + b" in preview.diff
    assert "--- a/demo.py" in preview.diff
    assert "+++ b/demo.py" in preview.diff


def test_apply_changes_file(
    tmp_path: Path,
    sample_file: Path,
) -> None:
    """应用补丁后应完成预期替换。"""

    editor = CodeEditor(tmp_path)

    preview = editor.preview_replace(
        "demo.py",
        "return a+b",
        "return a + b",
    )

    editor.apply(preview)

    assert sample_file.read_text(encoding="utf-8") == (
        "def add(a, b):\n    return a + b\n"
    )


def test_rejects_missing_old_text(
    tmp_path: Path,
    sample_file: Path,
) -> None:
    """找不到旧代码片段时不能修改文件。"""

    editor = CodeEditor(tmp_path)

    with pytest.raises(FileEditError, match="实际匹配 0 次"):
        editor.preview_replace(
            "demo.py",
            "return a - b",
            "return a + b",
        )

    assert "return a+b" in sample_file.read_text()


def test_rejects_ambiguous_match(tmp_path: Path) -> None:
    """旧代码片段出现多次时拒绝猜测修改位置。"""

    target = tmp_path / "demo.py"
    target.write_text(
        "def first():\n    return 1\n\ndef second():\n    return 1\n",
        encoding="utf-8",
    )

    editor = CodeEditor(tmp_path)

    with pytest.raises(FileEditError, match="实际匹配 2 次"):
        editor.preview_replace(
            "demo.py",
            "return 1",
            "return 2",
        )


def test_rejects_no_op(
    tmp_path: Path,
    sample_file: Path,
) -> None:
    """没有实际变化的替换应被拒绝。"""

    editor = CodeEditor(tmp_path)

    with pytest.raises(FileEditError, match="没有实际修改"):
        editor.preview_replace(
            "demo.py",
            "return a+b",
            "return a+b",
        )


@pytest.mark.parametrize(
    "file_path",
    [
        "../outside.py",
        "/tmp/outside.py",
        ".venv/demo.py",
        ".env",
        "README.md",
    ],
)
def test_rejects_disallowed_paths(
    tmp_path: Path,
    file_path: str,
) -> None:
    """拒绝越界路径、隐藏文件和非 Python 文件。"""

    editor = CodeEditor(tmp_path)

    with pytest.raises(FileEditError):
        editor.preview_replace(
            file_path,
            "old",
            "new",
        )


def test_rejects_symlink(tmp_path: Path) -> None:
    """不允许通过符号链接修改文件。"""

    real_file = tmp_path / "real.py"
    real_file.write_text("value = 1\n", encoding="utf-8")

    link = tmp_path / "link.py"
    link.symlink_to(real_file)

    editor = CodeEditor(tmp_path)

    with pytest.raises(FileEditError, match="符号链接"):
        editor.preview_replace(
            "link.py",
            "value = 1",
            "value = 2",
        )


def test_rejects_stale_preview(
    tmp_path: Path,
    sample_file: Path,
) -> None:
    """预览后原文件变化时不能覆盖新内容。"""

    editor = CodeEditor(tmp_path)

    preview = editor.preview_replace(
        "demo.py",
        "return a+b",
        "return a + b",
    )

    # 模拟其他程序在预览后修改了文件。
    sample_file.write_text(
        "def add(a, b):\n    return a - b\n",
        encoding="utf-8",
    )

    with pytest.raises(FileEditError, match="发生变化"):
        editor.apply(preview)

    assert "return a - b" in sample_file.read_text()


def test_rejects_modified_preview(
    tmp_path: Path,
    sample_file: Path,
) -> None:
    """预览内容不一致时不允许应用。"""

    editor = CodeEditor(tmp_path)

    preview = editor.preview_replace(
        "demo.py",
        "return a+b",
        "return a + b",
    )

    invalid_preview = replace(
        preview,
        diff="被修改过的差异内容",
    )

    with pytest.raises(FileEditError, match="预览差异不一致"):
        editor.apply(invalid_preview)

    assert "return a+b" in sample_file.read_text()


def test_rejects_oversized_update(
    tmp_path: Path,
    sample_file: Path,
) -> None:
    """替换后超过大小限制时不能写入。"""

    editor = CodeEditor(tmp_path)

    with pytest.raises(FileEditError, match="超过大小限制"):
        editor.preview_replace(
            "demo.py",
            "return a+b",
            "x" * (256 * 1024 + 1),
        )

    assert "return a+b" in sample_file.read_text()


def test_preserves_line_endings(tmp_path: Path) -> None:
    """修改时应保留文件原有的 CRLF 换行符。"""

    target = tmp_path / "demo.py"
    target.write_bytes(b"def add(a, b):\r\n    return a+b\r\n")

    editor = CodeEditor(tmp_path)

    preview = editor.preview_replace(
        "demo.py",
        "return a+b",
        "return a + b",
    )

    editor.apply(preview)

    assert target.read_bytes() == (b"def add(a, b):\r\n    return a + b\r\n")
