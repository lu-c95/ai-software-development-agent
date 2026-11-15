# Day 11｜Checkpoint & Session Persistence

**项目：AI Software Development Agent**

**日期：2026-11-15**

**主题：LangGraph 检查点与会话持久化**

**状态：功能开发、真实 CLI 验收、最终全量回归测试已通过**

---

## 1. 今日学习目标与整体设计

### 1.1 为什么需要会话持久化？

Day 05 已实现多轮 CLI 聊天，能够在同一个 Python 进程中保留聊天历史。

原来的工作方式：

```text
启动 chat
    ↓
创建 Agent
    ↓
用户输入问题
    ↓
调用模型和工具
    ↓
history 保存在内存
    ↓
继续下一轮
```

但是当程序退出时：

```text
Python 进程结束
    ↓
内存中的 history 消失
    ↓
再次启动无法自动恢复旧对话
```

因此，Day 11 的核心任务是：

**让 Agent 的状态保存在持久化存储中，使 CLI 退出后能够恢复之前的会话。**

### 1.2 今日完成的两阶段开发

**第一阶段：Checkpoint 基础**

使用：

- `MessagesState`
- `SqliteSaver`
- `thread_id`
- `graph.invoke()`
- `graph.get_state()`

实现一个独立的无工具对话图，理解 LangGraph 如何保存、恢复状态。

**第二阶段：集成现有开发 Agent**

在 Day 05 原有工具 Agent 的基础上：

- 增加 SQLite Checkpointer。
- 在现有 `chat` 命令中支持 `--session`。
- 使用 `--db` 指定数据库位置。
- 支持跨进程恢复聊天。
- 支持 `/new`、`/session`、`/history`。
- 保留原有临时对话模式。
- 保留原有工具输出及 CLI 接口。

### 1.3 最终架构

```text
ai-dev-agent chat
         │
         ▼
是否提供 --session？
         │
         ├── 否：临时聊天
         │        │
         │        ▼
         │    Day 05 原有 Agent
         │        │
         │        ▼
         │    内存 history
         │        │
         │        ▼
         │    退出后历史消失
         │
         └── 是：持久化聊天
                  │
                  ▼
              打开 SQLite
                  │
                  ▼
        创建带 Checkpointer 的 Agent
                  │
                  ▼
        根据 thread_id 读取旧 State
                  │
                  ▼
              用户输入问题
                  │
                  ▼
            Agent 调用模型/工具
                  │
                  ▼
              保存 Checkpoint
                  │
                  ▼
               输出回答
                  │
                  ▼
         退出后仍可恢复该会话
```

### 1.4 今日文件清单

```text
ai-software-development-agent/
│
├── pyproject.toml
│
├── src/ai_software_dev_agent/
│   ├── persistent_chat.py
│   ├── persistent_agent.py
│   └── commands/
│       └── chat.py
│
├── tests/
│   ├── test_persistent_chat.py
│   ├── test_persistent_agent.py
│   └── cli/
│       └── test_chat_persistence.py
│
└── docs/
    └── Day11-Checkpoint-And-Session-Persistence.md
```

本日没有必要修改统一入口 `cli.py`，因为 `chat` 子命令此前已注册。

### 1.5 开发环境

项目目录：

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

确认当前 Python 来自项目 `.venv`。

---

## 2. 文件一：`pyproject.toml`

### 2.1 文件职责

今天需要为 LangGraph 增加 SQLite Checkpoint 支持。

相关依赖：

| 依赖 | 作用 |
|---|---|
| `langgraph` | 图的构建、执行与状态管理 |
| `langgraph-checkpoint-sqlite` | SQLite 持久化实现 |
| `sqlite3` | Python 标准库中的 SQLite 接口 |

`sqlite3` 不需要单独安装，但 `SqliteSaver` 所在的扩展包需要添加到项目依赖。

### 2.2 打开与修改

```bash
nano pyproject.toml
```

找到已有的：

```toml
[project]
```

在原有 `dependencies` 列表中增加：

```toml
"langgraph-checkpoint-sqlite>=3.0,<4.0",
```

这是本日对该文件的全部修改。

不重写其他配置项，不删除已有的 LangChain、LangGraph 或项目依赖。

由于今天没有读取本地完整 `pyproject.toml`，这里仅记录实际需要的增量配置，不凭空构造完整配置文件。

### 2.3 安装与检查

```bash
python -m pip install -e .
```

检查：

```bash
python -m pip show langgraph-checkpoint-sqlite
```

验证：

```bash
python -c "from langgraph.checkpoint.sqlite import SqliteSaver; print('SQLite Checkpointer 可用')"
```

### 2.4 代码解释

`pip install -e .` 表示以 Editable Installation（可编辑安装）方式安装当前项目。

这样可以在开发时直接使用本地源码，而不需要每次修改 Python 文件都重新打包安装。

`SqliteSaver` 是 LangGraph 的 Checkpointer 实现，它负责把图状态保存到 SQLite 中。

SQLite 是数据库，Checkpointer 是 LangGraph 与数据库之间的持久化组件，两者不是同一个概念。

### 2.5 注意事项

- 这是已有配置文件，只做增量修改。
- 数据库引擎不需要单独安装。
- 本日使用同步 SQLite Checkpointer。
- 当前主要面向本地 CLI，而不是高并发生产环境。
- 会话数据库文件属于运行数据，不能作为源代码提交。
- 后续升级依赖需要重新运行兼容性测试。

---

## 3. 文件二：`src/ai_software_dev_agent/persistent_chat.py`

### 3.1 文件职责

这是第一阶段的核心学习文件。

实现一个独立的、没有工具调用能力的持久化对话图，用于理解：

- LangGraph 消息状态。
- Checkpointer 绑定。
- `thread_id` 会话隔离。
- 历史消息自动合并。
- 跨进程状态恢复。

这个文件用于学习持久化原理，不取代原有开发 Agent。

### 3.2 创建与打开

首次创建：

```bash
touch src/ai_software_dev_agent/persistent_chat.py
```

打开：

```bash
nano src/ai_software_dev_agent/persistent_chat.py
```

### 3.3 完整代码

```python
"""Day 11：使用 LangGraph Checkpoint 持久化对话历史。"""

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)
from langchain_core.runnables import Runnable
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph


SYSTEM_PROMPT = (
    "你是一名 Python 软件开发学习助手。"
    "请结合当前会话中已经出现的历史消息回答问题。"
    "如果历史中没有相关信息，请明确说明不知道。"
    "不要声称已经调用工具、运行测试或修改文件。"
    "使用简体中文回答。"
)


def build_persistent_chat_graph(
    model: Runnable,
    checkpointer: BaseCheckpointSaver,
) -> CompiledStateGraph:
    """创建支持 Checkpoint 的对话工作流。"""

    def respond_node(
        state: MessagesState,
    ) -> dict[str, list[AIMessage]]:
        """读取当前会话历史，并生成下一条回答。"""

        # 系统提示词每次传给模型，但不重复保存到对话历史。
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            *state["messages"],
        ]

        response = model.invoke(messages)

        # 当前是无工具对话节点，必须获得最终 AI 消息。
        if not isinstance(response, AIMessage) or response.tool_calls:
            raise ValueError("模型没有返回有效的最终 AI 消息")

        return {"messages": [response]}

    builder = StateGraph(MessagesState)

    builder.add_node("respond", respond_node)

    builder.add_edge(START, "respond")
    builder.add_edge("respond", END)

    # 编译时绑定持久化组件。
    return builder.compile(checkpointer=checkpointer)


def run_persistent_turn(
    graph: CompiledStateGraph,
    thread_id: str,
    question: str,
) -> tuple[str, list[BaseMessage]]:
    """执行指定会话的一轮对话。"""

    clean_thread_id = thread_id.strip()
    clean_question = question.strip()

    if not clean_thread_id:
        raise ValueError("会话 ID 不能为空")

    if not clean_question:
        raise ValueError("用户问题不能为空")

    config = {
        "configurable": {
            "thread_id": clean_thread_id,
        }
    }

    # 只传入当前新增的用户消息。
    # 历史会通过 Checkpointer 自动恢复。
    result = graph.invoke(
        {
            "messages": [
                HumanMessage(content=clean_question),
            ]
        },
        config=config,
    )

    history = list(result["messages"])
    last_message = history[-1]

    if not isinstance(last_message, AIMessage) or last_message.tool_calls:
        raise ValueError("工作流未返回有效的最终 AI 消息")

    return str(last_message.text), history
```

