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

    # 从中断结果中读取给人审查的内容。
    approval_request = result["__interrupt__"][0].value

    assert approval_request["operation"] == "create_file"
    assert approval_request["relative_path"] == "demo.py"
    assert "value = 123" in approval_request["diff"]

    # 从 Checkpoint 检查工作流实际暂停位置。
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

    # 模拟等待人工审批期间，另一操作创建了该文件。
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

    # 模拟第一次运行程序：准备变更并暂停。
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

    # 前一个数据库连接已经关闭。
    assert database.is_file()

    # 模拟重新启动：创建新 Graph，恢复相同 thread_id。
    with SqliteSaver.from_conn_string(str(database)) as saver:
        graph = build_approval_graph(saver)

        result = resume_approval(
            graph,
            "sqlite-request",
            approved=True,
        )

        assert result["status"] == "created"
        assert target.read_text(encoding="utf-8") == ("message = 'hello'\n")
