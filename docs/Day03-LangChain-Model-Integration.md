# Day 03 — LangChain Model Integration（LangChain 模型集成）

## 1. 当天目标

在 AI Software Development Agent 中引入 LangChain，实现统一的模型调用能力，为后续任务规划、工具调用和 Agent 开发奠定基础。

本次主要完成：

1. 安装 LangChain 相关依赖。
2. 使用 `.env` 管理模型配置。
3. 实现模型配置、Prompt（提示词）和模型调用模块。
4. 在 CLI 中增加 `ask` 命令。
5. 使用 Fake Model（假模型）完成自动化测试。
6. 接入真实免费模型，并解决实际 API 调用问题。

**最终模型配置：**

| 项目 | 配置 |
|---|---|
| 模型平台 | OpenRouter |
| 模型 | `cohere/north-mini-code:free` |
| LangChain 适配器 | `ChatOpenAI` |
| API 接口 | OpenAI 兼容的 Chat Completions |
| 模型调用 | `model.invoke()` |

本阶段实现单轮问答，Day 05 再增加持续多轮对话。

---

## 2. 项目结构与环境配置

### 2.1 文件变化

```text
ai-software-development-agent/
├── src/
│   └── ai_software_dev_agent/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py             # 修改：增加 ask 命令
│       ├── model.py           # 新增：LangChain 模型调用
│       └── repository.py
├── tests/
│   ├── test_cli.py           # 修改：增加 ask 测试
│   ├── test_model.py         # 新增：模型模块测试
│   └── test_repository.py
├── docs/
│   ├── Development-Plan.md
│   ├── Day01-Project-Setup.md
│   ├── Day02-Repository-Explorer.md
│   └── Day03-LangChain-Model-Integration.md
├── .env                     # 新增，不提交 Git
├── .env.example             # 新增
├── pyproject.toml           # 修改：增加依赖
└── README.md
```

### 2.2 创建文件

在项目根目录执行：

```bash
touch .env .env.example

touch src/ai_software_dev_agent/model.py

touch tests/test_model.py

touch docs/Day03-LangChain-Model-Integration.md
```

### 2.3 修改 pyproject.toml

在 `[project]` 中配置运行依赖：

```toml
dependencies = [
    "langchain>=1.0,<2.0",
    "langchain-core>=1.0,<2.0",
    "langchain-openai>=1.0,<2.0",
    "openai>=2.0,<4.0",
    "python-dotenv>=1.0,<2.0",
]
```

依赖职责：

| 依赖 | 作用 |
|---|---|
| `langchain` | 高层 Agent API，后续学习 `create_agent` |
| `langchain-core` | 消息、Prompt Template、模型接口 |
| `langchain-openai` | `ChatOpenAI` 模型适配器 |
| `openai` | OpenAI 兼容接口 SDK 与异常类型 |
| `python-dotenv` | 加载 `.env` 环境变量 |

安装：

```bash
python3 -m pip install -e ".[dev]"
```

注意：`langchain` 主包虽然已经安装，但 Day 03 的实际调用主要使用 `langchain-core` 和 `langchain-openai`，高层 Agent API 会在后续学习。

### 2.4 配置模型

`.env.example`：

```dotenv
LLM_API_KEY=
LLM_MODEL=cohere/north-mini-code:free
LLM_BASE_URL=https://openrouter.ai/api/v1
```

`.env`：

```dotenv
LLM_API_KEY=实际申请的API_Key
LLM_MODEL=cohere/north-mini-code:free
LLM_BASE_URL=https://openrouter.ai/api/v1
```

通过 `LLM_*` 通用环境变量管理模型配置，可以在更换兼容服务时减少 Python 代码修改。

`.env` 包含真实密钥，必须由 `.gitignore` 忽略，不应上传 GitHub。

---

## 3. model.py — LangChain 模型调用模块

### 3.1 完整代码

文件：`src/ai_software_dev_agent/model.py`

