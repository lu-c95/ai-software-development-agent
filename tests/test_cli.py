"""CLI 命令行功能测试。"""

import json
from pathlib import Path

import pytest
from langchain_core.language_models import FakeListChatModel

from ai_software_dev_agent import cli
from ai_software_dev_agent.model import ModelConfigError, ModelSettings
from ai_software_dev_agent.planning import (
    DevelopmentPlan,
    PlanningError,
    PlanStep,
)


def test_doctor_accepts_existing_directory(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = cli.main(["doctor", "--project", str(tmp_path)])
    output = capsys.readouterr().out

    assert result == 0
    assert "项目目录检查通过" in output
    assert str(tmp_path.resolve()) in output


def test_doctor_rejects_missing_directory(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
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
    monkeypatch.chdir(tmp_path)

    result = cli.main(["doctor"])
    output = capsys.readouterr().out

    assert result == 0
    assert str(tmp_path.resolve()) in output


def test_help_displays_doctor_command(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--help"])

    assert exc_info.value.code == 0
    assert "doctor" in capsys.readouterr().out


def test_inspect_lists_files(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "a.py").write_text(
        "pass\n",
        encoding="utf-8",
    )

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
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["ask"])

    assert exc_info.value.code == 2


def test_ask_reports_missing_config(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
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


def test_plan_outputs_structured_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """plan 命令应该输出合法 JSON。"""

    settings = ModelSettings(
        api_key="test-key",
        model_name="test-model",
        base_url="https://example.com/v1",
    )

    expected_plan = DevelopmentPlan(
        goal="增加用户登录功能",
        steps=[
            PlanStep(
                title="检查项目",
                action="了解现有代码结构",
                verification="确认认证相关文件",
            ),
            PlanStep(
                title="实现功能",
                action="编写登录接口",
                verification="运行 pytest",
            ),
        ],
    )

    # 避免 CLI 测试调用真实模型。
    monkeypatch.setattr(
        cli,
        "load_model_settings",
        lambda: settings,
    )
    monkeypatch.setattr(
        cli,
        "create_chat_model",
        lambda _settings: object(),
    )
    monkeypatch.setattr(
        cli,
        "generate_development_plan",
        lambda _model, _task: expected_plan,
    )

    result = cli.main(
        [
            "plan",
            "--task",
            "增加用户登录功能",
        ]
    )

    assert result == 0

    output = json.loads(capsys.readouterr().out)

    assert output["goal"] == "增加用户登录功能"
    assert len(output["steps"]) == 2
    assert output["steps"][1]["verification"] == "运行 pytest"


def test_plan_requires_task() -> None:
    """plan 命令必须提供开发任务。"""

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["plan"])

    assert exc_info.value.code == 2


def test_plan_reports_structured_output_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """结构化结果异常时，CLI 应返回错误码。"""

    settings = ModelSettings(
        api_key="test-key",
        model_name="test-model",
        base_url="https://example.com/v1",
    )

    def broken_plan(_model: object, _task: str) -> None:
        raise PlanningError("模型没有返回开发计划")

    monkeypatch.setattr(
        cli,
        "load_model_settings",
        lambda: settings,
    )
    monkeypatch.setattr(
        cli,
        "create_chat_model",
        lambda _settings: object(),
    )
    monkeypatch.setattr(
        cli,
        "generate_development_plan",
        broken_plan,
    )

    result = cli.main(
        [
            "plan",
            "--task",
            "增加用户登录功能",
        ]
    )

    assert result == 1
    assert "结构化生成失败" in capsys.readouterr().err
