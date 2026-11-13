# Day 08 — LangGraph Workflow & CLI Refactoring

**主题：LangGraph 工作流基础与 CLI 模块化重构**

## 1. 今日学习目标与成果

### 1.1 学习目标

Day 01～Day 07，我们已经完成仓库探索、模型问答、开发计划、Agent 多轮交互、代码编辑以及 pytest 执行器。

但这些功能大部分还是独立运行的。

Day 08 主要解决两个问题：

1. **工作流编排**：使用 LangGraph 将多个已有组件按照确定的顺序连接起来。
2. **项目架构优化**：把越来越大的 `cli.py` 和 `test_cli.py` 按职责拆分，降低后续功能开发的维护成本。

需要掌握的知识：

- `State`：共享状态
- `Node`：工作流节点
- `Edge`：节点之间的连接关系
- `Reducer`：状态更新的合并规则
- `StateGraph`：状态图构建器
- `compile()`：编译工作流
- `invoke()`：执行并获取最终状态
- `stream()`：逐步获取执行结果
- Refactoring（重构）
- Separation of Concerns（关注点分离）
- `argparse.set_defaults()`：命令处理函数绑定

### 1.2 本日完成的功能

本日按三个阶段开发：

**第一阶段：LangGraph 工作流**

- 新增 `workflow.py`。
- 定义共享 State。
- 创建仓库探索、运行测试、生成总结三个节点。
- 使用固定 Edge 指定执行顺序。
- 使用 Reducer 记录已完成节点。
- 编写工作流自动化测试。

**第二阶段 A：CLI 模块化重构**

- 新增 `commands/` 包。
- 将仓库、问答、规划、聊天、编辑和测试命令拆分。
- 将 `cli.py` 缩减为命令注册与分发入口。
- 将原来的大型 `test_cli.py` 按命令拆分到 `tests/cli/`。
- 迁移原有测试，避免重复收集或丢失测试。

**第二阶段 B：工作流 CLI 集成**

- 新增 `commands/workflow.py`。
- 新增 `tests/cli/test_workflow.py`。
- 注册 `ai-dev-agent workflow` 命令。
- 使用 `stream()` 逐节点展示完成进度。
- 根据 pytest 结果返回正确的 CLI 退出码。

---

## 2. 最终项目结构

```text
ai-software-development-agent/
├── pyproject.toml
├── src/
│   └── ai_software_dev_agent/
│       ├── __init__.py
│       ├── cli.py
│       ├── agent.py
│       ├── editor.py
│       ├── model.py
│       ├── planning.py
│       ├── repository.py
│       ├── test_runner.py
│       ├── tools.py
│       ├── workflow.py
│       └── commands/
│           ├── __init__.py
│           ├── _common.py
│           ├── repository.py
│           ├── ask.py
│           ├── plan.py
│           ├── chat.py
│           ├── edit.py
│           ├── testing.py
│           └── workflow.py
├── tests/
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── test_core.py
│   │   ├── test_repository.py
│   │   ├── test_ask.py
│   │   ├── test_plan.py
│   │   ├── test_chat.py
│   │   ├── test_edit.py
│   │   ├── test_testing.py
│   │   └── test_workflow.py
│   ├── test_agent.py
│   ├── test_editor.py
│   ├── test_model.py
│   ├── test_planning.py
│   ├── test_repository.py
│   ├── test_test_runner.py
│   ├── test_tools.py
│   └── test_workflow.py
└── docs/
    └── Day08-LangGraph-Workflow-And-CLI-Refactoring.md
```

需要注意：项目有两个不同的 `workflow.py`。

| 文件 | 职责 |
|---|---|
| `src/ai_software_dev_agent/workflow.py` | 定义 LangGraph 工作流的状态、节点与边 |
| `src/ai_software_dev_agent/commands/workflow.py` | 处理 CLI 参数、展示节点进度与退出码 |
| `tests/test_workflow.py` | 验证 LangGraph 业务流程 |
| `tests/cli/test_workflow.py` | 验证工作流 CLI 行为 |

这体现了业务逻辑与用户界面适配层分离的设计。

---

## 3. 开发环境

### 3.1 进入项目

```bash
cd "/Users/lc/Documents/公子路的长期成长计划/02-AI-Agent-Engineering/ai-software-development-agent"
```

激活虚拟环境：

```bash
source .venv/bin/activate
```

验证：

```bash
which python

python --version

python -c 'import sys; print(sys.executable)'
```

检查当前 Python 是否位于本项目 `.venv/bin/` 中。

### 3.2 验证 LangGraph

```bash
python - <<'PY'
from langgraph.graph import START, END, StateGraph

print("LangGraph 导入成功")
PY
```

这里：

- `python -`：从标准输入读取 Python 程序。
- `<<'PY'`：Shell 的 Here Document（此处文档）语法。
- `PY`：结束输入内容的标记，不属于 Python 代码。

这个写法适合运行简短的一次性检查脚本，不会创建额外的 Python 文件。

---

## 4. LangGraph 核心概念

### 4.1 什么是 LangGraph？

LangGraph 是用于构建有状态工作流和 Agent 的框架。

我们可以将一个复杂任务拆成多个步骤，再通过图的结构描述执行顺序和状态传递。

本日实现的是一个固定顺序工作流：

```text
START
  ↓
inspect_repository
  ↓
run_tests
  ↓
summarize
  ↓
END
```

对应职责：

| 节点 | 功能 |
|---|---|
| `inspect_repository` | 获取仓库文件列表 |
| `run_tests` | 使用 Day 07 的 TestRunner 执行 pytest |
| `summarize` | 根据前面结果生成摘要 |

今天没有 LLM 节点，因此不需要 API Key，也不会消耗 Token。

### 4.2 State（状态）

State 用来保存整个工作流在执行过程中共享的数据。

例如：

```python
{
    "project": "/my-project",
    "target": "tests",
    "timeout_seconds": 30,
    "completed_steps": [],
}
```

经过仓库探索节点后增加：

```python
"files": ["demo.py", "tests/test_demo.py"]
```

经过测试节点后增加：

```python
"test_result": TestRunResult(...)
```

最后再增加：

```python
"summary": "测试结果总结..."
```

**状态不只保存用户输入，也保存节点执行过程中产生的数据。**

### 4.3 Node（节点）

Node 是工作流中执行具体任务的函数。

例如：

```python
def inspect_repository_node(state):
    explorer = RepositoryExplorer(Path(state["project"]))

    files = [str(path) for path in explorer.list_files()]

    return {"files": files}
```

节点的输入是 State，输出通常是对 State 的部分更新。

### 4.4 Edge（边）

Edge 用来描述节点之间的执行关系：

```python
builder.add_edge(
    "inspect_repository",
    "run_tests",
)
```

表示仓库探索结束后运行测试。

今天使用固定边，因此节点顺序确定。

后面可以通过条件边实现：

```text
运行测试
    ↓
测试通过？
  ├── 是 → 继续
  └── 否 → 修复或退出
```

### 4.5 `TypedDict`

定义共享状态时使用：

```python
from typing import TypedDict


class PersonState(TypedDict):
    name: str
    age: int
```

它为字典声明固定的键与类型。

例如：

```python
person: PersonState = {
    "name": "小明",
    "age": 20,
}
```

`TypedDict` 不会自动将字典变为普通 Python 类实例，也不会自行完成全面的运行时数据校验。

### 4.6 `NotRequired`

```python
from typing import NotRequired


class ExampleState(TypedDict):
    project: str
    result: NotRequired[str]
```

表示初始状态可以没有 `result` 字段。

因为它可能由后续节点产生。

在本日项目中：

```python
files: NotRequired[list[str]]
test_result: NotRequired[TestRunResult]
summary: NotRequired[str]
```

它们都属于后续节点计算得到的数据。

### 4.7 Reducer（归约器）

本日使用：

```python
completed_steps: Annotated[list[str], operator.add]
```

先理解：

```python
import operator

print(operator.add(2, 3))
# 5

print(operator.add(["a"], ["b"]))
# ['a', 'b']
```

对于列表，`operator.add` 表示拼接。

LangGraph 中通过 `Annotated` 为字段指定状态合并规则：

```python
from typing import Annotated
import operator

completed_steps: Annotated[list[str], operator.add]
```

初始状态：

```python
"completed_steps": []
```

第一个节点返回：

```python
"completed_steps": ["inspect_repository"]
```

第二个节点返回：

