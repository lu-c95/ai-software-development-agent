# Day 12｜Human-in-the-Loop（人工审批）

**项目：AI Software Development Agent**

**学习日期：2026-11-15**

**学习主题：LangGraph 中断、人工审批与工作流恢复**

**学习状态：三个阶段已完成，自动化测试与真实 CLI 验收通过**

---

## 1. 今日学习目标

### 1.1 为什么需要 Human-in-the-Loop？

前面的学习中，我们已经实现了：

- Day 05：工具 Agent 与多轮 CLI 对话。
- Day 08：LangGraph 基础工作流。
- Day 10：条件路由与错误恢复。
- Day 11：SQLite Checkpoint 与会话持久化。

但是，当 AI Agent 具备修改文件的能力后，就会产生一个新问题：

**模型认为某项操作正确，不代表应该立即执行。**

例如，AI 希望修改项目中的 `config.py`：

```python
DEBUG = True
```

改成：

```python
DEBUG = False
```

如果没有审批机制，Agent 可能直接完成修改。

但实际工程开发需要先让人确认：

1. 修改的是哪个项目？
2. 修改的是哪个文件？
3. 修改前后的代码有什么区别？
4. 是否会覆盖其他人的新修改？
5. 用户是否真的同意执行？

因此需要 Human-in-the-Loop，简称 **HITL（人在回路中／人工介入）**。

本日主要学习的是 **Human Approval（人工审批）**，即在敏感操作前暂停工作流，等待用户决定。

### 1.2 今日的三个开发阶段

**第一阶段：新建文件审批**

实现：

```text
准备新文件
    ↓
生成 Diff
    ↓
interrupt() 暂停
    ↓
人工批准 / 拒绝
    ↓
创建文件 / 不执行写入
```

**第二阶段：已有文件修改审批**

复用之前开发的 CodeEditor：

```text
preview_replace()
    ↓
生成 Diff + 保存原文件 SHA-256
    ↓
interrupt() 暂停
    ↓
人工批准 / 拒绝
    ↓
重新检查文件
    ↓
apply() / 不执行写入
```

**第三阶段：CLI 审批与跨进程恢复**

增加：

```bash
ai-dev-agent edit-approval prepare
```

和：

```bash
ai-dev-agent edit-approval review
```

实现：

```text
终端进程 A
    ↓
准备文件修改
    ↓
保存 Checkpoint
    ↓
进程退出

终端进程 B
    ↓
恢复 Checkpoint
    ↓
显示待审批 Diff
    ↓
人工输入 yes/no
    ↓
批准后修改，拒绝则不修改
```

### 1.3 今日最终文件结构

```text
ai-software-development-agent/
│
├── src/
│   └── ai_software_dev_agent/
│       ├── approval_workflow.py
│       ├── edit_approval_workflow.py
│       ├── editor.py                 # 原有文件，不修改
│       ├── cli.py                    # 只增加注册
│       └── commands/
│           └── edit_approval.py
│
├── tests/
│   ├── test_approval_workflow.py
│   ├── test_edit_approval_workflow.py
│   ├── test_editor.py                # 原有测试
│   └── cli/
│       └── test_edit_approval.py
│
└── docs/
    └── Day12-Human-in-the-Loop-Approval.md
```

本日新建：

- `approval_workflow.py`
- `test_approval_workflow.py`
- `edit_approval_workflow.py`
- `test_edit_approval_workflow.py`
- `commands/edit_approval.py`
- `tests/cli/test_edit_approval.py`

修改：

- `cli.py`：只增加新命令注册。

不修改：

- 原有 `editor.py`。
- 原有 `chat.py`。
- Day 11 的持久化聊天实现。
- 原有工具 Agent。

这样设计，是为了避免重演 Day 11 曾经发生的旧接口兼容性问题。

---

## 2. 核心知识：LangGraph 人工审批机制

### 2.1 `interrupt()`：暂停工作流

普通 Python 函数通常会直接运行到结束：

```python
def process():
    prepare()
    execute()
    return "done"
```

但人工审批可能需要用户过几分钟、几小时甚至过几天才作出决定。

不能让 Agent 直接执行，也不应该一直占用一个正在等待输入的模型调用。

LangGraph 提供：

```python
from langgraph.types import interrupt
```

在节点内：

```python
decision = interrupt(
    {
        "question": "是否批准？",
        "diff": "...",
    }
)
```

第一次执行到这里时，图会暂停，并将待审批内容交给调用方。

### 2.2 `Command(resume=...)`：恢复工作流

人工作出决定后：

```python
from langgraph.types import Command

result = graph.invoke(
    Command(resume=True),
    config=config,
)
```

表示批准。

或者：

```python
result = graph.invoke(
    Command(resume=False),
    config=config,
)
```

表示拒绝。

恢复时，原来被 `interrupt()` 暂停的节点会获得对应的决定。

**重要：被中断的节点恢复时会从节点开头重新执行。**

所以不能把实际写入操作放在 `interrupt()` 之前。

错误示例：

```python
def approval_node(state):
    write_file()  # 错误：审批前已经写入

    approved = interrupt("是否批准？")
```

正确设计：

```text
request_approval
      ↓
人工决定
      ↓
条件路由
      ↓
apply_change
```

实际修改放在独立的后续节点。

### 2.3 Checkpoint：保存暂停状态

如果图没有 Checkpointer，程序关闭后很难可靠地恢复暂停中的执行。

Day 11 已经实现 SQLite Checkpoint。

Day 12 继续使用：

```python
with SqliteSaver.from_conn_string(str(db_path)) as saver:
    graph = build_approval_graph(saver)
```

在编译图时：

```python
graph.compile(checkpointer=saver)
```

从而把工作流状态与执行位置保存下来。

### 2.4 `thread_id`：识别待审批任务

Day 11 中，`thread_id` 用来识别聊天会话。

Day 12 中，它也可以标识一条独立的审批任务：

```text
approval-task-a
approval-task-b
```

每条任务保存自己的：

- 待修改文件。
- 原始文本。
- 新文本。
- Diff。
- 审批状态。
- 工作流执行位置。

因此批准任务 A，不应自动批准任务 B。

### 2.5 条件路由

人工审批结果通常分为两条路径：

```python
if state["approved"]:
    return "apply_edit"

return "reject_edit"
```

再由：

```python
builder.add_conditional_edges(...)
```

根据状态选择执行节点。

这与 Day 10 学过的 Conditional Routing（条件路由）是一致的。

区别是：Day 10 主要根据测试状态路由；Day 12 根据人工审批决定路由。

---

# 第一阶段｜新建文件的人工审批

## 3. 文件一：`src/ai_software_dev_agent/approval_workflow.py`

### 3.1 文件职责

实现一个独立的新建文件审批工作流。

本阶段限制操作范围：**只能创建新文件，不能覆盖已有文件。**

工作流包含：

1. `prepare_change`
2. `request_approval`
3. `create_file`
4. `reject_change`

### 3.2 创建与打开

首次创建：

```bash
touch src/ai_software_dev_agent/approval_workflow.py
```

打开：

```bash
nano src/ai_software_dev_agent/approval_workflow.py
```

### 3.3 完整代码

