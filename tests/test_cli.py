"""CLI 命令行功能测试。"""

from pathlib import Path

import pytest
from langchain_core.language_models import FakeListChatModel

from ai_software_dev_agent import cli
from ai_software_dev_agent.model import ModelConfigError, ModelSettings


def test_doctor_accepts_existing_directory(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """有效项目目录应该检查成功。"""

    result = cli.main(["doctor", "--project", str(tmp_path)])
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
        cli.main(["doctor", "--project", str(missing_path)])

    assert exc_info.value.code == 2
    assert "项目目录不存在" in capsys.readouterr().err


def test_doctor_uses_current_directory_by_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """未指定项目目录时使用当前工作目录。"""

    monkeypatch.chdir(tmp_path)

    result = cli.main(["doctor"])
    output = capsys.readouterr().out

    assert result == 0
    assert str(tmp_path.resolve()) in output


def test_help_displays_doctor_command(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """帮助信息应该包含 doctor 命令。"""

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--help"])

    assert exc_info.value.code == 0
    assert "doctor" in capsys.readouterr().out


def test_inspect_lists_files(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """CLI 应该能列出仓库代码文件。"""

    (tmp_path / "a.py").write_text("pass\n", encoding="utf-8")

    result = cli.main(
        [
            "inspect",
            "--project",
            str(tmp_path),
        ]
    )

    assert result == 0
    assert "a.py" in capsys.readouterr().out


def test_read_displays_file(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """CLI 应该能显示文件内容。"""

    (tmp_path / "a.py").write_text(
        "value = 42\n",
        encoding="utf-8",
    )

    result = cli.main(
        [
            "read",
            "--project",
            str(tmp_path),
            "--path",
            "a.py",
        ]
    )

    assert result == 0
    assert "value = 42" in capsys.readouterr().out


def test_search_displays_matches(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """CLI 应该能显示搜索结果和行号。"""

    (tmp_path / "a.py").write_text(
        "def main():\n    pass\n",
        encoding="utf-8",
    )

    result = cli.main(
        [
            "search",
            "--project",
            str(tmp_path),
            "--query",
            "def main",
        ]
    )

    assert result == 0
    assert "a.py:1: def main():" in capsys.readouterr().out


def test_ask_uses_fake_model(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """ask 命令应正确输出模型回答。"""

    settings = ModelSettings(
        api_key="test-key",
        model_name="test-model",
        base_url="https://example.com/v1",
    )

    fake_model = FakeListChatModel(responses=["这是来自假模型的回答"])

    monkeypatch.setattr(
        cli,
        "load_model_settings",
        lambda: settings,
    )

    monkeypatch.setattr(
        cli,
        "create_chat_model",
        lambda _settings: fake_model,
    )

    result = cli.main(
        [
            "ask",
            "--question",
            "你好",
        ]
    )

    assert result == 0
    assert "这是来自假模型的回答" in capsys.readouterr().out


def test_ask_requires_question() -> None:
    """ask 命令必须提供问题参数。"""

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["ask"])

    assert exc_info.value.code == 2


def test_ask_reports_missing_config(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """模型配置错误应该转换为 CLI 错误。"""

    def broken_settings() -> ModelSettings:
        raise ModelConfigError("缺少 API Key")

    monkeypatch.setattr(
        cli,
        "load_model_settings",
        broken_settings,
    )

    with pytest.raises(SystemExit) as exc_info:
        cli.main(
            [
                "ask",
                "--question",
                "你好",
            ]
        )

    assert exc_info.value.code == 2
    assert "缺少 API Key" in capsys.readouterr().err
