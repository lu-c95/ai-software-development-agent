# Day 10｜Conditional Routing & Error Recovery

**项目：AI Software Development Agent**

**日期：2026-11-15**

**学习主题：LangGraph 条件路由与错误恢复**

**开发状态：Day 10 两阶段功能及对应验收已通过**

---

## 1. 今日目标与整体设计

### 1.1 已有基础

截至 Day 09，我们已经完成：

- RepositoryExplorer：安全探索代码仓库。
- LangChain Model：调用大语言模型。
- LangChain Agent：工具调用与多轮对话。
- CodeEditor：代码修改、Diff 预览与人工确认。
- TestRunner：调用 pytest 并返回结构化结果。
- LangGraph Workflow：组织仓库探索、测试和总结。
- Agent Workflow：根据有限源码证据分析项目。

之前的工作流主要使用固定边：

```python
builder.add_edge("run_tests", "summarize")
```

这意味着执行完 `run_tests` 后，总是进入同一个总结节点。

但实际软件开发过程中，不同的测试结果需要不同的处理方式。

### 1.2 今日目标

本日重点解决两个问题：

**Conditional Routing（条件路由）**

让 LangGraph 根据当前 State 的内容，决定执行哪个节点。

**Error Recovery（错误恢复）**

遇到特定错误时，能够进行有限、可控的恢复，而不是全部立即终止，也不是无限重试。

最终新增 CLI：

```bash
ai-dev-agent conditional-workflow \
  --project . \
  --target tests \
  --timeout 60 \
  --max-retries 0
```

### 1.3 最终工作流

```text
START
  │
  ▼
inspect_repository
  │
  ├── 仓库异常 ──────────────► summarize_error ──► END
  │
  ▼
run_tests ◄─────────────┐
  │                     │
  ▼                     │
route_after_tests       │
  │                     │
  ├── passed ──────► summarize_passed ──► END
  │
  ├── failed ──────► summarize_failed ──► END
  │
  ├── no_tests ────► summarize_no_tests ──► END
  │
  ├── error ───────► summarize_error ──► END
  │
  └── timeout
        │
        ├── 无重试预算 ──► summarize_timeout ──► END
        │
        └── 有重试预算
                │
                ▼
           retry_tests
                │
                └────────────┘
```

本次使用 **State + Conditional Edges（条件边）**实现分支，使用显式的 `retry_count` 和 `max_retries` 实现有限循环。

### 1.4 今日新增或修改的文件

```text
ai-software-development-agent/
├── src/
│   └── ai_software_dev_agent/
│       ├── conditional_workflow.py              # 新增
│       ├── cli.py                               # 修改
│       └── commands/
│           └── conditional_workflow.py          # 新增
├── tests/
│   ├── test_conditional_workflow.py             # 新增
│   └── cli/
│       └── test_conditional_workflow.py         # 新增
└── docs/
    └── Day10-Conditional-Routing-And-Error-Recovery.md
```

Day 08 和 Day 09 已验收的业务工作流保持独立，本日没有要求重构它们。

### 1.5 环境准备

进入项目：

```bash
cd "/Users/lc/Documents/公子路的长期成长计划/02-AI-Agent-Engineering/ai-software-development-agent"
```

激活虚拟环境：

```bash
source .venv/bin/activate
```

检查 Python：

```bash
which python

python --version

python -c 'import sys; print(sys.executable)'
```

确认 Python 路径属于当前项目的 `.venv`。

本日没有增加新依赖，也不需要调用大模型 API。

---

## 2. 文件一：`src/ai_software_dev_agent/conditional_workflow.py`

### 2.1 文件职责

这是 Day 10 的核心业务文件，负责：

- 定义条件工作流的共享 State。
- 调用已有 RepositoryExplorer 检查仓库。
- 调用已有 TestRunner 执行 pytest。
- 将已知异常转成状态信息。
- 根据测试结果选择执行分支。
- 对超时进行有限重试。
- 汇总最终结果。
- 编译并执行 LangGraph。

与 Day 08 的固定工作流相比，最大的变化是使用 `add_conditional_edges()`，并引入有界循环。

### 2.2 创建与打开文件

首次创建：

```bash
touch src/ai_software_dev_agent/conditional_workflow.py
```

打开：

```bash
nano src/ai_software_dev_agent/conditional_workflow.py
```

本文件已经完成开发，日后复习时直接打开即可。

### 2.3 完整最终代码