```python
"""Day 12：LangGraph 人工审批与安全文件创建工作流。"""

from difflib import unified_diff
from pathlib import Path
from typing import Literal, NotRequired, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command, interrupt


ApprovalStatus = Literal[
    "pending",
    "approved",
    "created",
    "rejected",
    "conflict",
    "error",
]


class ApprovalState(TypedDict):
    """人工审批工作流的共享状态。"""

    project: str
    relative_path: str
    proposed_content: str

    diff: NotRequired[str]
    approved: NotRequired[bool]
    status: NotRequired[ApprovalStatus]
    summary: NotRequired[str]


def resolve_target(state: ApprovalState) -> Path:
    """校验项目与目标路径，禁止越出仓库。"""

    root = Path(state["project"]).expanduser().resolve()

    if not root.is_dir():
        raise ValueError(f"项目目录不存在：{root}")

    relative_text = state["relative_path"].strip()
    relative = Path(relative_text)

    if (
        not relative_text
        or relative == Path(".")
        or relative.is_absolute()
        or ".." in relative.parts
    ):
        raise ValueError("目标路径必须是仓库内的合法相对路径")

    target = (root / relative).resolve()

    # 防止目录穿越，也防止路径通过符号链接指向仓库外。
    if not target.is_relative_to(root) or target == root:
        raise ValueError("目标路径超出项目根目录")

    return target


def prepare_change_node(
    state: ApprovalState,
) -> dict[str, str]:
    """准备变更与 Diff，此阶段绝不写文件。"""

    target = resolve_target(state)

    content = state["proposed_content"]

    if not content.strip():
        raise ValueError("拟创建的文件内容不能为空")

    if target.exists() or target.is_symlink():
        raise FileExistsError(f"目标文件已存在：{target}")

    diff_lines = unified_diff(
        [],
        content.splitlines(keepends=True),
        fromfile="/dev/null",
        tofile=f"b/{state['relative_path']}",
        lineterm="\n",
    )

    return {
        "diff": "".join(diff_lines),
        "status": "pending",
    }


def request_approval_node(
    state: ApprovalState,
) -> dict[str, object]:
    """暂停图，等待外部人工明确批准或拒绝。"""

    # interrupt 前不能进行文件写入等有副作用操作。
    decision = interrupt(
        {
            "operation": "create_file",
            "relative_path": state["relative_path"],
            "diff": state["diff"],
            "question": "是否批准创建该文件？",
        }
    )

    # 严格要求布尔 True。字符串 "yes" 不等于批准。
    approved = decision is True

    return {
        "approved": approved,
        "status": "approved" if approved else "rejected",
    }


def route_after_approval(
    state: ApprovalState,
) -> Literal["create_file", "reject_change"]:
    """根据人工决定选择执行分支。"""

    if state["approved"]:
        return "create_file"

    return "reject_change"


def create_file_node(
    state: ApprovalState,
) -> dict[str, object]:
    """仅在批准之后创建新文件，拒绝覆盖旧文件。"""

    # 恢复执行时再次校验路径，防止审批期间路径发生变化。
    target = resolve_target(state)

    try:
        target.parent.mkdir(parents=True, exist_ok=True)

        # x 模式：独占创建，目标已存在就失败，不会覆盖。
        with target.open("x", encoding="utf-8") as file:
            file.write(state["proposed_content"])

    except FileExistsError:
        return {
            "status": "conflict",
            "summary": f"目标文件已经存在，未执行覆盖：{target}",
        }

    except OSError as exc:
        return {
            "status": "error",
            "summary": f"创建文件失败：{exc}",
        }

    return {
        "status": "created",
        "summary": f"人工已批准，文件创建成功：{target}",
    }


def reject_change_node(
    state: ApprovalState,
) -> dict[str, str]:
    """用户拒绝后直接结束，不创建文件。"""

    return {
        "status": "rejected",
        "summary": "人工已拒绝本次文件创建，未执行写入。",
    }


def build_approval_graph(
    checkpointer: BaseCheckpointSaver,
) -> CompiledStateGraph:
    """构建带持久化检查点的审批工作流。"""

    builder = StateGraph(ApprovalState)

    builder.add_node("prepare_change", prepare_change_node)
    builder.add_node("request_approval", request_approval_node)
    builder.add_node("create_file", create_file_node)
    builder.add_node("reject_change", reject_change_node)

    builder.add_edge(START, "prepare_change")
    builder.add_edge("prepare_change", "request_approval")

    builder.add_conditional_edges(
        "request_approval",
        route_after_approval,
        {
            "create_file": "create_file",
            "reject_change": "reject_change",
        },
    )

    builder.add_edge("create_file", END)
    builder.add_edge("reject_change", END)

    return builder.compile(checkpointer=checkpointer)


def make_approval_config(thread_id: str) -> dict[str, object]:
    """使用线程 ID 定位审批状态。"""

    clean_id = thread_id.strip()

    if not clean_id:
        raise ValueError("审批线程 ID 不能为空")

    return {
        "configurable": {
            "thread_id": clean_id,
        }
    }


def start_approval(
    graph: CompiledStateGraph,
    project: Path,
    relative_path: str,
    proposed_content: str,
    thread_id: str,
) -> dict:
    """发起审批，运行到 interrupt 并返回审批请求。"""

    config = make_approval_config(thread_id)

    # 不允许在已有审批线程中覆盖之前的状态。
    snapshot = graph.get_state(config)

    if snapshot.values:
        raise ValueError("审批线程已存在，请使用新的 thread_id")

    initial_state: ApprovalState = {
        "project": str(project.expanduser().resolve()),
        "relative_path": relative_path,
        "proposed_content": proposed_content,
    }

    return graph.invoke(initial_state, config=config)


def resume_approval(
    graph: CompiledStateGraph,
    thread_id: str,
    approved: bool,
) -> dict:
    """使用原线程恢复已暂停的审批工作流。"""

    if not isinstance(approved, bool):
        raise ValueError("审批决定必须是布尔值")

    config = make_approval_config(thread_id)

    snapshot = graph.get_state(config)

    # 已完成或不存在的线程，不能被当作待审批任务恢复。
    if snapshot.next != ("request_approval",):
        raise ValueError("当前线程没有等待处理的审批")

    return graph.invoke(
        Command(resume=approved),
        config=config,
    )
```

### 3.4 代码讲解

**（1）`ApprovalState` 的作用**

```python
class ApprovalState(TypedDict):
```

定义工作流不同节点共享的数据。

其中：

```python
project: str
relative_path: str
proposed_content: str
```

是发起请求时就必须提供的信息。

而：

```python
diff: NotRequired[str]
approved: NotRequired[bool]
status: NotRequired[ApprovalStatus]
```

是在工作流运行过程中逐步生成的。

`NotRequired` 表示 TypedDict 中对应的键可以暂时不存在。

这里需要注意：它不代表对应字段可以随意取值，而是描述键是否必须存在。

**（2）`resolve_target()` 的作用**

```python
root = Path(state["project"]).expanduser().resolve()
```

先把仓库根目录规范化。

```python
target = (root / relative).resolve()
```

再解析目标路径。

```python
target.is_relative_to(root)
```

检查目标是否仍然位于仓库内部。

它还显式禁止：

```text
../outside.py
```

这种路径穿越写法。

这是项目文件操作的基础防护，但不是完整的操作系统级沙箱。

**（3）`unified_diff()` 的作用**

```python
from difflib import unified_diff
```

这是 Python 标准库提供的差异生成工具。

创建新文件时，旧文件内容为空：

```python
[]
```

新内容为：

```python
content.splitlines(keepends=True)
```

最后生成类似：

```diff
--- /dev/null
+++ b/demo.py
@@ -0,0 +1 @@
+value = 123
```

这个 Diff 用于让用户明确知道即将创建什么。

**（4）`interrupt()` 为什么返回审批决定？**

第一次执行时：

```python
decision = interrupt({...})
```

会暂停并返回待审批信息。

之后使用：

```python
Command(resume=True)
```

恢复时，`interrupt()` 会得到布尔 `True`，然后节点继续执行后面的判断。

**（5）为什么使用 `decision is True`？**

因为：

```python
bool("no")
```

结果也是 `True`。

如果把任意非空字符串当成批准，就可能产生严重误操作。

因此我们只接受明确的布尔批准。

**（6）为什么使用 `open("x")`？**

```python
with target.open("x", encoding="utf-8") as file:
```

`x` 是 Exclusive Creation（独占创建）模式。

如果文件已存在，Python 会抛出 `FileExistsError`，而不是覆盖文件。

它与：

```python
open("w")
```

有本质区别。

**（7）为什么批准后还要检查一次路径？**

人工查看 Diff 和实际批准之间可能相隔一段时间。

期间文件系统可能发生变化。

所以写入节点再次调用：

```python
resolve_target(state)
```

而不是完全信任准备阶段的路径结果。

### 3.5 注意事项

本阶段只实现创建新文件，不覆盖已有文件。

当前设计仍有一些局限：

- 未实现完整的原子写入和失败回滚。
- 未实现多个本地进程间的严格并发保护。
- 未实现审批者身份认证。
- 尚不能防御所有文件系统竞态条件。
- Checkpoint 可能存储完整拟创建文件内容。

因此它是学习和本地原型开发方案，不应直接作为高权限生产环境中的安全隔离机制。

### 3.6 对应验证

```bash
python -m pytest tests/test_approval_workflow.py -v
```

实际验证已通过。

---

## 4. 文件二：`tests/test_approval_workflow.py`

### 4.1 文件职责

验证第一阶段最关键的安全规则：

**未批准之前绝不写入，拒绝之后仍不写入，批准之后才允许执行。**

同时测试：

- 非法路径。
- 已存在的文件。
- 等待审批期间的文件冲突。
- 不同线程隔离。
- 已完成任务不能重复恢复。
- SQLite 重新打开后的状态恢复。

### 4.2 创建与打开

```bash
touch tests/test_approval_workflow.py

nano tests/test_approval_workflow.py
```

### 4.3 完整代码

