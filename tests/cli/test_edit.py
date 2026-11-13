"""安全文件编辑命令测试。"""

from pathlib import Path

import pytest

from ai_software_dev_agent import cli


def test_edit_applies_after_exact_confirmation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target = tmp_path / "demo.py"
    target.write_text(
        "def add(a, b):\n    return a+b\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "builtins.input",
        lambda _prompt: "yes",
    )

    result = cli.main(
        [
            "edit",
            "--project",
            str(tmp_path),
            "--path",
            "demo.py",
            "--old",
            "return a+b",
            "--new",
            "return a + b",
        ]
    )

    output = capsys.readouterr().out

    assert result == 0
    assert "修改预览" in output
    assert "-    return a+b" in output
    assert "+    return a + b" in output
    assert "修改完成" in output

    assert target.read_text(encoding="utf-8") == ("def add(a, b):\n    return a + b\n")


@pytest.mark.parametrize(
    "confirmation",
    ["", "no", "YES"],
)
def test_edit_cancels_without_exact_yes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    confirmation: str,
) -> None:
    target = tmp_path / "demo.py"
    target.write_text(
        "value = 1\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "builtins.input",
        lambda _prompt: confirmation,
    )

    result = cli.main(
        [
            "edit",
            "--project",
            str(tmp_path),
            "--path",
            "demo.py",
            "--old",
            "value = 1",
            "--new",
            "value = 2",
        ]
    )

    output = capsys.readouterr().out

    assert result == 0
    assert "修改预览" in output
    assert "已取消修改" in output
    assert target.read_text(encoding="utf-8") == "value = 1\n"


def test_edit_rejects_unmatched_content(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target = tmp_path / "demo.py"
    target.write_text(
        "value = 1\n",
        encoding="utf-8",
    )

    result = cli.main(
        [
            "edit",
            "--project",
            str(tmp_path),
            "--path",
            "demo.py",
            "--old",
            "value = 999",
            "--new",
            "value = 2",
        ]
    )

    captured = capsys.readouterr()

    assert result == 1
    assert "实际匹配 0 次" in captured.err
    assert target.read_text(encoding="utf-8") == "value = 1\n"


def test_edit_rejects_unsafe_path(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = cli.main(
        [
            "edit",
            "--project",
            str(tmp_path),
            "--path",
            "../outside.py",
            "--old",
            "old",
            "--new",
            "new",
        ]
    )

    assert result == 1
    assert "无法生成修改预览" in capsys.readouterr().err


def test_edit_rejects_stale_preview(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target = tmp_path / "demo.py"
    target.write_text(
        "value = 1\n",
        encoding="utf-8",
    )

    def change_file_before_confirmation(_prompt: str) -> str:
        target.write_text(
            "value = 99\n",
            encoding="utf-8",
        )
        return "yes"

    monkeypatch.setattr(
        "builtins.input",
        change_file_before_confirmation,
    )

    result = cli.main(
        [
            "edit",
            "--project",
            str(tmp_path),
            "--path",
            "demo.py",
            "--old",
            "value = 1",
            "--new",
            "value = 2",
        ]
    )

    captured = capsys.readouterr()

    assert result == 1
    assert "文件在预览后已发生变化" in captured.err
    assert target.read_text(encoding="utf-8") == "value = 99\n"


def test_edit_cancels_on_eof(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target = tmp_path / "demo.py"
    target.write_text(
        "value = 1\n",
        encoding="utf-8",
    )

    def raise_eof(_prompt: str) -> str:
        raise EOFError

    monkeypatch.setattr(
        "builtins.input",
        raise_eof,
    )

    result = cli.main(
        [
            "edit",
            "--project",
            str(tmp_path),
            "--path",
            "demo.py",
            "--old",
            "value = 1",
            "--new",
            "value = 2",
        ]
    )

    assert result == 0
    assert target.read_text(encoding="utf-8") == "value = 1\n"
    assert "已取消修改" in capsys.readouterr().out


@pytest.mark.parametrize(
    "arguments",
    [
        ["--path", "demo.py", "--new", "changed"],
        ["--path", "demo.py", "--old", "original"],
    ],
)
def test_edit_requires_old_and_new_arguments(
    tmp_path: Path,
    arguments: list[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main(
            [
                "edit",
                "--project",
                str(tmp_path),
                *arguments,
            ]
        )

    assert exc_info.value.code == 2


def test_edit_help_displays_arguments(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["edit", "--help"])

    assert exc_info.value.code == 0

    output = capsys.readouterr().out

    assert "--project" in output
    assert "--path" in output
    assert "--old" in output
    assert "--new" in output