### 3.4 核心代码解释

**（1）`MessagesState` 是什么？**

```python
from langgraph.graph import MessagesState
```

它是 LangGraph 提供的消息状态结构，专门管理对话消息。

相比普通列表，`MessagesState` 已经包含用于合并消息的 Reducer。

所以节点只需要返回：

```python
return {"messages": [response]}
```

就可以将新消息更新到 State 中。

不需要自己重新拼接完整历史。

**（2）为什么使用 `add_messages`？**

`MessagesState` 内置的消息 Reducer 是 `add_messages`。

它不仅能够追加消息，还能够根据消息 ID 更新已有消息。

与 Day 10 使用的：

```python
Annotated[list[str], operator.add]
```

相比，`add_messages` 更适合聊天消息管理。

**（3）Checkpoint 在哪里绑定？**

最关键的代码：

```python
builder.compile(checkpointer=checkpointer)
```

之前普通工作流使用：

```python
builder.compile()
```

Day 11 则在编译时传入 Checkpointer，让工作流具备保存和恢复状态的能力。

**（4）`thread_id` 有什么作用？**

```python
config = {
    "configurable": {
        "thread_id": clean_thread_id,
    }
}
```

它标识具体会话。

例如：

```text
python-learning
agent-development
```

两者会保存各自的历史。

同一个 `thread_id` 再次执行时，会从对应的 Checkpoint 恢复状态。

**（5）为什么只传入新问题？**

```python
graph.invoke(
    {
        "messages": [
            HumanMessage(content=clean_question),
        ]
    },
    config=config,
)
```

因为旧历史已由 Checkpointer 加载。

如果再手动把旧历史作为新增输入传进去，可能造成消息重复。

**（6）为什么系统提示词不保存在 State 中？**

```python
messages = [
    SystemMessage(content=SYSTEM_PROMPT),
    *state["messages"],
]
```

系统提示词每轮调用模型时提供。

但节点只返回新的 AI 回答：

```python
{"messages": [response]}
```

这样不会每轮都把相同系统提示词重复保存。

### 3.5 注意事项

- 当前是无工具的教学图。
- 模型响应必须是有效 `AIMessage`。
- Checkpoint 保存状态，不等于实现完整的长期记忆系统。
- 消息历史会不断增长，未来需要考虑上下文裁剪。
- 模型请求失败时，仍可能留下部分 Checkpoint。
- 不能把某一轮执行失败直接等同于数据库没有变化。

### 3.6 对应测试

测试文件：

```text
tests/test_persistent_chat.py
```

执行：

```bash
python -m pytest tests/test_persistent_chat.py -v
```

完整测试代码与解释在下一条目。

---

## 4. 文件三：`tests/test_persistent_chat.py`

### 4.1 文件职责

验证第一阶段的基础持久化功能：

- 关闭并重新打开 SQLite 后，历史仍然存在。
- 同一个会话可以继续。
- 不同会话互不干扰。
- 能够通过 `get_state()` 查看保存的状态。
- 空输入被正确拒绝。
- 无效模型响应不能被误判为成功。

### 4.2 创建与打开

首次创建：

```bash
touch tests/test_persistent_chat.py
```

打开：

```bash
nano tests/test_persistent_chat.py
```

### 4.3 完整测试代码

```python
"""Day 11：LangGraph Checkpoint 与会话持久化测试。"""

from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableLambda
from langgraph.checkpoint.sqlite import SqliteSaver

from ai_software_dev_agent.persistent_chat import (
    build_persistent_chat_graph,
    run_persistent_turn,
)


def create_fake_model() -> RunnableLambda:
    """创建能够感知历史用户消息数量的模拟模型。"""

    def respond(messages: list) -> AIMessage:
        user_messages = [
            message for message in messages if isinstance(message, HumanMessage)
        ]

        last_question = str(user_messages[-1].content)

        return AIMessage(
            content=(
                f"这是第 {len(user_messages)} 轮用户消息，本轮问题：{last_question}"
            )
        )

    return RunnableLambda(respond)


def test_session_survives_database_reopen(
    tmp_path: Path,
) -> None:
    """关闭数据库后重新打开，同一会话仍保留历史。"""

    db_path = tmp_path / "checkpoints.sqlite"

    # 第一次打开数据库。
    with SqliteSaver.from_conn_string(str(db_path)) as saver:
        graph = build_persistent_chat_graph(
            create_fake_model(),
            saver,
        )

        answer, history = run_persistent_turn(
            graph,
            thread_id="python-learning",
            question="我正在学习 LangGraph",
        )

        assert "第 1 轮" in answer
        assert len(history) == 2

    assert db_path.is_file()

    # 第二次重新打开同一数据库。
    with SqliteSaver.from_conn_string(str(db_path)) as saver:
        graph = build_persistent_chat_graph(
            create_fake_model(),
            saver,
        )

        answer, history = run_persistent_turn(
            graph,
            thread_id="python-learning",
            question="现在学习 Checkpoint",
        )

        assert "第 2 轮" in answer
        assert len(history) == 4

        assert isinstance(history[0], HumanMessage)
        assert history[0].content == "我正在学习 LangGraph"

        assert isinstance(history[1], AIMessage)

        assert isinstance(history[2], HumanMessage)
        assert history[2].content == "现在学习 Checkpoint"

        assert isinstance(history[3], AIMessage)


def test_different_threads_are_isolated(
    tmp_path: Path,
) -> None:
    """不同 thread_id 应维护独立的会话历史。"""

    db_path = tmp_path / "checkpoints.sqlite"

    with SqliteSaver.from_conn_string(str(db_path)) as saver:
        graph = build_persistent_chat_graph(
            create_fake_model(),
            saver,
        )

        first_answer, _ = run_persistent_turn(
            graph,
            "session-a",
            "A 的第一轮",
        )

        second_answer, _ = run_persistent_turn(
            graph,
            "session-a",
            "A 的第二轮",
        )

        other_answer, other_history = run_persistent_turn(
            graph,
            "session-b",
            "B 的第一轮",
        )

        assert "第 1 轮" in first_answer
        assert "第 2 轮" in second_answer

        assert "第 1 轮" in other_answer
        assert len(other_history) == 2
        assert other_history[0].content == "B 的第一轮"


def test_checkpoint_can_be_inspected(
    tmp_path: Path,
) -> None:
    """通过 get_state() 检查保存的会话。"""

    db_path = tmp_path / "checkpoints.sqlite"

    with SqliteSaver.from_conn_string(str(db_path)) as saver:
        graph = build_persistent_chat_graph(
            create_fake_model(),
            saver,
        )

        run_persistent_turn(
            graph,
            "inspect-session",
            "请记住这个问题",
        )

        config = {
            "configurable": {
                "thread_id": "inspect-session",
            }
        }

        snapshot = graph.get_state(config)

        messages = snapshot.values["messages"]

        assert len(messages) == 2
        assert messages[0].content == "请记住这个问题"
        assert isinstance(messages[1], AIMessage)

        assert snapshot.next == ()


@pytest.mark.parametrize(
    ("thread_id", "question", "expected_error"),
    [
        ("   ", "你好", "会话 ID 不能为空"),
        ("session-a", "   ", "用户问题不能为空"),
    ],
)
def test_rejects_blank_inputs(
    tmp_path: Path,
    thread_id: str,
    question: str,
    expected_error: str,
) -> None:
    """空会话 ID 和空问题应提前拒绝。"""

    db_path = tmp_path / "checkpoints.sqlite"

    with SqliteSaver.from_conn_string(str(db_path)) as saver:
        graph = build_persistent_chat_graph(
            create_fake_model(),
            saver,
        )

        with pytest.raises(ValueError, match=expected_error):
            run_persistent_turn(
                graph,
                thread_id,
                question,
            )


def test_rejects_invalid_model_response(
    tmp_path: Path,
) -> None:
    """模型返回无效消息时，不能报告成功。"""

    db_path = tmp_path / "checkpoints.sqlite"

    invalid_model = RunnableLambda(lambda messages: "这不是 AIMessage")

    with SqliteSaver.from_conn_string(str(db_path)) as saver:
        graph = build_persistent_chat_graph(
            invalid_model,
            saver,
        )

        with pytest.raises(
            ValueError,
            match="有效的最终 AI 消息",
        ):
            run_persistent_turn(
                graph,
                "invalid-response",
                "你好",
            )
```

