# Day 18｜项目最终交付与 Dogfooding 实战

**项目：** AI Software Development Agent

**学习计划：** 18 天工程开发计划 · Day 18

**学习主题：** 自身代码修复、HITL、离线端到端验证、项目交付与 GitHub Release

**开发环境：** Python 3.13、LangChain、LangGraph、SQLite、pytest、Ruff、Git

**实际任务：** 修复评估报告分类成功率校验缺失

**开发分支：** `fix/day18-evaluation-category-rate`

---

# 一、学习目标

今天是 AI Software Development Agent 的最后一个计划学习日。

完成整个项目之前，必须让我们开发的工具真正参与维护自己的项目。

这就是 Dogfooding。

本日目标：

1. 找出 Agent 自身代码中的真实问题。
2. 先编写失败测试。
3. 使用 Agent 的真实仓库工具读取自身源码。
4. 通过 HITL 审批修改自身源码。
5. 验证失败测试变成通过。
6. 使用受控检查工具验证自身项目。
7. 保存操作与测试证据。
8. 运行完整回归。
9. 通过 GitHub PR 和 CI 交付修复。
10. 发布首个项目学习里程碑。

真实大模型 API 调用保持为零；工具链验证与模型自主开发验证需要明确区分。

---

# 二、Dogfooding 的含义

Dogfooding 是软件行业中“自己使用自己开发的产品”的实践方法。

例如我们开发一个软件开发 Agent，就应该让这个 Agent 的真实能力参与维护自己的代码，而不是始终只操作专门准备的外部 Demo。

本次使用的真实组件：

- `create_secure_repository_tools()`：读取自身仓库。
- `edit-approval prepare`：生成修改预览。
- `edit-approval review`：人工审批后执行修改。
- `RestrictedCheckRunner`：运行受控质量检查。
- `AuditLogger`：记录实际检查事件。
- pytest、Ruff：验证代码。
- Day 16 评估系统：执行回归验证。

本次没有由真实模型自主生成补丁，因此属于离线开发工具链 Dogfooding。

---

# 三、项目准备

## 3.1 设置项目路径

```bash
AGENT_ROOT="$HOME/Documents/公子路的长期成长计划/02-AI-Agent-Engineering/ai-software-development-agent"

LAB_ROOT="$HOME/Documents/公子路的长期成长计划/02-AI-Agent-Engineering/day14-bugfix-lab"

DAY18_STATE_DIR="${TMPDIR:-/tmp}/ai-dev-agent-day18"

export AGENT_ROOT LAB_ROOT DAY18_STATE_DIR

cd "$AGENT_ROOT"

source .venv/bin/activate

mkdir -p "$DAY18_STATE_DIR"
```

## 3.2 检查环境

```bash
which python
python --version
ai-dev-agent --version
git status --short
```

## 3.3 创建修复分支

本次开始时，从已同步的 `main` 创建：

```bash
git switch main
git pull --ff-only origin main
git switch -c fix/day18-evaluation-category-rate
```

如果分支已经创建，不需要重复执行。

## 3.4 今天修改的文件

主要修改：

```text
src/ai_software_dev_agent/evaluation_report.py
tests/test_evaluation_report.py
```

新增文档：

```text
docs/Day18-Dogfooding-Report.md
docs/Day18-Final-Delivery.md
docs/Project-Showcase.md
```

不需要修改 Day 14/15 独立实验仓库的业务代码。

---

# 四、分析真实 Bug

Day 16 开发了：

```python
def validate_report(
    data: dict[str, Any],
) -> None:
```

该函数检查评估结果是否一致。

原有分类统计部分：

```python
for category, stats in categories.items():
    category_results = [
        result
        for result in results
        if result["category"] == category
    ]

    category_passed = sum(
        1
        for result in category_results
        if result["passed"]
    )

    if (
        stats["total"] != len(category_results)
        or stats["passed"] != category_passed
    ):
        raise ValueError(
            f"分类统计不一致：{category}"
        )
```

它检查分类总数和通过数量，但没有检查分类自己的成功率。

例如：

```json
{
  "total": 1,
  "passed": 0,
  "success_rate": 100.0
}
```

实际通过率应为：

\[
0/1\times100\%=0\%
\]

如果继续生成 Markdown，就可能对外展示错误统计。

因此应该在 `validate_report()` 中增加分类成功率校验。

---

# 五、测试先行：Red

## 5.1 编辑测试文件

```bash
vim tests/test_evaluation_report.py
```

先编写失败测试，不要立即修改业务代码。

## 5.2 新增测试

