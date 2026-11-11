# Day 04 — LangChain Tools & Planning（工具与任务规划）

## 1. 当天目标

在 Day 03 模型问答功能的基础上，为 AI Software Development Agent 增加工具调用和结构化任务规划能力。

主要完成：

1. 将已有的仓库探索功能封装为 LangChain Tools（工具）。
2. 使用 Pydantic（数据校验库）定义工具参数。
3. 使用 `bind_tools()` 让模型识别和选择工具。
4. 使用 Pydantic 定义结构化开发计划。
5. 使用 `with_structured_output()` 生成开发计划。
6. 为 CLI 增加 `plan` 命令。
7. 编写自动化测试并完成真实模型验收。
8. 排查结构化输出异常并优化模型配置。

最终形成两条独立的模型能力：

**工具调用：**

```text
用户需求
    ↓
LangChain Chat Model
    ↓
模型产生 tool_calls
    ↓
Python 工具执行（后续 Agent 负责自动组织）
```

**任务规划：**

```text
用户开发需求
    ↓
Prompt Template
    ↓
LangChain Chat Model
    ↓
Structured Output
    ↓
Pydantic 校验
    ↓
DevelopmentPlan 对象
    ↓
CLI 输出 JSON
```

本日只实现只读仓库工具与规划能力，不自动修改文件、执行开发计划或完成 Agent 循环。

---

## 2. 项目结构和环境配置

### 2.1 文件变化

```text
ai-software-development-agent/
├── src/
│   └── ai_software_dev_agent/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py             # 修改：新增 plan 命令
│       ├── model.py           # 修改：增加模型生成空间
│       ├── planning.py        # 新增：开发计划
│       ├── repository.py      # 复用 Day 02 实现
│       └── tools.py           # 新增：仓库工具
├── tests/
│   ├── test_cli.py           # 修改：新增 plan 测试
│   ├── test_model.py
│   ├── test_planning.py      # 新增
│   ├── test_repository.py
│   └── test_tools.py         # 新增
├── docs/
│   ├── Development-Plan.md
│   ├── Day01-Project-Setup.md
│   ├── Day02-Repository-Explorer.md
│   ├── Day03-LangChain-Model-Integration.md
│   └── Day04-LangChain-Tools-And-Planning.md
├── .env
├── .env.example
├── .gitignore
└── pyproject.toml
```

### 2.2 创建文件

在项目根目录执行：

```bash
touch src/ai_software_dev_agent/tools.py
touch src/ai_software_dev_agent/planning.py

touch tests/test_tools.py
touch tests/test_planning.py

touch docs/Day04-LangChain-Tools-And-Planning.md
```

### 2.3 检查虚拟环境

```bash
source .venv/bin/activate

which python

python -c 'import sys; print(sys.executable)'
```

确认 Python 来自当前项目的 `.venv`。

### 2.4 更新依赖

本日直接使用 Pydantic，因此在 `pyproject.toml` 的 `[project]` 运行依赖中添加：

```toml
"pydantic>=2.0,<3.0",
```

安装：

```bash
python -m pip install -e ".[dev]"
```

检查：

```bash
python -m pip show langchain-core pydantic
```

Pydantic 可能已作为其他依赖的间接依赖安装，但项目直接使用的库应尽量显式声明。

---

## 3. LangChain Tools（工具）

### 3.1 为什么需要 Tools？

Day 02 已经实现：

```python
explorer = RepositoryExplorer(project)

explorer.list_files()
explorer.read_file("app.py")
explorer.search("FastAPI")
```

这些都是普通 Python 方法。

但大模型不知道我们有哪些 Python 方法，也不能直接执行本地 Python 代码。

因此需要把已有方法转换为模型能够理解的工具：

```text
Python 函数
    ↓
@tool 装饰器
    ↓
LangChain Tool
    ├── name
    ├── description
    ├── args_schema
    └── 执行逻辑
```

模型通过工具名称、描述和参数 Schema（结构定义）判断何时使用工具、需要传入哪些参数。

真正执行工具的仍然是 Python，而不是模型本身。

### 3.2 tools.py 完整代码

文件：`src/ai_software_dev_agent/tools.py`

```python
"""将已有仓库探索功能封装为 LangChain 工具。"""

from pathlib import Path

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

from ai_software_dev_agent.repository import RepositoryExplorer


class ReadFileArgs(BaseModel):
    """读取文件工具的参数结构。"""

    path: str = Field(
        min_length=1,
        description="相对于项目根目录的文件路径，例如 src/main.py",
    )


class SearchRepositoryArgs(BaseModel):
    """搜索仓库工具的参数结构。"""

    query: str = Field(
        min_length=1,
        description="要搜索的代码关键词，例如 FastAPI",
    )

    limit: int = Field(
        default=10,
        ge=1,
        le=20,
        description="最多返回的搜索结果数，范围 1～20",
    )


def create_repository_tools(project: Path) -> list[BaseTool]:
    """为指定项目创建一组只读的 LangChain 工具。"""

    explorer = RepositoryExplorer(project)

    @tool("inspect_repository")
    def inspect_repository() -> str:
        """列出代码仓库中可探索的文件，用于了解项目结构。"""

        files = explorer.list_files()

        if not files:
            return "没有找到可探索的文件。"

        return "\n".join(files)

    @tool("read_repository_file", args_schema=ReadFileArgs)
    def read_repository_file(path: str) -> str:
        """读取仓库中的指定文本文件，用于查看代码实现。"""

        return explorer.read_file(path)

    @tool("search_repository", args_schema=SearchRepositoryArgs)
    def search_repository(query: str, limit: int = 10) -> str:
        """在仓库中搜索代码关键词，返回文件路径、行号和内容。"""

        hits = explorer.search(query, limit=limit)

        if not hits:
            return "没有找到匹配的代码。"

        return "\n".join(f"{hit.path}:{hit.line_number}: {hit.line}" for hit in hits)

    return [
        inspect_repository,
        read_repository_file,
        search_repository,
    ]
```