```python
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


# 使用固定系统指令和动态用户问题构造消息。
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
    """从环境变量或当前目录的 .env 加载模型配置。"""

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
    """创建聊天模型对象，此时不会发送网络请求。"""

    return ChatOpenAI(
        model=settings.model_name,
        api_key=settings.api_key,
        base_url=settings.base_url,
        timeout=120,
        max_retries=0,
        max_tokens=1024,
        use_responses_api=False,
    )


def build_messages(question: str) -> list[BaseMessage]:
    """使用 Prompt Template 构建模型消息。"""

    if not question.strip():
        raise ModelConfigError("用户问题不能为空")

    return CHAT_PROMPT.format_messages(question=question)


def generate_answer(
    model: BaseChatModel,
    question: str,
) -> str:
    """调用模型并提取文本回答。"""

    messages = build_messages(question)

    response = model.invoke(messages)

    return str(response.text)
```

### 3.2 核心实现解释

#### 3.2.1 ModelSettings：管理模型配置

```python
@dataclass(frozen=True)
class ModelSettings:
    api_key: str
    model_name: str
    base_url: str
```

将模型配置组织成结构化对象，而不是在每个函数中分别读取环境变量。

例如：

```python
settings = ModelSettings(
    api_key="test-key",
    model_name="test-model",
    base_url="https://example.com/v1",
)

print(settings.model_name)
# test-model
```

`frozen=True` 表示对象创建后，不能直接修改其字段。

#### 3.2.2 load_model_settings()：加载模型配置

```python
load_dotenv(
    dotenv_path=Path.cwd() / ".env",
    override=False,
)
```

参数含义：

- `Path.cwd()`：获取程序当前工作目录。
- `dotenv_path`：指定 `.env` 文件位置。
- `override=False`：不覆盖进程中已经存在的同名环境变量。

读取配置：

```python
api_key = os.getenv("LLM_API_KEY", "").strip()
```

- `os.getenv()`：读取环境变量。
- 第二个参数 `""`：变量不存在时返回空字符串。
- `strip()`：去除首尾空白字符。

例如：

```python
import os

os.environ["LLM_MODEL"] = "test-model"

print(os.getenv("LLM_MODEL"))
# test-model
```

**注意：当前代码依赖程序运行时的工作目录。如果以后需要从任意目录启动 CLI，应进一步完善配置文件定位机制。**

另外，若终端中存在旧的 `LLM_MODEL` 环境变量，`override=False` 会保留终端变量，而不是使用 `.env` 中的新值。

#### 3.2.3 ChatPromptTemplate：构建消息

```python
CHAT_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", "你是一名专业的 Python 开发助手。"),
        ("human", "{question}"),
    ]
)
```

这里是简化示例，实际代码的系统指令更完整。

`{question}` 是动态变量，调用时替换成用户输入。

例如：

```python
messages = build_messages("什么是 Python 装饰器？")

print(type(messages[0]).__name__)
print(type(messages[1]).__name__)
print(messages[1].content)
```

结果：

```text
SystemMessage
HumanMessage
什么是 Python 装饰器？
```

三个常用消息类型：

| 消息类型 | 含义 |
|---|---|
| `SystemMessage` | 系统指令，定义模型职责 |
| `HumanMessage` | 用户输入 |
| `AIMessage` | 模型返回的回答 |

使用 Prompt Template 的好处是将固定指令与动态输入分离，避免在不同业务函数里重复拼接提示词。

#### 3.2.4 create_chat_model()：创建模型

```python
return ChatOpenAI(
    model=settings.model_name,
    api_key=settings.api_key,
    base_url=settings.base_url,
    timeout=120,
    max_retries=0,
    max_tokens=1024,
    use_responses_api=False,
)
```

`ChatOpenAI` 是 LangChain 提供的模型适配器。

这里通过 OpenAI 兼容协议调用 OpenRouter，而不是直接调用 OpenAI 的模型服务。

参数说明：