```python
"completed_steps": ["run_tests"]
```

第三个节点返回：

```python
"completed_steps": ["summarize"]
```

最终得到：

```python
[
    "inspect_repository",
    "run_tests",
    "summarize",
]
```

如果没有这样的 Reducer，普通字段更新通常采用覆盖语义。

这里要特别注意：`operator.add` 对列表是拼接，不会自动去重。

### 4.8 `StateGraph` 与 `compile()`

定义图：

```python
builder = StateGraph(DevelopmentWorkflowState)
```

添加节点：

```python
builder.add_node("run_tests", run_tests_node)
```

连接节点：

```python
builder.add_edge(START, "run_tests")
builder.add_edge("run_tests", END)
```

最后：

```python
workflow = builder.compile()
```

`StateGraph` 是构建阶段的对象。

`compile()` 将已经定义的图编译为可运行对象。

### 4.9 `invoke()` 与 `stream()` 的区别

`invoke()`：

```python
result = workflow.invoke(initial_state)
```

执行完整工作流，返回最终状态。

`stream()`：

```python
for event in workflow.stream(
    initial_state,
    stream_mode="updates",
):
    print(event)
```

随着节点完成，逐步产生更新事件。

对比：

| 方法 | 作用 | 本日使用位置 |
|---|---|---|
| `invoke()` | 执行完后获取最终状态 | 业务工作流与测试 |
| `stream()` | 逐节点获取更新 | CLI 进度展示 |

注意：`stream_mode="updates"` 返回的是节点完成后的更新，并不是每个节点开始执行时的通知。

---

## 5. 第一阶段：实现工作流

### 5.1 创建文件

```bash
touch src/ai_software_dev_agent/workflow.py
```

打开：

```bash
nano src/ai_software_dev_agent/workflow.py
```

### 5.2 `workflow.py` 完整代码

```python
"""使用 LangGraph 将仓库探索、测试和结果汇总连接成工作流。"""

import operator
from pathlib import Path
from typing import Annotated, NotRequired, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from ai_software_dev_agent.repository import RepositoryExplorer
from ai_software_dev_agent.test_runner import (
    DEFAULT_TIMEOUT_SECONDS,
    TestRunResult,
    TestRunner,
)


class DevelopmentWorkflowState(TypedDict):
    """工作流中所有节点共享的状态结构。"""

    # 用户输入：仓库位置、测试目标、超时时间。
    project: str
    target: str
    timeout_seconds: int

    # Reducer：不同节点写入的步骤记录会追加到列表。
    completed_steps: Annotated[list[str], operator.add]

    # 以下字段在工作流执行过程中逐步产生。
    files: NotRequired[list[str]]
    test_result: NotRequired[TestRunResult]
    summary: NotRequired[str]


def inspect_repository_node(
    state: DevelopmentWorkflowState,
) -> dict[str, object]:
    """节点一：读取仓库文件列表。"""

    explorer = RepositoryExplorer(Path(state["project"]))

    # 统一转换为字符串，方便展示和传递状态。
    files = [str(path) for path in explorer.list_files()]

    return {
        "files": files,
        "completed_steps": ["inspect_repository"],
    }


def run_tests_node(
    state: DevelopmentWorkflowState,
) -> dict[str, object]:
    """节点二：复用 Day 07 的 TestRunner。"""

    runner = TestRunner(Path(state["project"]))

    result = runner.run(
        target=state["target"],
        timeout_seconds=state["timeout_seconds"],
    )

    return {
        "test_result": result,
        "completed_steps": ["run_tests"],
    }


def summarize_node(
    state: DevelopmentWorkflowState,
) -> dict[str, object]:
    """节点三：根据前两个节点的结果生成摘要。"""

    files = state["files"]
    result = state["test_result"]

    # 进程超时或启动失败时，可能没有退出码。
    exit_code = str(result.exit_code) if result.exit_code is not None else "无"

    summary = (
        f"仓库文件数：{len(files)}\n"
        f"pytest 状态：{result.status}\n"
        f"pytest 退出码：{exit_code}\n"
        f"执行耗时：{result.duration_seconds:.2f} 秒"
    )

    return {
        "summary": summary,
        "completed_steps": ["summarize"],
    }


def build_development_workflow() -> CompiledStateGraph:
    """构建并编译 LangGraph 工作流。"""

    builder = StateGraph(DevelopmentWorkflowState)

    # 注册节点：建立节点名称与执行函数之间的关系。
    builder.add_node(
        "inspect_repository",
        inspect_repository_node,
    )

    builder.add_node(
        "run_tests",
        run_tests_node,
    )

    builder.add_node(
        "summarize",
        summarize_node,
    )

    # 固定执行顺序。
    builder.add_edge(START, "inspect_repository")
    builder.add_edge("inspect_repository", "run_tests")
    builder.add_edge("run_tests", "summarize")
    builder.add_edge("summarize", END)

    return builder.compile()


def run_development_workflow(
    project: Path,
    target: str = "tests",
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> DevelopmentWorkflowState:
    """准备初始状态并执行完整工作流。"""

    initial_state: DevelopmentWorkflowState = {
        "project": str(project.expanduser().resolve()),
        "target": target,
        "timeout_seconds": timeout_seconds,
        "completed_steps": [],
    }

    workflow = build_development_workflow()

    return workflow.invoke(initial_state)
```

### 5.3 理解工作流的执行过程

第一个节点：

```python
inspect_repository_node()
```

读取文件列表并返回：

```python
{
    "files": files,
    "completed_steps": ["inspect_repository"],
}
```

第二个节点：

```python
run_tests_node()
```

调用：

```python
TestRunner.run()
```

返回：

```python
{
    "test_result": result,
    "completed_steps": ["run_tests"],
}
```

第三个节点：

```python
summarize_node()
```

从状态中获取文件列表和测试结果，生成可读摘要。

这里特意复用之前的业务组件，而不是在 LangGraph 节点中重新实现文件遍历和 pytest 调用。

这体现了组合优于重复实现的工程思想。

---

## 6. 第一阶段：工作流自动化测试

### 6.1 创建测试文件

```bash
touch tests/test_workflow.py
```

打开：

```bash
nano tests/test_workflow.py
```

### 6.2 `tests/test_workflow.py` 完整代码

```python
"""LangGraph 工作流状态、节点顺序与执行结果测试。"""

from pathlib import Path

import pytest

from ai_software_dev_agent.repository import RepositoryError
from ai_software_dev_agent.test_runner import (
    TestRunnerError as RunnerError,
)
from ai_software_dev_agent.workflow import (
    DevelopmentWorkflowState,
    build_development_workflow,
    run_development_workflow,
)


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    """创建包含 Python 文件和 pytest 测试的临时项目。"""

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()

    (tmp_path / "demo.py").write_text(
        "def add(a, b):\n    return a + b\n",
        encoding="utf-8",
    )

    (tests_dir / "test_demo.py").write_text(
        "def test_add():\n    assert 1 + 1 == 2\n",
        encoding="utf-8",
    )

    return tmp_path


def make_initial_state(
    project: Path,
    target: str = "tests",
) -> DevelopmentWorkflowState:
    """构造一份新的工作流初始状态。"""

    return {
        "project": str(project),
        "target": target,
        "timeout_seconds": 30,
        "completed_steps": [],
    }


def test_workflow_runs_all_nodes(
    sample_project: Path,
) -> None:
    """验证三个节点依次执行，并产生完整状态。"""

    workflow = build_development_workflow()

    result = workflow.invoke(make_initial_state(sample_project))

    assert result["project"] == str(sample_project)
    assert result["target"] == "tests"

    assert any(Path(path).name == "demo.py" for path in result["files"])

    test_result = result["test_result"]

    assert test_result.status == "passed"
    assert test_result.exit_code == 0
    assert test_result.passed is True

    assert result["completed_steps"] == [
        "inspect_repository",
        "run_tests",
        "summarize",
    ]

    assert "pytest 状态：passed" in result["summary"]
    assert "仓库文件数：" in result["summary"]


def test_workflow_summarizes_failed_tests(
    sample_project: Path,
) -> None:
    """pytest 断言失败后，工作流仍应执行总结节点。"""

    (sample_project / "tests" / "test_demo.py").write_text(
        "def test_add():\n    assert 1 + 1 == 3\n",
        encoding="utf-8",
    )

    result = run_development_workflow(sample_project)

    assert result["test_result"].status == "failed"
    assert result["test_result"].exit_code == 1
    assert "pytest 状态：failed" in result["summary"]
    assert result["completed_steps"][-1] == "summarize"


def test_workflow_summarizes_no_tests(
    sample_project: Path,
) -> None:
    """没有测试时应生成 no_tests 摘要。"""

    (sample_project / "tests" / "test_demo.py").unlink()

    result = run_development_workflow(sample_project)

    assert result["test_result"].status == "no_tests"
    assert result["test_result"].exit_code == 5
    assert "pytest 状态：no_tests" in result["summary"]

    assert result["completed_steps"] == [
        "inspect_repository",
        "run_tests",
        "summarize",
    ]


def test_workflow_rejects_invalid_project(
    tmp_path: Path,
) -> None:
    """不存在的仓库应该在探索节点失败。"""

    with pytest.raises(RepositoryError):
        run_development_workflow(tmp_path / "missing")


def test_workflow_rejects_invalid_test_target(
    sample_project: Path,
) -> None:
    """测试目标无效时，应传播 TestRunner 参数错误。"""

    with pytest.raises(RunnerError):
        run_development_workflow(
            sample_project,
            target="tests/test_missing.py",
        )


def test_workflow_stream_shows_node_updates(
    sample_project: Path,
) -> None:
    """stream 模式逐步输出各节点的状态更新。"""

    workflow = build_development_workflow()

    events = list(
        workflow.stream(
            make_initial_state(sample_project),
            stream_mode="updates",
        )
    )

    node_names = [next(iter(event)) for event in events]

    assert node_names == [
        "inspect_repository",
        "run_tests",
        "summarize",
    ]


def test_workflow_runs_have_independent_state(
    sample_project: Path,
) -> None:
    """不同运行不应该共享上一次的完成步骤记录。"""

    first = run_development_workflow(sample_project)
    second = run_development_workflow(sample_project)

    expected_steps = [
        "inspect_repository",
        "run_tests",
        "summarize",
    ]

    assert first["completed_steps"] == expected_steps
    assert second["completed_steps"] == expected_steps
```