### 3.3 代码讲解

#### 3.3.1 @tool：把 Python 函数转换为工具

例如：

```python
@tool("read_repository_file", args_schema=ReadFileArgs)
def read_repository_file(path: str) -> str:
    """读取仓库中的指定文本文件，用于查看代码实现。"""

    return explorer.read_file(path)
```

这里需要理解四个部分。

**名称：**

`read_repository_file`

用于告诉模型当前工具叫什么。

**描述：**

函数的 Docstring（文档字符串）用于解释工具的用途。

模型可以依据描述选择工具，因此描述不能只写“读取文件”，还应说明什么时候使用。

**参数 Schema：**

`ReadFileArgs` 定义输入字段及校验规则。

**执行逻辑：**

仍然使用 Day 02 的：

```python
explorer.read_file(path)
```

所以今天没有重新编写文件读取功能，而是增加了一个 LangChain 适配层。

#### 3.3.2 BaseTool：统一工具接口

函数：

```python
def create_repository_tools(
    project: Path,
) -> list[BaseTool]:
```

返回的是 LangChain 工具对象列表。

这些对象具有统一接口，例如：

```python
tool.name
tool.description
tool.args
tool.invoke(...)
```

未来可以直接传给：

```python
model.bind_tools(tools)
```

#### 3.3.3 为什么使用工厂函数？

```python
def create_repository_tools(project: Path) -> list[BaseTool]:
    explorer = RepositoryExplorer(project)
```

因为工具需要绑定具体的代码仓库。

例如：

```python
from pathlib import Path

tools = create_repository_tools(Path.cwd())
```

工具内部使用的 `explorer` 始终对应这个项目。

嵌套函数可以访问外层的 `explorer`，这体现了 Python Closure（闭包）的应用。

同时，模型不需要自己提供项目根目录，而是在我们已经授权的范围内使用工具。

#### 3.3.4 为什么复用 RepositoryExplorer？

如果直接写：

```python
Path(path).read_text()
```

可能绕开 Day 02 已经设计的目录越界、文件类型及大小限制。

现在的调用链是：

```text
LangChain Tool
    ↓
Pydantic 参数校验
    ↓
RepositoryExplorer
    ↓
安全检查
    ↓
文件读取或代码搜索
```

Pydantic 负责验证参数结构，RepositoryExplorer 负责控制文件访问范围。

两者职责不同，不能互相替代。

---

## 4. Pydantic：工具参数校验

### 4.1 BaseModel 和 Field

例如：

```python
class SearchRepositoryArgs(BaseModel):
    query: str = Field(
        min_length=1,
        description="搜索关键词",
    )

    limit: int = Field(
        default=10,
        ge=1,
        le=20,
        description="最多返回的结果数量",
    )
```

参数说明：

| 参数 | 作用 |
|---|---|
| `BaseModel` | 定义结构化数据模型 |
| `Field()` | 配置字段的约束和描述 |
| `min_length=1` | 字符串至少一个字符 |
| `default=10` | 默认值为 10 |
| `ge=1` | 大于等于 1 |
| `le=20` | 小于等于 20 |
| `description` | 字段说明，可用于生成 Schema |

正常示例：

```python
args = SearchRepositoryArgs(
    query="FastAPI",
    limit=5,
)

print(args.model_dump())
```

结果：

```python
{
    "query": "FastAPI",
    "limit": 5,
}
```

错误示例：

```python
SearchRepositoryArgs(
    query="FastAPI",
    limit=100,
)
```

因为 `100` 超过允许上限，Pydantic 会抛出 `ValidationError`。

### 4.2 参数校验和业务校验的区别

Pydantic 能验证：

- 参数是否存在。
- 参数类型是否符合要求。
- 字符串长度。
- 数值范围。
- 列表元素数量。
- 嵌套对象结构。

但它不能单凭 `path: str` 判断文件是否允许读取。

例如：

```text
../private.py
```

这个字符串满足 `min_length=1`，但仍可能越过仓库根目录。

因此文件路径安全检查仍由 RepositoryExplorer 完成。

**结论：Schema 校验只能保证输入符合声明的结构，不能代替业务安全检查。**

---

## 5. 工具自动化测试

### 5.1 test_tools.py 完整代码

文件：`tests/test_tools.py`

