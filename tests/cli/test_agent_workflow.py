"""LangChain Agent + LangGraph CLI 命令测试。"""

from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.runnables import RunnableLambda
from openai import OpenAIError

from ai_software_dev_agent import agent_workflow as workflow_core
from ai_software_dev_agent import cli
from ai_software_dev_agent.agent import AgentExecutionError
from ai_software_dev_agent.commands import agent_workflow as command
from ai_software_dev_agent.model import ModelConfigError


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    """创建独立的测试仓库。"""

    (tmp_path / "demo.py").write_text(
        "def add(a, b):\n    return a + b\n",
        encoding="utf-8",
    )

    return tmp_path


@pytest.fixture
def fake_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, object]:
    """模拟模型和 Agent 构建，不访问模型服务。"""

    observed: dict[str, object] = {
        "settings_calls": 0,
    }

    settings = object()
    model = object()
    agent = RunnableLambda(lambda value: value)

    def fake_load_settings() -> object:
        observed["settings_calls"] = int(observed["settings_calls"]) + 1
        return settings

    def fake_create_model(actual_settings: object) -> object:
        observed["model_settings"] = actual_settings
        return model

    def fake_build_agent(
        actual_model: object,
        project: Path,
    ) -> RunnableLambda:
        observed["model"] = actual_model
        observed["project"] = project
        return agent

    monkeypatch.setattr(
        command,
        "load_model_settings",
        fake_load_settings,
    )

    monkeypatch.setattr(
        command,
        "create_chat_model",
        fake_create_model,
    )

    monkeypatch.setattr(
        command,
        "build_workflow_analysis_agent",
        fake_build_agent,
    )

    observed["expected_settings"] = settings
    observed["expected_model"] = model
    observed["expected_agent"] = agent

    return observed


@pytest.fixture
def fake_agent_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, object]:
    """模拟 run_agent_turn，并记录接收到的输入。"""

    observed: dict[str, object] = {}

    def fake_run_turn(
        agent: object,
        history: list[BaseMessage],
        question: str,
    ) -> tuple[str, list[BaseMessage]]:
        observed["agent"] = agent
        observed["history"] = history
        observed["question"] = question

        answer = "demo.py 包含一个加法函数。"

        updated_history = [
            *history,
            HumanMessage(content=question),
            AIMessage(content=answer),
        ]

        return answer, updated_history

    monkeypatch.setattr(
        workflow_core,
        "run_agent_turn",
        fake_run_turn,
    )

    return observed