```python
def test_reject_inconsistent_category_success_rate(
    sample_report: dict,
) -> None:
    """分类成功率不一致时拒绝生成报告。"""

    data = deepcopy(sample_report)

    data["categories"]["security"]["success_rate"] = 100.0

    with pytest.raises(
        ValueError,
        match="分类成功率不一致",
    ):
        render_markdown_report(data)
```

### 代码解释

`deepcopy()`：

复制嵌套数据，避免直接修改 Fixture。

`data["categories"]["security"]`：

定位安全评估分类。

修改 `success_rate`：

人为构造与实际通过数量不一致的数据。

`pytest.raises()`：

验证程序在检测到异常报告时主动抛出指定错误。

这是对异常行为的测试。

## 5.3 执行 Red 测试

```bash
python -m pytest \
  tests/test_evaluation_report.py \
  -k "category_success_rate" \
  -v
```

实际结果：新增测试失败。

失败意味着原有代码无法满足新的校验要求。

不要将这种预期失败理解为开发失败；它是测试先行过程的重要证据。

---

# 六、完整最终代码：evaluation_report.py

文件：

`src/ai_software_dev_agent/evaluation_report.py`

以下为 Day 16 报告模块结合 Day 18 新增校验后的完整参考实现。实际仓库已经通过 HITL 修改，应以最终经过 Ruff 与测试验证的本地代码为准，不需要重新覆盖文件。

```python
"""Day 16：将离线评估 JSON 转换为 Markdown 报告。"""

import argparse
import json
from pathlib import Path
from typing import Any


def markdown_cell(value: object) -> str:
    """转义 Markdown 表格中的特殊字符。"""

    return (
        str(value)
        .replace("|", r"\|")
        .replace("\r", " ")
        .replace("\n", " ")
    )


def validate_report(data: dict[str, Any]) -> None:
    """检查报告汇总数据是否与逐项结果一致。"""

    results = data["results"]

    total = len(results)
    passed = sum(
        1 for result in results if result["passed"]
    )
    failed = total - passed

    # 检查整体统计。
    if (
        data["total"] != total
        or data["passed"] != passed
        or data["failed"] != failed
    ):
        raise ValueError("评估报告的总数或通过数量不一致")

    expected_rate = (
        round(passed / total * 100, 2)
        if total
        else 0.0
    )

    if abs(data["success_rate"] - expected_rate) > 0.001:
        raise ValueError("评估报告的成功率不一致")

    # 检查失败案例与实际结果是否对应。
    actual_failures = {
        result["case_id"]
        for result in results
        if not result["passed"]
    }

    recorded_failures = {
        result["case_id"]
        for result in data["failures"]
    }

    if actual_failures != recorded_failures:
        raise ValueError("失败案例列表与实际结果不一致")

    # 验证分类列表与实际结果一致。
    categories = data["categories"]

    actual_categories = {
        result["category"]
        for result in results
    }

    if set(categories) != actual_categories:
        raise ValueError("评估分类与实际结果不一致")

    for category, stats in categories.items():
        category_results = [
            result
            for result in results
            if result["category"] == category
        ]

        category_passed = sum(
            1
            for result in category_results
            if result["passed"]
        )

        # 原有逻辑：校验分类任务总数与通过数。
        if (
            stats["total"] != len(category_results)
            or stats["passed"] != category_passed
        ):
            raise ValueError(f"分类统计不一致：{category}")

        # Day 18：新增分类成功率校验。
        expected_category_rate = round(
            category_passed / len(category_results) * 100,
            2,
        )

        if abs(
            stats["success_rate"] - expected_category_rate
        ) > 0.001:
            raise ValueError(f"分类成功率不一致：{category}")


def render_markdown_report(
    data: dict[str, Any],
) -> str:
    """根据真实 JSON 结果生成 Markdown 报告。"""

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

    for category, stats in sorted(
        data["categories"].items()
    ):
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
            "本次使用真实本地仓库工具、权限策略、"
            "固定白名单 pytest 和 Git 状态检查。",
            "",
            "评估结果仅反映当前固定评估集的离线执行表现。",
            "",
            "本次没有验证真实大模型独立理解需求、"
            "自主调用工具、生成补丁及完成开发任务的成功率。",
            "",
            "当前定向 pytest 执行仅适用于可信实验仓库，"
            "不属于操作系统级安全沙箱。",
            "",
        ]
    )

    return "\n".join(lines)


def main() -> int:
    """将 JSON 评估报告导出为 Markdown。"""

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

    data = json.loads(
        args.input.read_text(encoding="utf-8")
    )

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
```

## 6.1 为什么只修改分类成功率？

