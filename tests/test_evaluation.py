"""Day 16 评估框架的自动化测试。"""

import json
import re
from pathlib import Path

import pytest

from ai_software_dev_agent.evaluation import (
    EvaluationCase,
    Observation,
    evaluate,
    load_cases,
    save_report,
)


def make_case(
    case_id: str,
    expected: str = "allowed",
    contains: str | None = None,
) -> EvaluationCase:
    """创建测试使用的评估任务。"""

    return EvaluationCase(
        case_id=case_id,
        category="repository",
        kind="read",
        target="README.md",
        expected=expected,
        contains=contains,
    )


def test_load_cases_accepts_valid_dataset(
    tmp_path: Path,
) -> None:
    """正确加载合法的 JSON 评估集。"""

    dataset = tmp_path / "cases.json"

    dataset.write_text(
        json.dumps(
            [
                {
                    "id": "read_01",
                    "category": "repository",
                    "kind": "read",
                    "target": "README.md",
                    "expected": "allowed",
                }
            ]
        ),
        encoding="utf-8",
    )

    cases = load_cases(dataset)

    assert len(cases) == 1
    assert cases[0].case_id == "read_01"
    assert cases[0].target == "README.md"


def test_load_cases_rejects_duplicate_ids(
    tmp_path: Path,
) -> None:
    """重复的任务 ID 必须被拒绝。"""

    dataset = tmp_path / "duplicate.json"

    item = {
        "id": "same_id",
        "category": "repository",
        "kind": "read",
        "target": "README.md",
        "expected": "allowed",
    }

    dataset.write_text(
        json.dumps([item, item]),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="重复"):
        load_cases(dataset)


def test_evaluate_calculates_success_rate() -> None:
    """检查通过率和失败案例统计。"""

    cases = [
        make_case("success"),
        make_case("failure", expected="denied"),
    ]

    def fake_executor(
        case: EvaluationCase,
    ) -> Observation:
        # 两个任务都返回 allowed：
        # 第一个通过，第二个不符合 denied 预期。
        return Observation(
            outcome="allowed",
            output="README",
        )

    report = evaluate(
        cases,
        fake_executor,
        mode="unit_test_fake",
    )

    assert report.total == 2
    assert report.passed == 1
    assert report.failed == 1
    assert report.success_rate == 50.0

    data = report.to_dict()

    assert len(data["failures"]) == 1
    assert data["failures"][0]["case_id"] == "failure"


def test_missing_content_is_failure() -> None:
    """工具允许读取，但内容不匹配仍然失败。"""

    cases = [
        make_case(
            "missing_text",
            contains="FREESHIP",
        )
    ]

    report = evaluate(
        cases,
        lambda case: Observation(
            outcome="allowed",
            output="普通文件内容",
        ),
    )

    assert report.failed == 1
    assert "缺少预期内容" in report.results[0].reason


def test_executor_exception_is_not_denial() -> None:
    """执行异常不能被误判为安全拒绝成功。"""

    cases = [
        make_case(
            "denied_case",
            expected="denied",
        )
    ]

    def broken_executor(
        case: EvaluationCase,
    ) -> Observation:
        raise FileNotFoundError("文件不存在")

    report = evaluate(cases, broken_executor)

    assert report.failed == 1
    assert report.results[0].actual == "error"


def test_empty_evaluation_does_not_divide_by_zero() -> None:
    """空评估不发生除零异常。"""

    report = evaluate(
        [],
        lambda case: Observation(outcome="allowed"),
    )

    assert report.total == 0
    assert report.success_rate == 0.0


def test_save_report_contains_timestamp_and_results(
    tmp_path: Path,
) -> None:
    """报告保存成功，且时间精确到毫秒。"""

    report = evaluate(
        [make_case("read_01")],
        lambda case: Observation(
            outcome="allowed",
            output="README",
        ),
    )

    destination = tmp_path / "reports" / "result.json"

    save_report(report, destination)

    saved = json.loads(destination.read_text(encoding="utf-8"))

    assert saved["total"] == 1
    assert saved["passed"] == 1
    assert saved["success_rate"] == 100.0
    assert saved["timezone"] == "Asia/Shanghai"

    # YYYY-MM-DD HH:mm:ss.SSS
    assert re.fullmatch(
        r"\d{4}-\d{2}-\d{2} "
        r"\d{2}:\d{2}:\d{2}\.\d{3}",
        saved["timestamp"],
    )