### 6.3 重点测试内容

| 测试 | 验证目标 |
|---|---|
| 完整流程 | 三个节点执行并产生状态 |
| 测试失败 | `failed` 状态仍可总结 |
| 没有测试 | `no_tests` 不会误报成功 |
| 仓库不存在 | 正确传播仓库错误 |
| 测试目标不存在 | 正确传播参数错误 |
| Streaming | 节点更新按预定顺序产生 |
| 独立调用 | 不会混入上一次的步骤记录 |

这里的测试使用真正的 LangGraph 和 pytest，而不是只检查一个假状态字典。

执行：

```bash
python -m pytest tests/test_workflow.py -v
```

本阶段包含 7 个测试用例。

---

## 7. 第二阶段 A：为什么要重构 CLI？

### 7.1 重构前存在的问题

原来的 `cli.py` 同时负责：

- 解析命令行参数。
- 仓库探索。
- 模型问答。
- 生成开发计划。
- Agent 多轮对话。
- 文件编辑与人工确认。
- pytest 测试执行。

每次增加新功能，都需要继续修改这个文件。

与此同时，`tests/test_cli.py` 也不断变大。

长期下来容易出现：

1. 主文件承担过多职责。
2. 新增功能容易影响旧功能。
3. 单个文件过长，不便阅读。
4. 测试组织越来越混乱。
5. Mock 和 Monkeypatch 的依赖关系不清晰。

### 7.2 什么是 Refactoring（重构）？

重构是指在尽量不改变外部可观察行为的前提下，优化代码内部结构。

本次重构保持这些命令不变：

```text
doctor
inspect
read
search
ask
plan
chat
edit
test
```

改变的是内部模块的组织方式。

### 7.3 采用的分层结构

```text
cli.py
  ↓
commands/<command>.py
  ↓
业务组件
```

例如：

```text
cli.py
  ↓
commands/testing.py
  ↓
test_runner.py
  ↓
subprocess / pytest
```

三层职责：

| 层 | 负责什么 |
|---|---|
| CLI 入口层 | 注册命令与分发 |
| 命令适配层 | 读取参数、调用组件、打印结果 |
| 业务组件层 | 实现实际业务功能 |

以后新增命令，不应该把整段业务代码继续塞进 `cli.py`。

### 7.4 创建命令模块

先执行：

```bash
mkdir -p src/ai_software_dev_agent/commands
```

创建文件：

```bash
touch src/ai_software_dev_agent/commands/__init__.py
touch src/ai_software_dev_agent/commands/_common.py
touch src/ai_software_dev_agent/commands/repository.py
touch src/ai_software_dev_agent/commands/ask.py
touch src/ai_software_dev_agent/commands/plan.py
touch src/ai_software_dev_agent/commands/chat.py
touch src/ai_software_dev_agent/commands/edit.py
touch src/ai_software_dev_agent/commands/testing.py
```

这些文件分别承接以前 `cli.py` 中的对应命令逻辑。

### 7.5 各模块职责

| 模块 | 主要函数 |
|---|---|
| `_common.py` | `add_project_argument()`、`describe_api_error()` |
| `repository.py` | `run_doctor()`、`run_inspect()`、`run_read()`、`run_search()` |
| `ask.py` | `run_ask()` |
| `plan.py` | `run_plan()` |
| `chat.py` | `run_chat_session()`、`run_chat()` |
| `edit.py` | `run_edit_command()`、`run_edit()` |
| `testing.py` | `run_test_command()`、`run_test()` |

每个命令模块另外提供：

```python
register(subparsers)
```

用于注册对应 CLI 子命令。

本阶段迁移的是之前已存在的业务逻辑，因此这些命令模块继续沿用原有参数、异常处理和输出格式。其完整实现保存在项目对应的 Python 文件中；本节重点记录架构变动和新增的公共机制，避免将已有 Day 01～Day 07 的代码在学习文档里重复维护多份。

---

## 8. 公共命令模块 `_common.py`

### 8.1 打开文件

```bash
nano src/ai_software_dev_agent/commands/_common.py
```

### 8.2 完整代码

```python
"""多个 CLI 命令共享的参数与提示工具。"""

import argparse
from pathlib import Path


def add_project_argument(parser: argparse.ArgumentParser) -> None:
    """为需要操作项目的命令注册 --project 参数。"""

    parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="目标项目目录",
    )


def describe_api_error(status_code: int) -> str:
    """将常见模型服务 HTTP 错误转换为中文提示。"""

    reasons = {
        400: "请求参数错误或模型不支持该功能",
        401: "API Key 无效或没有访问权限",
        404: "模型不存在或当前不可用",
        429: "平台限流或模型访问量过大",
    }

    return reasons.get(
        status_code,
        "请检查模型服务状态和请求配置",
    )
```

### 8.3 为什么需要公共模块？

过去多个命令都需要重复定义：

```python
parser.add_argument(
    "--project",
    type=Path,
    default=Path.cwd(),
)
```

现在统一使用：

```python
add_project_argument(parser)
```

好处是减少重复，后续如果要调整公共参数的帮助文字或默认行为，只需要修改一个位置。

但是也不要将所有函数都放进 `_common.py`。只有真正被多个命令共享的逻辑，才适合放在公共模块中。

---

## 9. `argparse.set_defaults()` 如何实现命令分发？

这是本日 CLI 重构的核心知识点。

### 9.1 旧方案

以前在 `main()` 中判断：

```python
if args.command == "ask":
    ...

elif args.command == "plan":
    ...

elif args.command == "chat":
    ...
```

命令越多，分支越多。

### 9.2 新方案

例如在 `commands/testing.py` 中：

```python
def run_test(args: argparse.Namespace) -> int:
    return run_test_command(
        project=args.project,
        target=args.target,
        timeout_seconds=args.timeout,
    )
```

注册时：

```python
parser.set_defaults(handler=run_test)
```

用户执行：

```bash
ai-dev-agent test --project .
```

`argparse` 解析后得到的 `args` 除了命令行参数，还携带了：

```python
args.handler
```

这个字段指向：

```python
run_test
```

于是统一入口只需要：

```python
return args.handler(args)
```

### 9.3 函数对象与函数调用的区别

注意：

```python
parser.set_defaults(handler=run_test)
```

没有括号，传入的是函数对象。

而：

```python
parser.set_defaults(handler=run_test())
```