```python
"""Day 10：LangGraph 条件路由与有界错误恢复。"""

import operator
from pathlib import Path
from typing import Annotated, Literal, NotRequired, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from ai_software_dev_agent.repository import (
    RepositoryError,
    RepositoryExplorer,
)
from ai_software_dev_agent.test_runner import (
    TestRunResult,
    TestRunner,
    TestRunnerError,
)


WorkflowStatus = Literal[
    "passed",
    "failed",
    "no_tests",
    "timeout",
    "error",
]

# 限制用户可配置的重试上限，防止重复运行 pytest 失控。
MAX_ALLOWED_RETRIES = 2


class ConditionalWorkflowState(TypedDict):
    """条件工作流的共享状态。"""

    project: str
    target: str
    timeout_seconds: int

    # max_retries 是允许的额外重试次数。
    # retry_count 是实际已经发生的额外重试次数。
    max_retries: int
    retry_count: int

    completed_steps: Annotated[list[str], operator.add]

    files: NotRequired[list[str]]
    test_result: NotRequired[TestRunResult]
    status: NotRequired[WorkflowStatus]
    error_message: NotRequired[str]
    summary: NotRequired[str]


def inspect_repository_node(
    state: ConditionalWorkflowState,
) -> dict[str, object]:
    """检查仓库，已知仓库错误进入统一错误分支。"""

    try:
        explorer = RepositoryExplorer(Path(state["project"]))
        files = [str(path) for path in explorer.list_files()]
    except (RepositoryError, OSError) as exc:
        return {
            "status": "error",
            "error_message": str(exc),
            "completed_steps": ["inspect_repository"],
        }

    return {
        "files": files,
        "completed_steps": ["inspect_repository"],
    }


def route_after_inspection(
    state: ConditionalWorkflowState,
) -> Literal["run_tests", "summarize_error"]:
    """仓库有效才运行 pytest。"""

    if state.get("status") == "error":
        return "summarize_error"

    return "run_tests"


def run_tests_node(
    state: ConditionalWorkflowState,
) -> dict[str, object]:
    """运行一次 pytest，返回真实的结构化测试状态。"""

    try:
        runner = TestRunner(Path(state["project"]))

        result = runner.run(
            state["target"],
            timeout_seconds=state["timeout_seconds"],
        )

    except (TestRunnerError, OSError) as exc:
        return {
            "status": "error",
            "error_message": str(exc),
            "completed_steps": ["run_tests"],
        }

    return {
        "test_result": result,
        "status": result.status,
        "completed_steps": ["run_tests"],
    }


def route_after_tests(
    state: ConditionalWorkflowState,
) -> Literal[
    "retry_tests",
    "summarize_passed",
    "summarize_failed",
    "summarize_no_tests",
    "summarize_timeout",
    "summarize_error",
]:
    """根据测试状态和剩余重试预算选择下一个节点。"""

    status = state["status"]

    if status == "passed":
        return "summarize_passed"

    if status == "failed":
        return "summarize_failed"

    if status == "no_tests":
        return "summarize_no_tests"

    if status == "timeout":
        # 只有明确启用重试，且预算未耗尽，才再次运行 pytest。
        retry_count = state.get("retry_count", 0)
        max_retries = state.get("max_retries", 0)

        if retry_count < max_retries:
            return "retry_tests"

        return "summarize_timeout"

    return "summarize_error"


def retry_tests_node(
    state: ConditionalWorkflowState,
) -> dict[str, object]:
    """记录本次重试，随后通过普通边重新进入 run_tests。"""

    return {
        "retry_count": state["retry_count"] + 1,
        "completed_steps": ["retry_tests"],
    }


def summarize_passed_node(
    state: ConditionalWorkflowState,
) -> dict[str, object]:
    """总结测试通过的情况。"""

    retries = state.get("retry_count", 0)
    attempts = retries + 1

    result_text = "重试后测试通过" if retries else "测试通过"

    return {
        "summary": (
            f"{result_text}：{state['target']}\n"
            f"仓库文件数：{len(state['files'])}\n"
            f"实际测试次数：{attempts}"
        ),
        "completed_steps": ["summarize_passed"],
    }


def summarize_failed_node(
    state: ConditionalWorkflowState,
) -> dict[str, object]:
    """测试正常执行，但存在失败用例。"""

    return {
        "summary": (
            f"测试未通过：{state['target']}\n"
            "请查看 pytest 输出，定位失败的测试用例。\n"
            "本工作流不会盲目重试失败断言。"
        ),
        "completed_steps": ["summarize_failed"],
    }


def summarize_no_tests_node(
    state: ConditionalWorkflowState,
) -> dict[str, object]:
    """未发现测试用例时提示检查测试配置。"""

    return {
        "summary": (
            f"没有找到测试用例：{state['target']}\n"
            "请检查测试目录、文件名称和 pytest 收集规则。"
        ),
        "completed_steps": ["summarize_no_tests"],
    }


def summarize_timeout_node(
    state: ConditionalWorkflowState,
) -> dict[str, object]:
    """超时且没有剩余重试预算时结束工作流。"""

    retries = state.get("retry_count", 0)

    return {
        "summary": (
            f"测试超时：{state['target']}\n"
            f"单次超时时间：{state['timeout_seconds']} 秒\n"
            f"实际测试次数：{retries + 1}\n"
            f"已执行额外重试：{retries} 次\n"
            "请检查测试卡住的原因，不再继续重试。"
        ),
        "completed_steps": ["summarize_timeout"],
    }


def summarize_error_node(
    state: ConditionalWorkflowState,
) -> dict[str, object]:
    """统一汇总仓库异常与测试执行异常。"""

    reason = state.get("error_message") or "测试运行返回 error 状态或未知状态"

    return {
        "summary": f"工作流执行异常：{reason}",
        "completed_steps": ["summarize_error"],
    }


def build_conditional_workflow() -> CompiledStateGraph:
    """构建具有条件分支和有限循环的 LangGraph 工作流。"""

    builder = StateGraph(ConditionalWorkflowState)

    builder.add_node("inspect_repository", inspect_repository_node)
    builder.add_node("run_tests", run_tests_node)
    builder.add_node("retry_tests", retry_tests_node)

    builder.add_node("summarize_passed", summarize_passed_node)
    builder.add_node("summarize_failed", summarize_failed_node)
    builder.add_node("summarize_no_tests", summarize_no_tests_node)
    builder.add_node("summarize_timeout", summarize_timeout_node)
    builder.add_node("summarize_error", summarize_error_node)

    builder.add_edge(START, "inspect_repository")

    builder.add_conditional_edges(
        "inspect_repository",
        route_after_inspection,
    )

    builder.add_conditional_edges(
        "run_tests",
        route_after_tests,
    )

    # 重试节点只负责更新计数，下一步重新执行测试节点。
    builder.add_edge("retry_tests", "run_tests")

    # 所有总结分支都属于终点。
    for node_name in (
        "summarize_passed",
        "summarize_failed",
        "summarize_no_tests",
        "summarize_timeout",
        "summarize_error",
    ):
        builder.add_edge(node_name, END)

    return builder.compile()


def run_conditional_workflow(
    project: Path,
    target: str = "tests",
    timeout_seconds: int = 60,
    max_retries: int = 0,
) -> ConditionalWorkflowState:
    """验证输入并运行条件工作流。"""

    if not target.strip():
        raise ValueError("测试目标不能为空")

    if timeout_seconds <= 0:
        raise ValueError("超时时间必须大于 0")

    if not 0 <= max_retries <= MAX_ALLOWED_RETRIES:
        raise ValueError(f"重试次数必须在 0～{MAX_ALLOWED_RETRIES} 之间")

    initial_state: ConditionalWorkflowState = {
        "project": str(project.expanduser().resolve()),
        "target": target.strip(),
        "timeout_seconds": timeout_seconds,
        "max_retries": max_retries,
        "retry_count": 0,
        "completed_steps": [],
    }

    graph = build_conditional_workflow()

    return graph.invoke(initial_state)
```

### 2.4 代码讲解

**（1）`WorkflowStatus`：限制测试状态的预期取值。**

```python
WorkflowStatus = Literal[
    "passed",
    "failed",
    "no_tests",
    "timeout",
    "error",
]
```

`Literal` 是 Python 的类型标注工具，表示期望使用固定的字符串值。

它不负责运行时校验，因此仍需要路由函数处理未知状态。

这五种状态有明确区别：

| 状态 | 含义 | 本日处理 |
|---|---|---|
| `passed` | 测试通过 | 成功总结 |
| `failed` | 测试断言失败 | 失败总结，不重试 |
| `no_tests` | 没有找到测试 | 提示检查配置 |
| `timeout` | 测试运行超时 | 有预算时允许重试 |
| `error` | 测试执行异常 | 错误总结，不重试 |

