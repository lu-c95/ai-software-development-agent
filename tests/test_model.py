"""LangChain 模型配置与调用测试。"""

from pathlib import Path

import pytest
from langchain_core.language_models import FakeListChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from ai_software_dev_agent.model import (
    ModelConfigError,
    build_messages,
    generate_answer,
    load_model_settings,
)


def test_load_model_settings_from_env_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """能够从 .env 文件加载通用模型配置。"""

    monkeypatch.chdir(tmp_path)

    # 隔离真实环境变量，保证测试结果可重复。
    for name in (
        "LLM_API_KEY",
        "LLM_MODEL",
        "LLM_BASE_URL",
    ):
        monkeypatch.delenv(name, raising=False)

    (tmp_path / ".env").write_text(
        "LLM_API_KEY=test-key\n"
        "LLM_MODEL=qwen/qwen3.8-27b:free\n"
        "LLM_BASE_URL=https://openrouter.ai/api/v1\n",
        encoding="utf-8",
    )

    settings = load_model_settings()

    assert settings.api_key == "test-key"
    assert settings.model_name == "qwen/qwen3.8-27b:free"
    assert settings.base_url == "https://openrouter.ai/api/v1"


def test_missing_api_key_raises_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """缺少 API Key 时应该明确报错。"""

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("LLM_MODEL", "qwen/qwen3.8-27b:free")

    with pytest.raises(
        ModelConfigError,
        match="LLM_API_KEY",
    ):
        load_model_settings()


def test_build_messages_creates_correct_roles() -> None:
    """Prompt Template 应构造正确的消息角色。"""

    messages = build_messages("解释 Python 装饰器")

    assert len(messages) == 2
    assert isinstance(messages[0], SystemMessage)
    assert isinstance(messages[1], HumanMessage)

    assert "Python 开发助手" in messages[0].content
    assert messages[1].content == "解释 Python 装饰器"


def test_generate_answer_with_fake_model() -> None:
    """使用假模型验证调用流程，不消耗真实 API 额度。"""

    fake_model = FakeListChatModel(
        responses=["装饰器可以在不修改原函数的情况下扩展行为。"]
    )

    answer = generate_answer(
        fake_model,
        "什么是 Python 装饰器？",
    )

    assert "扩展行为" in answer


def test_empty_question_is_rejected() -> None:
    """空问题不应该触发模型调用。"""

    with pytest.raises(
        ModelConfigError,
        match="用户问题不能为空",
    ):
        build_messages("   ")
