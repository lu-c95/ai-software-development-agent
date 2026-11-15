"""Day 11：LangGraph Checkpoint 与会话持久化测试。"""

from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableLambda
from langgraph.checkpoint.sqlite import SqliteSaver

from ai_software_dev_agent.persistent_chat import (
    build_persistent_chat_graph,
    run_persistent_turn,
)


def create_fake_model() -> RunnableLambda:
    """创建能够感知历史用户消息数量的模拟模型。"""

    def respond(messages: list) -> AIMessage:
        user_messages = [
            message for message in messages if isinstance(message, HumanMessage)
        ]

        last_question = str(user_messages[-1].content)

        return AIMessage(
            content=(
                f"这是第 {len(user_messages)} 轮用户消息，本轮问题：{last_question}"
            )
        )

    return RunnableLambda(respond)


def test_session_survives_database_reopen(
    tmp_path: Path,
) -> None:
    """关闭数据库后重新打开，同一会话仍保留历史。"""

    db_path = tmp_path / "checkpoints.sqlite"

    # 模拟第一次启动程序。
    with SqliteSaver.from_conn_string(str(db_path)) as saver:
        graph = build_persistent_chat_graph(
            create_fake_model(),
            saver,
        )

        answer, history = run_persistent_turn(
            graph,
            thread_id="python-learning",
            question="我正在学习 LangGraph",
        )

        assert "第 1 轮" in answer
        assert len(history) == 2

    # 第一个 with 结束，数据库连接已经关闭。
    assert db_path.is_file()

    # 模拟程序重新启动，重新打开同一个数据库文件。
    with SqliteSaver.from_conn_string(str(db_path)) as saver:
        graph = build_persistent_chat_graph(
            create_fake_model(),
            saver,
        )

        answer, history = run_persistent_turn(
            graph,
            thread_id="python-learning",
            question="现在学习 Checkpoint",
        )

        # 新建了 Graph 和模型，仍然能够恢复上一轮消息。
        assert "第 2 轮" in answer
        assert len(history) == 4

        assert isinstance(history[0], HumanMessage)
        assert history[0].content == "我正在学习 LangGraph"

        assert isinstance(history[1], AIMessage)

        assert isinstance(history[2], HumanMessage)
        assert history[2].content == "现在学习 Checkpoint"

        assert isinstance(history[3], AIMessage)


def test_different_threads_are_isolated(
    tmp_path: Path,
) -> None:
    """不同 thread_id 应维护独立的会话历史。"""

    db_path = tmp_path / "checkpoints.sqlite"

    with SqliteSaver.from_conn_string(str(db_path)) as saver:
        graph = build_persistent_chat_graph(
            create_fake_model(),
            saver,
        )

        first_answer, _ = run_persistent_turn(
            graph,
            "session-a",
            "A 的第一轮",
        )

        second_answer, _ = run_persistent_turn(
            graph,
            "session-a",
            "A 的第二轮",
        )

        other_answer, other_history = run_persistent_turn(
            graph,
            "session-b",
            "B 的第一轮",
        )

        assert "第 1 轮" in first_answer
        assert "第 2 轮" in second_answer

        # B 不应该继承 A 的两轮历史。
        assert "第 1 轮" in other_answer
        assert len(other_history) == 2

        assert other_history[0].content == "B 的第一轮"


def test_checkpoint_can_be_inspected(
    tmp_path: Path,
) -> None:
    """使用 graph.get_state() 查看保存的会话状态。"""

    db_path = tmp_path / "checkpoints.sqlite"

    with SqliteSaver.from_conn_string(str(db_path)) as saver:
        graph = build_persistent_chat_graph(
            create_fake_model(),
            saver,
        )

        run_persistent_turn(
            graph,
            "inspect-session",
            "请记住这个问题",
        )

        config = {
            "configurable": {
                "thread_id": "inspect-session",
            }
        }

        snapshot = graph.get_state(config)

        messages = snapshot.values["messages"]

        assert len(messages) == 2
        assert messages[0].content == "请记住这个问题"
        assert isinstance(messages[1], AIMessage)

        # 图已经正常完成，不再有等待执行的节点。
        assert snapshot.next == ()


@pytest.mark.parametrize(
    ("thread_id", "question", "expected_error"),
    [
        ("   ", "你好", "会话 ID 不能为空"),
        ("session-a", "   ", "用户问题不能为空"),
    ],
)
def test_rejects_blank_inputs(
    tmp_path: Path,
    thread_id: str,
    question: str,
    expected_error: str,
) -> None:
    """空会话 ID 和空问题都应提前拒绝。"""

    db_path = tmp_path / "checkpoints.sqlite"

    with SqliteSaver.from_conn_string(str(db_path)) as saver:
        graph = build_persistent_chat_graph(
            create_fake_model(),
            saver,
        )

        with pytest.raises(ValueError, match=expected_error):
            run_persistent_turn(
                graph,
                thread_id,
                question,
            )


def test_rejects_invalid_model_response(
    tmp_path: Path,
) -> None:
    """模型没有返回 AIMessage 时，不能报告正常完成。"""

    db_path = tmp_path / "checkpoints.sqlite"

    # 故意模拟一个返回普通字符串的错误模型。
    invalid_model = RunnableLambda(lambda messages: "这不是 AIMessage")

    with SqliteSaver.from_conn_string(str(db_path)) as saver:
        graph = build_persistent_chat_graph(
            invalid_model,
            saver,
        )

        with pytest.raises(
            ValueError,
            match="有效的最终 AI 消息",
        ):
            run_persistent_turn(
                graph,
                "invalid-response",
                "你好",
            )