### 4.4 核心代码解释

**（1）`tmp_path` 为什么重要？**

```python
db_path = tmp_path / "checkpoints.sqlite"
```

pytest 会为测试创建临时目录。

这样测试数据库不会污染项目，也不会误使用真正的用户会话数据库。

**（2）为什么要关闭再打开数据库？**

```python
with SqliteSaver.from_conn_string(str(db_path)) as saver:
```

第一次运行结束后连接关闭。

第二次重新创建 Checkpointer、Graph 和模型对象。

如果还能恢复第一轮消息，说明历史确实保存在 SQLite 中。

**（3）如何证明不同会话隔离？**

同一数据库中分别使用：

```text
session-a
session-b
```

如果 `session-b` 的第一轮仍然被识别为第一轮，就说明没有继承 `session-a` 的历史。

**（4）`graph.get_state()` 的作用是什么？**

```python
snapshot = graph.get_state(config)
```

读取指定线程保存的状态。

例如：

```python
snapshot.values["messages"]
```

表示消息历史。

```python
snapshot.next
```

表示快照之后仍然等待执行的节点。

当前简单对话图正常完成后通常为空元组。

**（5）为什么需要错误测试？**

空会话 ID、空问题和无效模型响应都应该被明确拒绝。

不能因为程序没有崩溃，就认为回答有效。

### 4.5 注意事项

- 使用模拟模型，不调用真实 API。
- SQLite 关闭后重新打开可以验证持久化，但不是完整的真实 CLI 验收。
- 测试中不依赖固定系统时间。
- Checkpoint 可能包含中间状态，不一定只有最终成功状态。

### 4.6 验证命令

```bash
python -m pytest tests/test_persistent_chat.py -v
```

本日最终相关测试已通过。

---

## 5. 文件四：`src/ai_software_dev_agent/persistent_agent.py`

### 5.1 文件职责

第一阶段只是独立的无工具对话图。

第二阶段需要让原有开发 Agent 也具备持久化能力。

本文件负责：

- 复用 Day 05 的系统提示词。
- 复用 Day 05 的仓库工具。
- 创建带 Checkpointer 的工具 Agent。
- 生成带项目隔离的 `thread_id`。
- 获取已有会话历史。
- 执行一轮持久化 Agent 对话。

### 5.2 创建与打开

首次创建：

```bash
touch src/ai_software_dev_agent/persistent_agent.py
```

打开：

```bash
nano src/ai_software_dev_agent/persistent_agent.py
```

### 5.3 完整代码

```python
"""Day 11：为现有开发 Agent 添加检查点与会话持久化。"""

from pathlib import Path

from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph

from ai_software_dev_agent.agent import (
    AGENT_SYSTEM_PROMPT,
    AgentExecutionError,
    create_repository_tools,
)
from ai_software_dev_agent.model import ModelConfigError


# 与 Day 05 原有 Agent 保持一致的执行步数限制。
AGENT_RECURSION_LIMIT = 12


def build_persistent_development_agent(
    model: BaseChatModel,
    project: Path,
    checkpointer: BaseCheckpointSaver,
) -> CompiledStateGraph:
    """创建保留原有仓库工具的持久化 Agent。"""

    tools = create_repository_tools(project)

    return create_agent(
        model=model,
        tools=tools,
        system_prompt=AGENT_SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )


def make_session_config(
    project: Path,
    session_id: str,
) -> dict:
    """生成按项目隔离的会话配置。"""

    clean_session_id = session_id.strip()

    if not clean_session_id:
        raise ValueError("会话 ID 不能为空")

    project_key = project.expanduser().resolve().as_posix()

    thread_id = f"{project_key}::{clean_session_id}"

    return {
        "configurable": {
            "thread_id": thread_id,
        },
        "recursion_limit": AGENT_RECURSION_LIMIT,
    }


def get_persistent_agent_history(
    agent: CompiledStateGraph,
    project: Path,
    session_id: str,
) -> list[BaseMessage]:
    """读取指定项目和指定会话的保存历史。"""

    config = make_session_config(project, session_id)

    snapshot = agent.get_state(config)

    return list(snapshot.values.get("messages", []))


def run_persistent_agent_turn(
    agent: CompiledStateGraph,
    project: Path,
    session_id: str,
    question: str,
) -> tuple[str, list[BaseMessage]]:
    """执行一轮持久化工具 Agent 对话。"""

    clean_question = question.strip()

    if not clean_question:
        raise ModelConfigError("用户问题不能为空")

    config = make_session_config(project, session_id)

    # 只提交新消息，由 Checkpointer 恢复原有历史。
    result = agent.invoke(
        {
            "messages": [
                HumanMessage(content=clean_question),
            ]
        },
        config=config,
    )

    messages = list(result["messages"])

    if not messages:
        raise AgentExecutionError("Agent 没有返回任何消息")

    last_message = messages[-1]

    if not isinstance(last_message, AIMessage) or last_message.tool_calls:
        raise AgentExecutionError("Agent 未返回有效的最终回答")

    return str(last_message.text), messages
```

### 5.4 核心代码解释

**（1）为什么要复用 Day 05 的工具？**

```python
tools = create_repository_tools(project)
```

原有的仓库工具包括：

```text
inspect_repository
read_repository_file
```

本次只是增加持久化，不重新实现这些工具。

避免出现两套工具定义，导致维护困难或行为不一致。

**（2）为什么不再直接使用 `run_agent_turn()`？**

Day 05 的 `run_agent_turn()` 依赖手动管理历史：

```python
messages = [
    *history,
    HumanMessage(content=question),
]
```

而持久化 Agent 会通过 Checkpointer 自动恢复历史。

如果继续手动传入完整历史，容易重复追加旧消息。

因此只提交本轮新问题。

**（3）如何防止不同项目混用同名会话？**

```python
project_key = project.expanduser().resolve().as_posix()

thread_id = f"{project_key}::{clean_session_id}"
```

例如：

```text
/project-a::learning

/project-b::learning
```

虽然会话名称相同，但项目路径不同。

因此对应不同的线程状态。

**（4）为什么保留原有递归限制？**

```python
AGENT_RECURSION_LIMIT = 12
```

为了保持原有 Agent 的执行预算行为。

Day 11 不处理 Day 09 已经发现的复杂任务连续工具调用问题。

Checkpoint 不会自动解决 `GraphRecursionError`。