因为其他统计检查已经正常工作。

本次真实问题明确，改动应集中在：

```python
expected_category_rate = round(
    category_passed / len(category_results) * 100,
    2,
)
```

及其比较逻辑。

不需要为了一个小 Bug 重写报告生成器。

## 6.2 为什么使用 `round(..., 2)`？

评估报告统一保留两位小数。

例如：

```python
round(2 / 3 * 100, 2)
```

结果为：

```text
66.67
```

因此分类成功率应使用同样的精度规则。

## 6.3 为什么使用 `abs()`？

用于计算两个数值的差距：

```python
abs(actual_rate - expected_rate)
```

如果差距超出当前约定容差，就认为统计不一致。

这里的 `0.001` 与 Day 16 对整体成功率的比较方式一致。

## 6.4 为什么不会发生零除错误？

程序在进入分类循环之前，已经验证报告的分类集合与实际任务结果对应。

循环处理的是实际存在的分类，因此对应的 `category_results` 至少包含一条结果。

这个前提依赖现有 `validate_report()` 的校验顺序，不应单独抽取除法逻辑而忽略它。

---

# 七、完整最终测试：test_evaluation_report.py

文件：

`tests/test_evaluation_report.py`

本次在 Day 16 原有四个测试的基础上，新增一个分类成功率测试。

```python
"""Day 16/18：Markdown 评估报告测试。"""

from copy import deepcopy

import pytest

from ai_software_dev_agent.evaluation_report import (
    render_markdown_report,
)


@pytest.fixture
def sample_report() -> dict:
    """创建同时包含成功与失败任务的报告。"""

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
    """验证整体统计。"""

    markdown = render_markdown_report(sample_report)

    assert "评估任务总数 | 2" in markdown
    assert "通过任务数 | 1" in markdown
    assert "失败任务数 | 1" in markdown
    assert "离线成功率 | 50.00%" in markdown
    assert "Asia/Shanghai" in markdown


def test_render_markdown_failure_details(
    sample_report: dict,
) -> None:
    """验证失败案例和特殊字符转义。"""

    markdown = render_markdown_report(sample_report)

    assert "deny_secret_file" in markdown
    assert "实际结果：`error`" in markdown
    assert r"权限工具出错 \| 需要调查" in markdown


def test_render_markdown_without_failures(
    sample_report: dict,
) -> None:
    """全部通过时正确显示无失败案例。"""

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
    """整体成功率不一致时拒绝生成报告。"""

    data = deepcopy(sample_report)
    data["success_rate"] = 100.0

    with pytest.raises(
        ValueError,
        match="成功率不一致",
    ):
        render_markdown_report(data)


def test_reject_inconsistent_category_success_rate(
    sample_report: dict,
) -> None:
    """分类成功率不一致时拒绝生成报告。"""

    data = deepcopy(sample_report)

    # security 分类实际通过 0/1，但故意写成 100%。
    data["categories"]["security"]["success_rate"] = 100.0

    with pytest.raises(
        ValueError,
        match="分类成功率不一致",
    ):
        render_markdown_report(data)
```

## 7.1 主要测试知识

`@pytest.fixture`：

复用测试数据。

`deepcopy()`：

复制嵌套字典，避免测试间共享修改后的对象。

`pytest.raises()`：

验证无效输入会触发正确异常。

`match`：

检查异常信息，避免仅仅抛出某个无关异常也被认定为通过。

## 7.2 为什么要保留旧测试？

本次 Bug 修复不能破坏已有能力。

因此保留：

- 整体统计显示。
- 失败信息显示。
- 全部通过时的报告。
- 整体成功率校验。

新增分类成功率校验后，应当五个测试全部通过。

---

# 八、使用自身仓库工具读取代码

Day 13 开发了受限仓库工具。

今天需要把仓库路径设置为 Agent 自己。

关键操作：

```python
from pathlib import Path

from ai_software_dev_agent.secure_tools import (
    create_secure_repository_tools,
)

project = Path(AGENT_ROOT)

tools = {
    tool.name: tool
    for tool in create_secure_repository_tools(project)
}

source = tools["read_repository_file"].invoke(
    {
        "path": (
            "src/ai_software_dev_agent/"
            "evaluation_report.py"
        )
    }
)
```

注意：`AGENT_ROOT` 是这里用于表示项目路径的变量；实际运行时可以通过已导出的环境变量读取。

调用工具的意义：

- 不绕过工具抽象。
- 复用仓库访问权限检查。
- 验证 Agent 工具能够操作自身项目。

本次实际验证了源码和测试文件读取。

---

# 九、HITL 代码修改过程