```python
"""LangChain 仓库工具测试。"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from ai_software_dev_agent.repository import RepositoryError
from ai_software_dev_agent.tools import create_repository_tools


def test_create_repository_tools(tmp_path: Path) -> None:
    """应该创建三个名称明确的 LangChain 工具。"""

    tools = create_repository_tools(tmp_path)

    assert len(tools) == 3

    assert [item.name for item in tools] == [
        "inspect_repository",
        "read_repository_file",
        "search_repository",
    ]

    assert all(item.description for item in tools)


def test_inspect_repository_tool(tmp_path: Path) -> None:
    """工具能够列出仓库文件。"""

    (tmp_path / "main.py").write_text(
        "print('hello')\n",
        encoding="utf-8",
    )

    tools = create_repository_tools(tmp_path)
    inspect_tool = tools[0]

    result = inspect_tool.invoke({})

    assert "main.py" in result


def test_read_repository_file_tool(tmp_path: Path) -> None:
    """工具能够读取允许访问的文件。"""

    (tmp_path / "app.py").write_text(
        "answer = 42\n",
        encoding="utf-8",
    )

    tools = create_repository_tools(tmp_path)
    read_tool = tools[1]

    result = read_tool.invoke(
        {
            "path": "app.py",
        }
    )

    assert result == "answer = 42\n"


def test_search_repository_tool(tmp_path: Path) -> None:
    """工具能够搜索关键词并返回行号。"""

    (tmp_path / "app.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n",
        encoding="utf-8",
    )

    tools = create_repository_tools(tmp_path)
    search_tool = tools[2]

    result = search_tool.invoke(
        {
            "query": "FastAPI",
            "limit": 5,
        }
    )

    assert "app.py:1:" in result
    assert "app.py:2:" in result


def test_search_tool_rejects_invalid_limit(
    tmp_path: Path,
) -> None:
    """Pydantic 应拒绝超出范围的参数。"""

    tools = create_repository_tools(tmp_path)
    search_tool = tools[2]

    with pytest.raises(ValidationError):
        search_tool.invoke(
            {
                "query": "FastAPI",
                "limit": 100,
            }
        )


def test_read_tool_rejects_parent_directory(
    tmp_path: Path,
) -> None:
    """不允许通过 .. 读取仓库之外的文件。"""

    tools = create_repository_tools(tmp_path)
    read_tool = tools[1]

    with pytest.raises(RepositoryError):
        read_tool.invoke(
            {
                "path": "../private.py",
            }
        )
```

### 5.2 测试设计与意义

本文件共有六个测试：

| 测试 | 验证内容 |
|---|---|
| `test_create_repository_tools` | 工具数量、名称和描述 |
| `test_inspect_repository_tool` | 列出文件 |
| `test_read_repository_file_tool` | 读取文件 |
| `test_search_repository_tool` | 搜索和行号 |
| `test_search_tool_rejects_invalid_limit` | Pydantic 参数范围校验 |
| `test_read_tool_rejects_parent_directory` | 文件路径安全限制 |

测试使用 `tmp_path` 创建临时仓库，因此不会影响真实代码文件。

运行：

```bash
python -m pytest tests/test_tools.py -v
```

实际结果：六个测试通过。

### 5.3 手动调用工具

执行：

```bash
python - <<'PY'
from pathlib import Path

from ai_software_dev_agent.tools import create_repository_tools

tools = create_repository_tools(Path.cwd())

tool_map = {
    item.name: item
    for item in tools
}

print("=== 工具清单 ===")

for item in tools:
    print(item.name)
    print(item.description)
    print(item.args)

print("\n=== 仓库文件 ===")

result = tool_map["inspect_repository"].invoke({})
print(result)

print("\n=== 搜索 RepositoryExplorer ===")

result = tool_map["search_repository"].invoke({
    "query": "RepositoryExplorer",
    "limit": 5,
})

print(result)
PY
```

实际验证成功：

- 工具能够返回名称、描述与参数定义。
- `inspect_repository` 能列出项目文件。
- `search_repository` 能返回关键词匹配位置。

这里没有调用模型 API。

---

## 6. bind_tools()：让模型识别工具

### 6.1 核心原理

```python
model_with_tools = model.bind_tools(tools)
```

`bind_tools()` 的作用是把工具定义提供给聊天模型。

工具定义包括：

- 工具名称。
- 工具描述。
- 参数结构。

模型可以根据用户问题，决定是否产生工具调用请求。

但是：

**`bind_tools()` 不负责执行 Python 工具。**

例如，模型可能返回：

```python
[
    {
        "name": "inspect_repository",
        "args": {},
        "id": "call_xxx",
        "type": "tool_call",
    }
]
```

这只是请求，不代表仓库已经被读取。

### 6.2 真实模型调用命令

本日执行：

```bash
python - <<'PY'
from pathlib import Path

from langchain_core.messages import HumanMessage

from ai_software_dev_agent.model import (
    create_chat_model,
    load_model_settings,
)
from ai_software_dev_agent.tools import create_repository_tools

tools = create_repository_tools(Path.cwd())

settings = load_model_settings()
model = create_chat_model(settings)

model_with_tools = model.bind_tools(tools)

response = model_with_tools.invoke([
    HumanMessage(
        content=(
            "请查看当前项目有哪些代码文件。"
            "你应该调用 inspect_repository 工具，"
            "不要凭空编造文件列表。"
        )
    )
])

print("=== 模型回答 ===")
print(response.text)

print("\n=== 模型请求调用的工具 ===")
print(response.tool_calls)
PY
```

实际结果：模型成功生成了符合预期的工具调用请求。

说明目前使用的 OpenRouter 模型能够在这次实验中识别并请求调用 LangChain 工具。

### 6.3 model.invoke() 与 tool.invoke()

虽然名称一样，实际对象不同。

```python
model.invoke(messages)
```

调用模型，获取 AI 回复。

```python
tool.invoke({"path": "app.py"})
```

执行本地 Python 工具。

两者都遵循 LangChain Runnable（可运行对象）接口的使用方式。

### 6.4 模型什么时候真正使用工具？

完整的工具执行流程应该是：

```text
用户请求
    ↓
模型判断需要工具
    ↓
模型生成 tool_calls
    ↓
Python 根据名称找到工具
    ↓
校验参数并执行工具
    ↓
工具生成执行结果
    ↓
将结果返回模型
    ↓
模型继续回答
```

本日只分别验证了工具执行和模型生成工具调用请求，尚未自动连接成完整循环。

这部分将在 Day 05 使用 Agent 实现。

---

## 7. Planning：结构化开发计划

### 7.1 为什么不能只让模型输出普通文字？

例如：

> 首先检查代码，然后添加登录接口，最后运行测试。

这种文本可以让人阅读，但程序很难稳定地识别：

- 有多少个步骤？
- 每步的标题是什么？
- 具体操作是什么？
- 如何验证完成？
- 哪些条件还没有确认？