| 参数 | 作用 |
|---|---|
| `model` | 模型 ID |
| `api_key` | 请求鉴权 |
| `base_url` | API 服务地址 |
| `timeout` | 请求超时秒数 |
| `max_retries` | SDK 自动重试次数 |
| `max_tokens` | 限制最大生成 Token 数量 |
| `use_responses_api=False` | 使用 Chat Completions 接口 |

创建 `ChatOpenAI` 对象通常不会发起模型推理请求。

真正的网络请求发生在调用 `invoke()` 时。

#### 3.2.5 generate_answer()：执行模型调用

```python
messages = build_messages(question)

response = model.invoke(messages)

return str(response.text)
```

执行过程：

1. 将用户问题转换成 LangChain 消息。
2. 调用 `model.invoke(messages)`。
3. 模型服务返回结果。
4. LangChain 将结果封装为消息对象。
5. 提取文本并返回 CLI。

`response.content` 是消息原始内容，可能是字符串或内容块列表。

当前使用 `response.text` 提取回答中的文本部分。

#### 3.2.6 Dependency Injection（依赖注入）

```python
def generate_answer(
    model: BaseChatModel,
    question: str,
) -> str:
```

这里没有在函数内部创建 `ChatOpenAI`，而是由外部传入模型对象。

这样做的价值是同一套调用逻辑既可以使用真实模型，也可以使用 Fake Model。

```python
generate_answer(real_model, "你好")
```

用于真实 API 调用。

```python
generate_answer(fake_model, "你好")
```

用于自动化测试。

避免将模型创建、模型调用和测试逻辑强行绑定在一起。

---

## 4. LangChain 到底起到了什么作用？

这是 Day 03 最值得理解的知识点。

### 4.1 LangChain 是什么？

LangChain 是用于构建大模型应用和 Agent 的开发框架。

它不是大模型，也不负责自己生成文字。

实际生成回答的是 OpenRouter 提供的模型服务。

LangChain 在模型和我们的 Python 业务代码之间提供了一套相对统一的接口，包括：

- Chat Model（聊天模型）
- Messages（消息）
- Prompt Template（提示词模板）
- Tools（工具）
- Structured Output（结构化输出）
- Agent（智能体）

今天实际学习了前面三个方面，后面三个功能会在 Day 04、Day 05 继续实现。

### 4.2 本项目具体哪里使用了 LangChain？

**第一处：定义消息模板**

```python
from langchain_core.prompts import ChatPromptTemplate
```

使用：

```python
CHAT_PROMPT = ChatPromptTemplate.from_messages(...)
```

统一管理系统提示词和用户问题。

**第二处：统一消息对象**

```python
from langchain_core.messages import BaseMessage
```

由 `format_messages()` 生成 `SystemMessage`、`HumanMessage` 等消息对象。

**第三处：创建模型适配器**

```python
from langchain_openai import ChatOpenAI
```

通过：

```python
model = ChatOpenAI(...)
```

创建符合 LangChain 接口的模型对象。

**第四处：统一模型调用**

```python
response = model.invoke(messages)
```

调用模型时不需要自己构建完整 HTTP 请求。

**第五处：自动化测试**

```python
from langchain_core.language_models import FakeListChatModel
```

使用 LangChain 提供的假模型，不联网也能测试调用逻辑。

### 4.3 哪些部分不是 LangChain 的？

| 代码或功能 | 所属技术 |
|---|---|
| `ChatOpenAI` | LangChain OpenAI 集成 |
| `ChatPromptTemplate` | LangChain Core |
| `BaseChatModel` / `BaseMessage` | LangChain Core |
| `FakeListChatModel` | LangChain Core |
| `argparse` | Python 标准库 |
| `dataclass` | Python 标准库 |
| `os.getenv()` | Python 标准库 |
| `python-dotenv` | 独立第三方库 |
| OpenRouter | 模型服务聚合平台 |
| North Mini Code | 实际执行推理的模型 |

