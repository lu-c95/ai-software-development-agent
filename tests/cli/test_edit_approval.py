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

    # 第二次调用会重新创建 SQLite 连接和 Graph。
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

    # 第一次取消后，应能够重新进入同一待审批任务。
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

    # EOF 后再次运行，应仍能正常审批。
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