因此需要结构化输出：

```json
{
  "goal": "为 FastAPI 项目增加用户登录功能",
  "assumptions": [],
  "steps": [
    {
      "title": "检查项目",
      "action": "了解现有代码",
      "verification": "确认现有路由"
    },
    {
      "title": "实现功能",
      "action": "编写登录接口",
      "verification": "运行 pytest"
    }
  ]
}
```

这是结构示例，不是本次模型的原始输出。

### 7.2 planning.py 完整代码

文件：`src/ai_software_dev_agent/planning.py`

```python
"""使用 LangChain 和 Pydantic 生成结构化开发计划。"""

from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from ai_software_dev_agent.model import ModelConfigError


class PlanningError(RuntimeError):
    """模型未能返回符合预期结构的开发计划。"""


class PlanStep(BaseModel):
    """单个开发步骤。"""

    title: str = Field(
        min_length=1,
        description="步骤名称，例如检查现有代码结构",
    )

    action: str = Field(
        min_length=1,
        description="本步骤需要完成的具体开发操作",
    )

    verification: str = Field(
        min_length=1,
        description="如何验证这个步骤是否完成",
    )


class DevelopmentPlan(BaseModel):
    """完整的软件开发任务计划。"""

    goal: str = Field(
        min_length=1,
        description="开发任务的整体目标",
    )

    assumptions: list[str] = Field(
        default_factory=list,
        description="尚未验证、需要后续确认的前提条件",
    )

    steps: list[PlanStep] = Field(
        min_length=2,
        max_length=5,
        description="按执行顺序排列的开发步骤，数量为2到5",
    )


# 当前模型在简短规划任务上的结构化输出更稳定。
PLANNING_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "你是一名专业的 Python 软件开发规划助手。"
            "根据用户开发需求，生成恰好3个简短、可执行的步骤。"
            "每个步骤包含 title、action 和 verification。"
            "每项 action 和 verification 尽量控制在30个汉字以内。"
            "assumptions 最多列出2项，且必须是真正需要确认的前提。"
            "不要假设已经读取、修改或测试过项目代码。"
            "不要将未经确认的技术选择当作项目既定事实。",
        ),
        (
            "human",
            "请为下面的开发任务制定计划：\n{task}",
        ),
    ]
)


def generate_development_plan(
    model: BaseChatModel,
    task: str,
) -> DevelopmentPlan:
    """调用模型，生成经过 Pydantic 校验的开发计划。"""

    if not task.strip():
        raise ModelConfigError("开发任务不能为空")

    # 当前模型使用 function_calling 完成结构化输出。
    structured_model = model.with_structured_output(
        DevelopmentPlan,
        method="function_calling",
    )

    messages = PLANNING_PROMPT.format_messages(
        task=task.strip(),
    )

    plan = structured_model.invoke(messages)

    if not isinstance(plan, DevelopmentPlan):
        raise PlanningError("模型未返回有效的 DevelopmentPlan 对象")

    return plan
```

### 7.3 Pydantic 嵌套结构

```python
class PlanStep(BaseModel):
    title: str
    action: str
    verification: str
```

定义单个步骤。

```python
class DevelopmentPlan(BaseModel):
    goal: str
    assumptions: list[str]
    steps: list[PlanStep]
```

定义完整计划。

其中：

```python
steps: list[PlanStep]
```

表示列表中的每个元素都应符合 `PlanStep` 的结构。

例如：

```python
plan = DevelopmentPlan(
    goal="添加登录功能",
    steps=[
        PlanStep(
            title="检查现有代码",
            action="查看用户模型和路由",
            verification="确认相关接口",
        ),
        PlanStep(
            title="实现登录接口",
            action="编写登录验证逻辑",
            verification="运行 pytest",
        ),
    ],
)

print(plan.model_dump_json(indent=2))
```

`model_dump_json()` 可以输出格式化 JSON。

这适合 CLI、API 返回结果以及后续保存任务计划。

### 7.4 default_factory=list 为什么不直接用空列表？

```python
assumptions: list[str] = Field(
    default_factory=list,
)
```

表示创建新对象时生成一个默认空列表。

这是一种明确的默认值工厂写法，可以避免在普通 Python 类中常见的共享可变默认值问题。

Pydantic 对部分可变默认值也有特殊处理，但在这里使用 `default_factory` 能更清晰地表达意图。

### 7.5 with_structured_output() 的作用

```python
structured_model = model.with_structured_output(
    DevelopmentPlan,
    method="function_calling",
)
```

它为模型增加结构化输出要求。

这里使用的是 `function_calling` 方式。

基本过程：

```text
DevelopmentPlan Schema
    ↓
LangChain 转换为工具定义
    ↓
模型生成工具调用参数
    ↓
LangChain 解析参数
    ↓
Pydantic 验证
    ↓
DevelopmentPlan 对象
```

这个过程借用了工具调用机制，但并没有执行仓库工具。

### 7.6 为什么需要 isinstance()？

```python
if not isinstance(plan, DevelopmentPlan):
    raise PlanningError("模型未返回有效的 DevelopmentPlan 对象")
```

正常情况下，成功解析后的结果应当是 `DevelopmentPlan`。

但真实模型可能：

- 未生成预期工具调用。
- 返回普通文本。
- 生成不合法的工具参数。
- 返回无法解析的数据。

因此不能完全相信模型输出。

这里使用 `isinstance()` 作为结果类型检查，并在异常时主动报错。

需要注意，当前 `PlanningError` 只说明最终对象不符合预期，不直接包含底层原始响应。遇到问题时需要使用 `include_raw=True` 进一步诊断。

---

## 8. Planning 自动化测试

### 8.1 test_planning.py 完整代码

文件：`tests/test_planning.py`

