"""LangGraph 工作流状态、节点顺序与执行结果测试。"""

from pathlib import Path

import pytest

from ai_software_dev_agent.repository import RepositoryError
from ai_software_dev_agent.test_runner import (
    TestRunnerError as RunnerError,
)
from ai_software_dev_agent.workflow import (
    DevelopmentWorkflowState,
    build_development_workflow,
    run_development_workflow,
)


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    """创建包含 Python 文件和 pytest 测试的临时项目。"""

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()

    (tmp_path / "demo.py").write_text(
        "def add(a, b):\n    return a + b\n",
        encoding="utf-8",
    )

    (tests_dir / "test_demo.py").write_text(
        "def test_add():\n    assert 1 + 1 == 2\n",
        encoding="utf-8",
    )

    return tmp_path


def make_initial_state(
    project: Path,
    target: str = "tests",
) -> DevelopmentWorkflowState:
    """构造一份新的工作流初始状态。"""

    return {
        "project": str(project),
        "target": target,
        "timeout_seconds": 30,
        "completed_steps": [],
    }


def test_workflow_runs_all_nodes(
    sample_project: Path,
) -> None:
    """验证三个节点依次执行，并产生完整状态。"""

    workflow = build_development_workflow()

    result = workflow.invoke(make_initial_state(sample_project))

    # 初始输入信息仍保留在共享状态里。
    assert result["project"] == str(sample_project)
    assert result["target"] == "tests"

    # RepositoryExplorer 的结果已进入 State。
    assert any(Path(path).name == "demo.py" for path in result["files"])

    # TestRunner 的结果已进入 State。
    test_result = result["test_result"]

    assert test_result.status == "passed"
    assert test_result.exit_code == 0
    assert test_result.passed is True

    # Reducer 应追加三个节点的完成记录。
    assert result["completed_steps"] == [
        "inspect_repository",
        "run_tests",
        "summarize",
    ]

    assert "pytest 状态：passed" in result["summary"]
    assert "仓库文件数：" in result["summary"]


def test_workflow_summarizes_failed_tests(
    sample_project: Path,
) -> None:
    """pytest 断言失败后，工作流仍应执行总结节点。"""

    (sample_project / "tests" / "test_demo.py").write_text(
        "def test_add():\n    assert 1 + 1 == 3\n",
        encoding="utf-8",
    )

    result = run_development_workflow(sample_project)

    assert result["test_result"].status == "failed"
    assert result["test_result"].exit_code == 1
    assert "pytest 状态：failed" in result["summary"]

    assert result["completed_steps"][-1] == "summarize"


def test_workflow_summarizes_no_tests(
    sample_project: Path,
) -> None:
    """没有测试时应生成 no_tests 摘要，而不是误报通过。"""

    (sample_project / "tests" / "test_demo.py").unlink()

    result = run_development_workflow(sample_project)

    assert result["test_result"].status == "no_tests"
    assert result["test_result"].exit_code == 5
    assert "pytest 状态：no_tests" in result["summary"]

    assert result["completed_steps"] == [
        "inspect_repository",
        "run_tests",
        "summarize",
    ]


def test_workflow_rejects_invalid_project(
    tmp_path: Path,
) -> None:
    """不存在的仓库应该在探索节点失败。"""

    with pytest.raises(RepositoryError):
        run_development_workflow(tmp_path / "missing")


def test_workflow_rejects_invalid_test_target(
    sample_project: Path,
) -> None:
    """测试目标无效时，应传播 TestRunner 的参数错误。"""

    with pytest.raises(RunnerError):
        run_development_workflow(
            sample_project,
            target="tests/test_missing.py",
        )


def test_workflow_stream_shows_node_updates(
    sample_project: Path,
) -> None:
    """stream 模式应该逐步输出各节点的状态更新。"""

    workflow = build_development_workflow()

    events = list(
        workflow.stream(
            make_initial_state(sample_project),
            stream_mode="updates",
        )
    )

    node_names = [next(iter(event)) for event in events]

    assert node_names == [
        "inspect_repository",
        "run_tests",
        "summarize",
    ]


def test_workflow_runs_have_independent_state(
    sample_project: Path,
) -> None:
    """两次独立调用不应该继承前一次的步骤历史。"""

    first = run_development_workflow(sample_project)
    second = run_development_workflow(sample_project)

    expected_steps = [
        "inspect_repository",
        "run_tests",
        "summarize",
    ]

    assert first["completed_steps"] == expected_steps
    assert second["completed_steps"] == expected_steps