会立即调用函数，不符合注册处理函数的目的。

这个区别与之前注册 LangChain 工具、LangGraph Node 时传入函数对象的思想相似。

---

## 10. 第二阶段 A：拆分测试文件

### 10.1 创建测试目录

```bash
mkdir -p tests/cli
```

创建文件：

```bash
touch tests/cli/__init__.py
touch tests/cli/test_core.py
touch tests/cli/test_repository.py
touch tests/cli/test_ask.py
touch tests/cli/test_plan.py
touch tests/cli/test_chat.py
touch tests/cli/test_edit.py
touch tests/cli/test_testing.py
```

`tests/cli/__init__.py` 用于明确该目录为 Python 包，帮助避免与其他同名测试文件发生模块导入冲突。

### 10.2 为什么不直接删除旧测试？

重构的目标是改变代码组织方式，而不是减少测试覆盖。

旧的 `tests/test_cli.py` 中已经包含多个阶段积累的测试。

直接删除并重新写一份短测试，很可能遗漏已有边界条件。

因此本次使用迁移方式：

1. 备份旧测试文件。
2. 按 Day 01～Day 07 分区提取。
3. 分别生成命令对应的测试文件。
4. 调整 Monkeypatch 的目标模块。
5. 运行完整测试。
6. 确认无遗漏后，删除临时迁移产物。

### 10.3 Monkeypatch 为什么需要调整？

旧结构中：

```python
monkeypatch.setattr(
    cli,
    "create_chat_model",
    fake_create_model,
)
```

因为原来真正调用 `create_chat_model` 的函数定义在 `cli.py` 中。

重构后，实际读取该依赖的位置变成：

```python
commands / chat.py
```

因此需要改为：

```python
monkeypatch.setattr(
    chat,
    "create_chat_model",
    fake_create_model,
)
```

**Monkeypatch 应该作用于被测代码实际查找依赖的模块，而不是仅仅作用于这个依赖最初被定义的地方。**

这是本次重构非常重要的测试知识点。

### 10.4 测试迁移后的结果检查

```bash
python -m pytest tests/cli -v
```

然后：

```bash
python -m pytest -v
```

还应该检查测试收集结果：

```bash
python -m pytest --collect-only -q
```

确认没有因为拆分产生测试丢失、重复收集或者模块名冲突。

### 10.5 迁移脚本的定位

本次使用的一次性迁移脚本：

```text
scripts/migrate_cli_tests.py
```

只负责把历史测试按既定标题拆分到新目录。

它不是长期运行的业务功能。

迁移完成、测试验证通过后，可以移除这个脚本及临时参考文件；完整的历史测试最终保留在 `tests/cli/` 中。

---

## 11. 第二阶段 B：接入 LangGraph CLI

### 11.1 目标

让用户可以直接运行：

```bash
ai-dev-agent workflow --project .
```

支持：

```bash
ai-dev-agent workflow \
  --project . \
  --target tests/test_agent.py \
  --timeout 30
```

执行时逐节点展示：

```text
[1/3] inspect_repository 已完成
[2/3] run_tests 已完成
[3/3] summarize 已完成
```

最后输出测试结果与工作流摘要。

### 11.2 新建命令文件

```bash
touch src/ai_software_dev_agent/commands/workflow.py
```

打开：

```bash
nano src/ai_software_dev_agent/commands/workflow.py
```

### 11.3 `commands/workflow.py` 完整代码

```python
"""LangGraph 开发工作流的 CLI 命令。"""

import argparse
import sys
from pathlib import Path
from typing import Any

from ai_software_dev_agent.commands._common import add_project_argument
from ai_software_dev_agent.repository import RepositoryError
from ai_software_dev_agent.test_runner import (
    DEFAULT_TIMEOUT_SECONDS,
    TestRunResult,
    TestRunnerError,
)
from ai_software_dev_agent.workflow import (
    DevelopmentWorkflowState,
    build_development_workflow,
)


def run_workflow_command(
    project: Path,
    target: str,
    timeout_seconds: int,
) -> int:
    """逐节点执行工作流，展示进度与最终测试状态。"""

    initial_state: DevelopmentWorkflowState = {
        "project": str(project.expanduser().resolve()),
        "target": target,
        "timeout_seconds": timeout_seconds,
        "completed_steps": [],
    }

    graph = build_development_workflow()

    completed_nodes: list[str] = []
    test_result: TestRunResult | None = None
    summary: str | None = None

    print("开始执行 LangGraph 开发工作流...")
    print(f"项目目录：{initial_state['project']}")
    print(f"测试目标：{target}")
    print()

    try:
        for event in graph.stream(
            initial_state,
            stream_mode="updates",
        ):
            for node_name, update in event.items():
                if node_name not in {
                    "inspect_repository",
                    "run_tests",
                    "summarize",
                }:
                    continue

                completed_nodes.append(node_name)

                print(
                    f"[{len(completed_nodes)}/3] {node_name} 已完成",
                    flush=True,
                )

                if node_name == "inspect_repository":
                    files = update["files"]
                    print(f"      发现 {len(files)} 个可探索文件")

                elif node_name == "run_tests":
                    test_result = update["test_result"]
                    print(f"      pytest 状态：{test_result.status}")

                elif node_name == "summarize":
                    summary = update["summary"]

    except (RepositoryError, TestRunnerError) as exc:
        print(
            f"工作流参数或目标错误：{exc}",
            file=sys.stderr,
        )
        return 2

    except OSError as exc:
        print(
            f"工作流执行错误：{exc}",
            file=sys.stderr,
        )
        return 1

    if test_result is None or summary is None:
        print(
            "工作流执行不完整：缺少测试结果或总结。",
            file=sys.stderr,
        )
        return 1

    print("\n=== 工作流总结 ===")
    print(summary)

    print("\n=== 执行信息 ===")
    print(f"已完成节点：{len(completed_nodes)}/3")
    print(f"pytest 状态：{test_result.status}")

    exit_code = (
        str(test_result.exit_code) if test_result.exit_code is not None else "无"
    )

    print(f"pytest 退出码：{exit_code}")

    if not test_result.passed:
        if test_result.stdout:
            print("\n=== pytest 输出 ===")
            print(test_result.stdout)

        if test_result.stderr:
            print(
                "\n=== pytest 错误输出 ===",
                file=sys.stderr,
            )
            print(test_result.stderr, file=sys.stderr)

    return 0 if test_result.passed else 1


def run_workflow(args: argparse.Namespace) -> int:
    """将 argparse 参数交给工作流命令。"""

    return run_workflow_command(
        project=args.project,
        target=args.target,
        timeout_seconds=args.timeout,
    )


def register(subparsers: Any) -> None:
    """向统一 CLI 注册 workflow 子命令。"""

    parser = subparsers.add_parser(
        "workflow",
        help="运行 LangGraph 仓库检查与测试工作流",
    )

    add_project_argument(parser)

    parser.add_argument(
        "--target",
        default="tests",
        help="tests 目录或其中的 test_*.py 文件",
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="pytest 超时秒数，范围 1～120，默认 30",
    )

    parser.set_defaults(handler=run_workflow)
```

---

## 12. 工作流 CLI 的实现原理

### 12.1 为什么调用 `stream()`？

第一阶段的业务函数：

```python
run_development_workflow()
```

使用：

```python
workflow.invoke(initial_state)
```

一次返回最终状态。

但 CLI 想要在每个节点完成时显示进度，因此改用：

```python
for event in graph.stream(
    initial_state,
    stream_mode="updates",
):
    ...
```

### 12.2 `event.items()` 是什么意思？

假设事件：

```python
{
    "inspect_repository": {
        "files": ["demo.py"],
        "completed_steps": ["inspect_repository"],
    }
}
```

执行：

```python
for node_name, update in event.items():
    ...
```

可以拆出：

```python
node_name = "inspect_repository"
```

以及：

```python
update = {
    "files": ["demo.py"],
    "completed_steps": ["inspect_repository"],
}
```

`items()` 是普通 Python 字典方法，用于遍历键值对。

### 12.3 为什么单独维护 `completed_nodes`？

```python
completed_nodes: list[str] = []
```

每收到一个节点的更新事件：

```python
completed_nodes.append(node_name)
```

它用于显示：

```text
[1/3]
[2/3]
[3/3]
```

需要区分两个概念：

- `State["completed_steps"]`：LangGraph 通过 Reducer 合并的真实工作流状态。
- `completed_nodes`：CLI 自己记录的已观察到的节点完成事件。