**（2）State 增加重试控制。**

```python
max_retries: int
retry_count: int
```

含义分别是：

- `max_retries`：允许的最大额外重试次数。
- `retry_count`：已经发生的额外重试次数。

例如：

```python
max_retries = 2
retry_count = 1
```

说明最多允许额外重试两次，目前已经进行了一次额外重试。

实际测试次数：

```text
实际执行次数 = 1 + retry_count
```

注意初次执行不属于“重试”。

**（3）Reducer 为什么只用在 `completed_steps`？**

```python
completed_steps: Annotated[list[str], operator.add]
```

它会追加每个节点返回的执行记录。

例如：

```python
["inspect_repository"]
```

和：

```python
["run_tests"]
```

会合并为：

```python
["inspect_repository", "run_tests"]
```

但：

```python
retry_count: int
```

不使用 Reducer，因为我们需要用新计数覆盖旧计数。

**（4）`add_conditional_edges()` 的作用。**

```python
builder.add_conditional_edges(
    "run_tests",
    route_after_tests,
)
```

表示 `run_tests` 完成后，调用 `route_after_tests()`。

该函数读取最新 State，并返回下一节点名称：

```python
if status == "passed":
    return "summarize_passed"
```

这是条件路由的核心。

普通边：

```python
builder.add_edge("retry_tests", "run_tests")
```

则表示固定连接，无需判断。

**（5）Node 与 Router 的区别。**

Node（节点）负责执行业务，并返回 State 更新：

```python
def retry_tests_node(state):
    return {
        "retry_count": state["retry_count"] + 1,
        "completed_steps": ["retry_tests"],
    }
```

Router（路由函数）只负责选择下一节点：

```python
def route_after_tests(state):
    if state["status"] == "passed":
        return "summarize_passed"
```

不要把业务执行放进路由函数。

**（6）为什么把重试拆成独立节点？**

```python
def retry_tests_node(state):
```

只负责更新重试次数。

真正运行测试的代码只有一份：

```python
def run_tests_node(state):
```

当需要重试时：

```text
run_tests → retry_tests → run_tests
```

这样代码职责更清晰，也方便单独测试执行路径。

**（7）为什么重试不会无限循环？**

关键判断：

```python
if retry_count < max_retries:
    return "retry_tests"
```

如果 `max_retries=2`，最多运行三次测试：

```text
第一次测试 → timeout
第一次重试 → timeout
第二次重试 → timeout
                 ↓
          summarize_timeout
                 ↓
                END
```

通过显式计数和有限预算保证退出。

**（8）错误为什么写入 State？**

已知仓库错误：

```python
except (RepositoryError, OSError) as exc:
    return {
        "status": "error",
        "error_message": str(exc),
        ...
    }
```

已知测试执行错误：

```python
except (TestRunnerError, OSError) as exc:
```

这些错误被转换成 State 信息后，工作流可以走向 `summarize_error`。

而未知 `RuntimeError` 等异常没有被这里统一捕获，因此不会被悄悄隐藏。

### 2.5 注意事项

**第一：超时不一定值得重试。**

超时可能来自暂时资源紧张，也可能来自死锁、死循环等确定性问题。

所以默认：

```python
max_retries = 0
```

只有用户显式设置后才额外重试。

**第二：`failed` 不等于 `error`。**

`failed` 表示 pytest 正常运行，但某些测试没有通过。

`error` 表示执行环境或运行过程存在问题。

这两种情况对应的处理策略不同。

**第三：不要随意使用 `except Exception`。**

工作流内部只捕获明确知道如何分类的异常。

未知程序错误仍然应该传播。

**第四：测试状态来自已有 `TestRunner`。**

本文件复用 Day 07 的 `TestRunResult` 和 `TestRunner`，不重复实现 pytest 进程执行。

**第五：当前错误恢复不包含自动修改代码。**

Day 10 只研究受控重试。

不能把“失败后重新执行测试”理解为“失败后自动修复代码”。

### 2.6 对应测试

测试文件：

```text
tests/test_conditional_workflow.py
```

单独执行：

```bash
python -m pytest tests/test_conditional_workflow.py -v
```

具体测试内容统一放在第 3 节。

---

## 3. 文件二：`tests/test_conditional_workflow.py`

### 3.1 文件职责

该文件专门验证核心业务工作流。

需要确认：

- 五种测试状态能正确路由。
- 仓库不存在时不执行测试。
- 已知测试异常进入错误分支。
- 未知程序异常能够向上抛出。
- 流式执行只经过实际选择的节点。
- 超时后能够有限重试。
- 重试成功能够正确报告。
- 重试预算耗尽后能够结束。
- 非超时状态不会盲目重试。
- 无效输入会提前拒绝。

### 3.2 创建与打开

首次创建：

```bash
touch tests/test_conditional_workflow.py
```

打开：

```bash
nano tests/test_conditional_workflow.py
```

本日已创建，复习时直接打开即可。

### 3.3 完整最终代码