**（5）`get_persistent_agent_history()` 的作用是什么？**

```python
snapshot = agent.get_state(config)
```

可以读取当前线程的历史。

例如 CLI 启动时显示：

```text
当前会话：python-learning
已恢复用户消息：2 轮
```

不需要通过模型请求确认历史是否存在。

### 5.5 注意事项

- 项目目录移动或改名后，`thread_id` 可能变化。
- 保存的历史可能包含工具调用记录和源码内容。
- Checkpoint 不等于自动任务恢复。
- 有副作用的工具未来需要考虑幂等性。
- 模型执行失败后，可能存在中间 Checkpoint。
- 不要把数据库视为可以安全导入的任意外部文件。

### 5.6 对应测试

```bash
python -m pytest tests/test_persistent_agent.py -v
```

测试内容在下一条目。

---

## 6. 文件五：`tests/test_persistent_agent.py`

### 6.1 文件职责

验证真正的工具 Agent 在持久化模式下是否保持正确行为。

包括：

- 重新打开 SQLite 后恢复历史。
- 不同会话互相隔离。
- 不同项目中的同名会话互相隔离。
- 原有仓库工具仍然注册。
- 无效输入能够正确拒绝。

### 6.2 创建与打开

首次创建：

```bash
touch tests/test_persistent_agent.py
```

打开：

```bash
nano tests/test_persistent_agent.py
```

### 6.3 完整测试代码

```python
"""Day 11：持久化开发 Agent 的业务测试。"""

from pathlib import Path
from typing import Any

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.sqlite import SqliteSaver

from ai_software_dev_agent import persistent_agent
from ai_software_dev_agent.persistent_agent import (
    build_persistent_development_agent,
    get_persistent_agent_history,
    run_persistent_agent_turn,
)


class EchoToolModel(BaseChatModel):
    """支持工具绑定，但不实际执行工具的测试模型。"""

    @property
    def _llm_type(self) -> str:
        return "day11-echo-model"

    def bind_tools(self, tools: Any, **kwargs: Any) -> Any:
        """兼容 LangChain Agent 的工具绑定接口。"""
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        """根据历史用户消息数量生成回答。"""

        user_messages = [
            message for message in messages if isinstance(message, HumanMessage)
        ]

        last_question = user_messages[-1].content

        answer = AIMessage(
            content=(f"第 {len(user_messages)} 轮，当前问题：{last_question}")
        )

        return ChatResult(
            generations=[
                ChatGeneration(message=answer),
            ]
        )


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    """创建可供仓库探索使用的测试项目。"""

    (tmp_path / "demo.py").write_text(
        "def hello():\n    return 'hello'\n",
        encoding="utf-8",
    )

    return tmp_path


def test_persistent_agent_survives_reopen(
    sample_project: Path,
) -> None:
    """重新打开数据库后，继续原有 Agent 会话。"""

    database = sample_project / "sessions.sqlite"

    with SqliteSaver.from_conn_string(str(database)) as saver:
        agent = build_persistent_development_agent(
            EchoToolModel(),
            sample_project,
            saver,
        )

        answer, history = run_persistent_agent_turn(
            agent,
            sample_project,
            "learning",
            "第一轮",
        )

        assert "第 1 轮" in answer
        assert len(history) == 2

    with SqliteSaver.from_conn_string(str(database)) as saver:
        agent = build_persistent_development_agent(
            EchoToolModel(),
            sample_project,
            saver,
        )

        saved = get_persistent_agent_history(
            agent,
            sample_project,
            "learning",
        )

        assert len(saved) == 2
        assert saved[0].content == "第一轮"

        answer, history = run_persistent_agent_turn(
            agent,
            sample_project,
            "learning",
            "第二轮",
        )

        assert "第 2 轮" in answer
        assert len(history) == 4


def test_sessions_are_isolated(
    sample_project: Path,
) -> None:
    """不同会话名不应该共享历史。"""

    database = sample_project / "sessions.sqlite"

    with SqliteSaver.from_conn_string(str(database)) as saver:
        agent = build_persistent_development_agent(
            EchoToolModel(),
            sample_project,
            saver,
        )

        run_persistent_agent_turn(
            agent,
            sample_project,
            "session-a",
            "A 的第一轮",
        )

        answer, history = run_persistent_agent_turn(
            agent,
            sample_project,
            "session-b",
            "B 的第一轮",
        )

        assert "第 1 轮" in answer
        assert len(history) == 2
        assert history[0].content == "B 的第一轮"


def test_same_session_name_in_different_projects(
    tmp_path: Path,
) -> None:
    """不同项目使用同名会话时仍然隔离。"""

    first = tmp_path / "project-a"
    second = tmp_path / "project-b"

    first.mkdir()
    second.mkdir()

    (first / "demo.py").write_text(
        "x = 1\n",
        encoding="utf-8",
    )

    (second / "demo.py").write_text(
        "y = 2\n",
        encoding="utf-8",
    )

    database = tmp_path / "sessions.sqlite"

    with SqliteSaver.from_conn_string(str(database)) as saver:
        first_agent = build_persistent_development_agent(
            EchoToolModel(),
            first,
            saver,
        )

        second_agent = build_persistent_development_agent(
            EchoToolModel(),
            second,
            saver,
        )

        run_persistent_agent_turn(
            first_agent,
            first,
            "learning",
            "项目 A 的消息",
        )

        answer, history = run_persistent_agent_turn(
            second_agent,
            second,
            "learning",
            "项目 B 的消息",
        )

        assert "第 1 轮" in answer
        assert len(history) == 2
        assert history[0].content == "项目 B 的消息"


def test_original_repository_tools_are_registered(
    sample_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """持久化 Agent 仍然注册 Day 05 的仓库工具。"""

    observed: dict[str, object] = {}

    def fake_create_agent(
        *,
        model: Any,
        tools: Any,
        system_prompt: str,
        checkpointer: Any,
    ) -> object:
        observed["tool_names"] = [tool.name for tool in tools]

        observed["system_prompt"] = system_prompt
        observed["checkpointer"] = checkpointer

        return object()

    monkeypatch.setattr(
        persistent_agent,
        "create_agent",
        fake_create_agent,
    )

    with SqliteSaver.from_conn_string(":memory:") as saver:
        persistent_agent.build_persistent_development_agent(
            EchoToolModel(),
            sample_project,
            saver,
        )

        tool_names = observed["tool_names"]

        assert "inspect_repository" in tool_names
        assert "read_repository_file" in tool_names
        assert observed["checkpointer"] is saver


@pytest.mark.parametrize(
    ("session_id", "question", "message"),
    [
        ("  ", "你好", "会话 ID 不能为空"),
        ("learning", "  ", "用户问题不能为空"),
    ],
)
def test_invalid_input(
    sample_project: Path,
    session_id: str,
    question: str,
    message: str,
) -> None:
    """无效会话名和空问题应被拒绝。"""

    with SqliteSaver.from_conn_string(":memory:") as saver:
        agent = build_persistent_development_agent(
            EchoToolModel(),
            sample_project,
            saver,
        )

        with pytest.raises(ValueError, match=message):
            run_persistent_agent_turn(
                agent,
                sample_project,
                session_id,
                question,
            )
```

### 6.4 核心代码解释

**（1）为什么 `EchoToolModel` 要继承 `BaseChatModel`？**

```python
class EchoToolModel(BaseChatModel):
```

因为 LangChain Agent 需要聊天模型支持工具绑定。

例如：

```python
model.bind_tools(tools)
```

普通的 `RunnableLambda` 不一定满足完整聊天模型接口。

**（2）`_generate()` 有什么作用？**

这是模拟模型生成回复的方法。

我们根据历史中用户消息的数量返回：

