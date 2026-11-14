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
    TestRunner,
    TestRunnerError,
    TestRunResult,
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