```python
"""Day 10：条件路由、有限重试及错误处理测试。"""

from pathlib import Path
from types import SimpleNamespace

import pytest

from ai_software_dev_agent import conditional_workflow
from ai_software_dev_agent.test_runner import (
    TestRunnerError as RunnerExecutionError,
)


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    """创建独立的测试仓库。"""

    (tmp_path / "demo.py").write_text(
        "def add(a: int, b: int) -> int:\n    return a + b\n",
        encoding="utf-8",
    )

    return tmp_path


def mock_test_result(
    monkeypatch: pytest.MonkeyPatch,
    status: str,
) -> None:
    """模拟固定测试结果，不执行真实 pytest。"""

    class FakeTestRunner:
        def __init__(self, project: Path) -> None:
            self.project = project

        def run(
            self,
            target: str,
            timeout_seconds: int,
        ) -> SimpleNamespace:
            return SimpleNamespace(status=status)

    monkeypatch.setattr(
        conditional_workflow,
        "TestRunner",
        FakeTestRunner,
    )


@pytest.mark.parametrize(
    ("status", "expected_node", "expected_text"),
    [
        ("passed", "summarize_passed", "测试通过"),
        ("failed", "summarize_failed", "测试未通过"),
        ("no_tests", "summarize_no_tests", "没有找到测试用例"),
        ("timeout", "summarize_timeout", "测试超时"),
        ("error", "summarize_error", "工作流执行异常"),
    ],
)
def test_routes_by_test_result(
    sample_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    status: str,
    expected_node: str,
    expected_text: str,
) -> None:
    """默认不重试，测试状态决定最终处理分支。"""

    mock_test_result(monkeypatch, status)

    result = conditional_workflow.run_conditional_workflow(
        project=sample_project,
        target="tests",
        timeout_seconds=30,
    )

    assert result["status"] == status
    assert result["retry_count"] == 0

    assert result["completed_steps"] == [
        "inspect_repository",
        "run_tests",
        expected_node,
    ]

    assert expected_text in result["summary"]


def test_missing_project_routes_to_error(
    tmp_path: Path,
) -> None:
    """仓库不存在时，不应进入测试执行节点。"""

    result = conditional_workflow.run_conditional_workflow(
        project=tmp_path / "not_exists",
        max_retries=1,
    )

    assert result["status"] == "error"
    assert result["retry_count"] == 0
    assert result["completed_steps"] == [
        "inspect_repository",
        "summarize_error",
    ]
    assert "工作流执行异常" in result["summary"]


def test_runner_error_routes_to_error(
    sample_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试目标等已知错误，不应该触发重试。"""

    class FailingTestRunner:
        def __init__(self, project: Path) -> None:
            self.project = project

        def run(
            self,
            target: str,
            timeout_seconds: int,
        ) -> None:
            raise RunnerExecutionError("测试目标无效")

    monkeypatch.setattr(
        conditional_workflow,
        "TestRunner",
        FailingTestRunner,
    )

    result = conditional_workflow.run_conditional_workflow(
        sample_project,
        max_retries=2,
    )

    assert result["status"] == "error"
    assert result["retry_count"] == 0
    assert result["completed_steps"] == [
        "inspect_repository",
        "run_tests",
        "summarize_error",
    ]
    assert "测试目标无效" in result["summary"]


def test_unexpected_error_is_not_hidden(
    sample_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """真正未知的程序错误应该向上抛出。"""

    class BrokenTestRunner:
        def __init__(self, project: Path) -> None:
            self.project = project

        def run(
            self,
            target: str,
            timeout_seconds: int,
        ) -> None:
            raise RuntimeError("模拟未知程序错误")

    monkeypatch.setattr(
        conditional_workflow,
        "TestRunner",
        BrokenTestRunner,
    )

    with pytest.raises(
        RuntimeError,
        match="模拟未知程序错误",
    ):
        conditional_workflow.run_conditional_workflow(
            sample_project,
        )


def test_stream_only_visits_selected_branch(
    sample_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试通过时只执行成功分支。"""

    mock_test_result(monkeypatch, "passed")

    graph = conditional_workflow.build_conditional_workflow()

    initial_state = {
        "project": str(sample_project),
        "target": "tests",
        "timeout_seconds": 30,
        "max_retries": 0,
        "retry_count": 0,
        "completed_steps": [],
    }

    events = list(
        graph.stream(
            initial_state,
            stream_mode="updates",
        )
    )

    node_names = [next(iter(event)) for event in events]

    assert node_names == [
        "inspect_repository",
        "run_tests",
        "summarize_passed",
    ]


def test_timeout_recovers_after_retry(
    sample_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """第一次超时，第二次通过，应正常完成恢复。"""

    calls = 0

    class TemporaryTimeoutRunner:
        def __init__(self, project: Path) -> None:
            self.project = project

        def run(
            self,
            target: str,
            timeout_seconds: int,
        ) -> SimpleNamespace:
            nonlocal calls
            calls += 1

            status = "timeout" if calls == 1 else "passed"
            return SimpleNamespace(status=status)

    monkeypatch.setattr(
        conditional_workflow,
        "TestRunner",
        TemporaryTimeoutRunner,
    )

    result = conditional_workflow.run_conditional_workflow(
        sample_project,
        max_retries=1,
    )

    assert calls == 2
    assert result["status"] == "passed"
    assert result["retry_count"] == 1

    assert result["completed_steps"] == [
        "inspect_repository",
        "run_tests",
        "retry_tests",
        "run_tests",
        "summarize_passed",
    ]

    assert "重试后测试通过" in result["summary"]
    assert "实际测试次数：2" in result["summary"]


def test_timeout_stops_when_budget_exhausted(
    sample_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """持续超时只能在预算内重试，不能无限循环。"""

    calls = 0

    class AlwaysTimeoutRunner:
        def __init__(self, project: Path) -> None:
            self.project = project

        def run(
            self,
            target: str,
            timeout_seconds: int,
        ) -> SimpleNamespace:
            nonlocal calls
            calls += 1
            return SimpleNamespace(status="timeout")

    monkeypatch.setattr(
        conditional_workflow,
        "TestRunner",
        AlwaysTimeoutRunner,
    )

    result = conditional_workflow.run_conditional_workflow(
        sample_project,
        max_retries=2,
    )

    assert calls == 3
    assert result["status"] == "timeout"
    assert result["retry_count"] == 2

    assert result["completed_steps"] == [
        "inspect_repository",
        "run_tests",
        "retry_tests",
        "run_tests",
        "retry_tests",
        "run_tests",
        "summarize_timeout",
    ]

    assert "实际测试次数：3" in result["summary"]
    assert "不再继续重试" in result["summary"]


@pytest.mark.parametrize(
    "status",
    ["failed", "no_tests", "error"],
)
def test_non_timeout_status_does_not_retry(
    sample_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    status: str,
) -> None:
    """即使允许重试，非超时状态也不能重复执行。"""

    calls = 0

    class FixedStatusRunner:
        def __init__(self, project: Path) -> None:
            self.project = project

        def run(
            self,
            target: str,
            timeout_seconds: int,
        ) -> SimpleNamespace:
            nonlocal calls
            calls += 1
            return SimpleNamespace(status=status)

    monkeypatch.setattr(
        conditional_workflow,
        "TestRunner",
        FixedStatusRunner,
    )

    result = conditional_workflow.run_conditional_workflow(
        sample_project,
        max_retries=2,
    )

    assert calls == 1
    assert result["status"] == status
    assert result["retry_count"] == 0
    assert "retry_tests" not in result["completed_steps"]


@pytest.mark.parametrize(
    ("target", "timeout_seconds", "max_retries", "message"),
    [
        ("   ", 30, 0, "测试目标不能为空"),
        ("tests", 0, 0, "超时时间必须大于 0"),
        ("tests", -1, 0, "超时时间必须大于 0"),
        ("tests", 30, -1, "重试次数必须在"),
        ("tests", 30, 3, "重试次数必须在"),
    ],
)
def test_invalid_inputs(
    sample_project: Path,
    target: str,
    timeout_seconds: int,
    max_retries: int,
    message: str,
) -> None:
    """输入不合法时，不能进入工作流执行。"""

    with pytest.raises(ValueError, match=message):
        conditional_workflow.run_conditional_workflow(
            project=sample_project,
            target=target,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
```