```text
第 1 轮
第 2 轮
```

如果第二次重新打开数据库后返回“第 2 轮”，就说明旧消息已恢复。

**（3）为什么要测试工具注册？**

持久化不能以牺牲原有 Agent 能力为代价。

所以检查：

```python
assert "inspect_repository" in tool_names
assert "read_repository_file" in tool_names
```

确保原有工具没有因为重构而被遗漏。

**（4）为什么要测试跨项目隔离？**

因为我们将：

```python
project_path
```

与：

```python
session_id
```

一起用于生成 `thread_id`。

所以需要验证两个项目使用相同会话名时仍然独立。

### 6.5 注意事项

- 模拟模型没有实际调用工具。
- 这里验证的是工具注册和持久化，不是复杂工具调用的全部可靠性。
- 不依赖外部 API Key。
- 测试数据库使用临时路径。
- 真实模型仍需单独的 CLI 验收。

### 6.6 验证

```bash
python -m pytest tests/test_persistent_agent.py -v
```

---

## 7. 文件六：`src/ai_software_dev_agent/commands/chat.py`

### 7.1 文件职责

这是 Day 11 最重要的集成文件，也是最终 Debug 的主要问题来源。

它在原有 `chat` 命令中增加：

- 临时聊天和持久化聊天两种模式。
- `--session`。
- `--db`。
- `/session` 会话切换。
- `/history` 历史显示。
- SQLite 数据库生命周期管理。

同时必须保留 Day 05 已有的行为：

- `run_chat_session()` 入口。
- `run_agent_turn()` 的调用方式。
- 工具调用及工具返回显示。
- `/help`。
- `/new`。
- `/exit`。
- 未知命令提示。
- EOF 退出提示。
- Agent 执行失败后继续输入。

### 7.2 打开文件

本文件此前已存在，不需要重新创建。

```bash
nano src/ai_software_dev_agent/commands/chat.py
```

**本次最终版本的核心原则：保留原有接口，采用兼容包装函数，而不是删除旧接口。**

### 7.3 根据最终修复记录整理的完整代码

```python
"""交互式开发 Agent CLI，支持临时会话和 SQLite 持久化。"""

import argparse
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    ToolMessage,
)
from langchain_core.runnables import Runnable
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.errors import GraphRecursionError
from openai import OpenAIError

from ai_software_dev_agent.agent import (
    AgentExecutionError,
    build_development_agent,
    run_agent_turn,
)
from ai_software_dev_agent.commands._common import add_project_argument
from ai_software_dev_agent.model import (
    ModelConfigError,
    create_chat_model,
    load_model_settings,
)
from ai_software_dev_agent.persistent_agent import (
    build_persistent_development_agent,
    get_persistent_agent_history,
    run_persistent_agent_turn,
)
from ai_software_dev_agent.repository import (
    RepositoryError,
    RepositoryExplorer,
)


# 默认数据库位于用户主目录，不放在 Git 仓库中。
DEFAULT_DB_PATH = Path.home() / ".ai-software-development-agent" / "sessions.sqlite"


def print_help(persistent: bool) -> None:
    """显示当前聊天模式支持的命令。"""

    print("\n可用指令：")
    print("  /help       显示帮助")
    print("  /new        开始新会话")
    print("  /history    显示最近的对话消息")
    print("  /exit       退出聊天")

    if persistent:
        print("  /session ID 切换或恢复指定会话")

    print()


def print_recent_history(
    history: list[BaseMessage],
    limit: int = 8,
) -> None:
    """显示最近的用户消息与最终 AI 回答。"""

    visible_messages = [
        message
        for message in history
        if isinstance(message, HumanMessage)
        or (isinstance(message, AIMessage) and not message.tool_calls)
    ]

    if not visible_messages:
        print("当前没有对话历史。")
        return

    for message in visible_messages[-limit:]:
        role = "你" if isinstance(message, HumanMessage) else "AI"
        print(f"{role}：{str(message.text)[:300]}")


def interactive_chat(
    agent: Runnable,
    project: Path,
    session_id: str | None = None,
) -> int:
    """执行交互式聊天循环。"""

    # 临时聊天使用内存列表保存历史。
    history: list[BaseMessage] = []

    if session_id is None:
        print("已进入临时聊天模式，退出后不保留历史。")

    else:
        saved = get_persistent_agent_history(
            agent,
            project,
            session_id,
        )

        turns = sum(isinstance(message, HumanMessage) for message in saved)

        print(f"当前会话：{session_id}")
        print(f"已恢复用户消息：{turns} 轮")

    print("输入 /help 查看指令，输入 /exit 退出。")

    while True:
        try:
            question = input("\n你：").strip()

        except EOFError:
            # 保留原有 CLI 退出提示。
            print("\n再见，聊天已结束。")
            return 0

        except KeyboardInterrupt:
            print("\n聊天已中断。")
            return 130

        if not question:
            continue

        if question in {"/exit", "/quit"}:
            print("已退出聊天。")
            return 0

        if question == "/help":
            print_help(session_id is not None)
            continue

        if question == "/new":
            if session_id is None:
                # 保留 Day 05 的输出约定。
                history = []
                print("已清空当前对话历史。")
            else:
                # 持久化模式只创建新会话，不删除旧历史。
                session_id = f"session-{uuid4().hex}"
                print(f"已开始新会话：{session_id}")

            continue

        if question == "/history":
            current_history = (
                history
                if session_id is None
                else get_persistent_agent_history(
                    agent,
                    project,
                    session_id,
                )
            )

            print_recent_history(current_history)
            continue

        if question == "/session" or question.startswith("/session "):
            if session_id is None:
                print("请使用 --session ID 启动持久化聊天。")
                continue

            parts = question.split(maxsplit=1)

            if len(parts) != 2 or not parts[1].strip():
                print("使用方法：/session 会话ID")
                continue

            session_id = parts[1].strip()

            saved = get_persistent_agent_history(
                agent,
                project,
                session_id,
            )

            turns = sum(isinstance(message, HumanMessage) for message in saved)

            print(f"已切换会话：{session_id}")
            print(f"已恢复用户消息：{turns} 轮")
            continue

        if question.startswith("/"):
            # 必须保留 Day 05 的原有提示文字。
            print("未知命令。输入 /help 查看帮助。")
            continue

        try:
            if session_id is None:
                # 旧聊天模式：继续使用原有 Agent。
                previous_count = len(history)

                answer, updated_history = run_agent_turn(
                    agent,
                    history,
                    question,
                )

                # 只展示本轮新增的工具消息。
                for message in updated_history[previous_count:]:
                    if isinstance(message, AIMessage):
                        for tool_call in message.tool_calls:
                            print(f"[工具调用] {tool_call['name']}")

                    elif isinstance(message, ToolMessage):
                        tool_name = message.name or message.tool_call_id

                        # 保留 Day 05 原有工具返回标记。
                        print(f"[工具返回] {tool_name}")
                        print(message.text)

                history = updated_history

            else:
                # 持久化模式：历史由 Checkpointer 管理。
                answer, history = run_persistent_agent_turn(
                    agent,
                    project,
                    session_id,
                    question,
                )

            print(f"\nAI：{answer}")

        except (
            AgentExecutionError,
            ModelConfigError,
            RepositoryError,
            OpenAIError,
            httpx.HTTPError,
            GraphRecursionError,
        ) as exc:
            print(
                f"本轮对话失败：{type(exc).__name__}：{exc}",
                file=sys.stderr,
            )

            print("可以重新提问，或输入 /exit 结束。")

        except KeyboardInterrupt:
            print("\n用户已中断模型请求。")
            return 130


def run_chat_session(
    agent: Runnable,
    project: Path,
) -> int:
    """保留 Day 05 的公共聊天接口，兼容原有测试与调用方。"""

    return interactive_chat(
        agent=agent,
        project=project,
        session_id=None,
    )


def run_chat(args: argparse.Namespace) -> int:
    """根据参数选择临时模式或持久化模式。"""

    project = args.project.expanduser().resolve()

    if args.db is not None and args.session is None:
        print(
            "--db 需要与 --session 一起使用。",
            file=sys.stderr,
        )
        return 2

    if args.session is not None and not args.session.strip():
        print("会话 ID 不能为空。", file=sys.stderr)
        return 2

    try:
        # 先验证仓库，再创建模型。
        RepositoryExplorer(project)

        settings = load_model_settings()
        model = create_chat_model(settings)

        if args.session is None:
            agent = build_development_agent(
                model,
                project,
            )

            # 关键：临时模式仍从旧接口启动。
            return run_chat_session(agent, project)

        db_path = (
            (args.db if args.db is not None else DEFAULT_DB_PATH).expanduser().resolve()
        )

        db_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        # 整个会话都保持 SQLite 连接有效。
        with SqliteSaver.from_conn_string(str(db_path)) as saver:
            agent = build_persistent_development_agent(
                model,
                project,
                saver,
            )

            return interactive_chat(
                agent,
                project,
                session_id=args.session.strip(),
            )

    except (RepositoryError, ModelConfigError) as exc:
        print(
            f"项目或模型配置错误：{exc}",
            file=sys.stderr,
        )
        return 2

    except (OSError, OpenAIError, httpx.HTTPError) as exc:
        print(
            f"聊天初始化失败：{type(exc).__name__}：{exc}",
            file=sys.stderr,
        )
        return 1


def register(subparsers: Any) -> None:
    """注册原有 chat 子命令及持久化参数。"""

    parser = subparsers.add_parser(
        "chat",
        help="多轮开发 Agent 聊天，可选 SQLite 会话持久化",
    )

    add_project_argument(parser)

    parser.add_argument(
        "--session",
        default=None,
        help="会话 ID；传入后启用历史持久化",
    )

    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="SQLite 数据库路径，默认保存到用户主目录",
    )

    parser.set_defaults(handler=run_chat)
```

