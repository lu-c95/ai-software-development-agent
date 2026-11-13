"""使用 LangGraph 将仓库探索、测试和结果汇总连接成工作流。"""

import operator
from pathlib import Path
from typing import Annotated, NotRequired, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from ai_software_dev_agent.repository import RepositoryExplorer
from ai_software_dev_agent.test_runner import (
    DEFAULT_TIMEOUT_SECONDS,
    TestRunner,
    TestRunResult,
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

    # 1. 注册节点：告诉 LangGraph 每一步执行哪个函数。
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

    # 2. 添加边：定义节点的执行顺序。
    builder.add_edge(START, "inspect_repository")
    builder.add_edge("inspect_repository", "run_tests")
    builder.add_edge("run_tests", "summarize")
    builder.add_edge("summarize", END)

    # 3. 编译为可通过 invoke() 运行的图。
    return builder.compile()


def run_development_workflow(
    project: Path,
    target: str = "tests",
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> DevelopmentWorkflowState:
    """创建初始状态并执行完整工作流。"""

    initial_state: DevelopmentWorkflowState = {
        "project": str(project.expanduser().resolve()),
        "target": target,
        "timeout_seconds": timeout_seconds,
        "completed_steps": [],
    }

    workflow = build_development_workflow()

    return workflow.invoke(initial_state)