### 3.4 代码讲解

**（1）为什么使用 Fixture？**

```python
@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
```

`tmp_path` 是 pytest 提供的临时目录。

每次测试可以创建独立项目，不会修改真实仓库。

**（2）为什么使用 Mock TestRunner？**

```python
monkeypatch.setattr(
    conditional_workflow,
    "TestRunner",
    FakeTestRunner,
)
```

本次测试重点是 LangGraph 路由，而不是 pytest 进程本身。

因此模拟 TestRunner 返回不同状态，更容易验证分支是否正确。

**（3）为什么使用 `SimpleNamespace`？**

```python
return SimpleNamespace(status=status)
```

它可以快速生成支持属性访问的对象：

```python
result.status
```

当前业务只需要这个字段完成路由。

但它不是完整的 `TestRunResult`，不能用来验证全部测试输出字段。

**（4）为什么使用 `@pytest.mark.parametrize`？**

例如：

```python
@pytest.mark.parametrize(
    "status",
    ["failed", "no_tests", "error"],
)
```

可以让同一个测试函数分别运行三组数据。

比重复编写三个高度相似的测试函数更清晰。

**（5）为什么使用 `nonlocal calls`？**

```python
calls = 0
```

定义在外部测试函数中。

在内部类的方法中：

```python
nonlocal calls
calls += 1
```

用于记录模拟 TestRunner 的实际调用次数。

这样能够验证：

```python
assert calls == 3
```

而不只是依赖 State 中的 `retry_count`。

**（6）为什么测试未知异常？**

```python
raise RuntimeError("模拟未知程序错误")
```

希望确认这类错误不会被误认为正常的 `failed` 或 `error` 测试结果。

因此测试要求：

```python
with pytest.raises(RuntimeError):
```

未知代码 Bug 应当暴露，方便排查。

### 3.5 本日 Warning 修复

第一阶段执行测试时出现：

```text
PytestCollectionWarning:
cannot collect test class 'TestRunnerError'
because it has a __init__ constructor
```

当时测试文件直接导入：

```python
from ai_software_dev_agent.test_runner import TestRunnerError
```

pytest 会尝试收集名称以 `Test` 开头的类。

但 `TestRunnerError` 实际上是业务异常类，不是测试类。

最终改为：

```python
from ai_software_dev_agent.test_runner import (
    TestRunnerError as RunnerExecutionError,
)
```

然后将测试中的异常引用相应改成：

```python
raise RunnerExecutionError("测试目标无效")
```

这只改变了测试模块内的导入名称，不修改原始异常类。

第一次测试真实结果：

```text
12 passed, 1 warning in 0.22s
```

之后通过导入别名解决收集 Warning。

### 3.6 注意事项与验证

当前模拟测试能够验证：

- 条件分支正确。
- 重试次数正确。
- 不会无限重试。
- 错误能被正确分类。
- 非超时状态不会误触发重试。

但不能证明：

- 真实 pytest 一定执行成功。
- 所有超时都能通过重试恢复。
- 所有可能的异常都已经处理完毕。

本日最终还通过真实 CLI 调用了现有 TestRunner，作为独立验收。

单文件测试命令：

```bash
python -m pytest tests/test_conditional_workflow.py -v
```

本次开发者已确认阶段二相关测试通过。

---

## 4. 文件三：`src/ai_software_dev_agent/commands/conditional_workflow.py`

### 4.1 文件职责

这是 Day 10 新增的 CLI 命令模块。

负责：

- 注册 `conditional-workflow` 命令。
- 解析项目、测试目标、超时和重试次数。
- 调用核心业务工作流。
- 显示最终状态和执行路径。
- 在失败时显示必要的 pytest 诊断输出。
- 根据状态返回正确的 CLI 退出码。

本文件不直接创建 LangGraph 节点，也不重新实现 pytest 执行。

### 4.2 创建与打开

首次创建：

```bash
touch src/ai_software_dev_agent/commands/conditional_workflow.py
```

打开：

```bash
nano src/ai_software_dev_agent/commands/conditional_workflow.py
```

### 4.3 完整最终代码

```python
"""Day 10：条件路由与错误恢复工作流的 CLI 命令。"""

import argparse
import sys
from typing import Any

from ai_software_dev_agent.commands._common import add_project_argument
from ai_software_dev_agent.conditional_workflow import (
    MAX_ALLOWED_RETRIES,
    run_conditional_workflow,
)


def run_conditional_workflow_command(
    args: argparse.Namespace,
) -> int:
    """运行条件工作流，并根据最终状态返回退出码。"""

    try:
        result = run_conditional_workflow(
            project=args.project,
            target=args.target,
            timeout_seconds=args.timeout,
            max_retries=args.max_retries,
        )

    except ValueError as exc:
        print(f"参数错误：{exc}", file=sys.stderr)
        return 2

    except KeyboardInterrupt:
        print("\n用户已中断工作流。", file=sys.stderr)
        return 130

    except Exception as exc:
        # CLI 边界允许统一报告异常，但不能把异常伪装成测试通过。
        print(
            f"条件工作流执行失败：{type(exc).__name__}：{exc}",
            file=sys.stderr,
        )
        return 1

    status = result["status"]
    completed_steps = result["completed_steps"]

    print("\n=== Day 10 条件工作流结果 ===")
    print(f"项目：{result['project']}")
    print(f"测试目标：{result['target']}")
    print(f"测试状态：{status}")
    print(f"已重试：{result['retry_count']} 次")
    print(f"执行路径：{' → '.join(completed_steps)}")
    print()
    print(result["summary"])

    # 发生失败时，提供有限长度的 pytest 输出辅助排查。
    test_result = result.get("test_result")

    if status != "passed" and test_result is not None:
        for stream_name in ("stdout", "stderr"):
            content = getattr(test_result, stream_name, "")

            if content:
                print(f"\n--- pytest {stream_name}（末尾 1500 字符）---")
                print(str(content)[-1500:])

    if status == "passed":
        return 0

    # 未通过、无测试、超时及错误都不能返回成功退出码。
    return 1


def register(subparsers: Any) -> None:
    """注册 conditional-workflow 子命令。"""

    parser = subparsers.add_parser(
        "conditional-workflow",
        help="执行带条件路由和有界超时重试的 pytest 工作流",
    )

    add_project_argument(parser)

    parser.add_argument(
        "--target",
        default="tests",
        help="pytest 测试目标，默认 tests",
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="每次 pytest 执行的超时时间（秒），默认 60",
    )

    parser.add_argument(
        "--max-retries",
        type=int,
        choices=range(MAX_ALLOWED_RETRIES + 1),
        default=0,
        help="超时后额外重试次数，可选 0、1、2，默认 0",
    )

    parser.set_defaults(handler=run_conditional_workflow_command)
```