CLI 的列表不会自动变成工作流 State。

### 12.4 `flush=True` 是什么意思？

```python
print(
    f"[{len(completed_nodes)}/3] {node_name} 已完成",
    flush=True,
)
```

`flush=True` 表示立即刷新对应输出流的缓冲区。

适合逐步显示工作流进度，避免因为输出缓冲导致完成消息迟迟不显示。

它不会让节点执行得更快，也不会改变 LangGraph 的执行顺序。

### 12.5 为什么测试失败后仍生成摘要？

Day 07 的 `TestRunner` 返回结构化结果：

```python
TestRunResult(
    status="failed",
    exit_code=1,
    ...
)
```

普通测试断言失败不是节点本身抛出的异常。

因此工作流中的：

```text
run_tests → summarize
```

仍然可以继续。

而如果目标路径无效，`TestRunnerError` 会中断工作流。

这两种情况需要区别处理。

### 12.6 CLI 退出码设计

| CLI 退出码 | 含义 |
|---|---|
| `0` | 工作流完成且 pytest 通过 |
| `1` | 测试失败、超时、其他执行错误或结果不完整 |
| `2` | 项目路径或测试目标等参数错误 |

最后：

```python
return 0 if test_result.passed else 1
```

用于让后续程序识别测试是否通过。

---

## 13. 最终精简版 `cli.py`

### 13.1 打开已有文件

```bash
nano src/ai_software_dev_agent/cli.py
```

### 13.2 完整最终代码

```python
"""AI 软件开发智能体统一命令行入口。"""

import argparse

from ai_software_dev_agent import __version__
from ai_software_dev_agent.commands import (
    ask,
    chat,
    edit,
    plan,
    repository,
    testing,
    workflow,
)
from ai_software_dev_agent.model import ModelConfigError
from ai_software_dev_agent.repository import RepositoryError


def build_parser() -> argparse.ArgumentParser:
    """创建顶层解析器，并注册全部命令。"""

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

    repository.register(subparsers)
    ask.register(subparsers)
    plan.register(subparsers)
    chat.register(subparsers)
    edit.register(subparsers)
    testing.register(subparsers)

    # Day 08：新增 LangGraph 工作流命令。
    workflow.register(subparsers)

    return parser


def main(argv: list[str] | None = None) -> int:
    """解析参数并分发给对应的命令处理函数。"""

    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return args.handler(args)

    except (ModelConfigError, RepositoryError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
```

### 13.3 重构的实际价值

现在 `cli.py` 不再负责：

- 直接调用模型。
- 执行 pytest。
- 读取代码仓库。
- 处理聊天输入。
- 询问文件编辑确认。
- 展示 LangGraph 每个节点结果。

这些职责都进入了相应命令模块。

以后新增 CLI 命令，原则上只需要：

1. 创建独立命令模块。
2. 创建对应测试模块。
3. 在 `cli.py` 注册新命令。

这使项目更适合长期维护。

---

## 14. 第二阶段 B：CLI 自动化测试

### 14.1 创建文件

```bash
touch tests/cli/test_workflow.py
```

打开：

```bash
nano tests/cli/test_workflow.py
```

### 14.2 `tests/cli/test_workflow.py` 完整代码

```python
"""LangGraph workflow CLI 命令的集成测试。"""

from pathlib import Path

import pytest

from ai_software_dev_agent import cli
from ai_software_dev_agent.commands import workflow as workflow_command
from ai_software_dev_agent.test_runner import (
    TestRunResult as RunnerResult,
)


@pytest.fixture
def demo_project(tmp_path: Path) -> Path:
    """创建带有一个正常测试的临时 Python 项目。"""

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()

    (tmp_path / "demo.py").write_text(
        "def add(a, b):\n    return a + b\n",
        encoding="utf-8",
    )

    (tests_dir / "test_demo.py").write_text(
        "def test_add():\n    assert 1 + 1 == 2\n",
        encoding="utf-8",
    )

    return tmp_path


def test_workflow_cli_reports_success(
    demo_project: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """整个真实工作流运行通过，CLI 应返回 0。"""

    result = cli.main(
        [
            "workflow",
            "--project",
            str(demo_project),
        ]
    )

    output = capsys.readouterr().out

    assert result == 0

    assert "[1/3] inspect_repository 已完成" in output
    assert "[2/3] run_tests 已完成" in output
    assert "[3/3] summarize 已完成" in output

    assert "=== 工作流总结 ===" in output
    assert "pytest 状态：passed" in output
    assert "pytest 退出码：0" in output
    assert "已完成节点：3/3" in output


def test_workflow_cli_reports_failed_tests(
    demo_project: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """测试断言失败时，仍然执行总结并返回 1。"""

    (demo_project / "tests" / "test_bad.py").write_text(
        "def test_bad():\n    assert 1 == 2\n",
        encoding="utf-8",
    )

    result = cli.main(
        [
            "workflow",
            "--project",
            str(demo_project),
        ]
    )

    output = capsys.readouterr().out

    assert result == 1
    assert "[3/3] summarize 已完成" in output
    assert "pytest 状态：failed" in output
    assert "pytest 退出码：1" in output
    assert "=== pytest 输出 ===" in output
    assert "1 failed" in output


def test_workflow_cli_reports_no_tests(
    demo_project: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """没有测试时应输出 no_tests，不能误报成功。"""

    (demo_project / "tests" / "test_demo.py").unlink()

    result = cli.main(
        [
            "workflow",
            "--project",
            str(demo_project),
        ]
    )

    output = capsys.readouterr().out

    assert result == 1
    assert "pytest 状态：no_tests" in output
    assert "pytest 退出码：5" in output
    assert "=== 工作流总结 ===" in output


def test_workflow_cli_runs_selected_file(
    demo_project: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """指定正常测试文件时，不执行其他失败测试。"""

    (demo_project / "tests" / "test_bad.py").write_text(
        "def test_bad():\n    assert False\n",
        encoding="utf-8",
    )

    result = cli.main(
        [
            "workflow",
            "--project",
            str(demo_project),
            "--target",
            "tests/test_demo.py",
            "--timeout",
            "30",
        ]
    )

    output = capsys.readouterr().out

    assert result == 0
    assert "pytest 状态：passed" in output
    assert "pytest 退出码：0" in output


def test_workflow_cli_rejects_unsafe_target(
    demo_project: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """不允许通过 workflow CLI 绕过测试路径限制。"""

    result = cli.main(
        [
            "workflow",
            "--project",
            str(demo_project),
            "--target",
            "../outside.py",
        ]
    )

    captured = capsys.readouterr()

    assert result == 2
    assert "工作流参数或目标错误" in captured.err


def test_workflow_cli_rejects_invalid_timeout(
    demo_project: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """超时时间超出范围时，返回参数错误。"""

    result = cli.main(
        [
            "workflow",
            "--project",
            str(demo_project),
            "--timeout",
            "121",
        ]
    )

    captured = capsys.readouterr()

    assert result == 2
    assert "超时时间" in captured.err


def test_workflow_cli_rejects_missing_project(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """仓库不存在时，工作流不应报告成功。"""

    result = cli.main(
        [
            "workflow",
            "--project",
            str(tmp_path / "missing"),
        ]
    )

    captured = capsys.readouterr()

    assert result == 2
    assert "工作流参数或目标错误" in captured.err


def test_workflow_cli_help_shows_arguments(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """工作流命令应展示自己的参数说明。"""

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["workflow", "--help"])

    assert exc_info.value.code == 0

    output = capsys.readouterr().out

    assert "--project" in output
    assert "--target" in output
    assert "--timeout" in output


def test_workflow_cli_streams_node_updates(
    demo_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """确认 CLI 使用 updates 模式，而不是 invoke()。"""

    observed: dict[str, object] = {}

    fake_result = RunnerResult(
        status="passed",
        exit_code=0,
        stdout="1 passed",
        stderr="",
        duration_seconds=0.5,
        command=("python", "-m", "pytest", "tests"),
    )

    class FakeGraph:
        """模拟三个节点逐步返回更新的 LangGraph。"""

        def stream(
            self,
            state: dict,
            stream_mode: str,
        ):
            observed["state"] = state
            observed["stream_mode"] = stream_mode

            yield {
                "inspect_repository": {
                    "files": ["demo.py"],
                    "completed_steps": ["inspect_repository"],
                }
            }

            yield {
                "run_tests": {
                    "test_result": fake_result,
                    "completed_steps": ["run_tests"],
                }
            }

            yield {
                "summarize": {
                    "summary": "模拟工作流总结",
                    "completed_steps": ["summarize"],
                }
            }

    monkeypatch.setattr(
        workflow_command,
        "build_development_workflow",
        lambda: FakeGraph(),
    )

    result = workflow_command.run_workflow_command(
        demo_project,
        target="tests",
        timeout_seconds=30,
    )

    output = capsys.readouterr().out

    assert result == 0
    assert observed["stream_mode"] == "updates"
    assert observed["state"]["target"] == "tests"

    assert output.index("inspect_repository 已完成") < (
        output.index("run_tests 已完成")
    )
    assert output.index("run_tests 已完成") < (output.index("summarize 已完成"))

    assert "模拟工作流总结" in output


def test_workflow_cli_rejects_incomplete_result(
    demo_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """节点没有产生完整结果时，CLI 不能返回成功。"""

    class IncompleteGraph:
        def stream(
            self,
            state: dict,
            stream_mode: str,
        ):
            yield {
                "inspect_repository": {
                    "files": ["demo.py"],
                    "completed_steps": ["inspect_repository"],
                }
            }

    monkeypatch.setattr(
        workflow_command,
        "build_development_workflow",
        lambda: IncompleteGraph(),
    )

    result = workflow_command.run_workflow_command(
        demo_project,
        target="tests",
        timeout_seconds=30,
    )

    captured = capsys.readouterr()

    assert result == 1
    assert "工作流执行不完整" in captured.err


def test_workflow_cli_reports_execution_error(
    demo_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """工作流执行出现文件系统错误时返回非零退出码。"""

    class BrokenGraph:
        def stream(
            self,
            state: dict,
            stream_mode: str,
        ):
            raise OSError("模拟磁盘读取失败")
            yield

    monkeypatch.setattr(
        workflow_command,
        "build_development_workflow",
        lambda: BrokenGraph(),
    )

    result = workflow_command.run_workflow_command(
        demo_project,
        target="tests",
        timeout_seconds=30,
    )

    captured = capsys.readouterr()

    assert result == 1
    assert "模拟磁盘读取失败" in captured.err
```

