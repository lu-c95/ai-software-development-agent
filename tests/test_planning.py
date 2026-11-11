"""开发计划结构与生成流程测试。"""

import pytest
from langchain_core.runnables import RunnableLambda
from pydantic import ValidationError

from ai_software_dev_agent.model import ModelConfigError
from ai_software_dev_agent.planning import (
    DevelopmentPlan,
    PlanningError,
    PlanStep,
    generate_development_plan,
)


def create_sample_plan() -> DevelopmentPlan:
    """创建测试使用的合法开发计划。"""

    return DevelopmentPlan(
        goal="增加用户登录功能",
        assumptions=["尚未检查现有认证模块"],
        steps=[
            PlanStep(
                title="检查项目",
                action="了解现有用户模块",
                verification="确认相关文件和接口",
            ),
            PlanStep(
                title="实现登录",
                action="编写登录接口",
                verification="通过登录接口测试",
            ),
        ],
    )


class StubStructuredChatModel:
    """模拟支持结构化输出的模型，不调用真实 API。"""

    def __init__(self, output: object) -> None:
        self.output = output
        self.received_messages = None
        self.called_schema = None
        self.called_method = None

    def with_structured_output(
        self,
        schema: type[DevelopmentPlan],
        *,
        method: str,
    ) -> RunnableLambda:
        """记录传入的 Schema 和输出方法。"""

        self.called_schema = schema
        self.called_method = method

        return RunnableLambda(self._invoke)

    def _invoke(self, messages: object) -> object:
        """模拟模型返回结构化结果。"""

        self.received_messages = messages
        return self.output


def test_plan_step_rejects_empty_title() -> None:
    """开发步骤的名称不能为空。"""

    with pytest.raises(ValidationError):
        PlanStep(
            title="",
            action="编写登录接口",
            verification="运行测试",
        )


def test_development_plan_requires_two_steps() -> None:
    """开发计划至少包含两个步骤。"""

    with pytest.raises(ValidationError):
        DevelopmentPlan(
            goal="实现登录",
            steps=[],
        )


def test_development_plan_rejects_too_many_steps() -> None:
    """开发计划最多包含五个步骤。"""

    step = PlanStep(
        title="开发任务",
        action="执行开发操作",
        verification="运行测试",
    )

    with pytest.raises(ValidationError):
        DevelopmentPlan(
            goal="实现登录",
            steps=[step] * 6,
        )


def test_generate_development_plan() -> None:
    """验证模型使用指定 Schema 和 function_calling。"""

    expected_plan = create_sample_plan()
    fake_model = StubStructuredChatModel(expected_plan)

    result = generate_development_plan(
        fake_model,
        "增加用户登录功能",
    )

    assert result == expected_plan
    assert fake_model.called_schema is DevelopmentPlan
    assert fake_model.called_method == "function_calling"

    # 检查用户任务确实进入了模型消息。
    assert "增加用户登录功能" in (fake_model.received_messages[-1].content)


def test_generate_development_plan_rejects_empty_task() -> None:
    """空开发任务不能发送给模型。"""

    fake_model = StubStructuredChatModel(create_sample_plan())

    with pytest.raises(
        ModelConfigError,
        match="开发任务不能为空",
    ):
        generate_development_plan(fake_model, "   ")


def test_generate_development_plan_rejects_wrong_output() -> None:
    """模型没有返回 Pydantic 对象时应报错。"""

    fake_model = StubStructuredChatModel(
        {"goal": "普通字典，不是 DevelopmentPlan 对象"}
    )

    with pytest.raises(PlanningError):
        generate_development_plan(
            fake_model,
            "增加用户登录功能",
        )