### 4.4 代码讲解

**（1）CLI 为什么直接调用封装好的工作流？**

```python
result = run_conditional_workflow(...)
```

业务文件已经封装了：

- 参数校验。
- 初始 State 创建。
- Graph 构建。
- Graph 执行。

CLI 直接调用即可，避免重复代码。

**（2）`argparse` 的 `choices` 有什么用？**

```python
choices = range(MAX_ALLOWED_RETRIES + 1)
```

当允许的最大额外重试次数为 2 时：

```python
range(3)
```

允许：

```text
0、1、2
```

如果用户设置：

```bash
--max-retries 10
```

`argparse` 会提前拒绝。

业务函数中仍然保留重试范围校验，因为其他 Python 代码也可以绕过 CLI 直接调用该函数。

**（3）为什么 `except Exception` 可以出现在 CLI 最外层？**

业务层不应该随意隐藏未知异常。

但最外层 CLI 可以统一报告异常，并返回非零退出码。

例如：

```text
条件工作流执行失败：RuntimeError：……
```

这不表示错误已恢复，而是表示 CLI 将错误明确展示给使用者。

**（4）为什么要区分退出码？**

本次约定：

| 退出码 | 含义 |
|---|---|
| `0` | 测试通过 |
| `1` | 测试失败、超时、无测试或执行异常 |
| `2` | 参数错误 |
| `130` | 用户中断 |

例如：

```text
run_tests → summarize_failed → END
```

虽然 LangGraph 正常结束，但测试失败。

此时 CLI 不能返回 `0`，否则未来 CI 可能把失败任务误判为成功。

**（5）为什么只输出 pytest 日志尾部？**

```python
print(str(content)[-1500:])
```

限制终端输出长度，避免一次显示大量失败日志。

这里只是便于快速排查，不能替代完整的 pytest 日志。

### 4.5 注意事项

- 命令默认不额外重试。
- `--max-retries 2` 表示最多总共运行三次测试。
- 超时重试可能增加总执行时间。
- 当前只在工作流结束后输出执行路径，不是逐节点实时打印。
- 该命令不调用模型，也不自动修改代码。
- CLI 成功与否依据最终测试状态，而非仅依据 Graph 是否结束。

### 4.6 使用与验证

查看帮助：

```bash
ai-dev-agent conditional-workflow --help
```

默认执行：

```bash
ai-dev-agent conditional-workflow \
  --project . \
  --target tests
```

显式设置不重试：

```bash
ai-dev-agent conditional-workflow \
  --project . \
  --target tests/test_conditional_workflow.py \
  --timeout 60 \
  --max-retries 0
```

允许一次额外超时重试：

```bash
ai-dev-agent conditional-workflow \
  --project . \
  --target tests/test_conditional_workflow.py \
  --timeout 60 \
  --max-retries 1
```

最后这个命令只是在真正超时时才会重试，不代表每次都运行两遍。

本日真实 CLI 验收已由开发者确认通过。

对应自动化测试位于第 6 节。

---

## 5. 文件四：`src/ai_software_dev_agent/cli.py`

### 5.1 文件职责

这是项目已有的统一 CLI 入口。

Day 10 只需要增加新命令的导入和注册，不需要修改其他命令的业务逻辑。

### 5.2 打开文件

```bash
nano src/ai_software_dev_agent/cli.py
```

该文件早已存在，不要重新创建，也不要删除之前的子命令。

### 5.3 完整最终代码

```python
"""AI 软件开发智能体统一命令行入口。"""

import argparse

from ai_software_dev_agent import __version__
from ai_software_dev_agent.commands import (
    agent_workflow,
    ask,
    chat,
    conditional_workflow,
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
    workflow.register(subparsers)
    agent_workflow.register(subparsers)

    # Day 10：条件路由与有界错误恢复工作流。
    conditional_workflow.register(subparsers)

    return parser


def main(argv: list[str] | None = None) -> int:
    """解析参数并分发给对应命令。"""

    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return args.handler(args)

    except (ModelConfigError, RepositoryError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
```

### 5.4 代码讲解

新增导入：

```python
from ai_software_dev_agent.commands import conditional_workflow
```

实际在完整代码中统一放在 `commands` 的导入列表。

新增注册：

```python
conditional_workflow.register(subparsers)
```

这样命令分发仍然由：

```python
return args.handler(args)
```

统一处理。

这是前面 CLI 模块化重构带来的直接好处：新增命令时，不需要不断扩充顶层的 `if/elif` 逻辑。

### 5.5 注意事项

`cli.py` 只应该管理统一命令入口。

不要把：

- LangGraph 构建。
- pytest 执行。
- 超时重试。
- 分支判断。
- 状态总结。

直接写进该文件。

这些逻辑分别属于对应的业务模块和命令模块。

### 5.6 验证

```bash
ai-dev-agent --help

ai-dev-agent conditional-workflow --help
```

确认能够找到 `conditional-workflow` 子命令，以及：

```text
--project
--target
--timeout
--max-retries
```

---

## 6. 文件五：`tests/cli/test_conditional_workflow.py`

### 6.1 文件职责

专门测试 CLI 的外部行为，包括：

- 参数是否正确传入业务工作流。
- 测试通过时是否返回 `0`。
- 其他状态是否返回非零退出码。
- 非法重试次数是否被拒绝。
- 空测试目标是否返回参数错误。
- 未知异常是否被正确报告。
- 帮助信息是否包含新参数和命令。

这里不重复测试 LangGraph 的内部路由。

### 6.2 创建与打开

首次创建：

```bash
mkdir -p tests/cli

touch tests/cli/test_conditional_workflow.py
```

打开：

```bash
nano tests/cli/test_conditional_workflow.py
```

### 6.3 完整最终代码

