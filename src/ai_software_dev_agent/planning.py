"""使用 LangChain 和 Pydantic 生成结构化开发计划。"""

from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from ai_software_dev_agent.model import ModelConfigError


class PlanningError(RuntimeError):
    """模型未能返回符合预期结构的开发计划。"""


class PlanStep(BaseModel):
    """单个开发步骤。"""

    title: str = Field(
        min_length=1,
        description="步骤名称，例如检查现有代码结构",
    )

    action: str = Field(
        min_length=1,
        description="本步骤需要完成的具体开发操作",
    )

    verification: str = Field(
        min_length=1,
        description="如何验证这个步骤是否完成",
    )


class DevelopmentPlan(BaseModel):
    """完整的软件开发任务计划。"""

    goal: str = Field(
        min_length=1,
        description="开发任务的整体目标",
    )

    assumptions: list[str] = Field(
        default_factory=list,
        description="尚未验证、需要后续确认的前提条件",
    )

    steps: list[PlanStep] = Field(
        min_length=2,
        max_length=5,
        description="按执行顺序排列的开发步骤，数量为2到5",
    )


# 规划阶段只生成计划，不读取或修改真实代码仓库。
PLANNING_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "你是一名专业的 Python 软件开发规划助手。"
            "根据用户开发需求，生成恰好3个简短、可执行的步骤。"
            "每个步骤包含 title、action 和 verification。"
            "每项 action 和 verification 尽量控制在30个汉字以内。"
            "assumptions 最多列出2项，且必须是真正需要确认的前提。"
            "不要假设已经读取、修改或测试过项目代码。"
            "不要将未经确认的技术选择当作项目既定事实。",
        ),
        (
            "human",
            "请为下面的开发任务制定计划：\n{task}",
        ),
    ]
)


def generate_development_plan(
    model: BaseChatModel,
    task: str,
) -> DevelopmentPlan:
    """调用模型，生成经过 Pydantic 校验的开发计划。"""

    if not task.strip():
        raise ModelConfigError("开发任务不能为空")

    # function_calling 使用工具调用机制承载结构化输出。
    structured_model = model.with_structured_output(
        DevelopmentPlan,
        method="function_calling",
    )

    messages = PLANNING_PROMPT.format_messages(
        task=task.strip(),
    )

    plan = structured_model.invoke(messages)

    # 正常情况下，LangChain 会返回 DevelopmentPlan 实例。
    if not isinstance(plan, DevelopmentPlan):
        raise PlanningError("模型未返回有效的 DevelopmentPlan 对象")

    return plan