### 7.4 核心代码解释

**（1）为什么需要 `run_chat_session()` 和 `interactive_chat()` 两个函数？**

这是今天 Debug 最重要的结论。

Day 05 已经有：

```python
run_chat_session(agent, project)
```

其他调用方和原有测试都依赖该接口。

Day 11 增加了：

```python
interactive_chat(agent, project, session_id=None)
```

如果直接把旧函数删除或改名，就会破坏向后兼容。

最终采用：

```python
def run_chat_session(agent, project):
    return interactive_chat(
        agent,
        project,
        session_id=None,
    )
```

让旧接口继续有效，同时复用新实现。

这种方式称为 Compatibility Wrapper（兼容包装）。

**（2）为什么 `run_chat()` 仍然要调用旧接口？**

仅保留函数名称还不够。

原有测试使用：

```python
monkeypatch.setattr(
    chat,
    "run_chat_session",
    fake_session,
)
```

如果 `run_chat()` 绕过它，直接调用 `interactive_chat()`，测试中的 Mock 就不会生效。

所以临时模式必须继续执行：

```python
return run_chat_session(agent, project)
```

这体现了兼容性不仅是函数存在，还包括原有调用关系。

**（3）为什么需要导入 `ToolMessage`？**

```python
from langchain_core.messages import ToolMessage
```

工具 Agent 的消息历史可能包含：

```text
HumanMessage
AIMessage（工具调用请求）
ToolMessage（工具执行结果）
AIMessage（最终回答）
```

要识别工具返回：

```python
isinstance(message, ToolMessage)
```

就必须先导入该类。

否则执行时会出现：

```text
NameError: name 'ToolMessage' is not defined
```

**（4）为什么只展示本轮新增的工具消息？**

```python
previous_count = len(history)
```

执行本轮 Agent 后：

```python
updated_history[previous_count:]
```

只包含本轮新增消息。

这样不会每次提问都重复打印之前的所有工具调用。

**（5）为什么使用固定的工具输出格式？**

```python
print(f"[工具调用] {tool_call['name']}")
print(f"[工具返回] {tool_name}")
```

Day 05 的测试已经依赖这些输出标记。

CLI 输出虽然是人可读文本，但当测试或外部程序依赖固定字符串时，它也属于需要保持兼容的接口。

**（6）为什么临时模式的 `/new` 仍然清空 history？**

```python
history = []
print("已清空当前对话历史。")
```

这是原有行为。

持久化模式则切换到一个新的 `thread_id`，旧 SQLite 历史仍然保留。

两种模式使用同一个 `/new` 命令，但状态管理方式不同。

**（7）为什么区分临时与持久化模式？**

不指定 `--session`：

```python
run_agent_turn(agent, history, question)
```

指定 `--session`：

```python
run_persistent_agent_turn(
    agent,
    project,
    session_id,
    question,
)
```

前者依赖内存历史，后者依赖 Checkpointer。

不能混用两套历史更新机制。

**（8）为什么使用 `with SqliteSaver...`？**

```python
with SqliteSaver.from_conn_string(str(db_path)) as saver:
```

整个交互过程必须发生在数据库连接有效期间。

用户退出聊天后，才关闭数据库连接。

### 7.5 注意事项

- 本文件是现有模块的增量升级，不应该删除旧接口。
- `run_chat_session()` 必须保留。
- 旧 CLI 已验证的输出文字不应随意改名。
- 工具输出格式不应随意改变。
- 不能因为 Day 11 新增测试通过，就认为 Day 05 旧功能仍然正常。
- 持久化模式的 `/new` 不删除旧历史。
- SQLite 数据库可能包含源码和用户消息。
- SQLite 数据库默认保存在用户主目录，不进入 Git 仓库。

### 7.6 对应验证

Day 05 旧测试：

```bash
python -m pytest tests/cli/test_chat.py -v
```

Day 11 新测试：

```bash
python -m pytest tests/cli/test_chat_persistence.py -v
```

两个测试文件都必须通过。

**这是本日最终回归修复的关键要求。**

---

## 8. 文件七：`tests/cli/test_chat_persistence.py`

### 8.1 文件职责

本文件验证 `chat` CLI 的持久化功能，同时确认旧临时模式未被破坏。

主要覆盖：

- 重启后恢复会话。
- `/session` 切换会话。
- `/new` 不删除旧历史。
- 不提供 `--session` 时继续使用临时模式。
- `--db` 参数约束。
- CLI 帮助信息。

### 8.2 创建与打开

首次创建：

```bash
touch tests/cli/test_chat_persistence.py
```

打开：

```bash
nano tests/cli/test_chat_persistence.py
```

### 8.3 根据本次测试编辑记录整理的完整代码