### 14.3 测试覆盖

本阶段的 11 个测试覆盖：

- 正常执行。
- pytest 断言失败。
- 没有测试。
- 指定测试文件。
- 不安全目标路径。
- 非法超时时间。
- 项目不存在。
- CLI 帮助。
- 逐节点 Streaming。
- 工作流结果不完整。
- 执行过程中出现文件系统异常。

其中：

- 真实集成测试验证完整的调用链。
- Mock 测试验证难以稳定复现的错误分支。

---

## 15. 真实验收：创建临时 Python 项目

这一节详细解释每一个 Shell 命令及参数。

### 15.1 创建临时目录

执行：

```bash
DEMO_DIR="$(mktemp -d)"
```

这条命令包含多个部分。

#### 第一部分：`mktemp`

`mktemp` 用来创建具有随机名称的临时文件或目录。

#### 第二部分：`-d`

```bash
mktemp -d
```

这里 `-d` 的含义是 Directory（目录）。

也就是说：**创建一个临时目录，而不是临时文件。**

在 macOS 上可能得到类似：

```text
/var/folders/xx/yyyy/T/tmp.ABC12345
```

随机后缀可以降低临时目录重名的风险。

实际名称由操作系统决定，不需要自己填写。

#### 第三部分：`$(...)`

```bash
$(mktemp -d)
```

这是 Command Substitution（命令替换）。

Shell 会先执行括号里面的命令，再将命令的标准输出作为结果使用。

例如：

```bash
NAME="$(whoami)"

echo "$NAME"
```

#### 第四部分：`DEMO_DIR=`

```bash
DEMO_DIR="$(mktemp -d)"
```

这是 Shell 变量赋值。

它把 `mktemp -d` 返回的临时目录路径保存到变量 `DEMO_DIR`。

以后就不必反复输入那条很长的随机路径。

#### 第五部分：为什么加双引号？

```bash
"$(mktemp -d)"
```

双引号可以避免命令输出在变量赋值或后续使用时产生不必要的分词和路径通配问题。

实际使用变量时，也建议写成：

```bash
"$DEMO_DIR"
```

而不是：

```bash
$DEMO_DIR
```

#### 第六部分：怎么检查？

执行：

```bash
echo "$DEMO_DIR"
```

显示保存的临时目录路径。

再执行：

```bash
ls -ld "$DEMO_DIR"
```

参数：

- `ls`：列出文件或目录信息。
- `-l`：长格式，显示权限、所有者等信息。
- `-d`：显示目录本身，而不是列出目录里面的内容。

注意：`DEMO_DIR` 只是当前 Shell 会话中的变量，不会自动成为所有新终端窗口的变量。清理时最好仍在创建它的同一个终端中操作。

### 15.2 创建测试目录

执行：

```bash
mkdir -p "$DEMO_DIR/tests"
```

逐部分解释：

| 内容 | 含义 |
|---|---|
| `mkdir` | Make Directory，创建目录 |
| `-p` | Parents，按需要创建父目录；已有目录通常不会因此报错 |
| `"$DEMO_DIR/tests"` | 临时项目下的 `tests` 子目录 |

举例：

假设：

```bash
DEMO_DIR="/tmp/demo123"
```

那么：

```bash
mkdir -p "$DEMO_DIR/tests"
```

就会创建：

```text
/tmp/demo123/tests
```

为什么使用 `-p`？

因为实际开发中我们可能一次创建多级目录：

```bash
mkdir -p a/b/c
```

如果 `a` 和 `b` 还不存在，`-p` 会按需创建它们。

但是 `-p` 不代表无论发生什么都会成功，例如权限不足仍然会报错。

### 15.3 使用 `cat` 创建业务文件

执行：

```bash
cat > "$DEMO_DIR/demo.py" <<'PY'
def add(a: int, b: int) -> int:
    return a + b
PY
```

这是一个非常实用的 Shell 写文件方式。

逐部分解释：

#### `cat`

`cat` 原本用于读取、连接并输出文件内容。

但这里不指定要读取的文件，而是让它读取标准输入。

#### `>`

```bash
> "$DEMO_DIR/demo.py"
```

`>` 是 Shell 输出重定向操作符。

它把命令的标准输出写入目标文件。

注意：

- 文件不存在：创建。
- 文件已经存在：通常会截断并覆盖原文件内容。

因此，这个方式适合创建明确的一次性测试文件，但不要随意对重要业务文件使用。

#### `<<'PY'`

这是 Here Document（此处文档）语法。

表示：将后续的多行文本作为当前命令的标准输入，直到遇到单独一行的结束标记 `PY`。

```bash
<<'PY'
```

其中：

- `<<`：开始 Here Document。
- `PY`：我们自己选择的结束标记。
- `'PY'`：对结束标记加引号，防止 Here Document 内容发生 Shell 变量替换、命令替换等展开。

例如，正文包含：

```python
value = "$HOME"
```

使用：

```bash
<<'PY'
```

会保留字面文本 `"$HOME"`。

如果写成没有引号的：

```bash
<<PY
```

Shell 可能提前展开其中的 `$HOME`。

所以我们编写 Python 源代码时，通常推荐使用带引号的结束标记。

#### 为什么最后还需要一行 `PY`？

```bash
PY
```

这是结束标记，通知 Shell：多行输入结束。

它必须单独成行，且需要与开头指定的标记一致。

不能随意缩进，也不能少写。

### 15.4 创建 pytest 测试文件

执行：

```bash
cat > "$DEMO_DIR/tests/test_demo.py" <<'PY'
def test_add():
    assert 2 + 3 == 5
PY
```

这与上一条命令采用相同的写法。

只是写入路径变成：

```text
临时目录/tests/test_demo.py
```

检查文件：

```bash
cat "$DEMO_DIR/demo.py"

cat "$DEMO_DIR/tests/test_demo.py"
```

此处的 `cat` 没有配合 `>`，所以是将文件内容直接输出到终端，不会覆盖文件。

最终项目：

```text
临时目录/
├── demo.py
└── tests/
    └── test_demo.py
```

### 15.5 验收正常工作流

执行：

```bash
ai-dev-agent workflow \
  --project "$DEMO_DIR" \
  --timeout 30
```

