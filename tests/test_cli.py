"""CLI 命令行功能测试。"""

from pathlib import Path

import pytest

from ai_software_dev_agent.cli import main


def test_doctor_accepts_existing_directory(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """有效项目目录应该检查成功。"""

    result = main(["doctor", "--project", str(tmp_path)])

    output = capsys.readouterr().out

    assert result == 0
    assert "项目目录检查通过" in output
    assert str(tmp_path.resolve()) in output


def test_doctor_rejects_missing_directory(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """不存在的项目目录应该被拒绝。"""

    missing_path = tmp_path / "missing"

    with pytest.raises(SystemExit) as exc_info:
        main(["doctor", "--project", str(missing_path)])

    assert exc_info.value.code == 2
    assert "项目目录不存在" in capsys.readouterr().err


def test_doctor_uses_current_directory_by_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """未指定项目目录时，使用当前工作目录。"""

    monkeypatch.chdir(tmp_path)

    result = main(["doctor"])

    output = capsys.readouterr().out

    assert result == 0
    assert str(tmp_path.resolve()) in output


def test_help_displays_doctor_command(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """帮助信息应该包含 doctor 命令。"""

    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])

    assert exc_info.value.code == 0
    assert "doctor" in capsys.readouterr().out