## 9.1 准备补丁

先检查目标代码：

```bash
grep -n -A 25 -B 4 \
  'for category, stats in categories.items()' \
  src/ai_software_dev_agent/evaluation_report.py
```

根据实际源码创建唯一匹配的 `old_text`。

Day 18 首次操作中，旧代码匹配次数为零。

原因是代码已经经过 Ruff 格式化，目标 `raise ValueError()` 为单行形式，与最初准备的多行文本不同。

调整为：

```bash
old_text='            raise ValueError(f"分类统计不一致：{category}")'
```

新增代码放在该语句之后。

## 9.2 唯一匹配验证

```python
count = source.count(old_text)

if count != 1:
    raise RuntimeError("原始代码必须唯一匹配")
```

唯一匹配的作用：

避免补丁意外替换多个位置，或者在没有匹配目标时继续执行。

## 9.3 审批准备

使用：

```bash
ai-dev-agent edit-approval prepare \
  --project "$AGENT_ROOT" \
  --file src/ai_software_dev_agent/evaluation_report.py \
  --old "$old_text" \
  --new "$new_text" \
  --thread-id "$DAY18_THREAD_ID" \
  --db "$DAY18_STATE_DIR/approvals.sqlite"
```

`new_text` 应包含完整的替换文本，且已按前述检查确认正确。

这里的 `thread_id` 用于定位 LangGraph 审批状态。

## 9.4 人工审批

```bash
ai-dev-agent edit-approval review \
  --thread-id "$DAY18_THREAD_ID" \
  --db "$DAY18_STATE_DIR/approvals.sqlite"
```

审查 Diff，确认无误后输入：

```text
yes
```

本次实际结果：

```text
applied
```

## 9.5 审批的意义

模型或工具提出修改，不等于已经获得执行授权。

HITL 将“准备修改”和“实际写入”分开。

同时结合文件版本校验，避免对已经改变的源码应用过期补丁。

---

# 十、测试验证：Green

先运行新增测试：

```bash
python -m pytest \
  tests/test_evaluation_report.py \
  -k "category_success_rate" \
  -v
```

实际结果：

```text
1 passed
```

运行整个报告模块：

```bash
python -m pytest \
  tests/test_evaluation_report.py \
  -v
```

实际结果：

```text
5 passed
```

运行 Day 16 相关专项测试：

```bash
python -m pytest \
  tests/test_evaluation.py \
  tests/test_evaluation_report.py \
  -v
```

实际结果：

```text
12 passed
```

证明新增校验有效，旧测试没有发生回归。

---

# 十一、受控检查与审计

使用 Day 13 开发的：

```python
RestrictedCheckRunner
```

运行固定检查：

```python
checks = [
    "ruff_check",
    "ruff_format_check",
    "pytest",
]
```

其中 pytest 会执行真实 Python 代码，因此需要明确人工授权。

本次验证对象是自己维护的可信仓库。

受控执行器不是操作系统级安全沙箱。

## 11.1 检查结果

实际三项检查均通过。

通过执行器生成：

```text
checks-summary.json
audit.jsonl
```

## 11.2 JSONL

JSONL 表示每行一个独立 JSON 对象。

适合追加式审计。

检查：

```bash
tail -n 10 "$DAY18_STATE_DIR/audit.jsonl"
```

对每行执行 `json.loads()`，本次格式验证通过。

## 11.3 注意数据边界

原始审计日志可能包含本机绝对路径或内部输出。

公开报告只保留经过检查的必要证据，不直接上传 SQLite 审批数据库或完整临时目录。

---

# 十二、最终回归验证

## 12.1 全量 pytest

```bash
python -m pytest -v
```

实际全部通过。

完整测试数量以本地日志为准。

## 12.2 Ruff

```bash
python -m ruff check .

python -m ruff format --check .
```

均已通过。

## 12.3 验证历史合法报告

```bash
python -m ai_software_dev_agent.evaluation_report \
  --input evaluations/reports/day16-offline-baseline.json \
  --output "$DAY18_STATE_DIR/day16-baseline-after-fix.md"
```

历史报告仍能正常导出，说明修复没有破坏合法报告处理。

## 12.4 Day 16 离线评估回归

```bash
python examples/day16_offline_evaluation.py \
  --project "$LAB_ROOT" \
  --cases evaluations/day16_cases.json \
  --output "$DAY18_STATE_DIR/day18-regression-report.json"
```

实际结果：

```text
10/10
100%
```

说明 Day 16 固定离线评估集在本次修复后保持通过。

这不是模型自主编程成功率。

---

