"""Day 10：条件路由、有限重试及错误处理测试。"""

from pathlib import Path
from types import SimpleNamespace

import pytest

from ai_software_dev_agent import conditional_workflow
from ai_software_dev_agent.test_runner import (
    TestRunnerError as RunnerExecutionError,
)


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    """创建独立的测试仓库。"""

    (tmp_path / "demo.py").write_text(
        "def add(a: int, b: int) -> int:\n    return a + b\n",
        encoding="utf-8",
    )

    return tmp_path


def mock_test_result(
    monkeypatch: pytest.MonkeyPatch,
    status: str,
) -> None:
    """模拟固定测试结果，不执行真实 pytest。"""

    class FakeTestRunner:
        def __init__(self, project: Path) -> None:
            self.project = project

        def run(
            self,
            target: str,
            timeout_seconds: int,
        ) -> SimpleNamespace:
            return SimpleNamespace(status=status)

    monkeypatch.setattr(
        conditional_workflow,
        "TestRunner",
        FakeTestRunner,
    )


@pytest.mark.parametrize(
    ("status", "expected_node", "expected_text"),
    [
        ("passed", "summarize_passed", "测试通过"),
        ("failed", "summarize_failed", "测试未通过"),
        ("no_tests", "summarize_no_tests", "没有找到测试用例"),
        ("timeout", "summarize_timeout", "测试超时"),
        ("error", "summarize_error", "工作流执行异常"),
    ],
)
def test_routes_by_test_result(
    sample_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    status: str,
    expected_node: str,
    expected_text: str,
) -> None:
    """默认不重试，测试状态决定最终处理分支。"""

    mock_test_result(monkeypatch, status)

    result = conditional_workflow.run_conditional_workflow(
        project=sample_project,
        target="tests",
        timeout_seconds=30,
    )

    assert result["status"] == status
    assert result["retry_count"] == 0

    assert result["completed_steps"] == [
        "inspect_repository",
        "run_tests",
        expected_node,
    ]

    assert expected_text in result["summary"]


def test_missing_project_routes_to_error(
    tmp_path: Path,
) -> None:
    """仓库不存在时，不应进入测试执行节点。"""

    result = conditional_workflow.run_conditional_workflow(
        project=tmp_path / "not_exists",
        max_retries=1,
    )

    assert result["status"] == "error"
    assert result["retry_count"] == 0
    assert result["completed_steps"] == [
        "inspect_repository",
        "summarize_error",
    ]
    assert "工作流执行异常" in result["summary"]