```python
"""Day 11：chat CLI 会话持久化与恢复测试。"""

from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableLambda

from ai_software_dev_agent import cli
from ai_software_dev_agent.commands import chat as chat_command
from ai_software_dev_agent.persistent_chat import (
    build_persistent_chat_graph,
)


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    """创建独立测试仓库。"""

    (tmp_path / "demo.py").write_text(
        "value = 123\n",
        encoding="utf-8",
    )

    return tmp_path


@pytest.fixture
def fake_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """模拟模型配置与模型调用。"""

    def fake_model() -> RunnableLambda:
        def respond(messages: list) -> AIMessage:
            count = sum(isinstance(message, HumanMessage) for message in messages)

            return AIMessage(content=f"第 {count} 轮回答")

        return RunnableLambda(respond)

    monkeypatch.setattr(
        chat_command,
        "load_model_settings",
        lambda: object(),
    )

    monkeypatch.setattr(
        chat_command,
        "create_chat_model",
        lambda settings: fake_model(),
    )

    # CLI 测试使用无工具的持久化图。
    # 真实仓库工具另由 persistent_agent 测试验证。
    monkeypatch.setattr(
        chat_command,
        "build_persistent_development_agent",
        lambda model, project, saver: build_persistent_chat_graph(
            model,
            saver,
        ),
    )


def provide_inputs(
    monkeypatch: pytest.MonkeyPatch,
    *values: str,
) -> None:
    """模拟交互式输入。"""

    items = iter(values)

    monkeypatch.setattr(
        "builtins.input",
        lambda prompt="": next(items),
    )


def test_cli_restores_session_after_restart(
    sample_project: Path,
    fake_dependencies: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """两次启动 CLI，恢复同一会话。"""

    db_path = sample_project / "sessions.sqlite"

    args = [
        "chat",
        "--project",
        str(sample_project),
        "--session",
        "python-learning",
        "--db",
        str(db_path),
    ]

    provide_inputs(monkeypatch, "第一次提问", "/exit")

    assert cli.main(args) == 0

    first_output = capsys.readouterr().out
    assert "第 1 轮回答" in first_output

    # 再次调用 CLI，模拟重新打开数据库。
    provide_inputs(monkeypatch, "第二次提问", "/exit")

    assert cli.main(args) == 0

    second_output = capsys.readouterr().out

    assert "已恢复用户消息：1 轮" in second_output
    assert "第 2 轮回答" in second_output
    assert db_path.is_file()


def test_cli_switches_between_sessions(
    sample_project: Path,
    fake_dependencies: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """切换会话后应恢复对应历史。"""

    db_path = sample_project / "sessions.sqlite"

    provide_inputs(
        monkeypatch,
        "主会话第一轮",
        "/session other",
        "其他会话第一轮",
        "/session main",
        "主会话第二轮",
        "/exit",
    )

    result = cli.main(
        [
            "chat",
            "--project",
            str(sample_project),
            "--session",
            "main",
            "--db",
            str(db_path),
        ]
    )

    output = capsys.readouterr().out

    assert result == 0
    assert "已切换会话：other" in output
    assert "已切换会话：main" in output
    assert "第 1 轮回答" in output
    assert "第 2 轮回答" in output


def test_new_session_does_not_delete_old_history(
    sample_project: Path,
    fake_dependencies: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """新建会话不应该删除旧会话。"""

    db_path = sample_project / "sessions.sqlite"

    args = [
        "chat",
        "--project",
        str(sample_project),
        "--session",
        "original",
        "--db",
        str(db_path),
    ]

    provide_inputs(
        monkeypatch,
        "旧会话第一轮",
        "/new",
        "新会话第一轮",
        "/exit",
    )

    assert cli.main(args) == 0

    output = capsys.readouterr().out
    assert "已开始新会话" in output

    # 使用原会话 ID 再次启动。
    provide_inputs(monkeypatch, "旧会话第二轮", "/exit")

    assert cli.main(args) == 0

    restored_output = capsys.readouterr().out

    assert "已恢复用户消息：1 轮" in restored_output
    assert "第 2 轮回答" in restored_output


def test_legacy_chat_without_session(
    sample_project: Path,
    fake_dependencies: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """临时聊天模式继续保持原有行为。"""

    def fake_build_agent(
        model: object,
        project: Path,
    ) -> RunnableLambda:
        def respond(data: dict) -> dict:
            messages = data["messages"]

            count = sum(isinstance(message, HumanMessage) for message in messages)

            return {
                "messages": [
                    *messages,
                    AIMessage(content=f"第 {count} 轮回答"),
                ]
            }

        return RunnableLambda(respond)

    monkeypatch.setattr(
        chat_command,
        "build_development_agent",
        fake_build_agent,
    )

    provide_inputs(
        monkeypatch,
        "第一次",
        "第二次",
        "/new",
        "重新开始",
        "/exit",
    )

    result = cli.main(
        [
            "chat",
            "--project",
            str(sample_project),
        ]
    )

    output = capsys.readouterr().out

    assert result == 0
    assert "临时聊天模式" in output
    assert "第 2 轮回答" in output

    # 当前聊天中的代码块编辑记录采用了较宽松的断言。
    assert "已" in output


def test_db_requires_session(
    sample_project: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """只指定数据库而不指定会话时应报错。"""

    result = cli.main(
        [
            "chat",
            "--project",
            str(sample_project),
            "--db",
            str(sample_project / "sessions.sqlite"),
        ]
    )

    captured = capsys.readouterr()

    assert result == 2
    assert "--db 需要与 --session 一起使用" in captured.err


def test_chat_help_contains_persistence_options(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """帮助信息应包含新增参数。"""

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["chat", "--help"])

    assert exc_info.value.code == 0

    output = capsys.readouterr().out

    assert "--session" in output
    assert "--db" in output
```

### 8.4 核心代码解释

**（1）为什么测试里要模拟模型？**

我们只需要验证：

```text
第一次启动 → 保存历史
第二次启动 → 恢复历史
```

因此用确定性的模拟模型即可。

不需要为了验证 CLI 参数和数据库恢复而消耗真实 API Token。

**（2）如何模拟用户输入？**

```python
monkeypatch.setattr(
    "builtins.input",
    lambda prompt="": next(items),
)
```

可以依次模拟：

```text
第一次提问
/exit
```

这样测试能够自动运行。

**（3）为什么两次调用 `cli.main(args)`？**

第一次创建数据库并保存消息。

第二次重新打开同一个数据库。

如果第二次能够生成“第 2 轮回答”，说明历史确实被恢复。

**（4）为什么 `/new` 要单独测试？**

因为它不应该删除旧的持久化历史。

测试流程：

```text
original 会话第一轮
    ↓
/new
    ↓
新会话第一轮
    ↓
退出
    ↓
再次打开 original
    ↓
恢复旧会话第二轮
```

这样验证原来的消息没有丢失。

**（5）为什么还要测试旧聊天模式？**

Day 11 的新功能不能破坏 Day 05 原来的临时聊天。

这正是最终全量回归发现的问题所在。

新增测试通过，不等于旧接口一定正常。

### 8.5 注意：当前编辑过的断言过于宽松

本次聊天中，你对原断言做过如下编辑：

```python
assert "已" in output
```

它只是验证输出中包含“已”字。

这虽然可以通过，但可能出现一种问题：

即使 `/new` 没有正确清空历史，只要其他输出中包含“已”，测试仍可能通过。

**更有价值的断言应该是：**

```python
assert "已清空当前对话历史" in output
```

它明确验证 Day 05 原有的 `/new` 输出约定。

这里没有把建议替换成已经执行的修改；文档代码保留了当前聊天中编辑过的版本。建议后续维护时将断言恢复为更明确的完整提示文本。

### 8.6 对应验证

新测试：

```bash
python -m pytest tests/cli/test_chat_persistence.py -v
```

旧测试：

```bash
python -m pytest tests/cli/test_chat.py -v
```

最终两者均已确认通过。

---

## 9. 今日真实 Debug 记录

本次 Day 11 最终 Debug 的重点，不是 SQLite 功能本身，而是**旧 CLI 的向后兼容性**。

### 9.1 Debug 01：旧的 `run_chat_session()` 接口消失

第一次全量 pytest：

```text
6 failed, 184 passed
```

主要异常：

```text
AttributeError:
module 'ai_software_dev_agent.commands.chat'
has no attribute 'run_chat_session'
```

涉及多个旧测试。

**原因：**

Day 11 将原来的：

```python
run_chat_session()
```

改为：

```python
interactive_chat()
```

但旧测试和原有调用方仍然依赖原接口。

**修复：**

恢复兼容函数：

