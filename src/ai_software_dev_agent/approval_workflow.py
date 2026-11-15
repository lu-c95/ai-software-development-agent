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