```python
"""Day 10：conditional-workflow CLI 命令测试。"""

from pathlib import Path

import pytest

from ai_software_dev_agent import cli
from ai_software_dev_agent.commands import (
    conditional_workflow as command,
)


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    """创建测试用项目目录。"""

    (tmp_path / "demo.py").write_text(
        "print('hello')\n",
        encoding="utf-8",
    )

    return tmp_path


def test_cli_passes_arguments(
    sample_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """验证 CLI 将参数完整传给工作流。"""

    observed: dict[str, object] = {}

    def fake_run(
        project: Path,
        target: str,
        timeout_seconds: int,
        max_retries: int,
    ) -> dict:
        observed.update(
            {
                "project": project,
                "target": target,
                "timeout_seconds": timeout_seconds,
                "max_retries": max_retries,
            }
        )

        return {
            "project": str(project),
            "target": target,
            "status": "passed",
            "retry_count": 1,
            "completed_steps": [
                "inspect_repository",
                "run_tests",
                "retry_tests",
                "run_tests",
                "summarize_passed",
            ],
            "summary": "重试后测试通过",
        }

    monkeypatch.setattr(
        command,
        "run_conditional_workflow",
        fake_run,
    )

    result = cli.main(
        [
            "conditional-workflow",
            "--project",
            str(sample_project),
            "--target",
            "tests/test_demo.py",
            "--timeout",
            "30",
            "--max-retries",
            "1",
        ]
    )

    output = capsys.readouterr().out

    assert result == 0
    assert observed["project"] == sample_project.resolve()
    assert observed["target"] == "tests/test_demo.py"
    assert observed["timeout_seconds"] == 30
    assert observed["max_retries"] == 1

    assert "测试状态：passed" in output
    assert "已重试：1 次" in output
    assert "重试后测试通过" in output


@pytest.mark.parametrize(
    "status",
    ["failed", "no_tests", "timeout", "error"],
)
def test_cli_non_success_status_returns_failure(
    sample_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    status: str,
) -> None:
    """非 passed 状态都必须返回非零退出码。"""

    def fake_run(
        project: Path,
        target: str,
        timeout_seconds: int,
        max_retries: int,
    ) -> dict:
        return {
            "project": str(project),
            "target": target,
            "status": status,
            "retry_count": 0,
            "completed_steps": [
                "inspect_repository",
                "run_tests",
                "summarize_error",
            ],
            "summary": "模拟工作流未成功",
        }

    monkeypatch.setattr(
        command,
        "run_conditional_workflow",
        fake_run,
    )

    result = cli.main(
        [
            "conditional-workflow",
            "--project",
            str(sample_project),
        ]
    )

    output = capsys.readouterr().out

    assert result == 1
    assert f"测试状态：{status}" in output


def test_cli_rejects_invalid_retry_choice() -> None:
    """超过允许范围的 CLI 参数应被 argparse 拒绝。"""

    with pytest.raises(SystemExit) as exc_info:
        cli.main(
            [
                "conditional-workflow",
                "--max-retries",
                "10",
            ]
        )

    assert exc_info.value.code == 2


def test_cli_reports_invalid_input(
    sample_project: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """无效测试目标应返回参数错误退出码。"""

    result = cli.main(
        [
            "conditional-workflow",
            "--project",
            str(sample_project),
            "--target",
            "   ",
        ]
    )

    captured = capsys.readouterr()

    assert result == 2
    assert "测试目标不能为空" in captured.err


def test_cli_reports_unexpected_error(
    sample_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """未知程序错误不能被误报为成功。"""

    def fake_run(**kwargs: object) -> None:
        raise RuntimeError("模拟未知程序错误")

    monkeypatch.setattr(
        command,
        "run_conditional_workflow",
        fake_run,
    )

    result = cli.main(
        [
            "conditional-workflow",
            "--project",
            str(sample_project),
        ]
    )

    captured = capsys.readouterr()

    assert result == 1
    assert "RuntimeError" in captured.err
    assert "模拟未知程序错误" in captured.err


def test_cli_help(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """验证新子命令帮助信息。"""

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["conditional-workflow", "--help"])

    assert exc_info.value.code == 0

    output = capsys.readouterr().out

    assert "--project" in output
    assert "--target" in output
    assert "--timeout" in output
    assert "--max-retries" in output


def test_top_level_help_contains_command(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """顶层帮助应包含 conditional-workflow。"""

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--help"])

    assert exc_info.value.code == 0
    assert "conditional-workflow" in capsys.readouterr().out
```

### 6.4 代码讲解

**（1）为什么要 Mock 业务工作流？**

```python
monkeypatch.setattr(
    command,
    "run_conditional_workflow",
    fake_run,
)
```

CLI 测试主要检查参数传递和返回行为。

没必要为了验证 `--timeout 30` 是否正确传递，就真的启动一次 pytest。

真实 LangGraph 的分支逻辑已经在 `tests/test_conditional_workflow.py` 中单独验证。

**（2）为什么记录 `observed`？**

```python
observed: dict[str, object] = {}
```

模拟函数将收到的参数保存起来：

```python
observed.update({
    "project": project,
    "target": target,
    ...
})
```

随后测试验证：

```python
assert observed["timeout_seconds"] == 30
```

这能明确检查 CLI 到业务函数之间的数据传递。

**（3）为什么要检查所有非成功状态？**

```python
@pytest.mark.parametrize(
    "status",
    ["failed", "no_tests", "timeout", "error"],
)
```

因为正常结束工作流，并不一定代表测试通过。

这些状态的退出码都应该是 `1`，避免后续自动化系统误判。

**（4）为什么验证 CLI 帮助？**

```python
cli.main(["conditional-workflow", "--help"])
```

可以确认：

- 子命令已经注册。
- 参数名称正确。
- `argparse` 没有配置错误。

### 6.5 注意事项与验证

这类测试不调用真实模型，也不执行真实 pytest。

它们的价值是保证 CLI 的接口行为稳定。

如果未来业务函数增加新参数，需要同步更新这里的 Fake 函数签名和 Mock 返回值，避免出现 Day 09 曾经遇到的 Mock Contract（模拟对象接口契约）不一致问题。

单文件测试：

```bash
python -m pytest tests/cli/test_conditional_workflow.py -v
```

本日开发者已经确认阶段二 CLI 测试通过。

---

## 7. 今日 Debug 与真实验证记录

### 7.1 Debug 01：PytestCollectionWarning

第一阶段执行：

```bash
python -m pytest tests/test_conditional_workflow.py -v
```

得到：

```text
12 passed, 1 warning in 0.22s
```

Warning：

```text
PytestCollectionWarning:
cannot collect test class 'TestRunnerError'
because it has a __init__ constructor
```