```python
"""开发计划结构与生成流程测试。"""

import pytest
from langchain_core.runnables import RunnableLambda
from pydantic import ValidationError

from ai_software_dev_agent.model import ModelConfigError
from ai_software_dev_agent.planning import (
    DevelopmentPlan,
    PlanningError,
    PlanStep,
    generate_development_plan,
)


def create_sample_plan() -> DevelopmentPlan:
    """创建测试使用的合法开发计划。"""

    return DevelopmentPlan(
        goal="增加用户登录功能",
        assumptions=["尚未检查现有认证模块"],
        steps=[
            PlanStep(
                title="检查项目",
                action="了解现有用户模块",
                verification="确认相关文件和接口",
            ),
            PlanStep(
                title="实现登录",
                action="编写登录接口",
                verification="通过登录接口测试",
            ),
        ],
    )


class StubStructuredChatModel:
    """模拟支持结构化输出的模型，不调用真实 API。"""

    def __init__(self, output: object) -> None:
        self.output = output
        self.received_messages = None
        self.called_schema = None
        self.called_method = None

    def with_structured_output(
        self,
        schema: type[DevelopmentPlan],
        *,
        method: str,
    ) -> RunnableLambda:
        """记录传入的 Schema 和输出方法。"""

        self.called_schema = schema
        self.called_method = method

        return RunnableLambda(self._invoke)

    def _invoke(self, messages: object) -> object:
        """模拟模型返回结构化结果。"""

        self.received_messages = messages
        return self.output


def test_plan_step_rejects_empty_title() -> None:
    """开发步骤的名称不能为空。"""

    with pytest.raises(ValidationError):
        PlanStep(
            title="",
            action="编写登录接口",
            verification="运行测试",
        )


def test_development_plan_requires_two_steps() -> None:
    """开发计划至少包含两个步骤。"""

    with pytest.raises(ValidationError):
        DevelopmentPlan(
            goal="实现登录",
            steps=[],
        )


def test_development_plan_rejects_too_many_steps() -> None:
    """开发计划最多包含五个步骤。"""

    step = PlanStep(
        title="开发任务",
        action="执行开发操作",
        verification="运行测试",
    )

    with pytest.raises(ValidationError):
        DevelopmentPlan(
            goal="实现登录",
            steps=[step] * 6,
        )


def test_generate_development_plan() -> None:
    """验证模型使用指定 Schema 和 function_calling。"""

    expected_plan = create_sample_plan()
    fake_model = StubStructuredChatModel(expected_plan)

    result = generate_development_plan(
        fake_model,
        "增加用户登录功能",
    )

    assert result == expected_plan
    assert fake_model.called_schema is DevelopmentPlan
    assert fake_model.called_method == "function_calling"

    assert "增加用户登录功能" in (fake_model.received_messages[-1].content)


def test_generate_development_plan_rejects_empty_task() -> None:
    """空开发任务不能发送给模型。"""

    fake_model = StubStructuredChatModel(create_sample_plan())

    with pytest.raises(
        ModelConfigError,
        match="开发任务不能为空",
    ):
        generate_development_plan(fake_model, "   ")


def test_generate_development_plan_rejects_wrong_output() -> None:
    """模型没有返回 Pydantic 对象时应报错。"""

    fake_model = StubStructuredChatModel(
        {"goal": "普通字典，不是 DevelopmentPlan 对象"}
    )

    with pytest.raises(PlanningError):
        generate_development_plan(
            fake_model,
            "增加用户登录功能",
        )
```

### 8.2 为什么使用 StubStructuredChatModel？

Day 03 使用过：

```python
FakeListChatModel
```

它适合测试普通文本回答。

而今天需要验证：

```python
model.with_structured_output(...)
```

因此设计 `StubStructuredChatModel`，模拟支持结构化输出的模型接口。

这里的 Stub（替身对象）并不是真正的 LangChain Chat Model 子类，只是为了单元测试提供所需的方法。

实际测试验证的是：

1. 是否传入正确的 `DevelopmentPlan` Schema。
2. 是否指定了 `function_calling`。
3. 开发任务是否进入模型消息。
4. 是否正确处理合法和非法返回值。

### 8.3 RunnableLambda 的作用

```python
return RunnableLambda(self._invoke)
```

`RunnableLambda` 可以把 Python 函数包装为 LangChain Runnable。

因此测试中可以继续使用：

```python
structured_model.invoke(messages)
```

而不需要真实访问 OpenRouter。

### 8.4 执行测试

```bash
python -m pytest tests/test_planning.py -v
```

该文件设计六个测试。

本日测试执行通过。

---

## 9. CLI 集成

### 9.1 新增 plan 命令

新增：

```bash
ai-dev-agent plan \
  --task "为 FastAPI 项目添加用户登录功能"
```

它和原来的 `ask` 不同：

| 命令 | 作用 | 输出 |
|---|---|---|
| `ask` | 普通模型问答 | 文本 |
| `plan` | 开发任务规划 | JSON |
| `inspect` | 查看仓库文件 | 文件清单 |
| `read` | 读取文件 | 文件内容 |
| `search` | 搜索代码 | 匹配位置 |

当前 `plan` 仅根据任务文字制定计划，尚未读取当前仓库或执行开发步骤。

### 9.2 cli.py 完整代码

文件：`src/ai_software_dev_agent/cli.py`

