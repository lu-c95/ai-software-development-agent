"""LangChain Agent 与 LangGraph 工作流集成测试。"""

from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableLambda

from ai_software_dev_agent import agent_workflow
from ai_software_dev_agent.repository import RepositoryError


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    """创建一个最小的独立 Python 项目。"""

    (tmp_path / "demo.py").write_text(
        "def add(a, b):\n    return a + b\n",
        encoding="utf-8",
    )

    return tmp_path


@pytest.fixture
def fake_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> RunnableLambda:
    """创建假的 Agent 调用，避免消耗模型 API。"""

    def fake_run_agent_turn(
        agent: object,
        history: list,
        question: str,
    ) -> tuple[str, list]:
        answer = "模拟回答：demo.py 定义了一个加法函数。"

        updated_history = [
            *history,
            HumanMessage(content=question),
            AIMessage(content=answer),
        ]

        return answer, updated_history

    # 将真实 Agent 调用替换为可控的模拟函数。
    monkeypatch.setattr(
        agent_workflow,
        "run_agent_turn",
        fake_run_agent_turn,
    )

    return RunnableLambda(lambda value: value)


def test_agent_workflow_runs_all_nodes(
    sample_project: Path,
    fake_agent: RunnableLambda,
) -> None:
    """验证仓库探索、Agent 与总结三个节点正常执行。"""

    result = agent_workflow.run_agent_workflow(
        project=sample_project,
        task="解释这个项目",
        agent=fake_agent,
    )

    assert result["completed_steps"] == [
        "inspect_repository",
        "run_agent",
        "summarize",
    ]

    assert any(Path(path).name == "demo.py" for path in result["files"])

    assert "模拟回答" in result["answer"]
    assert "解释这个项目" in result["summary"]
    assert "Agent 回答：" in result["summary"]

    assert len(result["history"]) == 2
    assert isinstance(result["history"][0], HumanMessage)
    assert isinstance(result["history"][1], AIMessage)


def test_agent_receives_repository_context(
    sample_project: Path,
    fake_agent: RunnableLambda,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """确认 Agent 获得上游节点产生的文件信息。"""

    observed: dict[str, object] = {}

    def capture_turn(
        agent: object,
        history: list,
        question: str,
    ) -> tuple[str, list]:
        observed["agent"] = agent
        observed["history"] = history
        observed["question"] = question

        return (
            "已分析",
            [
                *history,
                HumanMessage(content=question),
                AIMessage(content="已分析"),
            ],
        )

    monkeypatch.setattr(
        agent_workflow,
        "run_agent_turn",
        capture_turn,
    )

    result = agent_workflow.run_agent_workflow(
        sample_project,
        "说明 demo.py 的作用",
        fake_agent,
    )

    assert observed["agent"] is fake_agent
    assert observed["history"] == []
    assert "demo.py" in observed["question"]
    assert "说明 demo.py 的作用" in observed["question"]
    assert result["answer"] == "已分析"


def test_agent_workflow_preserves_existing_history(
    sample_project: Path,
    fake_agent: RunnableLambda,
) -> None:
    """旧消息应该保留，并追加新一轮消息。"""

    history = [
        HumanMessage(content="你好"),
        AIMessage(content="你好，有什么需要帮助？"),
    ]

    result = agent_workflow.run_agent_workflow(
        project=sample_project,
        task="继续解释这个项目",
        agent=fake_agent,
        history=history,
    )

    updated = result["history"]

    assert len(history) == 2
    assert len(updated) == 4

    assert updated[0] is history[0]
    assert updated[1] is history[1]

    assert isinstance(updated[2], HumanMessage)
    assert isinstance(updated[3], AIMessage)
    assert "继续解释这个项目" in updated[2].content


def test_agent_workflow_streams_node_updates(
    sample_project: Path,
    fake_agent: RunnableLambda,
) -> None:
    """LangGraph 应按固定顺序输出三个节点的更新。"""

    graph = agent_workflow.build_agent_workflow(fake_agent)

    initial_state = {
        "project": str(sample_project),
        "task": "说明项目结构",
        "history": [],
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
        "run_agent",
        "summarize",
    ]


def test_agent_workflow_rejects_empty_task(
    sample_project: Path,
    fake_agent: RunnableLambda,
) -> None:
    """空任务在执行任何节点之前被拒绝。"""

    with pytest.raises(
        ValueError,
        match="任务不能为空",
    ):
        agent_workflow.run_agent_workflow(
            sample_project,
            "   ",
            fake_agent,
        )


def test_agent_workflow_rejects_missing_project(
    tmp_path: Path,
    fake_agent: RunnableLambda,
) -> None:
    """项目不存在时，仓库探索节点应报错。"""

    with pytest.raises(RepositoryError):
        agent_workflow.run_agent_workflow(
            tmp_path / "missing",
            "分析项目",
            fake_agent,
        )


def test_agent_error_is_not_reported_as_success(
    sample_project: Path,
    fake_agent: RunnableLambda,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Agent 执行失败时，不能虚构正常回答。"""

    def broken_turn(
        agent: object,
        history: list,
        question: str,
    ) -> None:
        raise RuntimeError("模拟 Agent 执行失败")

    monkeypatch.setattr(
        agent_workflow,
        "run_agent_turn",
        broken_turn,
    )

    with pytest.raises(
        RuntimeError,
        match="模拟 Agent 执行失败",
    ):
        agent_workflow.run_agent_workflow(
            sample_project,
            "分析项目",
            fake_agent,
        )