因此，并不是安装了 LangChain，整个项目的代码就都属于 LangChain。

### 4.4 如果不用 LangChain，会怎么样？

**仍然可以调用大模型。**

事实上，我们前面几个项目就主要使用原生 OpenAI 兼容 SDK 实现模型调用。

例如，不使用 LangChain，使用 OpenAI SDK：

```python
from openai import OpenAI

client = OpenAI(
    api_key="你的API_Key",
    base_url="https://openrouter.ai/api/v1",
)

response = client.chat.completions.create(
    model="cohere/north-mini-code:free",
    messages=[
        {
            "role": "system",
            "content": "你是一名 Python 开发助手。",
        },
        {
            "role": "user",
            "content": "解释 Python 装饰器。",
        },
    ],
)

print(response.choices[0].message.content)
```

上面是原生 SDK 的等价思路示例，未在本次文档中作为新增实验执行。

而使用 LangChain：

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "你是一名 Python 开发助手。"),
        ("human", "{question}"),
    ]
)

model = ChatOpenAI(
    model="cohere/north-mini-code:free",
    api_key="你的API_Key",
    base_url="https://openrouter.ai/api/v1",
    use_responses_api=False,
)

messages = prompt.format_messages(question="解释 Python 装饰器。")

response = model.invoke(messages)

print(response.text)
```

两种方式本质上都会调用远程模型 API。

LangChain 不一定能让简单问答的代码更短。

### 4.5 为什么第四个项目仍然要使用 LangChain？

因为我们的最终目标不是简单问答，而是开发软件工程 Agent。

后续需要：

1. 让模型理解开发需求。
2. 为模型提供代码搜索、文件读取等工具。
3. 将模型输出转换成结构化任务计划。
4. 管理模型与工具之间的交互。
5. 将模型能力放入 LangGraph 工作流中。

使用 LangChain 可以复用现成的模型、消息、工具和 Agent 抽象，减少重复编写模型接口适配代码。

**但 LangChain 不是必须使用的框架。**

如果项目只调用一个固定模型，任务流程很简单，直接使用 OpenAI SDK 也完全合理。

使用框架的代价包括：

- 新增依赖。
- 需要理解框架的 API 和抽象。
- 框架版本升级可能影响代码。
- 第三方模型的高级功能不一定完全兼容。

因此，选择 LangChain 是工程取舍，而不是所有 AI 项目都必须使用它。

### 4.6 LangChain 与 LangGraph 怎样分工？

本项目后续采用：

```text
用户开发需求
    ↓
CLI
    ↓
LangGraph（控制整体工作流）
    ↓
LangChain（模型、消息、工具、Agent）
    ↓
RepositoryExplorer / Code Editor / Test Runner
    ↓
执行结果
    ↓
LangGraph（路由、状态、恢复）
    ↓
用户
```

LangChain 主要解决：

**模型和工具如何交互。**

LangGraph 主要解决：

**整个任务按照什么流程执行，以及如何管理状态、分支、中断和恢复。**

当前 Day 03 尚未引入 LangGraph，也尚未让模型调用仓库探索工具。

---

## 5. CLI 与自动化测试

### 5.1 cli.py — 完整最终代码

文件：`src/ai_software_dev_agent/cli.py`

```python
"""AI 软件开发智能体的命令行入口。"""

import argparse
import sys
from pathlib import Path

from openai import APIStatusError, OpenAIError

from ai_software_dev_agent import __version__
from ai_software_dev_agent.model import (
    ModelConfigError,
    create_chat_model,
    generate_answer,
    load_model_settings,
)
from ai_software_dev_agent.repository import (
    RepositoryError,
    RepositoryExplorer,
)


