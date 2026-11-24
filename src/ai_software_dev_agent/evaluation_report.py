"""Day 16：将离线评估 JSON 转换为 Markdown 报告。"""

import argparse
import json
from pathlib import Path
from typing import Any


def markdown_cell(value: object) -> str:
    """转义 Markdown 表格中的特殊字符。"""

    return str(value).replace("|", r"\|").replace("\r", " ").replace("\n", " ")


def validate_report(data: dict[str, Any]) -> None:
    """检查报告汇总数据是否与逐项结果一致。"""

    results = data["results"]

    total = len(results)
    passed = sum(1 for result in results if result["passed"])
    failed = total - passed

    if data["total"] != total or data["passed"] != passed or data["failed"] != failed:
        raise ValueError("评估报告的总数或通过数量不一致")

    expected_rate = round(passed / total * 100, 2) if total else 0.0

    if abs(data["success_rate"] - expected_rate) > 0.001:
        raise ValueError("评估报告的成功率不一致")

    # 不仅检查失败数量，还要检查失败案例 ID。
    actual_failures = {result["case_id"] for result in results if not result["passed"]}

    recorded_failures = {result["case_id"] for result in data["failures"]}

    if actual_failures != recorded_failures:
        raise ValueError("失败案例列表与实际结果不一致")

    # 验证分类统计不是随意填入的数据。
    categories = data["categories"]

    actual_categories = {result["category"] for result in results}

    if set(categories) != actual_categories:
        raise ValueError("评估分类与实际结果不一致")

    for category, stats in categories.items():
        category_results = [
            result for result in results if result["category"] == category
        ]

        category_passed = sum(1 for result in category_results if result["passed"])

        if (
            stats["total"] != len(category_results)
            or stats["passed"] != category_passed
        ):
            raise ValueError(f"分类统计不一致：{category}")

        # 根据分类的真实通过数量重新计算成功率。
        expected_category_rate = round(
            category_passed / len(category_results) * 100,
            2,
        )

        # 分类成功率与实际结果不一致时拒绝生成报告。
        if abs(stats["success_rate"] - expected_category_rate) > 0.001:
            raise ValueError(f"分类成功率不一致：{category}")


def render_markdown_report(
    data: dict[str, Any],
) -> str:
    """根据真实 JSON 评估结果生成 Markdown 报告。"""

    validate_report(data)

    lines = [
        "# Day 16｜AI Software Development Agent 离线评估报告",
        "",
        f"- 评估时间：{data['timestamp']}",
        f"- 时区：{data['timezone']}",
        f"- 评估模式：`{data['mode']}`",
        "- 真实模型 API 请求：0",
        "",
        "## 一、评估结果总览",
        "",
        "| 指标 | 结果 |",
        "|---|---:|",
        f"| 评估任务总数 | {data['total']} |",
        f"| 通过任务数 | {data['passed']} |",
        f"| 失败任务数 | {data['failed']} |",
        f"| 离线成功率 | {data['success_rate']:.2f}% |",
        "",
        "## 二、分类评估结果",
        "",
        "| 类别 | 通过 / 总数 | 成功率 |",
        "|---|---:|---:|",
    ]

    for category, stats in sorted(data["categories"].items()):
        lines.append(
            f"| {markdown_cell(category)} "
            f"| {stats['passed']}/{stats['total']} "
            f"| {stats['success_rate']:.2f}% |"
        )

    lines.extend(
        [
            "",
            "## 三、逐项评估结果",
            "",
            "| 任务 ID | 预期 | 实际 | 结果 |",
            "|---|---|---|---|",
        ]
    )

    for result in data["results"]:
        status = "PASS" if result["passed"] else "FAIL"

        lines.append(
            f"| {markdown_cell(result['case_id'])} "
            f"| {markdown_cell(result['expected'])} "
            f"| {markdown_cell(result['actual'])} "
            f"| {status} |"
        )

    lines.extend(
        [
            "",
            "## 四、失败案例",
            "",
        ]
    )

    if not data["failures"]:
        lines.append("本次评估没有失败案例。")
    else:
        for failure in data["failures"]:
            lines.extend(
                [
                    f"### {markdown_cell(failure['case_id'])}",
                    "",
                    f"- 预期结果：`{failure['expected']}`",
                    f"- 实际结果：`{failure['actual']}`",
                    f"- 失败原因：{markdown_cell(failure['reason'])}",
                    "",
                ]
            )

    lines.extend(
        [
            "",
            "## 五、评估范围与限制",
            "",
            "本次使用真实本地仓库工具、权限策略、固定白名单 pytest 和 Git 状态检查。",
            "",
            "评估结果仅反映当前固定评估集的离线执行表现。",
            "",
            "本次没有验证真实大模型独立理解需求、"
            "自主调用工具、生成补丁及完成开发任务的成功率。",
            "",
            "当前定向 pytest 执行仅适用于可信实验仓库，不属于操作系统级安全沙箱。",
            "",
        ]
    )

    return "\n".join(lines)


def main() -> int:
    """通过命令行将 JSON 报告转换为 Markdown。"""

    parser = argparse.ArgumentParser(
        description="将 Day 16 JSON 评估报告导出为 Markdown"
    )

    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="已有的评估结果 JSON 文件",
    )

    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="输出的 Markdown 报告路径",
    )

    args = parser.parse_args()

    # 读取已经真实运行生成的报告。
    data = json.loads(args.input.read_text(encoding="utf-8"))

    markdown = render_markdown_report(data)

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    args.output.write_text(
        markdown,
        encoding="utf-8",
    )

    print(f"Markdown 评估报告已生成：{args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