```python
"""Day 12：人工审批、中断恢复和文件安全测试。"""

from pathlib import Path

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph.state import CompiledStateGraph

from ai_software_dev_agent.approval_workflow import (
    build_approval_graph,
    make_approval_config,
    resume_approval,
    start_approval,
)


@pytest.fixture
def graph() -> CompiledStateGraph:
    """使用内存 Checkpointer 构建独立测试图。"""

    return build_approval_graph(InMemorySaver())


def test_first_invoke_interrupts_without_writing(
    graph: CompiledStateGraph,
    tmp_path: Path,
) -> None:
    """发起审批后应暂停，文件不能提前出现。"""

    target = tmp_path / "demo.py"

    result = start_approval(
        graph,
        project=tmp_path,
        relative_path="demo.py",
        proposed_content="value = 123\n",
        thread_id="first-request",
    )

    assert "__interrupt__" in result
    assert not target.exists()

    approval_request = result["__interrupt__"][0].value

    assert approval_request["operation"] == "create_file"
    assert approval_request["relative_path"] == "demo.py"
    assert "value = 123" in approval_request["diff"]

    snapshot = graph.get_state(make_approval_config("first-request"))

    assert snapshot.values["status"] == "pending"
    assert snapshot.next == ("request_approval",)


def test_approved_request_creates_file(
    graph: CompiledStateGraph,
    tmp_path: Path,
) -> None:
    """明确批准后，才能创建目标文件。"""

    target = tmp_path / "demo.py"
    content = "def hello():\n    return 'hello'\n"

    start_approval(
        graph,
        tmp_path,
        "demo.py",
        content,
        "approved-request",
    )

    assert not target.exists()

    result = resume_approval(
        graph,
        "approved-request",
        approved=True,
    )

    assert result["approved"] is True
    assert result["status"] == "created"
    assert target.read_text(encoding="utf-8") == content


def test_rejected_request_never_writes(
    graph: CompiledStateGraph,
    tmp_path: Path,
) -> None:
    """人工拒绝后，必须直接结束且没有写入。"""

    target = tmp_path / "rejected.py"

    start_approval(
        graph,
        tmp_path,
        "rejected.py",
        "value = 999\n",
        "rejected-request",
    )

    result = resume_approval(
        graph,
        "rejected-request",
        approved=False,
    )

    assert result["approved"] is False
    assert result["status"] == "rejected"
    assert "未执行写入" in result["summary"]
    assert not target.exists()


def test_non_boolean_approval_is_rejected(
    graph: CompiledStateGraph,
    tmp_path: Path,
) -> None:
    """不能把字符串 yes、no 误当作布尔批准。"""

    target = tmp_path / "demo.py"

    start_approval(
        graph,
        tmp_path,
        "demo.py",
        "value = 1\n",
        "invalid-decision",
    )

    with pytest.raises(
        ValueError,
        match="审批决定必须是布尔值",
    ):
        resume_approval(
            graph,
            "invalid-decision",
            approved="yes",  # type: ignore[arg-type]
        )

    assert not target.exists()


def test_existing_file_cannot_be_overwritten(
    graph: CompiledStateGraph,
    tmp_path: Path,
) -> None:
    """已存在的文件不能进入创建审批流程。"""

    target = tmp_path / "important.py"
    target.write_text("original = True\n", encoding="utf-8")

    with pytest.raises(FileExistsError):
        start_approval(
            graph,
            tmp_path,
            "important.py",
            "original = False\n",
            "existing-file",
        )

    assert target.read_text(encoding="utf-8") == "original = True\n"


def test_path_traversal_is_rejected(
    graph: CompiledStateGraph,
    tmp_path: Path,
) -> None:
    """不能通过 ../ 路径访问项目外部文件。"""

    with pytest.raises(
        ValueError,
        match="合法相对路径",
    ):
        start_approval(
            graph,
            tmp_path,
            "../outside.py",
            "value = 1\n",
            "invalid-path",
        )

    assert not (tmp_path.parent / "outside.py").exists()


def test_file_appearing_during_review_is_not_overwritten(
    graph: CompiledStateGraph,
    tmp_path: Path,
) -> None:
    """审批等待期间目标出现，恢复后不能覆盖。"""

    target = tmp_path / "demo.py"

    start_approval(
        graph,
        tmp_path,
        "demo.py",
        "new_content = True\n",
        "conflict-request",
    )

    target.write_text("existing = True\n", encoding="utf-8")

    result = resume_approval(
        graph,
        "conflict-request",
        approved=True,
    )

    assert result["status"] == "conflict"
    assert target.read_text(encoding="utf-8") == "existing = True\n"


def test_nested_directories_created_only_after_approval(
    graph: CompiledStateGraph,
    tmp_path: Path,
) -> None:
    """等待审批时连目标子目录都不应该提前创建。"""

    target = tmp_path / "notes" / "day12" / "demo.py"

    start_approval(
        graph,
        tmp_path,
        "notes/day12/demo.py",
        "print('hello')\n",
        "nested-request",
    )

    assert not target.parent.exists()

    result = resume_approval(
        graph,
        "nested-request",
        approved=True,
    )

    assert result["status"] == "created"
    assert target.is_file()


def test_completed_request_cannot_resume_again(
    graph: CompiledStateGraph,
    tmp_path: Path,
) -> None:
    """已完成的审批不能被重复执行。"""

    start_approval(
        graph,
        tmp_path,
        "demo.py",
        "value = 1\n",
        "completed-request",
    )

    resume_approval(
        graph,
        "completed-request",
        approved=True,
    )

    with pytest.raises(
        ValueError,
        match="没有等待处理的审批",
    ):
        resume_approval(
            graph,
            "completed-request",
            approved=True,
        )


def test_same_thread_cannot_start_another_request(
    graph: CompiledStateGraph,
    tmp_path: Path,
) -> None:
    """同一个审批线程不能被新请求直接覆盖。"""

    start_approval(
        graph,
        tmp_path,
        "first.py",
        "value = 1\n",
        "same-thread",
    )

    with pytest.raises(
        ValueError,
        match="审批线程已存在",
    ):
        start_approval(
            graph,
            tmp_path,
            "second.py",
            "value = 2\n",
            "same-thread",
        )

    assert not (tmp_path / "first.py").exists()
    assert not (tmp_path / "second.py").exists()


def test_different_threads_are_isolated(
    graph: CompiledStateGraph,
    tmp_path: Path,
) -> None:
    """批准一个任务不会自动批准另一个任务。"""

    start_approval(
        graph,
        tmp_path,
        "first.py",
        "value = 1\n",
        "thread-a",
    )

    start_approval(
        graph,
        tmp_path,
        "second.py",
        "value = 2\n",
        "thread-b",
    )

    result = resume_approval(
        graph,
        "thread-a",
        approved=True,
    )

    assert result["status"] == "created"
    assert (tmp_path / "first.py").exists()
    assert not (tmp_path / "second.py").exists()

    snapshot = graph.get_state(make_approval_config("thread-b"))

    assert snapshot.next == ("request_approval",)


def test_sqlite_restores_pending_approval_after_reopen(
    tmp_path: Path,
) -> None:
    """数据库重新打开后，仍然可以继续等待中的审批。"""

    project = tmp_path / "project"
    project.mkdir()

    database = tmp_path / "approval.sqlite"
    target = project / "demo.py"

    with SqliteSaver.from_conn_string(str(database)) as saver:
        graph = build_approval_graph(saver)

        result = start_approval(
            graph,
            project,
            "demo.py",
            "message = 'hello'\n",
            "sqlite-request",
        )

        assert "__interrupt__" in result
        assert not target.exists()

    assert database.is_file()

    with SqliteSaver.from_conn_string(str(database)) as saver:
        graph = build_approval_graph(saver)

        result = resume_approval(
            graph,
            "sqlite-request",
            approved=True,
        )

        assert result["status"] == "created"
        assert target.read_text(encoding="utf-8") == ("message = 'hello'\n")
```

### 4.4 测试讲解

**（1）`InMemorySaver` 与 `SqliteSaver` 的区别**

```python
InMemorySaver()
```

适合测试短生命周期中的状态流转。

它不需要建立数据库文件，测试速度快。

但进程退出后，内存状态不会像 SQLite 文件那样保留。

```python
SqliteSaver
```

用于验证真正的持久化行为。

因此本文件主要用 `InMemorySaver` 测试分支，用 `SqliteSaver` 测试关闭连接后的恢复。

**（2）为什么先断言文件不存在？**

```python
assert not target.exists()
```

这是证明“人工审批前不写入”的关键。

只有批准后创建成功的测试还不够，因为那不能排除文件早在准备阶段就已被创建。

**（3）为什么测试审批期间的文件冲突？**

因为人工审批不是瞬间完成的。

如果用户查看 Diff 时，另一个操作已经创建了目标文件，之后批准也不能覆盖它。

因此测试模拟：

```python
target.write_text("existing = True\n")
```

再执行批准，要求状态为：

```text
conflict
```

而且原文件内容保持不变。

**（4）为什么不能重复恢复已完成任务？**

一次审批的结果应当是确定的。

如果已完成的任务还能重复恢复，就可能导致重复操作。

因此使用：

```python
snapshot.next
```

判断是否仍处于等待审批状态。

**（5）为什么测试不同线程？**

批准 A 后，B 仍应停留在：

```python
("request_approval",)
```

这样才能保证人工决定只作用于指定任务。

### 4.5 验证

```bash
python -m pytest tests/test_approval_workflow.py -v
```

最终验证已通过。

---

# 第二阶段｜已有文件的人工审批修改

## 5. 文件三：`src/ai_software_dev_agent/edit_approval_workflow.py`

### 5.1 为什么需要独立实现？

第一阶段使用的是：

```python
target.open("x")
```

它只允许创建新文件。

但实际软件开发中，更常见的是修改已有文件。

比如：

```python
answer = 1
```

改为：

```python
answer = 42
```

已有文件修改涉及：

- 路径安全。
- 目标文件类型。
- 原文本唯一匹配。
- Diff 预览。
- 文件版本检测。
- 原子写入。

这些逻辑在此前的 CodeEditor 中已经实现。

因此，第二阶段不重复开发编辑器，而是把 CodeEditor 接入 LangGraph 审批工作流。

### 5.2 创建与打开

```bash
touch src/ai_software_dev_agent/edit_approval_workflow.py

nano src/ai_software_dev_agent/edit_approval_workflow.py
```

### 5.3 完整代码

