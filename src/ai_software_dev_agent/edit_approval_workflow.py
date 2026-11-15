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

    # 以下字段由节点逐步写入。
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

    # 保存人即将审查的 Diff 和原文件哈希。
    # 审批之后必须确认文件仍是这个版本。
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

    # 只有真正的布尔 True 才代表批准。
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
        # 不能直接使用批准前的结果写文件。
        # 重新生成预览，确认旧片段现在仍然满足编辑规则。
        current_preview = editor.preview_replace(
            file_path=state["relative_path"],
            old_text=state["old_text"],
            new_text=state["new_text"],
        )

        # 原文件任何内容发生变化，都应拒绝应用旧审批。
        if (
            current_preview.original_sha256 != state["original_sha256"]
            or current_preview.diff != state["diff"]
        ):
            return {
                "status": "conflict",
                "summary": ("文件在审批期间发生变化，原修改方案已失效，未执行写入。"),
            }

        # 复用 CodeEditor 内部的哈希检查和原子写入逻辑。
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

    # 防止同一个审批 ID 覆盖已有的任务状态。
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

    # 只能恢复真正暂停在人工审批节点的任务。
    if snapshot.next != ("request_edit_approval",):
        raise ValueError("当前线程没有等待处理的修改审批")

    return graph.invoke(
        Command(resume=approved),
        config=config,
    )
