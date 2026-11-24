"""Day 16：离线评估数据、成功率统计与失败记录。"""

import json
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# 不同评估任务允许使用的预期结果。
VALID_EXPECTATIONS = {
    "read": {"allowed", "denied"},
    "pytest": {"passed"},
    "git_clean": {"clean"},
}


@dataclass(frozen=True)
class EvaluationCase:
    """一条固定的评估任务。"""

    case_id: str
    category: str
    kind: str
    target: str
    expected: str
    contains: str | None = None


@dataclass(frozen=True)
class Observation:
    """评估执行器实际观察到的结果。"""

    outcome: str
    output: str = ""
    detail: str = ""


@dataclass(frozen=True)
class CaseResult:
    """单个评估任务的评分结果。"""

    case_id: str
    category: str
    expected: str
    actual: str
    passed: bool
    reason: str


@dataclass(frozen=True)
class EvaluationReport:
    """一批评估任务的最终结果。"""

    timestamp: str
    timezone: str
    mode: str
    results: list[CaseResult]

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(result.passed for result in self.results)

    @property
    def failed(self) -> int:
        return self.total - self.passed

    @property
    def success_rate(self) -> float:
        """返回百分比，避免空评估集除零。"""

        if self.total == 0:
            return 0.0

        return round(self.passed / self.total * 100, 2)

    def to_dict(self) -> dict:
        """整理报告，包含分类统计和失败案例。"""

        categories: dict[str, dict] = {}

        for result in self.results:
            stats = categories.setdefault(
                result.category,
                {"total": 0, "passed": 0},
            )

            stats["total"] += 1

            if result.passed:
                stats["passed"] += 1

        # 计算每个类别自己的成功率。
        for stats in categories.values():
            stats["success_rate"] = round(
                stats["passed"] / stats["total"] * 100,
                2,
            )

        return {
            "timestamp": self.timestamp,
            "timezone": self.timezone,
            "mode": self.mode,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "success_rate": self.success_rate,
            "categories": categories,
            "failures": [
                asdict(result) for result in self.results if not result.passed
            ],
            "results": [asdict(result) for result in self.results],
        }


def load_cases(path: Path) -> list[EvaluationCase]:
    """读取并验证 JSON 评估集。"""

    raw = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(raw, list) or not raw:
        raise ValueError("评估集必须是非空 JSON 数组")

    cases = []
    seen_ids = set()

    required = (
        "id",
        "category",
        "kind",
        "target",
        "expected",
    )

    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"第 {index + 1} 条任务不是对象")

        # 缺失字段、空字符串都视为无效任务。
        if any(
            not isinstance(item.get(key), str) or not item[key].strip()
            for key in required
        ):
            raise ValueError(f"第 {index + 1} 条任务字段不完整")

        case_id = item["id"]
        kind = item["kind"]
        expected = item["expected"]
        contains = item.get("contains")

        if case_id in seen_ids:
            raise ValueError(f"重复的任务 ID：{case_id}")

        if kind not in VALID_EXPECTATIONS or expected not in VALID_EXPECTATIONS[kind]:
            raise ValueError(f"任务 {case_id} 的类型或预期结果无效")

        if contains is not None:
            if (
                kind != "read"
                or expected != "allowed"
                or not isinstance(contains, str)
                or not contains
            ):
                raise ValueError(f"任务 {case_id} 的 contains 配置无效")

        seen_ids.add(case_id)

        cases.append(
            EvaluationCase(
                case_id=case_id,
                category=item["category"],
                kind=kind,
                target=item["target"],
                expected=expected,
                contains=contains,
            )
        )

    return cases


def evaluate(
    cases: Sequence[EvaluationCase],
    executor: Callable[[EvaluationCase], Observation],
    *,
    mode: str = "offline",
) -> EvaluationReport:
    """执行评估并记录每个任务的成功或失败。"""

    results = []

    for case in cases:
        try:
            observation = executor(case)

            if not isinstance(observation, Observation):
                raise TypeError("执行器必须返回 Observation")

        except Exception as exc:
            # 执行异常不应直接导致整批评估中断。
            # 也不能把异常误判为任务成功。
            observation = Observation(
                outcome="error",
                detail=f"{type(exc).__name__}: {exc}",
            )

        passed = observation.outcome == case.expected

        reason = observation.detail

        if not passed:
            reason = reason or (f"预期 {case.expected}，实际 {observation.outcome}")

        # 读取成功还不够，必须匹配规定的关键内容。
        elif case.contains is not None and case.contains not in observation.output:
            passed = False
            reason = f"读取结果缺少预期内容：{case.contains}"

        elif not reason:
            reason = "符合预期"

        results.append(
            CaseResult(
                case_id=case.case_id,
                category=case.category,
                expected=case.expected,
                actual=observation.outcome,
                passed=passed,
                reason=reason,
            )
        )

    # 项目统一采用北京时间、精确到毫秒。
    timestamp = datetime.now(ZoneInfo("Asia/Shanghai")).strftime(
        "%Y-%m-%d %H:%M:%S.%f"
    )[:-3]

    return EvaluationReport(
        timestamp=timestamp,
        timezone="Asia/Shanghai",
        mode=mode,
        results=results,
    )


def save_report(
    report: EvaluationReport,
    path: Path,
) -> None:
    """将评估结果保存为可复查的 JSON 文件。"""

    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(
            report.to_dict(),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