def test_runner_error_routes_to_error(
    sample_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试目标等已知错误，不应该触发重试。"""

    class FailingTestRunner:
        def __init__(self, project: Path) -> None:
            self.project = project

        def run(
            self,
            target: str,
            timeout_seconds: int,
        ) -> None:
            raise RunnerExecutionError("测试目标无效")

    monkeypatch.setattr(
        conditional_workflow,
        "TestRunner",
        FailingTestRunner,
    )

    result = conditional_workflow.run_conditional_workflow(
        sample_project,
        max_retries=2,
    )

    assert result["status"] == "error"
    assert result["retry_count"] == 0
    assert result["completed_steps"] == [
        "inspect_repository",
        "run_tests",
        "summarize_error",
    ]
    assert "测试目标无效" in result["summary"]


def test_unexpected_error_is_not_hidden(
    sample_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """真正未知的程序错误应该向上抛出。"""

    class BrokenTestRunner:
        def __init__(self, project: Path) -> None:
            self.project = project

        def run(
            self,
            target: str,
            timeout_seconds: int,
        ) -> None:
            raise RuntimeError("模拟未知程序错误")

    monkeypatch.setattr(
        conditional_workflow,
        "TestRunner",
        BrokenTestRunner,
    )

    with pytest.raises(
        RuntimeError,
        match="模拟未知程序错误",
    ):
        conditional_workflow.run_conditional_workflow(
            sample_project,
        )


def test_stream_only_visits_selected_branch(
    sample_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试通过时只执行成功分支。"""

    mock_test_result(monkeypatch, "passed")

    graph = conditional_workflow.build_conditional_workflow()

    initial_state = {
        "project": str(sample_project),
        "target": "tests",
        "timeout_seconds": 30,
        "max_retries": 0,
        "retry_count": 0,
        "completed_steps": [],
    }

    events = list(
        graph.stream(
            initial_state,
            stream_mode="updates",
        )
    )

    node_names = [next(iter(event)) for event in events]

    assert node_names == [
        "inspect_repository",
        "run_tests",
        "summarize_passed",
    ]


def test_timeout_recovers_after_retry(
    sample_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """第一次超时，第二次通过，应正常完成恢复。"""

    calls = 0

    class TemporaryTimeoutRunner:
        def __init__(self, project: Path) -> None:
            self.project = project

        def run(
            self,
            target: str,
            timeout_seconds: int,
        ) -> SimpleNamespace:
            nonlocal calls
            calls += 1

            status = "timeout" if calls == 1 else "passed"
            return SimpleNamespace(status=status)

    monkeypatch.setattr(
        conditional_workflow,
        "TestRunner",
        TemporaryTimeoutRunner,
    )

    result = conditional_workflow.run_conditional_workflow(
        sample_project,
        max_retries=1,
    )

    assert calls == 2
    assert result["status"] == "passed"
    assert result["retry_count"] == 1

    assert result["completed_steps"] == [
        "inspect_repository",
        "run_tests",
        "retry_tests",
        "run_tests",
        "summarize_passed",
    ]

    assert "重试后测试通过" in result["summary"]
    assert "实际测试次数：2" in result["summary"]


def test_timeout_stops_when_budget_exhausted(
    sample_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """持续超时只能在预算内重试，不能无限循环。"""

    calls = 0

    class AlwaysTimeoutRunner:
        def __init__(self, project: Path) -> None:
            self.project = project

        def run(
            self,
            target: str,
            timeout_seconds: int,
        ) -> SimpleNamespace:
            nonlocal calls
            calls += 1
            return SimpleNamespace(status="timeout")

    monkeypatch.setattr(
        conditional_workflow,
        "TestRunner",
        AlwaysTimeoutRunner,
    )

    result = conditional_workflow.run_conditional_workflow(
        sample_project,
        max_retries=2,
    )

    assert calls == 3
    assert result["status"] == "timeout"
    assert result["retry_count"] == 2

    assert result["completed_steps"] == [
        "inspect_repository",
        "run_tests",
        "retry_tests",
        "run_tests",
        "retry_tests",
        "run_tests",
        "summarize_timeout",
    ]

    assert "实际测试次数：3" in result["summary"]
    assert "不再继续重试" in result["summary"]


@pytest.mark.parametrize(
    "status",
    ["failed", "no_tests", "error"],
)
def test_non_timeout_status_does_not_retry(
    sample_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    status: str,
) -> None:
    """即使允许重试，非超时状态也不能重复执行。"""

    calls = 0

    class FixedStatusRunner:
        def __init__(self, project: Path) -> None:
            self.project = project

        def run(
            self,
            target: str,
            timeout_seconds: int,
        ) -> SimpleNamespace:
            nonlocal calls
            calls += 1
            return SimpleNamespace(status=status)

    monkeypatch.setattr(
        conditional_workflow,
        "TestRunner",
        FixedStatusRunner,
    )

    result = conditional_workflow.run_conditional_workflow(
        sample_project,
        max_retries=2,
    )

    assert calls == 1
    assert result["status"] == status
    assert result["retry_count"] == 0
    assert "retry_tests" not in result["completed_steps"]


@pytest.mark.parametrize(
    ("target", "timeout_seconds", "max_retries", "message"),
    [
        ("   ", 30, 0, "测试目标不能为空"),
        ("tests", 0, 0, "超时时间必须大于 0"),
        ("tests", -1, 0, "超时时间必须大于 0"),
        ("tests", 30, -1, "重试次数必须在"),
        ("tests", 30, 3, "重试次数必须在"),
    ],
)
def test_invalid_inputs(
    sample_project: Path,
    target: str,
    timeout_seconds: int,
    max_retries: int,
    message: str,
) -> None:
    """输入不合法时，不能进入工作流执行。"""

    with pytest.raises(ValueError, match=message):
        conditional_workflow.run_conditional_workflow(
            project=sample_project,
            target=target,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