```python
"""AI 软件开发智能体的命令行入口。"""

import argparse
import sys
from pathlib import Path

from langchain_core.exceptions import OutputParserException
from openai import APIStatusError, OpenAIError
from pydantic import ValidationError

from ai_software_dev_agent import __version__
from ai_software_dev_agent.model import (
    ModelConfigError,
    create_chat_model,
    generate_answer,
    load_model_settings,
)
from ai_software_dev_agent.planning import (
    PlanningError,
    generate_development_plan,
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

    ask_parser = subparsers.add_parser(
        "ask",
        help="使用 LangChain 调用聊天模型",
    )

    plan_parser = subparsers.add_parser(
        "plan",
        help="生成结构化软件开发计划",
    )

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

    plan_parser.add_argument(
        "--task",
        required=True,
        help="需要制定计划的软件开发任务",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """解析命令并执行对应功能。"""

    parser = build_parser()
    args = parser.parse_args(argv)

    # ask 和 plan 都需要模型，但执行不同业务逻辑。
    if args.command in ("ask", "plan"):
        try:
            settings = load_model_settings()
            model = create_chat_model(settings)

            if args.command == "ask":
                answer = generate_answer(
                    model,
                    args.question,
                )
                print(answer)

            else:
                plan = generate_development_plan(
                    model,
                    args.task,
                )

                # 将结构化 Pydantic 对象转换为 JSON。
                print(plan.model_dump_json(indent=2))

        except ModelConfigError as exc:
            parser.error(str(exc))

        except (
            PlanningError,
            ValidationError,
            OutputParserException,
        ) as exc:
            print(
                f"开发计划结构化生成失败：{type(exc).__name__}。",
                file=sys.stderr,
            )
            return 1

        except APIStatusError as exc:
            if exc.status_code == 401:
                reason = "API Key 无效或没有访问权限"
            elif exc.status_code == 404:
                reason = "模型不存在或当前不可用"
            elif exc.status_code == 429:
                reason = "平台限流或模型访问量过大"
            elif exc.status_code == 400:
                reason = "请求参数错误或模型不支持该功能"
            else:
                reason = "请检查模型服务状态和请求配置"

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

### 9.3 主要修改说明

#### 增加命令解析

```python
plan_parser = subparsers.add_parser(
    "plan",
    help="生成结构化软件开发计划",
)

plan_parser.add_argument(
    "--task",
    required=True,
    help="需要制定计划的软件开发任务",
)
```

#### 复用模型初始化逻辑

```python
if args.command in ("ask", "plan"):
    settings = load_model_settings()
    model = create_chat_model(settings)
```

两种命令使用同一模型配置，但后续执行不同函数。

#### JSON 输出

```python
print(plan.model_dump_json(indent=2))
```

把 Pydantic 对象序列化成 JSON，方便程序处理。

#### 异常处理

本日新增：

```python
except (
    PlanningError,
    ValidationError,
    OutputParserException,
) as exc:
```

用于处理模型输出不符合预期的情况。

这里需要区分：

- `PlanningError`：本项目定义的结果类型异常。
- `ValidationError`：Pydantic 数据校验异常。
- `OutputParserException`：LangChain 输出解析异常。

实际调用仍可能有其他提供商异常，当前只处理已明确设计的主要类型，后续可以进一步完善。

---

## 10. CLI 自动化测试

### 10.1 test_cli.py 完整代码

文件：`tests/test_cli.py`

```python
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
```

### 10.2 本日新增的三个 CLI 测试

- `test_plan_outputs_structured_json`：验证能够输出合法 JSON。
- `test_plan_requires_task`：验证必须输入开发任务。
- `test_plan_reports_structured_output_error`：验证规划失败能够正常退出并返回错误码。

使用 `monkeypatch` 替代真实模型调用，避免自动化测试依赖网络。

运行：

```bash
python -m pytest tests/test_planning.py tests/test_cli.py -v
```

本日已执行通过。

---

## 11. model.py 最终配置

由于结构化输出实验中遇到了生成不完整的问题，本日将 `max_tokens` 从 `1024` 增加到 `2048`。

文件：`src/ai_software_dev_agent/model.py`

完整代码：

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
```

本日主要修改：

```python
max_tokens = (2048,)
```

这里需要理解，`max_tokens` 控制请求允许使用的生成空间，但不同模型对输出和推理 Token 的统计可能存在差异。

它不是越大越好。

更大的生成空间可能改善长 JSON 的完成概率，但也可能增加生成时间或资源消耗。

---

## 12. 真实 Debug：PlanningError

这是本日最重要的实践记录。

### 12.1 问题出现

最初执行：

```bash
ai-dev-agent plan \
  --task "为 FastAPI 项目添加用户登录功能，要求包含参数校验和 pytest 测试"
```

结果：

```text
开发计划结构化生成失败：PlanningError
```

对应代码：

```python
plan = structured_model.invoke(messages)

if not isinstance(plan, DevelopmentPlan):
    raise PlanningError("模型未返回有效的 DevelopmentPlan 对象")
```

此时已经知道结果不是 `DevelopmentPlan`，但不知道模型实际返回了什么。

### 12.2 为什么自动化测试通过，真实 API 仍失败？

因为测试中使用的是：

```python
StubStructuredChatModel
```

测试模型直接返回已经构造好的合法 `DevelopmentPlan`。

它验证了业务代码如何处理正确或错误结果，却不能证明真实模型一定会遵守 Schema。

这体现了两种测试的区别：

**Unit Test（单元测试）**

验证本地代码行为，通常不访问真实模型。

**Integration Test（集成测试）**

验证 LangChain、模型 API、输出解析等实际组件能否共同正常工作。

### 12.3 第一次诊断：查看原始响应

使用 LangChain 的：

```python
include_raw = True
```

它能够返回：

```python
{
    "raw": ...,
    "parsed": ...,
    "parsing_error": ...,
}
```

诊断命令：