```python
"""Day 12：为已有代码文件的文本替换添加人工审批。"""

from pathlib import Path
from typing import Literal, NotRequired, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command, interrupt

from ai_software_dev_agent.editor import CodeEditor, FileEditError


EditStatus = Literal[
    "pending",
    "approved",
    "applied",
    "rejected",
    "conflict",
]


class EditApprovalState(TypedDict):
    """已有文件修改审批工作流的共享状态。"""

    project: str
    relative_path: str
    old_text: str
    new_text: str

    diff: NotRequired[str]
    original_sha256: NotRequired[str]
    approved: NotRequired[bool]
    status: NotRequired[EditStatus]
    summary: NotRequired[str]


def prepare_edit_node(
    state: EditApprovalState,
) -> dict[str, str]:
    """通过 CodeEditor 准备修改预览，不写入文件。"""

    editor = CodeEditor(Path(state["project"]))

    preview = editor.preview_replace(
        file_path=state["relative_path"],
        old_text=state["old_text"],
        new_text=state["new_text"],
    )

    return {
        "diff": preview.diff,
        "original_sha256": preview.original_sha256,
        "status": "pending",
    }


def request_edit_approval_node(
    state: EditApprovalState,
) -> dict[str, object]:
    """暂停工作流，让调用方展示 Diff 并等待人工决定。"""

    decision = interrupt(
        {
            "operation": "replace_text",
            "relative_path": state["relative_path"],
            "diff": state["diff"],
            "original_sha256": state["original_sha256"],
            "question": "是否批准应用以上文件修改？",
        }
    )

    approved = decision is True

    return {
        "approved": approved,
        "status": "approved" if approved else "rejected",
    }


def route_after_edit_approval(
    state: EditApprovalState,
) -> Literal["apply_edit", "reject_edit"]:
    """按照审批结果决定是否允许写入文件。"""

    if state["approved"]:
        return "apply_edit"

    return "reject_edit"


def apply_edit_node(
    state: EditApprovalState,
) -> dict[str, str]:
    """重新检查文件版本，再调用 CodeEditor 执行修改。"""

    editor = CodeEditor(Path(state["project"]))

    try:
        # 审批后重新预览当前文件。
        current_preview = editor.preview_replace(
            file_path=state["relative_path"],
            old_text=state["old_text"],
            new_text=state["new_text"],
        )

        # 用户只批准了原版本的文件修改。
        if (
            current_preview.original_sha256 != state["original_sha256"]
            or current_preview.diff != state["diff"]
        ):
            return {
                "status": "conflict",
                "summary": ("文件在审批期间发生变化，原修改方案已失效，未执行写入。"),
            }

        # 最终写入仍交给原有 CodeEditor。
        editor.apply(current_preview)

    except FileEditError as exc:
        return {
            "status": "conflict",
            "summary": f"文件修改校验或执行失败：{exc}",
        }

    return {
        "status": "applied",
        "summary": (f"人工已批准，成功修改文件：{state['relative_path']}"),
    }


def reject_edit_node(
    state: EditApprovalState,
) -> dict[str, str]:
    """拒绝审批时直接结束，不调用 CodeEditor.apply。"""

    return {
        "status": "rejected",
        "summary": "人工拒绝了此次文件修改，未执行写入。",
    }


def build_edit_approval_graph(
    checkpointer: BaseCheckpointSaver,
) -> CompiledStateGraph:
    """创建支持 Checkpoint 的已有文件修改审批图。"""

    builder = StateGraph(EditApprovalState)

    builder.add_node("prepare_edit", prepare_edit_node)

    builder.add_node(
        "request_edit_approval",
        request_edit_approval_node,
    )

    builder.add_node("apply_edit", apply_edit_node)
    builder.add_node("reject_edit", reject_edit_node)

    builder.add_edge(START, "prepare_edit")
    builder.add_edge("prepare_edit", "request_edit_approval")

    builder.add_conditional_edges(
        "request_edit_approval",
        route_after_edit_approval,
        {
            "apply_edit": "apply_edit",
            "reject_edit": "reject_edit",
        },
    )

    builder.add_edge("apply_edit", END)
    builder.add_edge("reject_edit", END)

    return builder.compile(checkpointer=checkpointer)


def make_edit_approval_config(
    thread_id: str,
) -> dict[str, object]:
    """生成当前审批请求的 LangGraph 线程配置。"""

    clean_id = thread_id.strip()

    if not clean_id:
        raise ValueError("审批线程 ID 不能为空")

    return {
        "configurable": {
            "thread_id": clean_id,
        }
    }


def start_edit_approval(
    graph: CompiledStateGraph,
    project: Path,
    relative_path: str,
    old_text: str,
    new_text: str,
    thread_id: str,
) -> dict:
    """提交修改请求，执行到 interrupt 并返回预览。"""

    config = make_edit_approval_config(thread_id)

    snapshot = graph.get_state(config)

    if snapshot.values:
        raise ValueError("审批线程已存在，请使用新的 thread_id")

    initial_state: EditApprovalState = {
        "project": str(project.expanduser().resolve()),
        "relative_path": relative_path,
        "old_text": old_text,
        "new_text": new_text,
    }

    return graph.invoke(initial_state, config=config)


def resume_edit_approval(
    graph: CompiledStateGraph,
    thread_id: str,
    approved: bool,
) -> dict:
    """根据人工批准或拒绝，恢复指定的待审批工作流。"""

    if not isinstance(approved, bool):
        raise ValueError("审批决定必须是布尔值")

    config = make_edit_approval_config(thread_id)

    snapshot = graph.get_state(config)

    if snapshot.next != ("request_edit_approval",):
        raise ValueError("当前线程没有等待处理的修改审批")

    return graph.invoke(
        Command(resume=approved),
        config=config,
    )
```

### 5.4 核心代码解释

**（1）为什么复用 CodeEditor？**

本次采用 Separation of Concerns（关注点分离）：

| 模块 | 职责 |
|---|---|
| `CodeEditor` | 怎样安全预览、校验并修改文件 |
| `edit_approval_workflow` | 修改前后如何组织工作流 |
| `interrupt()` | 在修改前暂停，要求人工决定 |
| `SqliteSaver` | 持久化等待中的任务 |
| CLI | 展示 Diff、收集人工输入 |

这样不需要在工作流中重新实现文件编辑细节。

**（2）`preview_replace()` 与 `apply()` 的区别**

```python
preview = editor.preview_replace(...)
```

负责生成预览，不修改原文件。

```python
editor.apply(preview)
```

负责最终应用修改。

本次保证 `apply()` 只会出现在批准分支中。

**（3）为什么使用 SHA-256？**

假设准备审批时，文件内容是：

```python
answer = 1
```

用户查看 Diff 后，其他程序将文件改成：

```python
answer = 1
print("new code")
```

旧文本 `"answer = 1"` 仍然可以匹配。

如果只检查旧文本是否存在，就可能错误地执行一份过期修改。

所以保存原文件哈希：

```python
original_sha256
```

恢复时重新计算哈希。

只要文件内容发生变化，就应停止使用原审批。

**（4）为什么还要比较 Diff？**

```python
current_preview.diff != state["diff"]
```

再次检查现在准备执行的修改是否与当时展示给用户的内容一致。

这样不仅验证文件版本，还验证修改方案本身。

**（5）为什么还需要 CodeEditor 自己的检查？**

工作流层比较的是：

**当前文件是否仍然对应用户批准时的文件版本。**

CodeEditor 内部还负责：

**准备实际写入时，是否仍满足它自身的安全条件。**

两层检查各司其职。

**（6）为什么 `conflict` 不一定只表示哈希冲突？**

当前代码将：

```python
except FileEditError:
```

也转换为 `conflict`。

所以此状态表示这次修改未能按原方案执行，具体原因还需要查看 `summary`。

后续若做生产级错误管理，可以细分为：

```text
stale_file
invalid_edit
write_error
```

但本日暂不扩展。

### 5.5 注意事项

- 本阶段只处理已有文件的精确文本替换。
- 不支持任意删除文件。
- 不支持批量修改。
- 不支持自动执行 Shell 命令。
- 不意味着整个 Agent 中的其他路径都无法直接调用 CodeEditor。
- Checkpoint 中可能包含源码片段、Diff 与路径信息。
- 对已经批准但出现冲突的任务，应重新生成预览并重新审批。

### 5.6 验证

```bash
python -m pytest tests/test_edit_approval_workflow.py -v
```

同时验证原有 CodeEditor：

```bash
python -m pytest tests/test_editor.py -v
```

两项均已通过验收。

---

## 6. 文件四：`tests/test_edit_approval_workflow.py`

### 6.1 文件职责

验证第二阶段已有文件修改审批的完整过程。

重点检查：

- 审批前文件不变化。
- 批准后执行精确替换。
- 拒绝后不写入。
- 文件在审批期间变化时拒绝执行。
- 旧文本缺失或重复时拒绝预览。
- 非法路径与符号链接不能越界修改。
- 线程不能重复使用。
- 已完成任务不能重复审批。
- SQLite 重新打开后可恢复。

### 6.2 创建与打开

```bash
touch tests/test_edit_approval_workflow.py

nano tests/test_edit_approval_workflow.py
```

### 6.3 完整代码

