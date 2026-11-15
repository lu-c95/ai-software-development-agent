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

    # 在等待审批时，文件仍然不变。
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
    """审批等待期间文件变化，即使批准也不能使用旧预览。"""

    target = project / "demo.py"

    begin(graph, project, "stale-request")

    # 保留旧片段，但修改文件的其他部分。
    # 这样可以专门验证 SHA-256 版本检查。
    changed_content = ORIGINAL + "# added during review\n"
    target.write_text(changed_content, encoding="utf-8")

    result = resume_edit_approval(
        graph,
        "stale-request",
        approved=True,
    )

    assert result["approved"] is True
    assert result["status"] == "conflict"

    # 不能覆盖审批期间发生的新变化。
    assert target.read_text(encoding="utf-8") == changed_content


def test_missing_or_duplicate_old_text_is_rejected(
    graph: CompiledStateGraph,
    project: Path,
) -> None:
    """旧片段缺失或出现多次时不能生成安全预览。"""

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

    # 任务 B 还没有获得批准。
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

    # 第一次运行：生成 Diff 并等待审批。
    with SqliteSaver.from_conn_string(str(database)) as saver:
        graph = build_edit_approval_graph(saver)

        result = begin(graph, project, "sqlite-edit-request")

        assert "__interrupt__" in result
        assert target.read_text(encoding="utf-8") == ORIGINAL

    # 模拟程序退出并重新启动。
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