```bash
python - <<'PY'
from ai_software_dev_agent.model import (
    create_chat_model,
    load_model_settings,
)
from ai_software_dev_agent.planning import (
    DevelopmentPlan,
    PLANNING_PROMPT,
)

settings = load_model_settings()
model = create_chat_model(settings)

print("当前模型：", settings.model_name)

structured_model = model.with_structured_output(
    DevelopmentPlan,
    method="function_calling",
    include_raw=True,
)

messages = PLANNING_PROMPT.format_messages(
    task="为 FastAPI 项目添加用户登录功能，要求包含参数校验和 pytest 测试"
)

result = structured_model.invoke(messages)

raw = result["raw"]
parsed = result["parsed"]
error = result["parsing_error"]

print("\n=== 1. 解析结果 ===")
print("解析结果类型：", type(parsed).__name__)

if isinstance(parsed, DevelopmentPlan):
    print(parsed.model_dump_json(indent=2))
else:
    print("解析结果摘要：", str(parsed)[:500])

print("\n=== 2. 解析异常 ===")
print("异常类型：", type(error).__name__ if error else None)
print("异常摘要：", str(error)[:500] if error else None)

print("\n=== 3. 模型工具调用 ===")
print("工具调用数量：", len(raw.tool_calls))

for call in raw.tool_calls:
    print("工具名称：", call["name"])
    print("工具参数：", str(call["args"])[:1000])

print("\n=== 4. 无效工具调用 ===")
print("无效工具调用：", str(raw.invalid_tool_calls)[:500])

print("\n=== 5. 模型普通文本 ===")
print("文本摘要：", str(raw.content)[:1000])

print("\n=== 6. 模型结束原因 ===")
print("结束原因：", raw.response_metadata.get("finish_reason"))
PY
```

### 12.4 第一次诊断实际结果

模型：

```text
cohere/north-mini-code:free
```

返回：

```text
解析结果类型：NoneType

解析异常：None

工具调用数量：0

无效工具调用数量：1

无效工具名称：DevelopmentPlan

结束原因：error
```

无效调用中包含了模型尝试生成的开发计划参数。

这说明模型并非完全没有调用工具，而是**尝试生成了 `DevelopmentPlan` 工具调用，但返回的参数没有成功解析为有效工具调用**。

需要特别注意：

```python
raw.tool_calls
```

表示成功解析的工具调用。

```python
raw.invalid_tool_calls
```

表示不能正常解析的工具调用。

另外，`parsing_error=None` 不等于整个请求成功，因为无效工具调用可能已经被记录在 `invalid_tool_calls` 中。

当时输出的参数内容只显示前 500 个字符，不能仅凭显示末尾就断定 JSON 一定在该位置截断。

### 12.5 第二次诊断：调整生成长度和提示词

根据第一次结果，考虑两种可能：

1. 输出空间不够，导致参数生成不完整。
2. 模型在较复杂结构化任务中生成不稳定。

本次诊断临时调整：

```python
model.max_tokens = 2048
```

并要求模型：

- 生成三个简短步骤。
- 每个操作和验证描述尽量不超过 30 字。
- 最多两个假设条件。

执行：

```bash
python - <<'PY'
import json

from ai_software_dev_agent.model import (
    create_chat_model,
    load_model_settings,
)
from ai_software_dev_agent.planning import (
    DevelopmentPlan,
    PLANNING_PROMPT,
)

settings = load_model_settings()
model = create_chat_model(settings)

# 仅调整本次诊断的模型对象。
model.max_tokens = 2048

structured_model = model.with_structured_output(
    DevelopmentPlan,
    method="function_calling",
    include_raw=True,
)

messages = PLANNING_PROMPT.format_messages(
    task=(
        "为 FastAPI 项目添加用户登录功能。"
        "请只列出3个简短步骤，"
        "每项 action 和 verification 不超过30个汉字，"
        "assumptions 最多2项。"
    )
)

result = structured_model.invoke(messages)

raw = result["raw"]
parsed = result["parsed"]

print("=== 解析结果 ===")
print("解析类型：", type(parsed).__name__)

if isinstance(parsed, DevelopmentPlan):
    print(parsed.model_dump_json(indent=2))

print("\n=== 结束状态 ===")
print("finish_reason：", raw.response_metadata.get("finish_reason"))
print("Token 用量：", raw.usage_metadata)

print("\n=== 工具调用 ===")
print("有效数量：", len(raw.tool_calls))
print("无效数量：", len(raw.invalid_tool_calls))

for call in raw.invalid_tool_calls:
    args = call.get("args") or ""

    print("\n工具名称：", call.get("name"))
    print("参数字符串长度：", len(args))
    print("参数末尾：", repr(args[-300:]))
    print("LangChain 错误：", call.get("error"))

    try:
        json.loads(args)
        print("JSON 语法：有效")
    except json.JSONDecodeError as exc:
        print("JSON 语法错误：", str(exc))
        print("错误位置：", exc.pos)
PY
```

### 12.6 第二次诊断实际结果

解析类型：

```text
DevelopmentPlan
```

实际得到的计划：

```json
{
  "goal": "为 FastAPI 项目添加用户登录功能",
  "assumptions": [
    "FastAPI 应用已创建并配置",
    "用户模型中存在密码字段"
  ],
  "steps": [
    {
      "title": "配置 JWT 认证依赖",
      "action": "创建 JWT 令牌验证依赖",
      "verification": "测试依赖处理有效令牌请求"
    },
    {
      "title": "实现登录及 token 获取端点",
      "action": "添加 /login 路由返回 JWT 令牌",
      "verification": "验证用户密码并返回 token"
    },
    {
      "title": "验证登录功能集成",
      "action": "在应用中测试登录端点功能",
      "verification": "确认返回 token 及认证头有效"
    }
  ]
}
```

结束状态：

```text
finish_reason：tool_calls
```

工具调用：

```text
有效数量：1
无效数量：0
```

Token 数据：