```python
"""Day 12：已有文件修改的人工审批工作流测试。"""

from pathlib import Path

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph.state import CompiledStateGraph

from ai_software_dev_agent.edit_approval_workflow import (
    build_edit_approval_graph,
    make_edit_approval_config,
    resume_edit_approval,
    start_edit_approval,
)
from ai_software_dev_agent.editor import FileEditError


ORIGINAL = "answer = 1\n"
MODIFIED = "answer = 42\n"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """创建含有一个 Python 文件的临时项目。"""

    (tmp_path / "demo.py").write_text(
        ORIGINAL,
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def graph() -> CompiledStateGraph:
    """使用独立的内存 Checkpointer。"""

    return build_edit_approval_graph(InMemorySaver())


def begin(
    graph: CompiledStateGraph,
    project: Path,
    thread_id: str,
    path: str = "demo.py",
) -> dict:
    """统一发起一条测试修改请求。"""

    return start_edit_approval(
        graph=graph,
        project=project,
        relative_path=path,
        old_text="answer = 1",
        new_text="answer = 42",
        thread_id=thread_id,
    )


def test_preview_interrupts_without_modifying_file(
    graph: CompiledStateGraph,
    project: Path,
) -> None:
    """生成 Diff 并暂停时，磁盘文件不能被修改。"""

    target = project / "demo.py"

    result = begin(graph, project, "preview-only")

    assert "__interrupt__" in result
    assert target.read_text(encoding="utf-8") == ORIGINAL

    request = result["__interrupt__"][0].value

    assert request["operation"] == "replace_text"
    assert request["relative_path"] == "demo.py"
    assert "-answer = 1" in request["diff"]
    assert "+answer = 42" in request["diff"]
    assert len(request["original_sha256"]) == 64

    snapshot = graph.get_state(make_edit_approval_config("preview-only"))

    assert snapshot.values["status"] == "pending"
    assert snapshot.next == ("request_edit_approval",)


def test_approved_edit_changes_only_expected_text(
    graph: CompiledStateGraph,
    project: Path,
) -> None:
    """人工批准后才实际替换文件内容。"""

    begin(graph, project, "approve-request")

    assert (project / "demo.py").read_text(encoding="utf-8") == ORIGINAL

    result = resume_edit_approval(
        graph,
        "approve-request",
        approved=True,
    )

    assert result["approved"] is True
    assert result["status"] == "applied"
    assert (project / "demo.py").read_text(encoding="utf-8") == MODIFIED


def test_rejected_edit_keeps_original_file(
    graph: CompiledStateGraph,
    project: Path,
) -> None:
    """拒绝审批后不能执行写入。"""

    begin(graph, project, "reject-request")

    result = resume_edit_approval(
        graph,
        "reject-request",
        approved=False,
    )

    assert result["approved"] is False
    assert result["status"] == "rejected"
    assert "未执行写入" in result["summary"]
    assert (project / "demo.py").read_text(encoding="utf-8") == ORIGINAL


def test_stale_file_blocks_approved_edit(
    graph: CompiledStateGraph,
    project: Path,
) -> None:
    """审批等待期间文件变化，不能使用旧预览。"""

    target = project / "demo.py"

    begin(graph, project, "stale-request")

    changed_content = ORIGINAL + "# added during review\n"
    target.write_text(changed_content, encoding="utf-8")

    result = resume_edit_approval(
        graph,
        "stale-request",
        approved=True,
    )

    assert result["approved"] is True
    assert result["status"] == "conflict"

    assert target.read_text(encoding="utf-8") == changed_content


def test_missing_or_duplicate_old_text_is_rejected(
    graph: CompiledStateGraph,
    project: Path,
) -> None:
    """旧片段缺失或重复时不能生成安全预览。"""

    target = project / "demo.py"

    target.write_text("other = 1\n", encoding="utf-8")

    with pytest.raises(FileEditError):
        begin(graph, project, "missing-old-text")

    target.write_text(
        ORIGINAL + ORIGINAL,
        encoding="utf-8",
    )

    with pytest.raises(FileEditError):
        begin(graph, project, "duplicate-old-text")

    assert target.read_text(encoding="utf-8") == (ORIGINAL + ORIGINAL)


@pytest.mark.parametrize(
    "relative_path",
    [
        "../outside.py",
        "/tmp/outside.py",
        ".hidden.py",
        "notes.txt",
    ],
)
def test_invalid_paths_are_rejected(
    graph: CompiledStateGraph,
    project: Path,
    relative_path: str,
) -> None:
    """复用 CodeEditor 的路径与文件类型安全规则。"""

    with pytest.raises(FileEditError):
        begin(
            graph,
            project,
            f"invalid-{relative_path}",
            path=relative_path,
        )

    assert (project / "demo.py").read_text(encoding="utf-8") == ORIGINAL


def test_symlink_to_outside_is_rejected(
    graph: CompiledStateGraph,
    tmp_path: Path,
) -> None:
    """不能通过符号链接修改仓库外的文件。"""

    root = tmp_path / "project"
    root.mkdir()

    outside = tmp_path / "outside.py"
    outside.write_text(ORIGINAL, encoding="utf-8")

    (root / "linked.py").symlink_to(outside)

    with pytest.raises(FileEditError):
        begin(
            graph,
            root,
            "symlink-request",
            path="linked.py",
        )

    assert outside.read_text(encoding="utf-8") == ORIGINAL


def test_completed_approval_cannot_run_twice(
    graph: CompiledStateGraph,
    project: Path,
) -> None:
    """审批执行完成后，不得重复恢复同一个任务。"""

    begin(graph, project, "completed-request")

    resume_edit_approval(
        graph,
        "completed-request",
        approved=True,
    )

    with pytest.raises(
        ValueError,
        match="没有等待处理的修改审批",
    ):
        resume_edit_approval(
            graph,
            "completed-request",
            approved=True,
        )


def test_non_boolean_decision_is_rejected(
    graph: CompiledStateGraph,
    project: Path,
) -> None:
    """字符串 yes/no 不应该被当作人工批准。"""

    begin(graph, project, "invalid-decision")

    with pytest.raises(
        ValueError,
        match="审批决定必须是布尔值",
    ):
        resume_edit_approval(
            graph,
            "invalid-decision",
            approved="yes",  # type: ignore[arg-type]
        )

    assert (project / "demo.py").read_text(encoding="utf-8") == ORIGINAL


def test_existing_approval_thread_cannot_be_reused(
    graph: CompiledStateGraph,
    project: Path,
) -> None:
    """不能用同一个线程 ID 覆盖已有待审批任务。"""

    begin(graph, project, "same-thread")

    with pytest.raises(
        ValueError,
        match="审批线程已存在",
    ):
        begin(graph, project, "same-thread")

    assert (project / "demo.py").read_text(encoding="utf-8") == ORIGINAL


def test_different_approval_threads_are_isolated(
    graph: CompiledStateGraph,
    project: Path,
) -> None:
    """批准任务 A 不应该自动批准任务 B。"""

    (project / "second.py").write_text(
        ORIGINAL,
        encoding="utf-8",
    )

    begin(graph, project, "thread-a", path="demo.py")
    begin(graph, project, "thread-b", path="second.py")

    result = resume_edit_approval(
        graph,
        "thread-a",
        approved=True,
    )

    assert result["status"] == "applied"
    assert (project / "demo.py").read_text(encoding="utf-8") == MODIFIED

    assert (project / "second.py").read_text(encoding="utf-8") == ORIGINAL

    snapshot = graph.get_state(make_edit_approval_config("thread-b"))

    assert snapshot.next == ("request_edit_approval",)


def test_sqlite_restores_pending_edit_after_reopen(
    tmp_path: Path,
) -> None:
    """关闭数据库后再次打开，可继续此前等待中的审批。"""

    project = tmp_path / "project"
    project.mkdir()

    target = project / "demo.py"
    target.write_text(ORIGINAL, encoding="utf-8")

    database = tmp_path / "edit-approval.sqlite"

    with SqliteSaver.from_conn_string(str(database)) as saver:
        graph = build_edit_approval_graph(saver)

        result = begin(graph, project, "sqlite-edit-request")

        assert "__interrupt__" in result
        assert target.read_text(encoding="utf-8") == ORIGINAL

    assert database.is_file()

    with SqliteSaver.from_conn_string(str(database)) as saver:
        graph = build_edit_approval_graph(saver)

        result = resume_edit_approval(
            graph,
            "sqlite-edit-request",
            approved=True,
        )

        assert result["status"] == "applied"
        assert target.read_text(encoding="utf-8") == MODIFIED
```

### 6.4 测试讲解

**（1）为什么只预览是不够的？**

测试：

```python
assert "__interrupt__" in result
```

证明进入了暂停状态。

但还要检查：

```python
assert target.read_text(...) == ORIGINAL
```

才能证明在等待审批时，文件没有被修改。

**（2）什么是 Stale Preview？**

Stale Preview（过期预览）指的是：

用户批准时看到的预览，对应的文件版本已经不再是当前版本。

例如：

```python
answer = 1
```

后来变成：

```python
answer = 1
# added during review
```

虽然替换片段仍存在，但文件整体 SHA-256 已变化。

因此必须拒绝应用。

**（3）为什么要测试唯一匹配？**

如果目标文件中有：

```python
answer = 1
answer = 1
```

而用户要求替换：

```python
answer = 1
```

系统无法确认应该修改哪一处。

CodeEditor 的策略是拒绝执行，而不是擅自猜测。

**（4）为什么测试符号链接？**

某个看似在仓库内的路径可能指向仓库外：

```text
project/linked.py → /outside.py
```

如果不验证实际路径，就可能修改不属于项目的文件。

因此需要检查 CodeEditor 原有的符号链接保护仍然有效。

**（5）为什么重新打开数据库后还要验证？**

因为只有关闭旧连接、创建新 Graph 后仍能恢复审批，才说明任务状态确实保存到了 SQLite。

### 6.5 验证

```bash
python -m pytest tests/test_edit_approval_workflow.py -v
```

同时回归验证：

```bash
python -m pytest tests/test_editor.py -v
```

均已确认通过。

---

# 第三阶段｜CLI 审批与跨进程恢复

## 7. 文件五：`src/ai_software_dev_agent/commands/edit_approval.py`

### 7.1 文件职责

第一、第二阶段实现了工作流，但只能通过 Python 函数调用。

第三阶段将它转换成用户真正可以使用的 CLI。

新增两个命令：

```bash
ai-dev-agent edit-approval prepare
```

负责：

- 接收修改要求。
- 生成 Diff。
- 保存待审批状态。
- 输出审批 ID。
- 退出进程。

以及：

```bash
ai-dev-agent edit-approval review
```

负责：

- 读取已有审批。
- 显示 Diff。
- 读取人工输入。
- 使用 `Command(resume=...)` 恢复。
- 输出执行结果。

### 7.2 创建与打开

```bash
touch src/ai_software_dev_agent/commands/edit_approval.py

nano src/ai_software_dev_agent/commands/edit_approval.py
```

### 7.3 完整代码

