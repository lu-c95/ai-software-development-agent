"""使用 LangChain 通过 OpenAI 兼容接口调用聊天模型。"""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI


class ModelConfigError(ValueError):
    """模型配置或用户输入不合法。"""


@dataclass(frozen=True)
class ModelSettings:
    """通用模型服务配置。"""

    api_key: str
    model_name: str
    base_url: str


# 固定助手角色与动态用户问题分开管理。
CHAT_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "你是一名专业的 Python 开发助手。"
            "请使用中文回答技术问题，解释清楚关键原理。"
            "没有真正读取或执行代码时，不要声称已经完成相关操作。",
        ),
        ("human", "{question}"),
    ]
)


def load_model_settings() -> ModelSettings:
    """从环境变量或当前目录 .env 加载通用模型配置。"""

    load_dotenv(
        dotenv_path=Path.cwd() / ".env",
        override=False,
    )

    api_key = os.getenv("LLM_API_KEY", "").strip()
    model_name = os.getenv("LLM_MODEL", "").strip()
    base_url = os.getenv("LLM_BASE_URL", "").strip()

    if not api_key:
        raise ModelConfigError("缺少 LLM_API_KEY，请检查 .env 配置")

    if not model_name:
        raise ModelConfigError("缺少 LLM_MODEL，请检查模型名称")

    if not base_url:
        raise ModelConfigError("缺少 LLM_BASE_URL，请检查 API 地址")

    return ModelSettings(
        api_key=api_key,
        model_name=model_name,
        base_url=base_url,
    )


def create_chat_model(settings: ModelSettings) -> BaseChatModel:
    """创建 LangChain Chat Model，此时不发送 API 请求。"""

    return ChatOpenAI(
        model=settings.model_name,
        api_key=settings.api_key,
        base_url=settings.base_url,
        timeout=120,
        max_retries=0,
        max_tokens=2048,
        use_responses_api=False,
    )


def build_messages(question: str) -> list[BaseMessage]:
    """通过 Prompt Template 构建聊天消息。"""

    if not question.strip():
        raise ModelConfigError("用户问题不能为空")

    return CHAT_PROMPT.format_messages(question=question)


def generate_answer(
    model: BaseChatModel,
    question: str,
) -> str:
    """发送模型请求并返回文本回答。"""

    messages = build_messages(question)

    response = model.invoke(messages)

    return str(response.text)