def test_agent_workflow_cli_success(
    sample_project: Path,
    fake_dependencies: dict[str, object],
    fake_agent_turn: dict[str, object],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """真正执行外层 LangGraph，内部 Agent 使用模拟实现。"""

    result = cli.main(
        [
            "agent-workflow",
            "--project",
            str(sample_project),
            "--task",
            "解释 demo.py 的作用",
        ]
    )

    output = capsys.readouterr().out

    assert result == 0

    assert "[1/3] inspect_repository 已完成" in output
    assert "[2/3] run_agent 已完成" in output
    assert "[3/3] summarize 已完成" in output

    assert "demo.py 包含一个加法函数" in output
    assert "当前消息数：2" in output
    assert "工作流状态：completed" in output

    # 验证模型和 Agent 依赖确实经过预期的创建过程。
    assert (
        fake_dependencies["model_settings"] is (fake_dependencies["expected_settings"])
    )
    assert fake_dependencies["model"] is (fake_dependencies["expected_model"])
    assert fake_dependencies["project"] == sample_project.resolve()

    # 验证上游仓库文件信息和任务被传给 Agent。
    assert fake_agent_turn["agent"] is (fake_dependencies["expected_agent"])

    assert "demo.py" in str(fake_agent_turn["question"])
    assert "解释 demo.py 的作用" in str(fake_agent_turn["question"])
    assert fake_agent_turn["history"] == []


def test_agent_workflow_cli_uses_current_directory(
    sample_project: Path,
    fake_dependencies: dict[str, object],
    fake_agent_turn: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """不传 --project 时使用当前工作目录。"""

    monkeypatch.chdir(sample_project)

    result = cli.main(
        [
            "agent-workflow",
            "--task",
            "解释项目",
        ]
    )

    output = capsys.readouterr().out

    assert result == 0
    assert f"项目目录：{sample_project.resolve()}" in output


def test_agent_workflow_cli_rejects_blank_task(
    sample_project: Path,
    fake_dependencies: dict[str, object],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """空任务直接拒绝，不创建模型。"""

    result = cli.main(
        [
            "agent-workflow",
            "--project",
            str(sample_project),
            "--task",
            "   ",
        ]
    )

    captured = capsys.readouterr()

    assert result == 2
    assert "任务不能为空" in captured.err
    assert fake_dependencies["settings_calls"] == 0


def test_agent_workflow_cli_rejects_missing_project(
    tmp_path: Path,
    fake_dependencies: dict[str, object],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """项目不存在时，不应该初始化模型。"""

    missing = tmp_path / "missing"

    result = cli.main(
        [
            "agent-workflow",
            "--project",
            str(missing),
            "--task",
            "分析项目",
        ]
    )

    captured = capsys.readouterr()

    assert result == 2
    assert "项目或模型配置错误" in captured.err
    assert fake_dependencies["settings_calls"] == 0


def test_agent_workflow_cli_requires_task() -> None:
    """--task 是必填参数。"""

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["agent-workflow"])

    assert exc_info.value.code == 2


def test_agent_workflow_cli_help(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """子命令帮助中应包含项目和任务参数。"""

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["agent-workflow", "--help"])

    assert exc_info.value.code == 0

    output = capsys.readouterr().out

    assert "--project" in output
    assert "--task" in output


def test_top_level_help_lists_agent_workflow(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """顶层 CLI 帮助中应出现新命令。"""

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--help"])

    assert exc_info.value.code == 0
    assert "agent-workflow" in capsys.readouterr().out


def test_agent_workflow_cli_reports_model_config_error(
    sample_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """模型配置缺失时，返回参数/配置错误。"""

    def broken_settings() -> None:
        raise ModelConfigError("缺少模型 API Key")

    monkeypatch.setattr(
        command,
        "load_model_settings",
        broken_settings,
    )

    result = cli.main(
        [
            "agent-workflow",
            "--project",
            str(sample_project),
            "--task",
            "分析项目",
        ]
    )

    captured = capsys.readouterr()

    assert result == 2
    assert "缺少模型 API Key" in captured.err


def test_agent_workflow_cli_reports_agent_failure(
    sample_project: Path,
    fake_dependencies: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Agent 执行失败不能被报告为工作流成功。"""

    def broken_turn(
        agent: object,
        history: list[BaseMessage],
        question: str,
    ) -> None:
        raise AgentExecutionError("模拟 Agent 执行失败")

    monkeypatch.setattr(
        workflow_core,
        "run_agent_turn",
        broken_turn,
    )

    result = cli.main(
        [
            "agent-workflow",
            "--project",
            str(sample_project),
            "--task",
            "分析项目",
        ]
    )

    captured = capsys.readouterr()

    assert result == 1
    assert "模拟 Agent 执行失败" in captured.err
    assert "工作流状态：completed" not in captured.out


def test_agent_workflow_cli_reports_model_error(
    sample_project: Path,
    fake_dependencies: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """模型调用失败时，CLI 应返回非零退出码。"""

    def broken_turn(
        agent: object,
        history: list[BaseMessage],
        question: str,
    ) -> None:
        raise OpenAIError("模拟模型服务连接失败")

    monkeypatch.setattr(
        workflow_core,
        "run_agent_turn",
        broken_turn,
    )

    result = cli.main(
        [
            "agent-workflow",
            "--project",
            str(sample_project),
            "--task",
            "分析项目",
        ]
    )

    captured = capsys.readouterr()

    assert result == 1
    assert "模拟模型服务连接失败" in captured.err


def test_agent_workflow_cli_rejects_incomplete_graph(
    sample_project: Path,
    fake_dependencies: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """外层工作流未完成全部节点时不能返回成功。"""

    class IncompleteGraph:
        """模拟只完成仓库探索的工作流。"""

        def stream(
            self,
            state: dict,
            stream_mode: str,
        ):
            # 模拟新版 inspect_repository 节点的数据结构。
            yield {
                "inspect_repository": {
                    "files": ["demo.py"],
                    "read_files": ["demo.py"],
                    "evidence": "demo.py 中定义了一个加法函数",
                    "completed_steps": ["inspect_repository"],
                }
            }

    monkeypatch.setattr(
        command,
        "build_agent_workflow",
        lambda agent: IncompleteGraph(),
    )

    result = cli.main(
        [
            "agent-workflow",
            "--project",
            str(sample_project),
            "--task",
            "分析项目",
        ]
    )

    captured = capsys.readouterr()

    # 只完成第一个节点，不应报告整个工作流成功。
    assert result == 1
    assert "工作流执行不完整" in captured.err
    assert "工作流状态：completed" not in captured.out