逐部分解释：

| 内容 | 含义 |
|---|---|
| `ai-dev-agent` | 本项目注册的 CLI 程序 |
| `workflow` | Day 08 新增子命令 |
| `--project` | 指定目标项目根目录 |
| `"$DEMO_DIR"` | 临时项目的真实路径 |
| `--timeout` | 为 pytest 设置最大执行时间 |
| `30` | 超时时间为 30 秒 |
| `\` | Shell 续行符，将多行命令连接为一条 |

关于 `\`：

```bash
ai-dev-agent workflow \
  --project "$DEMO_DIR" \
  --timeout 30
```

和：

```bash
ai-dev-agent workflow --project "$DEMO_DIR" --timeout 30
```

在这里效果相同。

需要注意：续行反斜杠应直接位于行尾，不要在它后面再写空格或其他内容。

### 15.6 为什么 `--project` 必须指向项目根目录？

我们的 LangGraph 工作流会：

1. 使用 `RepositoryExplorer` 检查项目。
2. 使用 `TestRunner` 寻找项目中的 `tests` 目录。
3. 进入项目根目录运行 pytest。

因此：

```bash
--project "$DEMO_DIR"
```

对应：

```text
临时目录/
├── demo.py
└── tests/
```

而不是：

```bash
--project "$DEMO_DIR/tests"
```

后者会被当作项目根目录，导致测试执行器寻找：

```text
临时目录/tests/tests
```

这不是我们想要的结构。

### 15.7 验收指定测试文件

执行：

```bash
ai-dev-agent workflow \
  --project "$DEMO_DIR" \
  --target tests/test_demo.py \
  --timeout 30
```

新增参数：

```bash
--target tests/test_demo.py
```

用于指定测试目标。

这里的路径是相对于 `--project` 指定的项目根目录，而不是相对于当前终端所在目录。

当前 Test Runner 要求目标位于 `tests/` 下。

### 15.8 验收测试失败

创建一个故意失败的测试文件：

```bash
cat > "$DEMO_DIR/tests/test_bad.py" <<'PY'
def test_bad():
    assert 1 == 2
PY
```

执行：

```bash
ai-dev-agent workflow \
  --project "$DEMO_DIR"
```

预计：

- `inspect_repository` 完成。
- `run_tests` 完成，pytest 状态为 `failed`。
- `summarize` 仍然执行。
- CLI 最终返回非零退出码。

这证明普通测试失败被表示为结构化执行结果，而不是让整个 LangGraph 工作流立即丢失总结能力。

### 15.9 `echo $?` 是什么意思？

工作流命令结束后，立刻执行：

```bash
echo $?
```

其中：

- `$?`：上一个前台命令的退出码。
- `echo`：将后面的值输出到终端。

例如：

```bash
ai-dev-agent workflow --project "$DEMO_DIR"
echo $?
```

如果 pytest 全部通过，通常得到：

```text
0
```

如果测试失败，则得到：

```text
1
```

注意必须在需要检查的命令结束后立即执行。

例如：

```bash
ai-dev-agent workflow --project "$DEMO_DIR"
echo "测试结束"
echo $?
```

这里最后的 `$?` 已经是 `echo "测试结束"` 的退出码，不再是工作流的退出码。

### 15.10 没有测试时如何验收？

创建新的空项目：

```bash
mkdir -p "$DEMO_DIR/empty-project/tests"
```

再执行：

```bash
ai-dev-agent workflow \
  --project "$DEMO_DIR/empty-project"
```

预期：

```text
pytest 状态：no_tests
pytest 退出码：5
```

这里 pytest 的原始退出码 `5` 表示没有收集到测试。

CLI 对外仍返回 `1`，因为没有测试不能当作测试通过。

---

## 16. 临时测试项目如何安全清理？

这是今天需要特别理解的 Shell 操作。

### 16.1 清理命令

此前使用：

```bash
test -n "${DEMO_DIR:-}" && test -d "$DEMO_DIR" && rm -r "$DEMO_DIR"
```

它由三个判断或动作构成。

### 16.2 第一部分：`test -n`

```bash
test -n "${DEMO_DIR:-}"
```

`test` 是 Shell 条件判断命令。

`-n` 表示检查字符串是否非空。

例如：

```bash
test -n "hello"
```

结果为真。

```bash
test -n ""
```

结果为假。

这里检查 `DEMO_DIR` 是否有非空值。

### 16.3 `${DEMO_DIR:-}` 是什么意思？

这是一种 Shell Parameter Expansion（参数展开）。

```bash
${DEMO_DIR:-}
```

含义是：

- 变量有非空值：使用变量的值。
- 变量未设置或为空：使用后面提供的默认值。
- 这里 `:-` 后面没有指定内容，因此默认是空字符串。

它的作用是让变量未设置时仍然可以安全地进行字符串检查。

与直接写：

```bash
"$DEMO_DIR"
```

相比，在开启某些严格的 Shell 选项时更稳妥。

例如，Shell 启用了 `set -u` 时，直接读取未定义变量可能报错，而 `${DEMO_DIR:-}` 可以得到默认空值。

### 16.4 第二部分：`test -d`

```bash
test -d "$DEMO_DIR"
```

`-d` 表示判断目标是否为现存目录。

也就是说：

```text
DEMO_DIR 有值吗？
       ↓
对应路径确实是目录吗？
```

只有满足条件才继续。

### 16.5 第三部分：`&&`

完整命令：

```bash
A && B && C
```

含义：

1. 执行 A。
2. 如果 A 成功，执行 B。
3. 如果 B 成功，执行 C。
4. 其中任何一步失败，就停止后续执行。

所以：

```bash
test -n "${DEMO_DIR:-}" && test -d "$DEMO_DIR" && rm -r "$DEMO_DIR"
```

实际逻辑为：

```text
变量非空？
   ├── 否 → 不删除
   └── 是
       ↓
路径是目录？
   ├── 否 → 不删除
   └── 是
       ↓
删除这个目录
```

### 16.6 第四部分：`rm -r`

```bash
rm -r "$DEMO_DIR"
```

其中：

- `rm`：Remove，删除文件或目录。
- `-r`：Recursive，递归删除目录及其中的文件和子目录。

因为 `DEMO_DIR` 是一个目录，且里面还有 `tests/` 和 Python 文件，所以需要递归删除。

不要为了省事就使用：

```bash
rm -rf "$DEMO_DIR"
```

`-f` 是 Force（强制），可能掩盖部分错误。对于当前教学实验，使用 `rm -r` 更容易观察删除过程中的异常。

### 16.7 为什么删除前必须检查变量？

危险示例：

```bash
rm -r "$SOME_PATH"
```

如果变量指向了错误目录，可能删除不应该删除的文件。

加入：

```bash
test -n "${DEMO_DIR:-}"
```

可以防止空变量导致误操作。

但还要知道它的局限：

**这两个 `test` 检查只能确认变量非空且对应目录存在，不能证明它一定是本次创建的临时目录。**

例如，如果有人错误地执行：

```bash
DEMO_DIR="$HOME/Documents"
```

即使前面的条件通过，也不应该删除它。

因此真正安全的操作流程是：

1. 使用 `mktemp -d` 创建目录。
2. 保留其原始变量。
3. 删除前打印并核对路径。
4. 确认是刚才创建的临时项目。
5. 再执行递归删除。

### 16.8 推荐的实际清理流程

先检查：

```bash
echo "$DEMO_DIR"
```

确认显示的是刚才由 `mktemp` 创建的临时目录，而不是你的正式开发项目。

然后：

```bash
ls -la "$DEMO_DIR"
```

这里：

- `-l`：长格式显示。
- `-a`：显示包括隐藏文件在内的目录内容。

确认无误之后，执行：

```bash
test -n "${DEMO_DIR:-}" && test -d "$DEMO_DIR" && rm -r "$DEMO_DIR"
```

最后验证：

```bash
test ! -e "${DEMO_DIR:-}" && echo "临时项目已清理"
```

其中：

- `-e`：检查路径是否存在。
- `!`：对判断结果取反。
- `&&`：仅在判断成功时执行后续命令。

注意最后的检查只反映该路径目前是否存在；并不意味着系统上所有临时文件都已清理。

---

## 17. 临时目录操作命令速查

| 命令或语法 | 解释 |
|---|---|
| `mktemp -d` | 创建随机命名的临时目录 |
| `DEMO_DIR=...` | 给 Shell 变量赋值 |
| `$(...)` | 执行命令并使用其输出 |
| `"$DEMO_DIR"` | 引用变量，并用双引号保护路径 |
| `mkdir -p` | 按需创建多级目录 |
| `touch file.py` | 创建空文件；若已存在则更新其时间戳 |
| `cat file.py` | 输出文件内容 |
| `cat > file.py` | 将标准输出重定向写入文件，可能覆盖原文件 |
| `<<'PY'` | 将后续多行内容作为输入，禁止 Shell 展开正文 |
| `\` | 在行末续行 |
| `echo "$DEMO_DIR"` | 打印变量值 |
| `echo $?` | 打印上一个命令的退出码 |
| `test -n` | 检查字符串是否非空 |
| `test -d` | 检查路径是否为目录 |
| `test -e` | 检查路径是否存在 |
| `!` | 对条件结果取反 |
| `&&` | 前一个命令成功才执行下一个 |
| `rm -r` | 递归删除目录及内容 |

本日最值得熟练掌握的组合：

```bash
DEMO_DIR="$(mktemp -d)"
mkdir -p "$DEMO_DIR/tests"
```

以及：

```bash
test -n "${DEMO_DIR:-}" && test -d "$DEMO_DIR" && rm -r "$DEMO_DIR"
```

这些命令不仅适用于 LangGraph，也适用于以后测试文件处理、CLI、自动化脚本和项目构建。

---

## 18. Day 08 测试与验收

### 18.1 第一阶段：工作流测试

```bash
python -m pytest tests/test_workflow.py -v
```

本阶段新增 7 个测试用例。

前面已确认这一阶段通过。

### 18.2 第二阶段 A：CLI 重构回归

```bash
python -m pytest tests/cli -v
```

再运行：

```bash
python -m pytest -v
```

重点关注：

- 历史 CLI 命令是否正常。
- 原有测试是否丢失。
- 是否发生导入冲突。
- Monkeypatch 是否仍然作用于正确的模块。
- 是否新增 Warning。

### 18.3 第二阶段 B：工作流 CLI 测试

```bash
python -m pytest tests/cli/test_workflow.py -v
```

本阶段新增 11 个测试用例。

然后：

```bash
python -m pytest tests/test_workflow.py -v
```

最后完整回归：

```bash
python -m pytest -v
```

### 18.4 CLI 验收命令

查看帮助：

```bash
ai-dev-agent --help