# 十三、重要 Debug 记录

## 13.1 精确文本匹配失败

**现象：**

```text
旧代码匹配次数：0
```

**原因：**

Ruff 格式化改变了源代码的文本布局。

原先准备的多行 `raise ValueError()` 与实际单行写法不一致。

**解决：**

先使用 `grep` 查看真实源码，再修正 `old_text`。

只有唯一匹配后才执行审批。

**经验：**

文本补丁工具必须具备：

- 实际源码检查。
- 唯一匹配验证。
- Diff 预览。
- 文件版本校验。
- 匹配失败时停止执行。

## 13.2 审批状态不一致

检查：

- `thread_id` 是否一致。
- `prepare` 与 `review` 是否使用同一个 SQLite 数据库。
- 原文件是否在准备审批后发生变化。
- 修改范围是否在允许的工作区中。

出现文件版本冲突时，应重新准备审批，而不是绕过校验。

## 13.3 pytest 失败

先运行最小失败用例，再运行完整测试：

```bash
python -m pytest \
  tests/test_evaluation_report.py \
  -k "category_success_rate" \
  -v

python -m pytest -v
```

优先定位第一条明确的失败原因。

## 13.4 Ruff 检查失败

```bash
python -m ruff check .
python -m ruff format --check .
```

确需修复时：

```bash
python -m ruff check . --fix
python -m ruff format .
```

修复后重新运行全量 pytest 和 Ruff。

---

# 十四、GitHub 交付流程

本次使用修复分支：

```text
fix/day18-evaluation-category-rate
```

先整理以下文件：

```text
src/ai_software_dev_agent/evaluation_report.py
tests/test_evaluation_report.py
docs/Day18-Dogfooding-Report.md
docs/Day18-Final-Delivery.md
docs/Project-Showcase.md
```

全部检查通过后提交：

```bash
git add \
  src/ai_software_dev_agent/evaluation_report.py \
  tests/test_evaluation_report.py \
  docs/Day18-Dogfooding-Report.md \
  docs/Day18-Final-Delivery.md \
  docs/Project-Showcase.md

git diff --cached --stat
git diff --cached --check

git commit -m "fix: validate category evaluation success rates"
```

推送：

```bash
git push -u origin fix/day18-evaluation-category-rate
```

然后创建目标为 `main` 的 Pull Request。

通过 GitHub Actions 验证 pytest 和 Ruff。

检查 PR Diff 后再合并。

合并后同步本地 `main`，并检查 CI 结果。

---

# 十五、GitHub Release

首次学习里程碑可采用：

```text
v0.1.0
```

发布前需要确认该 Tag 尚未被使用。

GitHub Release 是基于 Git Tag 的项目发布记录，不等于自动发布 PyPI 包，也不代表项目已经达到生产环境要求。

建议在 PR 合并、`main` CI 通过之后创建 Release。

Release 内容应包括：

- 已实现的主要能力。
- Dogfooding 实战。
- pytest 和 CI 验证。
- 安装说明。
- 当前限制。
- 不属于生产级自主开发系统的说明。

---

# 十六、面向求职的项目展示

本项目可以展示以下真实工程能力：

1. Python CLI 项目组织。
2. LangChain 工具调用。
3. LangGraph 有状态工作流。
4. SQLite Checkpoint。
5. 人工审批与文件修改。
6. 仓库路径权限控制。
7. pytest、Ruff 与 GitHub Actions。
8. 离线能力评估与回归测试。
9. Dogfooding 实战与 Debug。

需要区分：

**能够真实演示的功能**和**目前尚未完整验证的模型自主开发能力**。

不能把确定性补丁执行写成完全自主代码生成。

---

# 十七、最终总结

Day 18 最重要的工作不是新建一个 Demo，而是让 AI Software Development Agent 的真实工具对自己的项目执行一次修复任务。

本次完成了：

- 找到真实的统计校验缺陷。
- 编写失败测试。
- 通过自身仓库工具读取代码。
- 使用 HITL 审批工作流修改源码。
- 从 Red 转为 Green。
- 全量测试与 Ruff 检查。
- 受控检查与审计。
- Day 16 离线回归验证。

同时记录了文本补丁在代码格式化后匹配失败的实际 Debug 经验。

**本次最重要的工程认识：一个 Agent 不仅需要能够调用工具，更需要在真实项目中表现出可控、可审查、可验证和可追踪的执行过程。**

本项目已完成原定的 18 天学习开发阶段。

未来的真实模型自主开发验证、执行隔离强化和更多真实项目实践，可以作为后续迭代方向，而不是将尚未验证的能力写成已经完成。