def build_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器。"""

    parser = argparse.ArgumentParser(
        prog="ai-dev-agent",
        description="AI Software Development Agent",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="检查目标项目目录",
    )

    inspect_parser = subparsers.add_parser(
        "inspect",
        help="列出项目中的代码文件",
    )

    read_parser = subparsers.add_parser(
        "read",
        help="读取指定代码文件",
    )

    search_parser = subparsers.add_parser(
        "search",
        help="搜索代码关键词",
    )

    # 新增模型问答命令。
    ask_parser = subparsers.add_parser(
        "ask",
        help="使用 LangChain 调用聊天模型",
    )

    # 仓库相关命令统一支持 --project。
    for command_parser in (
        doctor_parser,
        inspect_parser,
        read_parser,
        search_parser,
    ):
        command_parser.add_argument(
            "--project",
            type=Path,
            default=Path.cwd(),
            help="目标项目目录",
        )

    read_parser.add_argument(
        "--path",
        required=True,
        help="相对项目根目录的文件路径",
    )

    search_parser.add_argument(
        "--query",
        required=True,
        help="搜索关键词",
    )

    search_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="最多返回的结果数",
    )

    ask_parser.add_argument(
        "--question",
        required=True,
        help="发送给模型的问题",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """解析命令并执行对应功能。"""

    parser = build_parser()
    args = parser.parse_args(argv)

    # 模型问答不依赖目标代码仓库。
    if args.command == "ask":
        try:
            settings = load_model_settings()
            model = create_chat_model(settings)
            answer = generate_answer(model, args.question)

        except ModelConfigError as exc:
            parser.error(str(exc))

        except APIStatusError as exc:
            # 将不同 HTTP 错误转换成更明确的用户提示。
            if exc.status_code == 404:
                reason = "模型不存在或当前不可用，请检查模型 ID"
            elif exc.status_code == 429:
                reason = "平台限流或模型访问量过大"
            elif exc.status_code == 401:
                reason = "API Key 无效或没有访问权限"
            else:
                reason = "请检查模型服务状态及请求配置"

            print(
                f"模型请求失败：HTTP {exc.status_code}，{reason}。",
                file=sys.stderr,
            )
            return 1

        except OpenAIError as exc:
            print(
                f"模型请求失败：{type(exc).__name__}。",
                file=sys.stderr,
            )
            return 1

        print(answer)
        return 0

    try:
        explorer = RepositoryExplorer(args.project)

        if args.command == "doctor":
            print(f"项目目录检查通过：{explorer.root}")
            print("当前模式：仅进行目录检查，不修改任何文件。")

        elif args.command == "inspect":
            files = explorer.list_files()

            print(f"找到 {len(files)} 个可探索文件：")

            for path in files:
                print(path)

        elif args.command == "read":
            content = explorer.read_file(args.path)
            print(content, end="")

        elif args.command == "search":
            hits = explorer.search(
                args.query,
                limit=args.limit,
            )

            print(f"找到 {len(hits)} 条匹配结果：")

            for hit in hits:
                print(f"{hit.path}:{hit.line_number}: {hit.line}")

    except RepositoryError as exc:
        parser.error(str(exc))

    return 0
```

### 5.2 cli.py 主要改动

新增 `ask` 命令：

```python
ask_parser = subparsers.add_parser(
    "ask",
    help="使用 LangChain 调用聊天模型",
)
```

增加 `--question` 参数：

```python
ask_parser.add_argument(
    "--question",
    required=True,
    help="发送给模型的问题",
)
```

模型调用：

```python
settings = load_model_settings()
model = create_chat_model(settings)
answer = generate_answer(model, args.question)
```

对应：

```text
CLI 接收问题
    ↓
加载配置
    ↓
创建 LangChain 模型
    ↓
构建 Messages
    ↓
model.invoke()
    ↓
提取并输出回答
```

原来的仓库探索功能不需要修改。

异常处理中，`APIStatusError` 必须放在 `OpenAIError` 前面，因为前者属于后者的子类。

### 5.3 test_model.py — 完整代码

文件：`tests/test_model.py`

```python
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
    """能够从 .env 文件加载模型配置。"""

    monkeypatch.chdir(tmp_path)

    # 清除真实环境变量，保证使用测试 .env。
    for name in (
        "LLM_API_KEY",
        "LLM_MODEL",
        "LLM_BASE_URL",
    ):
        monkeypatch.delenv(name, raising=False)

    (tmp_path / ".env").write_text(
        "LLM_API_KEY=test-key\n"
        "LLM_MODEL=cohere/north-mini-code:free\n"
        "LLM_BASE_URL=https://openrouter.ai/api/v1\n",
        encoding="utf-8",
    )

    settings = load_model_settings()

    assert settings.api_key == "test-key"
    assert settings.model_name == "cohere/north-mini-code:free"
    assert settings.base_url == "https://openrouter.ai/api/v1"


def test_missing_api_key_raises_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """缺少 API Key 时应报错。"""

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("LLM_MODEL", "test-model")

    with pytest.raises(
        ModelConfigError,
        match="LLM_API_KEY",
    ):
        load_model_settings()


def test_build_messages_creates_correct_roles() -> None:
    """验证 Prompt Template 构造正确的消息。"""

    messages = build_messages("解释 Python 装饰器")

    assert len(messages) == 2
    assert isinstance(messages[0], SystemMessage)
    assert isinstance(messages[1], HumanMessage)

    assert "Python 开发助手" in messages[0].content
    assert messages[1].content == "解释 Python 装饰器"


def test_generate_answer_with_fake_model() -> None:
    """使用假模型验证调用逻辑，不访问真实 API。"""

    fake_model = FakeListChatModel(
        responses=["装饰器可以在不修改原函数的情况下扩展行为。"]
    )

    answer = generate_answer(
        fake_model,
        "什么是 Python 装饰器？",
    )

    assert "扩展行为" in answer


def test_empty_question_is_rejected() -> None:
    """空问题不能触发模型调用。"""

    with pytest.raises(
        ModelConfigError,
        match="用户问题不能为空",
    ):
        build_messages("   ")
```

### 5.4 test_cli.py — 完整代码

文件：`tests/test_cli.py`

```python
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
    """CLI 能列出代码文件。"""

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
    """CLI 能读取指定文件。"""

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
    """CLI 能显示搜索结果及行号。"""

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
    """ask 命令使用假模型输出回答。"""

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
    """模型配置错误应转换为 CLI 错误。"""

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
```

### 5.5 测试重点

**FakeListChatModel**

使用预设返回内容代替真实模型，避免自动化测试依赖网络和付费 API。

**monkeypatch**

临时替换配置加载、模型创建等函数，让测试只关注当前业务逻辑。

**tmp_path**

生成独立临时目录，避免测试修改真实 `.env` 或项目文件。

本次测试设计总数为 24 项，最终以实际 pytest 执行结果为准。

---

## 6. 真实 Debug：模型 API 接入

今天先后使用智谱和 OpenRouter，真实遇到了 HTTP 429、HTTP 404 等问题。

以下保留排查时使用过的终端命令、实际结果、判断和处理方式。诊断脚本读取运行时的模型配置，重新执行时会使用当前 `.env`，不一定重现历史错误。

### 6.1 智谱模型调用返回 HTTP 429

最初使用：

```dotenv
ZAI_API_KEY=实际API_Key
LLM_MODEL=glm-4.7-flash
ZAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
```

执行模型调用：

```bash
ai-dev-agent ask \
  --question "你好，请只回答：连接成功"
```

结果：

```text
模型请求失败：OpenAIRateLimitError
```

最初 CLI 隐藏了平台业务错误信息，无法确定原因。

#### 6.1.1 查看真实 API 错误

使用过的诊断命令：

```bash
python - <<'PY'
from openai import OpenAIError

from ai_software_dev_agent.model import (
    create_chat_model,
    generate_answer,
    load_model_settings,
)

settings = load_model_settings()
model = create_chat_model(settings)

print("当前模型：", settings.model_name)
print("API 地址：", settings.base_url)

try:
    answer = generate_answer(model, "你好，只回答OK")
    print("模型回答：", answer)

except OpenAIError as exc:
    print("异常类型：", type(exc).__name__)
    print("HTTP 状态码：", getattr(exc, "status_code", None))

    body = getattr(exc, "body", None)

    if isinstance(body, dict):
        detail = body.get("error", body)

        if isinstance(detail, dict):
            print("业务错误码：", detail.get("code"))
            print("平台错误说明：", detail.get("message"))
        else:
            print("错误说明：", str(detail)[:300])
    else:
        print("错误摘要：", str(exc)[:300])
PY
```

第一次获得：

```text
异常类型：OpenAIRateLimitError
HTTP 状态码：429
业务错误码：1302
平台错误说明：您的账户已达到速率限制
```

用户当天请求次数很少，因此不能简单认定是当天调用总次数过高。

随后将：

```python
max_retries = (1,)
```

改为：

```python
max_retries = (0,)
```

目的是防止 SDK 自动增加重试请求。

再次测试，获得：

```text
异常类型：OpenAIRateLimitError
HTTP 状态码：429
业务错误码：1305
平台错误说明：该模型当前访问量过大，请您稍后再试
```

这说明模型服务仍然拒绝请求，而关闭自动重试并不能解决服务端限制。

#### 6.1.2 绕过 LangChain，验证原生 SDK

为了排查是否是 LangChain 的请求配置导致错误，又直接使用 OpenAI SDK。

执行：

```bash
python - <<'PY'
from openai import OpenAI, APIStatusError
from ai_software_dev_agent.model import load_model_settings

settings = load_model_settings()

client = OpenAI(
    api_key=settings.api_key,
    base_url=settings.base_url,
    max_retries=0,
    timeout=60,
)

try:
    response = client.chat.completions.create(
        model=settings.model_name,
        messages=[
            {"role": "user", "content": "你好，只回答OK"}
        ],
        max_tokens=32,
    )

    print("调用成功")
    print("模型回答：", response.choices[0].message.content)

except APIStatusError as exc:
    print("HTTP 状态码：", exc.status_code)

    body = exc.response.json()
    error = body.get("error", body)

    print("平台错误：", error)
PY
```

实际结果：仍然无法获得正常回答，返回 API 限制错误。

**判断：**

原生 SDK 绕过了 LangChain，也出现限制错误，说明没有证据表明 LangChain 是导致本次失败的原因。

此外，智谱官方体验中心能够正常回答，但体验中心和开放 API 可能采用不同的流量限制策略。

**处理：**

不再反复请求同一个免费模型，尝试其他可用模型服务。

### 6.2 OpenRouter Qwen 免费版本返回 HTTP 404

随后切换到 OpenRouter。

初始配置：

```dotenv
LLM_MODEL=qwen/qwen3.8-27b:free
LLM_BASE_URL=https://openrouter.ai/api/v1
```

执行：

```bash
ai-dev-agent ask \
  --question "你好，请只回答：连接成功"
```

返回 HTTP 404。

#### 6.2.1 先检查实际加载的配置

执行：

```bash
python - <<'PY'
from ai_software_dev_agent.model import load_model_settings

settings = load_model_settings()

print("API Key 已配置：", bool(settings.api_key))
print("实际模型：", repr(settings.model_name))
print("实际 API 地址：", repr(settings.base_url))
PY
```

目的：排除 `.env` 配置错误或旧环境变量覆盖问题。

#### 6.2.2 使用原生 SDK 获取平台错误说明

执行：

```bash
python - <<'PY'
from openai import OpenAI, APIStatusError, OpenAIError
from ai_software_dev_agent.model import load_model_settings

settings = load_model_settings()

client = OpenAI(
    api_key=settings.api_key,
    base_url=settings.base_url,
    max_retries=0,
    timeout=60,
)

try:
    response = client.chat.completions.create(
        model=settings.model_name,
        messages=[
            {"role": "user", "content": "你好，只回答OK"}
        ],
        max_tokens=32,
    )

    print("调用成功：", response.choices[0].message.content)

except APIStatusError as exc:
    print("异常类型：", type(exc).__name__)
    print("HTTP 状态码：", exc.status_code)

    body = exc.body
    error = body.get("error", body) if isinstance(body, dict) else {}

    if isinstance(error, dict):
        print("平台错误码：", error.get("code"))
        print("平台错误说明：", error.get("message"))
    else:
        print("平台错误摘要：", str(error)[:200])

except OpenAIError as exc:
    print("异常类型：", type(exc).__name__)
    print("请求失败，未收到有效的 API 状态响应")
PY
```

实际返回：

```text
异常类型：NotFoundError
HTTP 状态码：404
平台错误码：404
平台错误说明：
This model is unavailable for free.
The paid version is available now -
use this slug instead: qwen/qwen3.8-27b
```

**判断：**

平台明确指出该模型的免费版本不可用。

因此不是普通的请求频率问题，也没有必要修改 LangChain 架构。

**处理：**

不切换到收费模型，改用其他免费模型。

### 6.3 更换 North Mini Code 后调用成功

最终修改 `.env`：

```dotenv
LLM_MODEL=cohere/north-mini-code:free
LLM_BASE_URL=https://openrouter.ai/api/v1
```

先检查模型配置：

```bash
python - <<'PY'
from ai_software_dev_agent.model import load_model_settings

settings = load_model_settings()

print("API Key 已配置：", bool(settings.api_key))
print("模型：", settings.model_name)
print("API 地址：", settings.base_url)
PY
```

再执行：

```bash
ai-dev-agent ask \
  --question "你好，请只回答：连接成功"
```

**实际结果：连接成功。**

至此完成真实模型调用链：

```text
ai-dev-agent ask
    ↓
load_model_settings()
    ↓
create_chat_model()
    ↓
ChatOpenAI
    ↓
ChatPromptTemplate
    ↓
model.invoke()
    ↓
OpenRouter API
    ↓
North Mini Code
    ↓
AIMessage
    ↓
CLI 输出模型回答
```

### 6.4 改进异常处理

Debug 过程中发现：

- 404 曾被错误描述为速率限制。
- 429 只显示异常类型，不方便判断服务问题。

因此修改 `cli.py`，通过 `APIStatusError.status_code` 区分 HTTP 错误类型，并避免直接打印可能包含敏感信息的完整异常。

本次 Debug 最重要的工程结论是：

**模型调用失败时，应先取得具体状态码和平台业务错误，再区分代码问题、网络问题、账户限制和模型服务不可用，不能只凭异常名称盲目修改配置。**

---

## 7. 当天核心知识总结

### 7.1 LangChain 的价值

LangChain 提供模型、消息、提示词、工具和 Agent 的统一抽象。

它不是大模型，也不是执行工作流的唯一选择。

简单问答可以直接用 OpenAI SDK；复杂 Agent 开发中，LangChain 的工具和 Agent 抽象更有价值。

### 7.2 模型调用与业务代码分离

当前设计：

```text
CLI → model.py → LangChain → 模型服务
```

模型配置、创建、消息构造和调用职责独立，方便测试和切换兼容服务。

### 7.3 自动化测试不依赖真实模型

使用 Fake Model 可以验证 Python 调用逻辑，不需要每次测试都消耗 API 额度。

但是 Fake Model 测试不能证明真实平台、模型权限或高级功能一定可用。

### 7.4 模型服务需要独立排查

真实 API 调用可能失败于：

- 鉴权
- 模型不存在
- 平台限流
- 模型访问量过大
- 网络超时
- 第三方接口兼容性问题

这些问题必须结合实际 HTTP 状态码、平台错误信息以及最小化诊断请求判断。

**Day 03 最终成果：通过 LangChain 成功调用 OpenRouter 免费模型，并完成可复用、可测试的模型接入模块。**