ai-dev-agent workflow --help
```

正常执行：

```bash
ai-dev-agent workflow \
  --project "$DEMO_DIR" \
  --timeout 30
```

指定测试文件：

```bash
ai-dev-agent workflow \
  --project "$DEMO_DIR" \
  --target tests/test_demo.py \
  --timeout 30
```

测试失败：

```bash
ai-dev-agent workflow \
  --project "$DEMO_DIR"
```

非法路径：

```bash
ai-dev-agent workflow \
  --project "$DEMO_DIR" \
  --target ../outside.py
```

无测试：

```bash
ai-dev-agent workflow \
  --project "$DEMO_DIR/empty-project"
```

验收时应核对状态、完成节点数、pytest 原始退出码以及 CLI 退出码。

本学习文档没有收到第二阶段 B 的完整终端输出，因此不虚构最终的 `passed` 数量。以实际测试统计为准。

---

## 19. 本日 Debug 与工程注意事项

### 19.1 重构后 Mock 失效

可能表现：

```text
AttributeError
```

或者模拟函数没有被调用。

原因可能是旧测试仍然给 `cli` 模块打桩，但实际调用已经移动到 `commands/<name>.py`。

处理思路：

1. 找到被测函数当前定义在哪个模块。
2. 找到该函数从哪里引用依赖。
3. 将 Monkeypatch 改到真正查找依赖的模块。
4. 重新执行对应测试。

不要通过删除失败测试来完成重构。

### 19.2 测试重复收集

如果迁移后保留：

```text
tests/test_cli.py
```

同时又保留：

```text
tests/cli/test_*.py
```

就可能重复执行一批相同的测试。

所以迁移时需要先保留备份，在确认新测试全部有效后移除旧测试副本。

### 19.3 模块名称相同

例如：

```text
tests/test_repository.py
tests/cli/test_repository.py
```

两个文件虽然位于不同目录，但名称相同。

通过为 `tests/cli` 添加 `__init__.py`，可以帮助 pytest 使用明确的包路径处理模块。

如果仍然出现导入冲突，需要检查 Python 包结构及 pytest 导入模式。

### 19.4 测试失败与工作流异常不同

测试失败：

```python
result.status == "failed"
```

工作流仍然可以继续总结。

参数错误：

```python
raise TestRunnerError(...)
```

则会中断当前图的正常执行。

这正是后续实现 Conditional Edges 的基础。

### 19.5 当前工作流的局限

本日只有固定节点顺序。

尚未实现：

- 根据测试结果条件分支。
- 自动代码修改。
- 自动执行修复循环。
- 工作流持久化。
- 中断后恢复。
- Human-in-the-Loop 审批。
- 对不可信代码进行沙箱执行。

尤其注意：`TestRunner` 运行 pytest 时会执行测试中的 Python 代码，因此当前系统只适合测试可信任的本地项目。

---

## 20. 本日工程知识总结

### 20.1 LangGraph 与 LangChain 的角色区别

在当前项目里：

- LangChain 主要用于连接模型、定义 Agent 和工具调用。
- LangGraph 主要用于管理状态、节点执行顺序和工作流编排。

今天的 LangGraph 工作流虽然完全不调用大模型，但依然有价值。

它负责将已有组件组合成一个可执行的流程。

### 20.2 组合已有组件，而不是重复开发

本日没有重新实现：

```python
RepositoryExplorer
```

也没有重新实现：

```python
TestRunner
```

而是把它们包装为 LangGraph Node。

这减少重复，并保持单个组件职责稳定。

### 20.3 CLI 是界面，不是业务核心

重构后：

```text
cli.py
```

只负责入口。

```text
commands/
```

负责终端交互。

```text
repository.py、test_runner.py、workflow.py
```

负责业务能力。

这样未来无论使用 CLI、Web API 还是其他程序接口，都可以复用同一套业务组件。

### 20.4 自动化测试应随着代码一起重构

不能只拆生产代码，不迁移测试。

测试中对模块内部依赖的 Mock 和 Monkeypatch，也需要跟随代码位置调整。

### 20.5 不确定时优先保证功能不回归

本日的 CLI 重构不是为了增加新命令，而是为了提高可维护性。

因此每个已有命令的参数、退出码和输出行为都应尽可能保持不变。

---

## 21. Day 01～Day 08 能力演进

```text
Day 01：项目初始化与 CLI
          ↓
Day 02：RepositoryExplorer
          ↓
Day 03：LangChain 模型问答
          ↓
Day 04：结构化规划与工具调用
          ↓
Day 05：Agent Loop 与多轮交互
          ↓
Day 06：文件编辑、Diff 预览、人工确认
          ↓
Day 07：TestRunner、pytest、结构化执行结果
          ↓
Day 08：LangGraph 工作流 + CLI 模块化重构
```

现在已经拥有：

```text
RepositoryExplorer
        ↓
     LangGraph
        ↓
    TestRunner
        ↓
  TestRunResult
        ↓
 工作流总结与 CLI 状态
```

同时，CLI 已经从大型单文件结构转变为按命令组织的模块化结构。

---

## 22. 今日最终总结

今天最重要的不是又增加了一个 CLI 命令，而是形成了两个工程认识。

**第一，功能组件需要通过工作流协同。**

仓库探索器和测试执行器各自能正常运行，并不代表它们已经构成软件开发流程。

LangGraph 的作用就是明确：

- 什么数据需要共享。
- 每个节点负责什么。
- 节点按什么顺序执行。
- 节点完成后如何更新 State。
- 如何观察整个执行过程。

**第二，项目架构需要随着复杂度增长而演进。**

当 `cli.py` 和 `test_cli.py` 不断变大时，继续堆叠代码会提高维护成本。

通过 `commands/` 包、独立测试文件和 `set_defaults(handler=...)`，我们将命令行入口与业务功能分开，让后续开发更加清晰。

**本日最终成果：一个能够真实执行仓库探索和 pytest 测试、逐节点展示状态的 LangGraph 工作流，以及一套更易维护的模块化 CLI 架构。**

