"""Day 16 Markdown 评估报告测试。"""

from copy import deepcopy

import pytest

from ai_software_dev_agent.evaluation_report import (
    render_markdown_report,
)


@pytest.fixture
def sample_report() -> dict:
    """构造包含成功与失败案例的评估报告。"""

    failed_case = {
        "case_id": "deny_secret_file",
        "category": "security",
        "expected": "denied",
        "actual": "error",
        "passed": False,
        "reason": "权限工具出错 | 需要调查",
    }

    return {
        "timestamp": "2026-11-24 15:27:30.123",
        "timezone": "Asia/Shanghai",
        "mode": "offline_local_tools",
        "total": 2,
        "passed": 1,
        "failed": 1,
        "success_rate": 50.0,
        "categories": {
            "repository": {
                "total": 1,
                "passed": 1,
                "success_rate": 100.0,
            },
            "security": {
                "total": 1,
                "passed": 0,
                "success_rate": 0.0,
            },
        },
        "results": [
            {
                "case_id": "read_readme",
                "category": "repository",
                "expected": "allowed",
                "actual": "allowed",
                "passed": True,
                "reason": "符合预期",
            },
            failed_case,
        ],
        "failures": [failed_case],
    }


def test_render_markdown_summary(
    sample_report: dict,
) -> None:
    """Markdown 应正确展示整体统计。"""

    markdown = render_markdown_report(sample_report)

    assert "评估任务总数 | 2" in markdown
    assert "通过任务数 | 1" in markdown
    assert "失败任务数 | 1" in markdown
    assert "离线成功率 | 50.00%" in markdown
    assert "Asia/Shanghai" in markdown


def test_render_markdown_failure_details(
    sample_report: dict,
) -> None:
    """失败案例必须完整保留，不能只展示成功率。"""

    markdown = render_markdown_report(sample_report)

    assert "deny_secret_file" in markdown
    assert "实际结果：`error`" in markdown

    # 竖线必须被转义，避免破坏 Markdown 表格。
    assert r"权限工具出错 \| 需要调查" in markdown


def test_render_markdown_without_failures(
    sample_report: dict,
) -> None:
    """全部通过时应明确说明没有失败案例。"""

    data = deepcopy(sample_report)

    success = data["results"][0]

    data["results"] = [success]
    data["failures"] = []

    data["total"] = 1
    data["passed"] = 1
    data["failed"] = 0
    data["success_rate"] = 100.0

    data["categories"] = {
        "repository": {
            "total": 1,
            "passed": 1,
            "success_rate": 100.0,
        }
    }

    markdown = render_markdown_report(data)

    assert "离线成功率 | 100.00%" in markdown
    assert "本次评估没有失败案例" in markdown


def test_reject_inconsistent_success_rate(
    sample_report: dict,
) -> None:
    """统计数据矛盾时必须拒绝生成报告。"""

    data = deepcopy(sample_report)

    # 故意把 50% 写成 100%。
    data["success_rate"] = 100.0

    with pytest.raises(ValueError, match="成功率不一致"):
        render_markdown_report(data)