```python
"""Day 12：已有文件修改的人工审批 CLI。"""

import argparse
import sqlite3
import sys
from pathlib import Path
from shlex import quote
from typing import Any
from uuid import uuid4

from langgraph.checkpoint.sqlite import SqliteSaver

from ai_software_dev_agent.edit_approval_workflow import (
    build_edit_approval_graph,
    make_edit_approval_config,
    resume_edit_approval,
    start_edit_approval,
)
from ai_software_dev_agent.editor import FileEditError


# 与 Day 11 的聊天数据库分离。
DEFAULT_APPROVAL_DB = (
    Path.home() / ".ai-software-development-agent" / "edit-approvals.sqlite"
)


def resolve_db_path(path: Path | None) -> Path:
    """获取本地审批数据库的绝对路径。"""

    selected = path if path is not None else DEFAULT_APPROVAL_DB
    return selected.expanduser().resolve()


def run_prepare(args: argparse.Namespace) -> int:
    """创建一条待审批修改请求，不修改目标文件。"""

    db_path = resolve_db_path(args.db)
    thread_id = args.thread_id or uuid4().hex

    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)

        with SqliteSaver.from_conn_string(str(db_path)) as saver:
            graph = build_edit_approval_graph(saver)

            result = start_edit_approval(
                graph=graph,
                project=args.project,
                relative_path=args.relative_path,
                old_text=args.old_text,
                new_text=args.new_text,
                thread_id=thread_id,
            )

            interrupts = result.get("__interrupt__", ())

            if not interrupts:
                print(
                    "工作流没有进入待审批状态。",
                    file=sys.stderr,
                )
                return 1

            request = interrupts[0].value

            print("\n===== 文件修改预览 =====")
            print(f"项目目录：{args.project.resolve()}")
            print(f"目标文件：{request['relative_path']}")
            print(f"原文件哈希：{request['original_sha256']}")

            print("\n===== Diff =====")
            print(request["diff"])

            print("审批状态：等待人工确认")
            print(f"审批 ID：{thread_id}")
            print(f"数据库：{db_path}")

            # 生成适合复制到 Shell 中的恢复命令。
            command = (
                "ai-dev-agent edit-approval review"
                f" --thread-id {quote(thread_id)}"
                f" --db {quote(str(db_path))}"
            )

            print("\n之后运行以下命令进行审批：")
            print(command)

            return 0

    except (FileEditError, ValueError, OSError, sqlite3.Error) as exc:
        print(
            f"准备审批失败：{type(exc).__name__}：{exc}",
            file=sys.stderr,
        )
        return 1


def run_review(args: argparse.Namespace) -> int:
    """恢复审批任务，显示 Diff 后读取人工决定。"""

    db_path = resolve_db_path(args.db)

    if not db_path.is_file():
        print(
            f"审批数据库不存在：{db_path}",
            file=sys.stderr,
        )
        return 2

    try:
        config = make_edit_approval_config(args.thread_id)

        with SqliteSaver.from_conn_string(str(db_path)) as saver:
            graph = build_edit_approval_graph(saver)

            snapshot = graph.get_state(config)

            if snapshot.next != ("request_edit_approval",):
                print(
                    "没有找到等待处理的文件修改审批。",
                    file=sys.stderr,
                )
                return 2

            state = snapshot.values

            print("\n===== 待审批的修改 =====")
            print(f"审批 ID：{args.thread_id}")
            print(f"项目目录：{state['project']}")
            print(f"目标文件：{state['relative_path']}")
            print(f"原文件哈希：{state['original_sha256']}")

            print("\n===== Diff =====")
            print(state["diff"])

            print("请确认以上项目路径与代码修改内容。")
            print("yes：批准修改")
            print("no ：拒绝修改")
            print("其他输入：取消本次操作，保留待审批状态")

            try:
                answer = input("\n请输入决定（yes/no）：")

            except EOFError:
                print("\n未收到审批输入，任务仍处于待审批状态。")
                return 2

            except KeyboardInterrupt:
                print("\n用户取消审批，任务仍处于待审批状态。")
                return 130

            decision = answer.strip().lower()

            if decision not in {"yes", "no"}:
                print("本次未提交决定，任务仍处于待审批状态。")
                return 0

            approved = decision == "yes"

            result = resume_edit_approval(
                graph=graph,
                thread_id=args.thread_id,
                approved=approved,
            )

            print(f"\n最终状态：{result['status']}")
            print(f"执行说明：{result['summary']}")

            if result["status"] in {"applied", "rejected"}:
                return 0

            return 1

    except (
        FileEditError,
        ValueError,
        OSError,
        sqlite3.Error,
        KeyError,
    ) as exc:
        print(
            f"审批处理失败：{type(exc).__name__}：{exc}",
            file=sys.stderr,
        )
        return 1


def register(subparsers: Any) -> None:
    """注册 edit-approval 及其两个子命令。"""

    parser = subparsers.add_parser(
        "edit-approval",
        help="预览代码修改，并通过人工审批决定是否执行",
    )

    actions = parser.add_subparsers(
        dest="approval_action",
        required=True,
    )

    prepare = actions.add_parser(
        "prepare",
        help="生成 Diff 并保存待审批任务",
    )

    prepare.add_argument(
        "--project",
        type=Path,
        required=True,
        help="项目根目录",
    )
    prepare.add_argument(
        "--file",
        dest="relative_path",
        required=True,
        help="相对项目根目录的 Python 文件路径",
    )
    prepare.add_argument(
        "--old",
        dest="old_text",
        required=True,
        help="需要唯一匹配的原始文本",
    )
    prepare.add_argument(
        "--new",
        dest="new_text",
        required=True,
        help="用于替换的新文本",
    )
    prepare.add_argument(
        "--thread-id",
        default=None,
        help="自定义审批 ID；默认自动生成",
    )
    prepare.add_argument(
        "--db",
        type=Path,
        default=None,
        help="SQLite 审批数据库路径",
    )
    prepare.set_defaults(handler=run_prepare)

    review = actions.add_parser(
        "review",
        help="恢复待审批任务，交互式批准或拒绝",
    )

    review.add_argument(
        "--thread-id",
        required=True,
        help="prepare 阶段生成的审批 ID",
    )
    review.add_argument(
        "--db",
        type=Path,
        default=None,
        help="与 prepare 相同的 SQLite 数据库路径",
    )
    review.set_defaults(handler=run_review)
```

### 7.4 核心代码解释

**（1）为什么拆成两个命令？**

因为我们需要证明工作流能够在**不同 Python 进程之间恢复**。

如果整个流程都放在同一个函数里：

```python
prepare()
input()
resume()
```

只能证明进程内可以暂停和继续。

现在的设计是：

```text
prepare 命令运行结束
    ↓
Python 进程退出
    ↓
review 命令重新启动
    ↓
重新打开 SQLite
    ↓
恢复审批
```

因此更符合 Day 11 与 Day 12 的学习目标。

**（2）`uuid4()` 的作用**

```python
thread_id = args.thread_id or uuid4().hex
```

如果用户没有指定审批 ID，就自动生成一个。

这样每次准备审批通常使用不同的线程，降低 ID 冲突的概率。

如果用户主动传入相同的审批 ID，工作流会拒绝覆盖旧任务。

**（3）为什么使用 `shlex.quote()`？**

```python
from shlex import quote
```

它会帮助我们正确引用 Shell 参数。

例如路径包含空格：

```text
/Users/example/My Documents/approvals.sqlite
```

如果直接拼接命令，Shell 可能把路径拆成多个参数。

使用：

```python
quote(str(db_path))
```

可以降低这个问题的出现概率。

**（4）为什么不直接提供 `--approve`？**

本阶段刻意使用：

```python
answer = input(...)
```

让用户在看到 Diff 之后输入决定。

如果提供可以跳过显示的自动批准参数，其他程序可能在没有人工审查的情况下直接触发写入。

因此当前 CLI 只接受交互式批准。

但需要理解：交互式输入只是人工交互流程，不等同于用户身份认证。

**（5）为什么 `yes` 和 `no` 之外的输入不等于拒绝？**

例如：

```text
maybe
```

可能只是用户尚未作出决定。

所以当前行为：

| 用户输入 | 执行结果 |
|---|---|
| `yes` | 批准 |
| `no` | 拒绝 |
| `maybe` 等其他输入 | 保留待审批状态 |
| EOF | 保留待审批状态 |
| Ctrl+C | 保留待审批状态 |

只有明确输入 `yes` 才会触发写入分支。

**（6）为什么 CLI 也要检查 `snapshot.next`？**

```python
if snapshot.next != ("request_edit_approval",):
```

防止恢复：

- 不存在的任务。
- 已经完成的任务。
- 并非停在审批节点的任务。

业务层也进行同样的检查。

虽然看似重复，但 CLI 和业务逻辑承担不同职责：CLI 尽早给用户清晰提示；业务层保证直接调用时也遵守约束。

**（7）为什么审批数据库独立于聊天数据库？**

Day 11 聊天数据库：

```text
sessions.sqlite
```

Day 12 审批数据库：

```text
edit-approvals.sqlite
```

将两种用途分开，可以降低不同类型任务意外混用线程状态的风险。

### 7.5 注意事项

- 目前只支持精确文本替换。
- `--old` 和 `--new` 主要适合较短文本。
- 对多行复杂代码，直接传 Shell 参数容易产生引号与换行问题。
- 当前没有审批任务列表、搜索和归档功能。
- 数据库可能包含完整修改片段和源码内容。
- 不应把 Checkpoint 数据库当作公开可共享文件。
- 不提供自动批准入口，是本阶段刻意保留的人工作业要求。

### 7.6 对应验证

```bash
ai-dev-agent edit-approval --help
ai-dev-agent edit-approval prepare --help
ai-dev-agent edit-approval review --help
```

以及：

```bash
python -m pytest tests/cli/test_edit_approval.py -v
```

均已通过验证。

---

## 8. 文件六：`src/ai_software_dev_agent/cli.py`

### 8.1 文件职责

这是已有 CLI 的统一入口。

本次只需要把新命令注册到已有 `argparse` 子命令系统中。

**不重写原文件。**

这样保留 Day 01～Day 11 已经完成的全部命令和调用关系。

### 8.2 打开文件

```bash
nano src/ai_software_dev_agent/cli.py
```

### 8.3 本次完整增量修改

在原有导入区域增加：

```python
from ai_software_dev_agent.commands import edit_approval
```

在现有子命令注册区域增加：

```python
edit_approval.register(subparsers)
```

注意：这里的 `subparsers` 必须是现有 CLI 已经创建的那个对象。

原有的其他注册语句全部保留。

由于本次聊天没有读取到 `cli.py` 原有的完整代码，所以文档只记录这两处实际增量变更，不虚构整个文件。

### 8.4 核心代码解释

使用：

```python
parser.add_subparsers(...)
```

创建子命令系统后，各个模块可以自行提供：

```python
register(subparsers)
```

避免把全部参数定义堆在 `cli.py` 里。

新增功能时只需要：

```text
创建 commands/xxx.py
    ↓
在其中实现 register()
    ↓
在 cli.py 中注册
```

这体现了模块化 CLI 的设计思路。

同时，本次采用增量修改，是因为 Day 11 曾出现过直接重构旧 `chat.py` 导致回归测试失败的问题。

### 8.5 验证

```bash
ai-dev-agent --help
```

确认出现：

```text
edit-approval
```

继续：

```bash
ai-dev-agent edit-approval --help
```

确认出现：

```text
prepare
review
```

原有 `chat`、`agent-workflow` 等命令仍然可用。

---

## 9. 文件七：`tests/cli/test_edit_approval.py`

### 9.1 文件职责

验证第三阶段 CLI 的端到端交互行为。

重点检查：

- 准备审批时不修改文件。
- 重新打开 CLI 后批准能成功修改。
- 拒绝后文件不变化。
- 无效输入保留审批。
- EOF 保留审批。
- 文件变化阻止应用旧预览。
- 非法路径被拒绝。
- 重复审批 ID 被拒绝。
- 数据库不存在时不能恢复。
- 帮助信息包含新命令。

