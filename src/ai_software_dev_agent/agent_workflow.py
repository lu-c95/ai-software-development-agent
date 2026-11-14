"""基于仓库证据的 LangChain Agent + LangGraph 工作流。"""

import operator
import re
from pathlib import Path
from typing import Annotated, NotRequired, TypedDict

from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from ai_software_dev_agent.agent import run_agent_turn
from ai_software_dev_agent.repository import RepositoryExplorer

# 仓库概览任务的固定读取预算，避免一次性加载整个项目。
MAX_FILES = 8
MAX_CHARS_PER_FILE = 1500
MAX_FILE_LIST = 100

# 常见 Python 工程核心文件优先级。
# 不在清单中的文件也有机会通过后备排序被选中。
FILE_PRIORITY = {
    "pyproject.toml": 100,
    "readme.md": 98,
    "agent.py": 96,
    "agent_workflow.py": 94,
    "main.py": 92,
    "app.py": 90,
    "cli.py": 88,
    "model.py": 86,
    "repository.py": 84,
    "workflow.py": 82,
    "test_runner.py": 80,
    "_common.py": 78,
    "chat.py": 76,
    "edit.py": 74,
    "plan.py": 72,
    "testing.py": 70,
}


class AgentWorkflowState(TypedDict):
    """外层工作流共享状态。"""

    project: str
    task: str
    history: list[BaseMessage]
    completed_steps: Annotated[list[str], operator.add]

    files: NotRequired[list[str]]
    read_files: NotRequired[list[str]]
    evidence: NotRequired[str]
    answer: NotRequired[str]
    summary: NotRequired[str]


def normalize_file_path(path: str | Path, root: Path) -> str:
    """统一为相对于当前仓库根目录的文件路径。"""

    item = Path(path)

    if item.is_absolute():
        item = item.relative_to(root)

    return item.as_posix()


def select_relevant_files(
    files: list[str],
    task: str,
) -> list[str]:
    """优先选择核心文件，并考虑任务中出现的文件名。"""

    # 提取英文标识符及文件名，匹配任务中明确提到的模块。
    keywords = [
        word.casefold()
        for word in re.findall(
            r"[A-Za-z_][A-Za-z0-9_.-]*",
            task,
        )
        if len(word) >= 3
    ]

    def score(path: str) -> int:
        name = Path(path).name.casefold()
        result = FILE_PRIORITY.get(name, 0)

        # 如果用户明确提到了某个文件或模块，则提高优先级。
        for word in keywords:
            if word in path.casefold():
                result += 120

        # 在其他条件相同时，优先考虑层级较浅的文件。
        return result

    ordered = sorted(
        set(files),
        key=lambda path: (
            -score(path),
            path.count("/"),
            path,
        ),
    )

    return ordered[:MAX_FILES]


def inspect_repository_node(
    state: AgentWorkflowState,
) -> dict[str, object]:
    """节点一：探索仓库并准备有读取上限的源码证据。"""

    root = Path(state["project"])
    explorer = RepositoryExplorer(root)

    files = [normalize_file_path(path, root) for path in explorer.list_files()]

    selected = select_relevant_files(
        files,
        state["task"],
    )

    evidence_parts: list[str] = []

    for relative_path in selected:
        content = explorer.read_file(relative_path)

        snippet = content[:MAX_CHARS_PER_FILE]
        truncated = len(content) > MAX_CHARS_PER_FILE

        evidence_parts.append(
            f"文件：{relative_path}\n"
            f"源码片段：\n{snippet}\n"
            f"内容是否截断：{'是' if truncated else '否'}"
        )

    return {
        "files": files,
        "read_files": selected,
        "evidence": "\n\n---\n\n".join(evidence_parts),
        "completed_steps": ["inspect_repository"],
    }


def run_agent_node(
    state: AgentWorkflowState,
    agent: Runnable,
) -> dict[str, object]:
    """节点二：让只读分析 Agent 根据证据生成回答。"""

    file_list = "\n".join(f"- {path}" for path in state["files"][:MAX_FILE_LIST])

    if not file_list:
        file_list = "（没有发现可探索文件）"

    evidence = state["evidence"]

    if not evidence:
        evidence = "（没有可供阅读的源码片段）"

    question = (
        "请基于下面的仓库信息完成用户任务。\n\n"
        f"用户任务：{state['task']}\n\n"
        "项目文件列表：\n"
        f"{file_list}\n\n"
        "已读取的源码证据：\n"
        f"{evidence}\n\n"
        "回答要求：\n"
        "1. 优先根据已提供的源码证据分析。\n"
        "2. 对未读取或被截断的部分，明确说明局限。\n"
        "3. 不要把根据文件名的推测当作已确认事实。\n"
        "4. 不要声称已经阅读了全部项目文件。\n"
        "5. 如果证据不足，请说明需要进一步查看哪些文件。\n"
        "6. 本次只进行只读分析，不修改代码。\n"
        "7. 使用简体中文，尽量条理清晰。"
    )

    # 继续复用 Day 05 的 Agent 消息历史处理函数。
    # 此处由 CLI 注入不带工具的分析 Agent，避免无界工具循环。
    answer, updated_history = run_agent_turn(
        agent,
        state["history"],
        question,
    )

    return {
        "answer": answer,
        "history": updated_history,
        "completed_steps": ["run_agent"],
    }


def summarize_agent_node(
    state: AgentWorkflowState,
) -> dict[str, object]:
    """节点三：整理分析结果及证据覆盖范围。"""

    summary = (
        f"项目：{state['project']}\n"
        f"用户任务：{state['task']}\n"
        f"可探索文件数：{len(state['files'])}\n"
        f"已读取文件数：{len(state['read_files'])}\n"
        f"已读取文件：{', '.join(state['read_files'])}\n\n"
        f"Agent 回答：\n{state['answer']}"
    )

    return {
        "summary": summary,
        "completed_steps": ["summarize"],
    }


def build_agent_workflow(
    agent: Runnable,
) -> CompiledStateGraph:
    """将已有的 LangChain Agent 接入外层 LangGraph。"""

    builder = StateGraph(AgentWorkflowState)

    builder.add_node(
        "inspect_repository",
        inspect_repository_node,
    )

    def execute_agent(
        state: AgentWorkflowState,
    ) -> dict[str, object]:
        return run_agent_node(state, agent)

    builder.add_node(
        "run_agent",
        execute_agent,
    )

    builder.add_node(
        "summarize",
        summarize_agent_node,
    )

    builder.add_edge(START, "inspect_repository")
    builder.add_edge("inspect_repository", "run_agent")
    builder.add_edge("run_agent", "summarize")
    builder.add_edge("summarize", END)

    return builder.compile()


def run_agent_workflow(
    project: Path,
    task: str,
    agent: Runnable,
    history: list[BaseMessage] | None = None,
) -> AgentWorkflowState:
    """执行完整的仓库分析工作流。"""

    clean_task = task.strip()

    if not clean_task:
        raise ValueError("用户任务不能为空")

    initial_state: AgentWorkflowState = {
        "project": str(project.expanduser().resolve()),
        "task": clean_task,
        "history": list(history) if history is not None else [],
        "completed_steps": [],
    }

    graph = build_agent_workflow(agent)

    return graph.invoke(initial_state)