问题定位到测试文件中的导入：

```python
from ai_software_dev_agent.test_runner import TestRunnerError
```

由于类名以 `Test` 开头，pytest 尝试将其识别为测试类。

但它实际上是一个继承自 `ValueError` 的业务异常类。

**解决方法：**

```python
from ai_software_dev_agent.test_runner import (
    TestRunnerError as RunnerExecutionError,
)
```

并同步修改测试内引用：

```python
raise RunnerExecutionError("测试目标无效")
```

这样不影响业务异常类的真实行为，也不需要修改 `test_runner.py`。

**经验：**

测试文件中导入名称以 `Test` 开头的业务类时，要注意 pytest 的自动收集规则。

### 7.2 Debug 02：错误类型不能一概重试

Day 10 设计时，需要区分以下状态：

```text
passed
failed
no_tests
timeout
error
```

我们没有采用：

```text
只要失败 → 再运行一次
```

因为不同错误对应不同原因。

例如：

- `failed`：代码断言失败，需要定位问题。
- `no_tests`：测试配置可能不正确，需要检查路径和收集规则。
- `error`：执行过程存在问题，应报告错误。
- `timeout`：可能是临时问题，也可能是程序卡住。

最终采用保守策略：

```python
if status == "timeout" and retry_count < max_retries:
    return "retry_tests"
```

只对用户明确允许的超时情况进行有限重试。

### 7.3 Debug 03：重试预算必须有明确的终止条件

如果工作流写成：

```text
run_tests
   ↓
timeout
   ↓
run_tests
```

但没有重试计数，就可能出现无限重复执行。

本日增加：

```python
max_retries
retry_count
```

以及：

```python
MAX_ALLOWED_RETRIES = 2
```

实际最多执行：

```text
1 次初始测试 + 2 次额外重试 = 3 次测试
```

并增加自动化测试：

```python
test_timeout_stops_when_budget_exhausted()
```

验证持续超时也能正常结束。

### 7.4 Debug 04：业务执行完成不等于测试成功

例如：

```text
run_tests → summarize_failed → END
```

外层 LangGraph 正常结束。

但最终测试状态：

```text
failed
```

所以 CLI 应返回：

```text
exit code = 1
```

而不是 `0`。

最终通过：

```python
if status == "passed":
    return 0

return 1
```

明确区分工作流完成与业务成功。

### 7.5 第二阶段真实验收

本日完成后执行了：

```bash
python -m pytest \
  tests/test_conditional_workflow.py \
  tests/cli/test_conditional_workflow.py \
  -v
```

以及：

```bash
ai-dev-agent conditional-workflow --help
```

真实仓库执行：

```bash
ai-dev-agent conditional-workflow \
  --project . \
  --target tests/test_conditional_workflow.py \
  --timeout 60 \
  --max-retries 0
```

上述阶段二验收已由开发者确认全部通过。

目前未提供完整终端统计，因此不在文档中编造实际测试总数、耗时或输出内容。

### 7.6 与 Day 09 调试的联系

Day 09 曾经因为 Agent 不断调用文件工具而遇到：

```text
GraphRecursionError
```

Day 10 进一步体现了相同的工程原则：

**工作流中的循环必须有明确的预算、状态更新和终止条件。**

区别在于：

- Day 09 的问题来自内层 Agent 不断探索文件。
- Day 10 的循环是我们主动设计的重试机制。
- Day 10 通过 `retry_count` 和 `max_retries` 明确控制循环。

因此，循环本身不是问题，**不受控制的循环才是问题**。

---

## 8. 最终总结与下一步

### 8.1 今日完成的功能

本日已经实现：

- LangGraph 条件边。
- 基于 State 的分支判断。
- 仓库检查异常分流。
- pytest 五种测试状态分流。
- 有界超时重试。
- 重试次数统计。
- 失败与错误的独立总结。
- CLI 命令集成。
- CLI 退出码处理。
- 自动化回归测试。
- PytestCollectionWarning 修复。

### 8.2 今天最重要的 Python 与 LangGraph 知识

| 知识点 | 本日应用 |
|---|---|
| `TypedDict` | 定义共享 State |
| `NotRequired` | 定义执行中产生的可选状态字段 |
| `Annotated` | 声明状态更新方式 |
| `operator.add` | 追加已执行节点列表 |
| `Literal` | 标记预期状态及路由名称 |
| `add_conditional_edges()` | 实现条件分支 |
| `add_edge()` | 实现固定连接和重试回路 |
| `nonlocal` | 测试中统计模拟调用次数 |
| `pytest.mark.parametrize` | 多状态参数化测试 |
| `monkeypatch` | 替换依赖并隔离业务 |
| `argparse` | CLI 参数解析与范围约束 |

### 8.3 需要记住的核心区别

**Node 与 Router**

Node 执行具体业务，Router 决定下一步去哪里。

**普通边与条件边**

普通边表示固定执行路径，条件边根据 State 选择路径。

**业务错误与程序异常**

已知且能够分类的错误可以写入 State；未知程序异常不应该被悄悄隐藏。

**失败与重试**

失败不一定值得重试，重试必须有合理条件与预算。

**工作流结束与业务成功**

走到 `END` 只说明工作流结束，不保证测试通过。

### 8.4 当前方案仍有哪些局限？

本日的 Error Recovery 是基础版本，仍有以下限制：

- 只针对 `timeout` 状态设计了自动重试。
- 没有实现指数退避（Exponential Backoff）。
- 没有实现错误恢复的持久化。
- 工作流中断后不能自动恢复之前的 State。
- 当前没有跨进程保存重试次数。
- 没有实现复杂任务的多步骤补救计划。
- 没有自动修复失败的代码。
- 没有与 Day 09 的分析 Agent 合并为统一自主开发流程。

这些不是 Day 10 未完成的必要功能，而是后续继续学习的内容。

### 8.5 Day 10 学习结论

Day 10 让我们从固定执行顺序，进入了根据状态进行决策的工作流设计。

之前：

```text
A → B → C
```

今天：

```text
A
↓
判断
├── B
├── C
└── D → 重试 → 再次判断
```

更重要的是理解：

**一个可靠的软件开发 Agent，不仅要知道成功时做什么，还应该明确失败时走哪条路径、哪些错误值得恢复、什么时候必须停止。**

这也是从简单 Agent 向实际工程系统演进的重要一步。

**Day 10 完成。**

下一学习日：

**Day 11｜Checkpoint & Session Persistence（检查点与会话持久化）**

继续按原定 18 天学习路线进行。