### 9.2 创建与打开

```bash
touch tests/cli/test_edit_approval.py

nano tests/cli/test_edit_approval.py
```

### 9.3 完整代码

```python
"""Day 12：文件修改审批 CLI 的自动化测试。"""

from pathlib import Path

import pytest

from ai_software_dev_agent import cli


ORIGINAL = "answer = 1\n"
MODIFIED = "answer = 42\n"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """创建独立的测试项目和待修改文件。"""

    root = tmp_path / "project"
    root.mkdir()

    (root / "demo.py").write_text(
        ORIGINAL,
        encoding="utf-8",
    )

    return root


def prepare_args(
    project: Path,
    db_path: Path,
    thread_id: str,
    relative_path: str = "demo.py",
) -> list[str]:
    """构造准备审批的 CLI 参数。"""

    return [
        "edit-approval",
        "prepare",
        "--project",
        str(project),
        "--file",
        relative_path,
        "--old",
        "answer = 1",
        "--new",
        "answer = 42",
        "--thread-id",
        thread_id,
        "--db",
        str(db_path),
    ]


def review_args(
    db_path: Path,
    thread_id: str,
) -> list[str]:
    """构造恢复审批的 CLI 参数。"""

    return [
        "edit-approval",
        "review",
        "--thread-id",
        thread_id,
        "--db",
        str(db_path),
    ]


def test_prepare_only_saves_pending_request(
    project: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """准备审批后，目标文件不得发生变化。"""

    db_path = tmp_path / "approval.sqlite"

    result = cli.main(prepare_args(project, db_path, "prepare-only"))

    output = capsys.readouterr().out

    assert result == 0
    assert "等待人工确认" in output
    assert "prepare-only" in output
    assert "-answer = 1" in output
    assert "+answer = 42" in output
    assert db_path.is_file()

    assert (project / "demo.py").read_text(encoding="utf-8") == ORIGINAL


def test_approve_after_reopening_cli(
    project: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """分两次运行 CLI，批准后才修改文件。"""

    db_path = tmp_path / "approval.sqlite"
    thread_id = "approve-request"

    assert cli.main(prepare_args(project, db_path, thread_id)) == 0

    assert (project / "demo.py").read_text(encoding="utf-8") == ORIGINAL

    monkeypatch.setattr(
        "builtins.input",
        lambda prompt: "yes",
    )

    result = cli.main(review_args(db_path, thread_id))

    output = capsys.readouterr().out

    assert result == 0
    assert "最终状态：applied" in output
    assert (project / "demo.py").read_text(encoding="utf-8") == MODIFIED


def test_reject_keeps_original_file(
    project: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """输入 no 后，原文件保持不变。"""

    db_path = tmp_path / "approval.sqlite"
    thread_id = "reject-request"

    assert cli.main(prepare_args(project, db_path, thread_id)) == 0

    monkeypatch.setattr(
        "builtins.input",
        lambda prompt: "no",
    )

    result = cli.main(review_args(db_path, thread_id))

    output = capsys.readouterr().out

    assert result == 0
    assert "最终状态：rejected" in output
    assert (project / "demo.py").read_text(encoding="utf-8") == ORIGINAL


def test_unknown_answer_preserves_pending_request(
    project: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """输入不明确时，不修改文件，并允许再次审批。"""

    db_path = tmp_path / "approval.sqlite"
    thread_id = "unknown-answer"

    assert cli.main(prepare_args(project, db_path, thread_id)) == 0

    monkeypatch.setattr(
        "builtins.input",
        lambda prompt: "maybe",
    )

    assert cli.main(review_args(db_path, thread_id)) == 0

    assert (project / "demo.py").read_text(encoding="utf-8") == ORIGINAL

    monkeypatch.setattr(
        "builtins.input",
        lambda prompt: "yes",
    )

    assert cli.main(review_args(db_path, thread_id)) == 0

    output = capsys.readouterr().out

    assert "最终状态：applied" in output
    assert (project / "demo.py").read_text(encoding="utf-8") == MODIFIED


def test_eof_keeps_approval_pending(
    project: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """终端未提供输入时不能自动批准或拒绝。"""

    db_path = tmp_path / "approval.sqlite"
    thread_id = "eof-request"

    assert cli.main(prepare_args(project, db_path, thread_id)) == 0

    def raise_eof(prompt: str) -> str:
        raise EOFError

    monkeypatch.setattr(
        "builtins.input",
        raise_eof,
    )

    assert cli.main(review_args(db_path, thread_id)) == 2

    assert (project / "demo.py").read_text(encoding="utf-8") == ORIGINAL

    monkeypatch.setattr(
        "builtins.input",
        lambda prompt: "yes",
    )

    assert cli.main(review_args(db_path, thread_id)) == 0

    assert (project / "demo.py").read_text(encoding="utf-8") == MODIFIED


def test_changed_file_blocks_old_approval(
    project: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """审批期间文件变化，输入 yes 也不能强制覆盖。"""

    db_path = tmp_path / "approval.sqlite"
    thread_id = "stale-request"

    assert cli.main(prepare_args(project, db_path, thread_id)) == 0

    target = project / "demo.py"
    changed = ORIGINAL + "# later change\n"

    target.write_text(changed, encoding="utf-8")

    monkeypatch.setattr(
        "builtins.input",
        lambda prompt: "yes",
    )

    result = cli.main(review_args(db_path, thread_id))

    output = capsys.readouterr().out

    assert result == 1
    assert "最终状态：conflict" in output
    assert target.read_text(encoding="utf-8") == changed


def test_invalid_path_is_rejected(
    project: Path,
    tmp_path: Path,
) -> None:
    """不能通过 CLI 请求修改仓库外的文件。"""

    db_path = tmp_path / "approval.sqlite"

    result = cli.main(
        prepare_args(
            project,
            db_path,
            "bad-path",
            relative_path="../outside.py",
        )
    )

    assert result == 1
    assert (project / "demo.py").read_text(encoding="utf-8") == ORIGINAL


def test_duplicate_thread_id_is_rejected(
    project: Path,
    tmp_path: Path,
) -> None:
    """同一个审批 ID 不能覆盖已经存在的审批任务。"""

    db_path = tmp_path / "approval.sqlite"
    args = prepare_args(project, db_path, "same-id")

    assert cli.main(args) == 0
    assert cli.main(args) == 1

    assert (project / "demo.py").read_text(encoding="utf-8") == ORIGINAL


def test_review_missing_database(
    tmp_path: Path,
) -> None:
    """不能恢复不存在的 SQLite 审批数据库。"""

    result = cli.main(
        review_args(
            tmp_path / "not-exist.sqlite",
            "missing-request",
        )
    )

    assert result == 2


def test_help_contains_new_commands(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """顶层与子命令帮助包含审批入口。"""

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["edit-approval", "--help"])

    assert exc_info.value.code == 0

    output = capsys.readouterr().out

    assert "prepare" in output
    assert "review" in output
```

### 9.4 核心测试解释

**（1）`monkeypatch` 如何模拟人工输入？**

CLI 使用：

```python
input("请输入决定：")
```

但自动化测试不能要求测试人员每次键入 `yes`。

所以使用：

```python
monkeypatch.setattr(
    "builtins.input",
    lambda prompt: "yes",
)
```

模拟批准。

同理可以模拟：

```python
"no"
```

或者主动抛出：

```python
EOFError
```

这让 CLI 审批能够自动测试。

**（2）为什么 `test_eof_keeps_approval_pending()` 很重要？**

如果终端没有提供输入，程序应该保留待审批状态，而不是默认批准。

因此测试不仅检查 EOF 返回码，还要再次执行审批，证明原来的任务仍可恢复。

这对应实际操作中用户取消、终端关闭等情况。

**（3）为什么要测试文件发生变化？**

即使人工输入了：

```text
yes
```

也不能无条件写入。

如果文件版本已经变化，CodeEditor 和审批工作流必须拒绝应用旧修改。

这体现了：

**人工批准是必要条件，但不应是唯一条件。**

**（4）为什么要测试重复审批 ID？**

如果相同线程能够被新任务覆盖，就可能出现：

```text
用户审查的是任务 A
    ↓
状态被任务 B 覆盖
    ↓
用户批准
    ↓
实际执行的是任务 B
```

因此同一审批线程不能直接被新请求复用。

**（5）为什么 CLI 测试还要配合真实终端验收？**

pytest 通过 `monkeypatch` 模拟输入，能够稳定检查业务路径。

但实际终端验收还能检查：

- 命令是否正确注册。
- 参数是否正确解析。
- 输出是否清晰。
- 用户是否真的能输入。
- 两次独立进程能否恢复数据库状态。

两种验证不能完全相互替代。

### 9.5 验证

```bash
python -m pytest tests/cli/test_edit_approval.py -v
```

本阶段验证已通过。

---

## 10. 今日真实操作与验收记录

### 10.1 第一阶段自动化验收

执行：

```bash
python -m pytest tests/test_approval_workflow.py -v
```

验证了：

- 暂停后不创建文件。
- 人工批准后创建文件。
- 拒绝后不创建文件。
- 非法决定被拒绝。
- 已存在的文件不被覆盖。
- 路径穿越被拒绝。
- 审批期间出现文件冲突时不覆盖。
- 子目录仅在批准后创建。
- 不能重复恢复已完成任务。
- 不能复用已有审批线程。
- 不同线程隔离。
- SQLite 重新打开后恢复审批。

**结果：已通过。**

### 10.2 第二阶段自动化验收

执行：

```bash
python -m pytest tests/test_edit_approval_workflow.py -v
```

回归检查原有 CodeEditor：

```bash
python -m pytest tests/test_editor.py -v
```

重点验证：

- 已有文件修改前先生成 Diff。
- 未批准时不写入。
- 批准后正确执行替换。
- 拒绝后保留原文件。
- 原文件变化时旧审批失效。
- CodeEditor 路径保护继续生效。
- SQLite 可恢复待审批修改。

**结果：已通过。**

### 10.3 第三阶段自动化验收