```python
def run_chat_session(agent, project):
    return interactive_chat(
        agent,
        project,
        session_id=None,
    )
```

同时在临时聊天分支中继续调用：

```python
return run_chat_session(agent, project)
```

不能只新增函数而不恢复原调用关系。

### 9.2 Debug 02：`ToolMessage` 未导入

修复旧接口之后，仍存在：

```text
NameError: name 'ToolMessage' is not defined
```

涉及多个旧测试。

**原因：**

新增了：

```python
isinstance(message, ToolMessage)
```

但没有同步导入 `ToolMessage`。

**修复：**

```python
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    ToolMessage,
)
```

### 9.3 Debug 03：未知命令提示发生变化

原测试要求：

```text
未知命令
```

但修改后的代码输出：

```text
未知指令
```

因此：

```text
AssertionError
```

**修复：**

```python
print("未知命令。输入 /help 查看帮助。")
```

这体现了：CLI 对外输出也是需要保持兼容的接口。

### 9.4 Debug 04：EOF 退出提示被遗漏

原有测试要求输出包含：

```text
再见
```

Day 11 初始版本输出：

```text
聊天已结束。
```

导致测试失败。

**修复：**

```python
except EOFError:
    print("\n再见，聊天已结束。")
    return 0
```

### 9.5 Debug 05：工具返回信息格式不一致

继续运行旧测试，出现：

```text
assert '[工具返回] read_repository_file' in output
```

当时程序打印的是：

```text
工具结果：read_repository_file
```

与原测试要求不一致。

**修复：**

```python
elif isinstance(message, ToolMessage):
    tool_name = message.name or message.tool_call_id

    print(f"[工具返回] {tool_name}")
    print(message.text)
```

同时保留工具调用信息：

```python
print(f"[工具调用] {tool_call['name']}")
```

最终确认测试通过。

### 9.6 Debug 06：`/new` 提示与旧测试不一致

旧测试要求：

```text
已清空当前对话历史
```

新代码曾输出：

```text
已清空当前临时会话历史
```

造成断言失败。

**修复业务代码：**

```python
history = []
print("已清空当前对话历史。")
```

保留 Day 05 的原有输出。

### 9.7 Debug 07：新增测试与旧接口约定冲突

修复 Day 05 的输出后，全量测试又出现：

```text
1 failed, 189 passed
```

失败来自：

```text
tests/cli/test_chat_persistence.py
```

因为 Day 11 新测试仍然要求：

```text
已清空当前临时会话历史
```

而旧接口实际采用：

```text
已清空当前对话历史
```

**正确处理方向：**

不应再次修改业务代码，而应让新增测试遵守既有接口约定。

聊天中的后续代码编辑采用了：

```python
assert "已" in output
```

测试随后确认通过。

不过该断言过宽。更严格、更有意义的写法是：

```python
assert "已清空当前对话历史" in output
```

### 9.8 最终测试结果

本日曾经历：

| 阶段 | 测试结果 | 主要问题 |
|---|---|---|
| 初次全量回归 | 184 passed，6 failed | 旧接口消失 |
| 恢复接口后 | 1 passed，5 failed（旧测试文件） | 导入和提示兼容 |
| 继续修复 | 4 passed，2 failed（旧测试文件） | 工具输出、`/new` |
| 继续修复 | 5 passed，1 failed（旧测试文件） | 工具返回格式 |
| 后续全量回归 | 189 passed，1 failed | 新旧测试断言冲突 |
| 最终 | 全量测试通过 | 用户已确认 |

最终准确的测试统计以本机最后一次 pytest 输出为准；这里不推断未贴出的最终耗时或用例总数。

### 9.9 这次 Debug 最重要的教训

**第一：向后兼容不仅是函数还能调用。**

还包括：

- 原有函数名称。
- 函数参数。
- 调用关系。
- 异常处理。
- CLI 输出文字。
- 工具日志格式。

**第二：新测试通过，不等于没有破坏旧功能。**

Day 11 新增的测试最初全部通过，但 Day 05 的旧测试失败。

因此最终必须执行全量 pytest。

**第三：Mock 依赖也属于接口约定。**

如果测试通过 `monkeypatch` 替换某个函数，重构后绕过该函数，也可能造成测试失败。

**第四：不要为了让测试通过而反复改变已经确立的旧行为。**

应该先确认原有规范，再让新增实现与新增测试共同遵守它。

**第五：修改已有模块时，必须优先采用增量式改造。**

如果没有完整读取旧代码，直接重写整个文件很容易遗漏细节。

这次连续回归问题正是由这一点引起。

---

## 10. 最终学习总结

### 10.1 今日完成的能力

- LangGraph Checkpoint 基础。
- SQLite 持久化存储。
- `MessagesState`。
- `thread_id` 会话隔离。
- `graph.get_state()`。
- 跨数据库连接恢复历史。
- 原有工具 Agent 的持久化集成。
- `chat --session`。
- `chat --db`。
- `/new`。
- `/session`。
- `/history`。
- 原有临时聊天兼容。
- 原有工具输出格式兼容。
- 旧测试与新测试全量回归通过。

### 10.2 重点概念总结

| 概念 | 作用 |
|---|---|
| Checkpoint | 一次工作流状态快照 |
| Checkpointer | 保存、读取 Checkpoint 的组件 |
| SQLite | 本地持久化数据库 |
| `SqliteSaver` | LangGraph 的 SQLite 存储实现 |
| `MessagesState` | 管理聊天消息状态 |
| `add_messages` | 合并新旧消息 |
| `thread_id` | 标识具体会话 |
| `compile(checkpointer=...)` | 为图启用 Checkpoint |
| `graph.get_state()` | 读取保存的状态 |
| `uuid4()` | 生成新会话标识 |
| `monkeypatch` | 测试中替换依赖 |
| Backward Compatibility | 保持已有接口与行为兼容 |

### 10.3 本日重点区分

**Checkpoint 与普通内存 history**

内存 history 随 Python 进程结束而消失。

Checkpoint 可以通过持久化存储，在进程退出后恢复。

**Checkpointer 与 thread_id**

Checkpointer 负责状态保存在哪里。

`thread_id` 决定状态属于哪条会话。

**持久化与长期记忆**

Checkpoint 主要解决状态保存和恢复。

长期记忆系统还可能需要信息提取、检索、更新、过期策略等能力。

**工作流恢复与外部操作恢复**

恢复历史消息，不代表可以安全重复执行之前的代码修改、文件删除等有副作用操作。

**新增功能与向后兼容**

新增功能正确，不代表已有功能不会回归。

工程开发必须同时验证新功能与旧接口。

### 10.4 当前局限

目前尚未实现：

- 查看全部会话列表。
- 会话删除与归档。
- 多设备同步。
- 数据库加密。
- 稳定项目 ID。
- 历史消息裁剪。
- 高并发数据库写入。
- 对中断任务的完整安全恢复。
- 对有副作用工具的幂等恢复。
- 对所有历史会话的检索。

这些属于后续工程完善方向。

### 10.5 今日核心认识

Day 05 解决的是：

**Agent 如何在同一进程中持续多轮对话？**

Day 11 解决的是：

**Agent 如何在程序退出后，恢复之前的真实会话？**

同时，最终 Debug 又让我们学到一条非常重要的工程原则：

**重构已有功能时，不能只验证新增功能是否可用，还必须保证旧接口、旧行为与旧测试继续成立。**

一个真正可靠的软件工程项目，不只是不断增加新功能，还要能够在增加功能的同时保持已有系统的稳定性。

**Day 11 完成。**

下一学习日：

**Day 12｜Human-in-the-Loop（人工审批）**

重点研究 LangGraph 工作流暂停、等待用户审批，以及在批准或拒绝后安全恢复执行。