```python
{
    "input_tokens": 292,
    "output_tokens": 720,
    "total_tokens": 1012,
    "input_token_details": {
        "audio": 0,
        "cache_read": 0,
        "cache_creation": 0,
    },
    "output_token_details": {
        "audio": 0,
        "reasoning": 758,
    },
}
```

说明本次真实模型调用成功返回工具参数，并被 LangChain 解析和 Pydantic 校验。

需要注意：

`reasoning=758` 与 `output_tokens=720` 的关系并不直观，可能与平台报告 Token 用量的方式有关。当前不能仅凭这份数据确定准确的内部计数规则。

### 12.7 对结果的进一步判断

本次成功的调整包含两项：

1. 增大 `max_tokens`。
2. 缩短并明确规划提示词。

因此可以判断：**调整后这次调用成功了。**

但不能通过一次实验确定究竟是哪一项单独解决了问题，也不能保证以后每次请求都成功。

此外，模型生成的 JWT 方案只是建议，用户并未明确指定 JWT。模型把它作为具体实施方案，说明除了结构校验，还需要检查业务合理性。

Pydantic 能保证数据结构符合要求，但不能保证开发方案一定正确。

### 12.8 将成功配置应用到正式项目

首先在 `model.py` 修改：

```python
max_tokens = (2048,)
```

然后在 `planning.py` 中优化系统提示词，要求三个简洁步骤、最多两个前提假设，并避免把未经确认的技术选型当作既定事实。

修改后运行：

```bash
python -m pytest tests/test_planning.py tests/test_cli.py -v
```

再执行：

```bash
ai-dev-agent plan \
  --task "为 FastAPI 项目添加用户登录功能，要求包含参数校验和 pytest 测试"
```

**实际结果：正式 CLI 的 `plan` 命令成功执行，返回了结构化开发计划。**

至此，本次 Debug 完成。

### 12.9 本次 Debug 的工程经验

遇到结构化输出失败，应逐层判断：

```text
1. API 是否成功返回？
    ↓
2. 模型是否尝试生成工具调用？
    ↓
3. 工具调用参数是否为合法 JSON？
    ↓
4. 参数是否符合 Pydantic Schema？
    ↓
5. 结果是否为预期对象？
    ↓
6. 计划在业务上是否合理？
```

不能只看：

```python
response.tool_calls
```

还需要根据问题检查：

```python
response.invalid_tool_calls
response.response_metadata
response.usage_metadata
```

以及 `include_raw=True` 返回的原始结果。

**重要结论：模型输出必须经过验证，结构合法也不等于业务决策正确。**

---

## 13. LangChain 与 Pydantic 的分工

### 13.1 LangChain 本日负责什么？

本日主要使用以下 LangChain 能力：

| 组件 | 作用 |
|---|---|
| `@tool` | 把 Python 函数注册为工具 |
| `BaseTool` | 统一工具接口 |
| `tool.invoke()` | 执行工具 |
| `bind_tools()` | 向模型提供工具定义 |
| `AIMessage.tool_calls` | 获取可解析的工具调用请求 |
| `AIMessage.invalid_tool_calls` | 检查无效工具调用 |
| `ChatPromptTemplate` | 组织规划提示词 |
| `with_structured_output()` | 约束并解析结构化输出 |
| `RunnableLambda` | 在测试中包装可调用对象 |

### 13.2 Pydantic 本日负责什么？

Pydantic 主要负责：

- 定义工具输入参数。
- 定义开发计划的嵌套结构。
- 检查类型、长度和数量限制。
- 把结构化对象转换为 JSON。

因此本日实现：

```text
LangChain：组织模型、工具和输出解析
Pydantic：定义并校验数据结构
Python：执行真实业务逻辑
```

### 13.3 不使用 LangChain 可以吗？

可以。

可以使用原生 OpenAI SDK：

```python
client.chat.completions.create(
    model="...",
    messages=[...],
    tools=[...],
)
```

自己定义工具 JSON Schema，再解析 `tool_calls`，调用对应 Python 函数，并使用 Pydantic 校验结果。

但这样需要自己编写更多工具适配、结果解析和调用组织代码。

LangChain 的价值是复用统一抽象，而不是让模型自动变得更聪明。

### 13.4 bind_tools() 和 with_structured_output() 的区别

| 对比项 | `bind_tools()` | `with_structured_output()` |
|---|---|---|
| 目的 | 让模型选择工具 | 让模型生成规定的数据结构 |
| 返回重点 | 工具调用请求 | 解析后的结构化对象 |
| 是否执行仓库工具 | 不自动执行 | 不执行 |
| 本日应用 | 仓库文件查询请求 | DevelopmentPlan |
| 后续用途 | Agent 工具执行 | 任务计划、状态、结果验证 |

它们底层都可能使用 Tool Calling 协议，但目标不同。

---

## 14. 当天知识与实践总结

Day 04 将软件开发 Agent 的能力从简单模型问答进一步扩展为：

**一、工具能力**

将仓库探索功能封装为 LangChain 工具，为后续模型驱动的代码分析提供接口。

**二、参数与结果校验**

通过 Pydantic 分别约束工具输入和模型输出。

**三、模型工具调用**

验证真实模型能够根据工具描述生成 `tool_calls`，但尚未实现自动工具执行循环。

**四、结构化任务规划**

通过 `with_structured_output()` 生成 `DevelopmentPlan` 对象，并使用 CLI 输出 JSON。

**五、真实故障排查**

遇到 `PlanningError` 后，使用 `include_raw=True` 检查模型原始输出、无效工具调用和结束原因，调整生成空间及提示词，最终使正式 `plan` 命令成功运行。

本日已完成的能力，为 Day 05 的 LangChain Agent 和 Interactive CLI 提供了基础。