执行：

```bash
python -m pytest tests/cli/test_edit_approval.py -v
```

验证 CLI 的准备、批准、拒绝、异常输入、文件冲突和数据库恢复。

**结果：已通过。**

### 10.4 实际 CLI 验收：批准

测试使用系统临时目录，不修改正式项目文件。

首先创建临时项目：

```bash
demo_root="$(mktemp -d)"

mkdir -p "$demo_root/project"

printf 'answer = 1\n' > "$demo_root/project/demo.py"

demo_db="$demo_root/approvals.sqlite"
```

准备审批：

```bash
ai-dev-agent edit-approval prepare \
  --project "$demo_root/project" \
  --file demo.py \
  --old "answer = 1" \
  --new "answer = 42" \
  --thread-id day12-approve-demo \
  --db "$demo_db"
```

审批前文件：

```python
answer = 1
```

生成 Diff：

```diff
--- a/demo.py
+++ b/demo.py
@@ -1 +1 @@
-answer = 1
+answer = 42
```

准备命令结束后，重新执行：

```bash
ai-dev-agent edit-approval review \
  --thread-id day12-approve-demo \
  --db "$demo_db"
```

终端输入：

```text
yes
```

预期：

```text
最终状态：applied
```

最终文件：

```python
answer = 42
```

**结果：真实验收已通过。**

### 10.5 实际 CLI 验收：拒绝

准备另一个文件：

```bash
printf 'answer = 1\n' > "$demo_root/project/rejected.py"
```

准备：

```bash
ai-dev-agent edit-approval prepare \
  --project "$demo_root/project" \
  --file rejected.py \
  --old "answer = 1" \
  --new "answer = 42" \
  --thread-id day12-reject-demo \
  --db "$demo_db"
```

恢复：

```bash
ai-dev-agent edit-approval review \
  --thread-id day12-reject-demo \
  --db "$demo_db"
```

输入：

```text
no
```

预期：

```text
最终状态：rejected
```

最终文件仍然是：

```python
answer = 1
```

**结果：真实验收已通过。**

---

## 11. 今日真实 Debug 记录

### 11.1 问题：交互演示触发 `EOFError`

第二阶段第一次进行人工体验时，使用了下面的命令形式：

```bash
python - <<'PY'
answer = input("是否批准修改？输入 yes 批准：")
PY
```

运行到审批阶段时，出现：

```text
EOFError: EOF when reading a line
```

### 11.2 错误现象

错误发生前，程序已经成功显示 Diff：

```diff
--- a/demo.py
+++ b/demo.py
@@ -1 +1 @@
-answer = 1
+answer = 42
```

并且显示了修改前的文件内容：

```python
answer = 1
```

随后执行：

```python
answer = input(...)
```

触发 `EOFError`。

### 11.3 原因分析

`python -` 表示：

**从标准输入 stdin 读取 Python 程序代码。**

`<<'PY'` 是 Shell 的 Here-document（此处文档），用于把多行内容传递给命令的标准输入。

而：

```python
input()
```

也需要从标准输入读取用户键盘输入。

因此出现了冲突：

```text
stdin
  │
  ├── 已用于提供 Python 源代码
  │
  └── input() 又尝试从同一输入流读取
              ↓
             EOFError
```

**这个错误不是 LangGraph 的 `interrupt()` 造成的，也不是 SQLite Checkpoint 失败。**

因为工作流已经成功准备 Diff，并执行到了终端采集人工决定的环节。

### 11.4 修复方式

将 Python 代码写入一个真正的脚本文件，再执行：

```bash
python demo_script.py
```

这样 Python 源码从文件读取，`input()` 可以正常使用终端标准输入。

为了避免污染项目，可使用临时脚本：

```bash
demo_script="$(mktemp)"

cat > "$demo_script" <<'PY'
answer = input("请输入 yes 或 no：")
print("你的输入是：", answer)
PY

python "$demo_script"

rm -f "$demo_script"
```

然后在真正的第三阶段，我们直接把人工输入放在 CLI 命令中：

```bash
ai-dev-agent edit-approval review ...
```

不再用 Here-document 运行交互式审批。

### 11.5 Debug 结论

以下方式适用于非交互 Python 脚本：

```bash
python - <<'PY'
print("hello")
PY
```

但如果脚本需要：

```python
input()
```

优先使用：

```bash
python script.py
```

或者正常运行的 CLI。

**本次不需要修改业务工作流代码，修复的是演示程序的启动方式。**

---

## 12. 今日知识点完整总结

### 12.1 核心 API

| API | 作用 |
|---|---|
| `interrupt()` | 暂停工作流，提交待审批内容 |
| `Command(resume=...)` | 将人工决定传给已暂停的图 |
| `SqliteSaver` | 将图状态持久化到 SQLite |
| `InMemorySaver` | 在内存中保存图状态，常用于测试 |
| `graph.get_state()` | 查询当前线程的状态快照 |
| `snapshot.next` | 查看图接下来等待执行的节点 |
| `add_conditional_edges()` | 根据状态选择不同分支 |
| `unified_diff()` | 生成代码差异 |
| `CodeEditor.preview_replace()` | 生成已有文件的修改预览 |
| `CodeEditor.apply()` | 应用经过校验的编辑方案 |
| `Path.resolve()` | 规范化路径 |
| `Path.is_relative_to()` | 检查路径包含关系 |
| `Path.open("x")` | 独占创建新文件，不覆盖已有文件 |
| `uuid4()` | 生成审批任务标识 |
| `shlex.quote()` | 安全引用 Shell 参数 |
| `monkeypatch` | 测试中模拟终端输入及外部依赖 |

### 12.2 HITL 与普通交互式输入的区别

普通 Python：

```python
answer = input("是否批准？")
```

这只是当前进程等待用户输入。

LangGraph：

```python
decision = interrupt({...})
```

配合 Checkpointer，可以让工作流暂停，并在新的执行调用中恢复。

**HITL 的重点不仅是采集用户输入，还包括保存执行状态、明确恢复位置及控制后续副作用。**

### 12.3 批准不代表可以无条件修改

第二阶段的执行条件是：

```text
用户批准
  AND
文件仍然是当时预览的版本
  AND
CodeEditor 校验通过
```

这三个条件必须同时满足。

如果文件变化了，就重新预览、重新审批。

### 12.4 为什么检查 SHA-256？

SHA-256 可以为原文件内容生成摘要。

如果文件发生变化，摘要通常也会改变。

因此它适合检测：

**用户批准时的文件，是否仍然是当前准备修改的文件。**

但 SHA-256 只是内容一致性检查，不是权限控制，也不能防止所有文件系统竞态。

### 12.5 为什么既要用业务测试，又要用 CLI 测试？

业务测试关注：

```text
状态转移是否正确？
写入前是否经过批准？
文件变化后是否拒绝？
```

CLI 测试关注：

```text
命令是否正确解析？
用户输入是否正确处理？
数据库是否正确重新打开？
错误是否清晰反馈？
```

真实终端验收关注：

```text
用户是否能按实际使用方式完成审批？
退出程序后，是否真的能恢复？
```

三者各有价值。

### 12.6 今天形成的工程原则

**原则一：有风险的操作应设计明确的人工审批边界。**

**原则二：展示给用户批准的内容，必须与最终准备执行的内容一致。**

**原则三：中断节点不应在 `interrupt()` 之前执行有副作用的操作。**

**原则四：审批结果必须是明确决定，不能把任意非空输入当作批准。**

**原则五：批准、拒绝、取消、冲突应具有不同语义。**

**原则六：持久化与恢复不等于可以安全重复执行所有外部操作。**

**原则七：扩展已有项目时，优先复用现有能力并采用增量修改。**

---

## 13. 当前实现的局限与后续方向

本日实现满足学习目标，但还不是完整生产级审批系统。

当前没有实现：

- 审批者身份认证和权限分级。
- 审批任务列表与搜索。
- 审批任务到期策略。
- 完整审计日志与审批历史管理。
- 多人协同审批。
- 多文件原子事务。
- 对任意 Shell 命令的审批。
- 完整文件系统竞态保护。
- 将人工审批强制应用到 Agent 的所有可能写入路径。
- 文件修改失败后的完整事务回滚。
- 自动生成复杂多文件修改方案并统一审批。

其中尤其需要理解：

**当前已实现“通过审批 CLI 进行受控文件修改”，不代表整个 AI Agent 的所有文件写入路径已经被强制纳入审批。**

未来如果让 Agent 自动规划和执行代码修改，需要确保真正的写入工具只能经过审批流程，不能再由模型直接绕过。

这属于后续完整软件开发 Agent 的架构设计问题。

---

## 14. 今日最终总结

### 14.1 我们实现了什么？

Day 12 完成三个阶段：

**第一阶段**

实现新建文件的人工审批工作流。

**第二阶段**

复用 CodeEditor，实现已有文件修改的 Diff 审批和 SHA-256 版本保护。

**第三阶段**

增加 `edit-approval prepare/review` CLI，支持 SQLite 保存等待中的审批任务，以及跨进程恢复。

### 14.2 和前面学习内容的关系

Day 08 学到：

**如何使用 LangGraph 编排工作流？**

Day 10 学到：

**如何根据执行结果决定下一步？**

Day 11 学到：

**如何保存和恢复工作流状态？**

Day 12 学到：

**如何让工作流在敏感操作前暂停，等待人工决定，再根据审批结果安全地继续？**

这些能力已经开始组合成一个更完整的 Agent 执行系统。

### 14.3 今日最重要的认识

一个软件开发 Agent 不应该只追求“会自动修改代码”。

更重要的是：

**它应该知道什么时候不能直接修改，应该向用户展示什么，以及在获得批准后如何保证执行的仍然是用户审查过的那项修改。**

这才是 Human-in-the-Loop 在软件开发 Agent 中的真正意义。

**Day 12 完成。**

后续学习继续围绕原定 18 天路线，逐步将规划、代码编辑、测试、审批、错误处理与持久化会话组合为完整的软件开发 Agent。