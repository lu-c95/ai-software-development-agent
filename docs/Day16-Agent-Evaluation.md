# Day 16｜Agent 能力评估（Agent Evaluation）

**项目：** AI Software Development Agent

**学习计划：** 18 天工程开发计划 · Day 16

**学习主题：** 评估集、真实离线执行、成功率、失败案例、评估报告与回归基线

**开发语言：** Python 3.13

**学习方式：** 亲手编码 → 单元测试 → 离线集成评估 → 分析结果 → 总结

**真实大模型 API 请求：** 0 次

**本日实际离线评估结果：** 10/10，通过率 100%

---

# 一、今天要解决什么问题？

经过 Day 01～Day 15，我们已经逐步开发了一个 AI Software Development Agent。

它已经具备以下能力：

- 读取和分析代码仓库。
- 使用 LangChain 注册工具。
- 使用 LangGraph 编排工作流。
- 保存和恢复持久化会话。
- 预览代码修改。
- 通过 HITL（Human-in-the-Loop）执行人工审批。
- 使用权限策略限制文件访问。
- 运行受限的代码检查。
- 记录操作审计日志。

Day 14，我们使用它的真实工具完成了 Bug 修复的离线实战。

Day 15，我们又增加了 `FREESHIP` 免运费优惠码，并通过人工审批和自动化测试。

但还有一个重要问题：

**我们怎么知道这些能力在后续修改后仍然可靠？**

以前我们的验证方式主要是：

```text
开发一个功能
    ↓
运行对应的 pytest
    ↓
检查是否通过
    ↓
继续开发
```

这种方式可以验证具体功能，但不方便对整个 Agent 的多个能力进行统一统计。

例如：

- 仓库读取是否正常？
- 路径越界是否仍然被拒绝？
- Day 14 修复过的 Bug 是否重新出现？
- Day 15 的新功能是否保持正常？
- 执行评估之后，实验仓库是否仍然干净？
- 如果某项评估失败，能否准确记录失败原因？

因此，Day 16 的任务是建立一套**可重复执行、能够统计结果、能够保留失败案例的小型评估系统**。

## 1.1 今天的最终目标

实现下面的评估流程：

```text
固定评估数据集
      ↓
加载并校验数据
      ↓
运行真实离线工具
      ↓
取得实际观察结果
      ↓
比较预期与实际
      ↓
统计通过率和失败案例
      ↓
生成 JSON 报告
      ↓
生成 Markdown 报告
      ↓
保存评估基线
```

这次以本地工具为主，不调用真实模型 API。

**重要说明：离线评估通过率，不等于大模型自主完成软件开发任务的成功率。**

本次 100% 的结果只表示预定义的十条离线评估任务全部通过。

---

# 二、今天要掌握的核心知识

## 2.1 Evaluation Dataset：评估数据集

评估集是一组提前定义好的测试任务。

每个任务都要描述：

- 任务是什么。
- 属于哪个类别。
- 应该执行什么操作。
- 预期结果是什么。
- 必要时，成功结果必须包含什么内容。

例如：

```json
{
  "id": "read_pricing",
  "category": "repository",
  "kind": "read",
  "target": "src/order_pricing/pricing.py",
  "expected": "allowed",
  "contains": "FREESHIP"
}
```

含义：

```text
任务 ID：read_pricing

任务类别：仓库读取

执行操作：读取文件

目标文件：pricing.py

预期状态：允许读取

内容要求：必须包含 FREESHIP
```

为什么需要 `contains`？

因为“工具没有报错”和“工具读取到了正确内容”是两回事。

例如工具返回一个空字符串：

```python
""
```

如果仅检查有没有异常，就可能错误地认为读取成功。

增加内容检查后，可以进一步验证结果是否符合业务预期。

## 2.2 Observation：实际观察结果

评估任务只描述预期。

真正的执行结果必须由实际工具提供。

例如：

```python
Observation(
    outcome="allowed",
    output="文件的真实内容",
    detail="仓库读取成功",
)
```

或者：

```python
Observation(
    outcome="denied",
    detail="权限策略拒绝访问",
)
```

也可能是：

```python
Observation(
    outcome="error",
    detail="工具执行异常",
)
```

必须注意：

**`denied` 和 `error` 不一样。**

`denied` 表示权限策略明确拒绝操作。

`error` 表示执行过程中发生错误，例如文件不存在、工具异常等。

假设安全测试预期是：

```text
denied
```

但实际结果为：

```text
error
```

不能把它算作成功。

否则评估系统就可能把程序 Bug 误认为安全机制生效。

## 2.3 Success Rate：成功率

计算公式：

\[
成功率=\frac{通过任务数量}{总任务数量}\times100\%
\]

例如：

```text
总任务：10
通过：9
失败：1

成功率 = 9 / 10 × 100% = 90%
```

需要注意：

成功率只能说明**当前评估集中的表现**。

它不能自动代表：

- 真实模型的推理正确率。
- 任意软件项目的 Bug 修复成功率。
- 所有安全场景的通过率。

## 2.4 Regression Evaluation：回归评估

回归评估的核心思想是：

**系统修改之后，重新运行以前的评估任务，确认旧能力没有被破坏。**

例如：

```text
Day 16：
10/10，通过率 100%

以后修改安全策略：
9/10，通过率 90%
```

这时不能只看总分下降了 10%。

还必须知道：

```text
到底是哪条任务失败了？
实际出现了什么错误？
是产品功能回归，还是评估器出错？
```

这也是为什么我们要记录失败案例。

## 2.5 Evaluation Baseline：评估基线

评估基线是一份保留下来的历史结果。

例如：

```text
evaluations/
└── reports/
    ├── day16-offline-baseline.json
    └── day16-offline-baseline.md
```

以后可以用同一组任务再次评估 Agent，再与 Day 16 的结果进行比较。

---

# 三、项目准备

## 3.1 本地项目路径

Agent 主项目：

```text
~/Documents/公子路的长期成长计划/
└── 02-AI-Agent-Engineering/
    └── ai-software-development-agent/
```

实验仓库：

```text
~/Documents/公子路的长期成长计划/
└── 02-AI-Agent-Engineering/
    └── day14-bugfix-lab/
```

实验仓库是 Day 14 创建、Day 15 增加了 `FREESHIP` 功能的项目。

今天直接复用，不重新创建。

## 3.2 进入项目并激活虚拟环境

终端执行：

```bash
AGENT_ROOT="$HOME/Documents/公子路的长期成长计划/02-AI-Agent-Engineering/ai-software-development-agent"

LAB_ROOT="$HOME/Documents/公子路的长期成长计划/02-AI-Agent-Engineering/day14-bugfix-lab"

DAY16_STATE_DIR="${TMPDIR:-/tmp}/ai-dev-agent-day16"

export AGENT_ROOT LAB_ROOT DAY16_STATE_DIR

cd "$AGENT_ROOT"

source .venv/bin/activate
```

检查虚拟环境：

```bash
which python

python --version

python -m pytest --version

python -m ruff --version
```

确认使用的是 Agent 项目的 `.venv`，而不是系统 Python。

## 3.3 创建今天的目录

执行：

```bash
mkdir -p evaluations/reports

mkdir -p examples

mkdir -p tests

mkdir -p docs

mkdir -p "$DAY16_STATE_DIR"
```

说明：

`mkdir -p` 表示目录不存在时创建，存在时不报错。

我们今天新增的代码仍然放在现有的：

```text
src/ai_software_dev_agent/
```

这样可以保持已有的 `src` 项目布局。

## 3.4 最终目录结构

完成 Day 16 后，主要新增文件如下：

```text
ai-software-development-agent/
├── evaluations/
│   ├── day16_cases.json
│   └── reports/
│       ├── day16-offline-baseline.json
│       └── day16-offline-baseline.md
│
├── examples/
│   └── day16_offline_evaluation.py
│
├── src/
│   └── ai_software_dev_agent/
│       ├── evaluation.py
│       └── evaluation_report.py
│
├── tests/
│   ├── test_evaluation.py
│   └── test_evaluation_report.py
│
└── docs/
    └── Day16-Agent-Evaluation.md
```

其中：

| 文件 | 职责 |
|---|---|
| `day16_cases.json` | 定义固定评估任务 |
| `evaluation.py` | 数据模型、加载、评分、统计 |
| `test_evaluation.py` | 测试评估框架 |
| `day16_offline_evaluation.py` | 运行真实离线评估 |
| `evaluation_report.py` | JSON 转 Markdown |
| `test_evaluation_report.py` | 测试报告生成 |
| `day16-offline-baseline.json` | 保存真实评估结果 |
| `day16-offline-baseline.md` | 保存人类可读评估结果 |
| `Day16-Agent-Evaluation.md` | 本学习文档 |

**注意：两个 baseline 报告是程序运行生成的，不要手动编造统计结果。**

---

# 四、第一阶段：建立评估数据集

## 4.1 创建文件

在 Agent 主项目根目录：

```bash
touch evaluations/day16_cases.json

vim evaluations/day16_cases.json
```

### Vim 基本操作

打开文件后：

1. 按 `i` 进入插入模式。
2. 输入或粘贴代码。
3. 按 `Esc` 退出插入模式。
4. 输入 `:wq` 并回车，保存并退出。

常用命令：

```text
i       进入插入模式
Esc     返回普通模式
:w      保存文件
:q      退出
:wq     保存并退出
:q!     放弃修改退出
```

以后本项目的文件编辑统一采用 `vim`。

## 4.2 完整代码：`day16_cases.json`

```json
[
  {
    "id": "read_readme",
    "category": "repository",
    "kind": "read",
    "target": "README.md",
    "expected": "allowed",
    "contains": "AI"
  },
  {
    "id": "read_pricing",
    "category": "repository",
    "kind": "read",
    "target": "src/order_pricing/pricing.py",
    "expected": "allowed",
    "contains": "FREESHIP"
  },
  {
    "id": "read_tests",
    "category": "repository",
    "kind": "read",
    "target": "tests/test_pricing.py",
    "expected": "allowed",
    "contains": "test_unknown_coupon"
  },
  {
    "id": "deny_parent_path",
    "category": "security",
    "kind": "read",
    "target": "../README.md",
    "expected": "denied"
  },
  {
    "id": "deny_absolute_path",
    "category": "security",
    "kind": "read",
    "target": "/etc/passwd",
    "expected": "denied"
  },
  {
    "id": "deny_secret_file",
    "category": "security",
    "kind": "read",
    "target": ".env",
    "expected": "denied"
  },
  {
    "id": "regression_bugfix",
    "category": "regression",
    "kind": "pytest",
    "target": "tests/test_pricing.py::test_coupon_does_not_discount_shipping",
    "expected": "passed"
  },
  {
    "id": "feature_freeship",
    "category": "feature",
    "kind": "pytest",
    "target": "tests/test_pricing.py::test_freeship_coupon_waives_shipping_below_threshold",
    "expected": "passed"
  },
  {
    "id": "full_regression",
    "category": "regression",
    "kind": "pytest",
    "target": "tests/test_pricing.py",
    "expected": "passed"
  },
  {
    "id": "workspace_integrity",
    "category": "safety",
    "kind": "git_clean",
    "target": ".",
    "expected": "clean"
  }
]
```

## 4.3 十个评估任务的意义

| 任务 | 作用 |
|---|---|
| `read_readme` | 验证 README 能正常读取 |
| `read_pricing` | 验证 Day 15 代码能够读取 |
| `read_tests` | 验证业务测试文件能够读取 |
| `deny_parent_path` | 拒绝 `..` 路径越界 |
| `deny_absolute_path` | 拒绝绝对路径访问 |
| `deny_secret_file` | 拒绝读取敏感配置文件 |
| `regression_bugfix` | 验证 Day 14 的 Bug 没有复发 |
| `feature_freeship` | 验证 Day 15 新功能 |
| `full_regression` | 验证完整业务测试 |
| `workspace_integrity` | 检查 Git 工作区是否干净 |

注意：

`read_readme` 的 `"contains": "AI"` 要求实验仓库 README 中确实存在这段文本。

我们使用的 Day 14 实验 README 已包含 AI Software Development Agent 的说明。

如果后续修改 README 内容，需要判断评估集是否仍然反映合理要求，而不是为了通过测试随意删除检查条件。

## 4.4 验证 JSON

执行：

```bash
python -m json.tool evaluations/day16_cases.json > /dev/null
```

没有错误输出即可。

也可以查看格式化结果：

```bash
python -m json.tool evaluations/day16_cases.json
```

### 注意事项

JSON 与 Python 字典不同：

- JSON 字符串必须使用双引号。
- 最后一项后面不能有多余逗号。
- 不能直接写 Python 注释。
- `id` 必须唯一。

我们会在下一阶段使用 Python 对任务内容继续校验。

---

# 五、第二阶段：开发评估框架

这一阶段实现：

```text
JSON 数据
   ↓
EvaluationCase
   ↓
执行器
   ↓
Observation
   ↓
CaseResult
   ↓
EvaluationReport
```

## 5.1 创建文件

```bash
touch src/ai_software_dev_agent/evaluation.py

vim src/ai_software_dev_agent/evaluation.py
```

## 5.2 完整代码：`evaluation.py`

```python
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

        return round(
            self.passed / self.total * 100,
            2,
        )

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
                asdict(result)
                for result in self.results
                if not result.passed
            ],
            "results": [
                asdict(result)
                for result in self.results
            ],
        }


def load_cases(path: Path) -> list[EvaluationCase]:
    """读取并验证 JSON 评估集。"""

    raw = json.loads(
        path.read_text(encoding="utf-8")
    )

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
            raise ValueError(
                f"第 {index + 1} 条任务不是对象"
            )

        # 缺失字段、空字符串都视为无效任务。
        if any(
            not isinstance(item.get(key), str)
            or not item[key].strip()
            for key in required
        ):
            raise ValueError(
                f"第 {index + 1} 条任务字段不完整"
            )

        case_id = item["id"]
        kind = item["kind"]
        expected = item["expected"]
        contains = item.get("contains")

        if case_id in seen_ids:
            raise ValueError(
                f"重复的任务 ID：{case_id}"
            )

        if (
            kind not in VALID_EXPECTATIONS
            or expected not in VALID_EXPECTATIONS[kind]
        ):
            raise ValueError(
                f"任务 {case_id} 的类型或预期结果无效"
            )

        if contains is not None:
            if (
                kind != "read"
                or expected != "allowed"
                or not isinstance(contains, str)
                or not contains
            ):
                raise ValueError(
                    f"任务 {case_id} 的 contains 配置无效"
                )

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
    executor: Callable[
        [EvaluationCase],
        Observation,
    ],
    *,
    mode: str = "offline",
) -> EvaluationReport:
    """执行评估并记录每个任务的成功或失败。"""

    results = []

    for case in cases:
        try:
            observation = executor(case)

            if not isinstance(
                observation,
                Observation,
            ):
                raise TypeError(
                    "执行器必须返回 Observation"
                )

        except Exception as exc:
            # 单条任务异常不能中断整批评估。
            # 但异常也不能被误判为任务成功。
            observation = Observation(
                outcome="error",
                detail=(
                    f"{type(exc).__name__}: {exc}"
                ),
            )

        passed = (
            observation.outcome == case.expected
        )

        reason = observation.detail

        if not passed:
            reason = (
                reason
                or (
                    f"预期 {case.expected}，"
                    f"实际 {observation.outcome}"
                )
            )

        # 合法读取还要检查实际文件内容。
        elif (
            case.contains is not None
            and case.contains not in observation.output
        ):
            passed = False
            reason = (
                "读取结果缺少预期内容："
                f"{case.contains}"
            )

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

    # 使用北京时间，精确到毫秒。
    timestamp = datetime.now(
        ZoneInfo("Asia/Shanghai")
    ).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

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
    """将评估结果保存为 JSON 文件。"""

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            report.to_dict(),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
```

## 5.3 代码解析：数据模型

### `EvaluationCase`

```python
@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    category: str
    kind: str
    target: str
    expected: str
    contains: str | None = None
```

表示一条评估任务。

例如：

```python
case = EvaluationCase(
    case_id="read_readme",
    category="repository",
    kind="read",
    target="README.md",
    expected="allowed",
    contains="AI",
)
```

为什么使用 `@dataclass`？

因为它可以自动生成初始化方法，并减少重复代码。

`frozen=True` 表示对象创建后不能直接修改字段。

对于评估任务来说，这是合理的：**任务预期不应该在执行过程中被随意改动。**

### `Observation`

```python
@dataclass(frozen=True)
class Observation:
    outcome: str
    output: str = ""
    detail: str = ""
```

它负责存储实际观察结果，而不是预期结果。

例如：

```python
Observation(
    outcome="allowed",
    output="实际读取到的文件内容",
    detail="读取成功",
)
```

其中：

- `outcome`：执行状态。
- `output`：工具输出。
- `detail`：补充说明或错误信息。

### `CaseResult`

用于记录比较后的结果。

```python
CaseResult(
    case_id="read_readme",
    category="repository",
    expected="allowed",
    actual="allowed",
    passed=True,
    reason="符合预期",
)
```

为什么还需要一个 `CaseResult`？

因为 `Observation` 只告诉我们发生了什么。

`CaseResult` 进一步告诉我们：

**这个结果是否符合评估集的要求。**

## 5.4 代码解析：`@property`

例如：

```python
@property
def total(self) -> int:
    return len(self.results)
```

使用：

```python
report.total
```

而不是：

```python
report.total()
```

`@property` 将方法封装成只读属性的访问形式。

适合这种由已有数据计算出来的指标。

`passed`：

```python
sum(result.passed for result in self.results)
```

这里利用了 Python 中：

```python
True == 1
False == 0
```

的计数特性。

因此可以直接统计通过的任务数量。

## 5.5 代码解析：`setdefault()`

代码：

```python
stats = categories.setdefault(
    result.category,
    {"total": 0, "passed": 0},
)
```

作用：

如果 `categories` 中没有当前类别，就创建初始统计数据。

如果已经存在，就取出原有数据。

可以理解为：

```python
if result.category not in categories:
    categories[result.category] = {
        "total": 0,
        "passed": 0,
    }

stats = categories[result.category]
```

`setdefault()` 使分类统计代码更简洁。

## 5.6 代码解析：`load_cases()`

主要流程：

```text
读取 JSON 文件
     ↓
确认是非空数组
     ↓
逐条检查字段
     ↓
检查任务 ID 是否重复
     ↓
检查 kind 和 expected 是否匹配
     ↓
检查 contains 是否合理
     ↓
创建 EvaluationCase
```

特别需要注意：

```python
VALID_EXPECTATIONS = {
    "read": {"allowed", "denied"},
    "pytest": {"passed"},
    "git_clean": {"clean"},
}
```

这可以避免 JSON 中出现无效的组合，例如：

```json
{
  "kind": "pytest",
  "expected": "allowed"
}
```

因为 `pytest` 的成功结果应该是 `passed`，不是 `allowed`。

此外：

```python
seen_ids = set()
```

用于检查重复 ID。

为什么使用 `set`？

因为集合支持高效的成员判断：

```python
if case_id in seen_ids:
```

避免重复任务导致结果统计混乱。

## 5.7 代码解析：依赖注入

核心函数：

```python
def evaluate(
    cases,
    executor,
    *,
    mode="offline",
):
    ...
```

注意：

`evaluate()` 并没有直接导入 LangChain 工具，也没有直接调用 pytest。

它只要求：

```python
observation = executor(case)
```

执行器返回一个 `Observation`。

这就是依赖注入的一种简单形式。

以后可以替换执行器：

```text
Fake Executor
     ↓
evaluate()

Offline Executor
     ↓
evaluate()

未来真实模型 Executor
     ↓
evaluate()
```

但评分逻辑不需要重写。

**这是本日最重要的架构设计。**

## 5.8 代码解析：单条任务异常处理

```python
try:
    observation = executor(case)
except Exception as exc:
    observation = Observation(
        outcome="error",
        detail=f"{type(exc).__name__}: {exc}",
    )
```

为什么不让异常直接结束整个评估？

因为一个评估集可能包含十个甚至更多任务。

如果第三条任务出错就直接退出，后面的任务根本没有机会执行。

我们希望：

```text
任务 1：PASS
任务 2：PASS
任务 3：ERROR
任务 4：PASS
...
```

这样可以得到完整的失败记录。

但注意：

这里捕获异常是为了**记录失败**，不是为了掩盖异常或让测试通过。

## 5.9 代码解析：北京时间到毫秒

```python
timestamp = datetime.now(
    ZoneInfo("Asia/Shanghai")
).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
```

这里分为三步。

第一步：

```python
datetime.now(ZoneInfo("Asia/Shanghai"))
```

获取北京时间。

第二步：

```python
strftime("%Y-%m-%d %H:%M:%S.%f")
```

格式化为带六位微秒的时间。

第三步：

```python
[:-3]
```

去掉最后三位，将微秒显示截取成三位毫秒。

最终格式：

```text
2026-11-24 15:27:30.123
```

注意这是用户可读时间。由于字符串本身不携带时区偏移，我们另外保存：

```json
{
  "timezone": "Asia/Shanghai"
}
```

避免时间含义不明确。

---

# 六、第三阶段：评估框架单元测试

## 6.1 创建文件

```bash
touch tests/test_evaluation.py

vim tests/test_evaluation.py
```

## 6.2 完整代码：`test_evaluation.py`

```python
"""Day 16：评估框架的自动化测试。"""

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
    """正确加载合法 JSON 评估集。"""

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
    """重复任务 ID 必须被拒绝。"""

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

    with pytest.raises(
        ValueError,
        match="重复",
    ):
        load_cases(dataset)


def test_evaluate_calculates_success_rate() -> None:
    """检查成功率和失败案例统计。"""

    cases = [
        make_case("success"),
        make_case(
            "failure",
            expected="denied",
        ),
    ]

    def fake_executor(
        case: EvaluationCase,
    ) -> Observation:
        # 两条任务都返回 allowed。
        # 第一条符合预期，第二条不符合预期。
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
    assert (
        data["failures"][0]["case_id"]
        == "failure"
    )


def test_missing_content_is_failure() -> None:
    """读取成功但缺少规定内容，仍算失败。"""

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
    assert "缺少预期内容" in (
        report.results[0].reason
    )


def test_executor_exception_is_not_denial() -> None:
    """执行异常不能误判为安全拒绝成功。"""

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

    report = evaluate(
        cases,
        broken_executor,
    )

    assert report.failed == 1
    assert report.results[0].actual == "error"


def test_empty_evaluation_does_not_divide_by_zero() -> None:
    """空任务列表不应产生除零错误。"""

    report = evaluate(
        [],
        lambda case: Observation(
            outcome="allowed"
        ),
    )

    assert report.total == 0
    assert report.success_rate == 0.0


def test_save_report_contains_timestamp_and_results(
    tmp_path: Path,
) -> None:
    """验证 JSON 保存及毫秒时间格式。"""

    report = evaluate(
        [make_case("read_01")],
        lambda case: Observation(
            outcome="allowed",
            output="README",
        ),
    )

    destination = (
        tmp_path / "reports" / "result.json"
    )

    save_report(report, destination)

    saved = json.loads(
        destination.read_text(
            encoding="utf-8"
        )
    )

    assert saved["total"] == 1
    assert saved["passed"] == 1
    assert saved["success_rate"] == 100.0
    assert (
        saved["timezone"]
        == "Asia/Shanghai"
    )

    assert re.fullmatch(
        r"\d{4}-\d{2}-\d{2} "
        r"\d{2}:\d{2}:\d{2}\.\d{3}",
        saved["timestamp"],
    )
```

## 6.3 关键知识：Fake Executor

例如：

```python
def fake_executor(case):
    return Observation(
        outcome="allowed",
        output="README",
    )
```

这是测试替身。

它不会调用真实的仓库工具，而是返回预先设定的数据。

为什么要使用 Fake？

因为现在测试的是：

**评分模块能不能正确判断结果。**

我们不需要每次验证成功率公式时都读取真实文件。

例如：

```text
任务 A：预期 allowed，实际 allowed
任务 B：预期 denied，实际 allowed
```

预期：

```text
通过：1
失败：1
成功率：50%
```

这样测试稳定、快速，也不依赖外部环境。

但必须区分：

**Fake Executor 的测试通过，不代表真实仓库工具已经通过。**

真实工具集成将在下一阶段单独执行。

## 6.4 关键知识：`tmp_path`

测试中的：

```python
def test_xxx(tmp_path: Path):
```

这里的 `tmp_path` 是 pytest 提供的 Fixture。

它会为测试提供临时目录。

例如：

```python
dataset = tmp_path / "cases.json"
```

我们可以在这里创建测试文件，而不污染真实项目目录。

这样有几个优点：

- 测试之间不容易互相影响。
- 不会覆盖真实数据。
- 测试结束后由 pytest 管理临时资源。
- 避免依赖固定文件路径。

## 6.5 关键知识：`pytest.raises`

例如：

```python
with pytest.raises(
    ValueError,
    match="重复",
):
    load_cases(dataset)
```

表示：

我们预期这段代码会抛出 `ValueError`，并且错误信息包含“重复”。

这属于异常行为测试。

有时正确行为并不是返回一个值，而是**拒绝不合法输入**。

## 6.6 运行测试

```bash
python -m pytest tests/test_evaluation.py -v
```

预期：

```text
7 passed
```

你在第一阶段已经实际执行，并确认通过。

这一阶段只验证评估框架，不消耗 API。

---

# 七、第四阶段：开发真实离线评估执行器

之前的 Fake Executor 只是模拟结果。

现在我们需要实际调用：

- Day 13 的权限策略。
- Day 13 的仓库读取工具。
- Day 14/15 实验仓库的真实 pytest。
- Git 工作区状态检查。

## 7.1 创建文件

```bash
touch examples/day16_offline_evaluation.py

vim examples/day16_offline_evaluation.py
```

## 7.2 完整代码：`day16_offline_evaluation.py`

```python
"""Day 16：使用真实本地工具运行离线评估集。

本脚本只评估可信的本地实验仓库，不调用大模型 API。
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from ai_software_dev_agent.evaluation import (
    EvaluationCase,
    Observation,
    evaluate,
    load_cases,
    save_report,
)
from ai_software_dev_agent.secure_tools import (
    create_secure_repository_tools,
)
from ai_software_dev_agent.security import (
    PermissionPolicy,
)


# 每个 pytest 任务 ID 只能执行固定的测试目标。
# 不允许 JSON 评估集直接指定任意 pytest 路径。
ALLOWED_PYTEST_TARGETS = {
    "regression_bugfix": (
        "tests/test_pricing.py::"
        "test_coupon_does_not_discount_shipping"
    ),
    "feature_freeship": (
        "tests/test_pricing.py::"
        "test_freeship_coupon_waives_shipping_below_threshold"
    ),
    "full_regression": "tests/test_pricing.py",
}


class OfflineEvaluationExecutor:
    """执行离线任务，不负责给任务评分。"""

    def __init__(
        self,
        project_root: Path,
    ) -> None:
        self.project_root = (
            project_root.resolve()
        )

        # 复用 Day 13 权限策略。
        self.policy = PermissionPolicy(
            self.project_root
        )

        # 复用真实的 LangChain 仓库工具。
        self.tools = {
            tool.name: tool
            for tool in create_secure_repository_tools(
                self.project_root
            )
        }

        if (
            "read_repository_file"
            not in self.tools
        ):
            raise RuntimeError(
                "未找到 read_repository_file 工具"
            )

    def __call__(
        self,
        case: EvaluationCase,
    ) -> Observation:
        """根据任务类型分发执行。"""

        if case.kind == "read":
            return self._execute_read(case)

        if case.kind == "pytest":
            return self._execute_pytest(case)

        if case.kind == "git_clean":
            return self._execute_git_clean(case)

        return Observation(
            outcome="error",
            detail=(
                "不支持的评估类型："
                f"{case.kind}"
            ),
        )

    def _check_read_permission(
        self,
        target: str,
    ) -> Observation:
        """调用真实权限策略。"""

        try:
            decision = self.policy.authorize(
                "read_file",
                target,
            )

        except PermissionError as exc:
            return Observation(
                outcome="denied",
                detail=str(exc),
            )

        except Exception as exc:
            # 对明确的自定义权限异常进行识别。
            # 普通工具异常不能误判为安全拒绝。
            exception_name = (
                type(exc).__name__.lower()
            )

            permission_names = (
                "security",
                "permission",
                "denied",
                "forbidden",
                "policy",
                "accessdenied",
            )

            if any(
                name in exception_name
                for name in permission_names
            ):
                return Observation(
                    outcome="denied",
                    detail=(
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    ),
                )

            return Observation(
                outcome="error",
                detail=(
                    f"{type(exc).__name__}: "
                    f"{exc}"
                ),
            )

        if decision is False:
            return Observation(
                outcome="denied",
                detail=(
                    "PermissionPolicy 返回拒绝"
                ),
            )

        if (
            getattr(
                decision,
                "allowed",
                None,
            )
            is False
        ):
            return Observation(
                outcome="denied",
                detail=(
                    "PermissionPolicy 拒绝本次读取"
                ),
            )

        return Observation(
            outcome="allowed"
        )

    def _execute_read(
        self,
        case: EvaluationCase,
    ) -> Observation:
        """检查权限，再通过真实工具读取。"""

        permission = (
            self._check_read_permission(
                case.target
            )
        )

        if permission.outcome != "allowed":
            return permission

        try:
            result = self.tools[
                "read_repository_file"
            ].invoke(
                {"path": case.target}
            )

        except Exception as exc:
            return Observation(
                outcome="error",
                detail=(
                    f"{type(exc).__name__}: "
                    f"{exc}"
                ),
            )

        if not isinstance(result, str):
            return Observation(
                outcome="error",
                detail=(
                    "仓库读取工具返回类型不符合预期："
                    f"{type(result).__name__}"
                ),
            )

        return Observation(
            outcome="allowed",
            output=result,
            detail=(
                "真实仓库读取工具执行完成"
            ),
        )

    def _execute_pytest(
        self,
        case: EvaluationCase,
    ) -> Observation:
        """仅执行固定白名单中的 pytest 目标。"""

        allowed_target = (
            ALLOWED_PYTEST_TARGETS.get(
                case.case_id
            )
        )

        if allowed_target is None:
            return Observation(
                outcome="error",
                detail=(
                    "测试任务 ID 不在白名单中"
                ),
            )

        if case.target != allowed_target:
            return Observation(
                outcome="error",
                detail=(
                    "测试目标与白名单配置不一致"
                ),
            )

        command = [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            allowed_target,
        ]

        # 仅对可信实验仓库执行。
        # 禁止自动加载第三方 pytest 插件，
        # 避免生成 Python 字节码缓存。
        # 但这不是安全沙箱。
        environment = os.environ.copy()

        environment[
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD"
        ] = "1"

        environment[
            "PYTHONDONTWRITEBYTECODE"
        ] = "1"

        try:
            completed = subprocess.run(
                command,
                cwd=self.project_root,
                env=environment,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )

        except subprocess.TimeoutExpired:
            return Observation(
                outcome="error",
                detail=(
                    "pytest 执行超时（60 秒）"
                ),
            )

        except OSError as exc:
            return Observation(
                outcome="error",
                detail=(
                    f"无法启动 pytest：{exc}"
                ),
            )

        output = (
            completed.stdout
            + "\n"
            + completed.stderr
        ).strip()

        if completed.returncode == 0:
            return Observation(
                outcome="passed",
                output=output,
                detail=(
                    "pytest 执行成功，退出码为 0"
                ),
            )

        return Observation(
            outcome="failed",
            output=output,
            detail=(
                "pytest 退出码为 "
                f"{completed.returncode}；"
                f"输出摘要：{output[-1000:]}"
            ),
        )

    def _execute_git_clean(
        self,
        case: EvaluationCase,
    ) -> Observation:
        """检查实验项目 Git 工作区。"""

        if (
            case.case_id
            != "workspace_integrity"
            or case.target != "."
        ):
            return Observation(
                outcome="error",
                detail=(
                    "Git 检查目标不在白名单中"
                ),
            )

        try:
            completed = subprocess.run(
                [
                    "git",
                    "status",
                    "--porcelain",
                    "--untracked-files=all",
                ],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )

        except (
            OSError,
            subprocess.TimeoutExpired,
        ) as exc:
            return Observation(
                outcome="error",
                detail=(
                    f"Git 检查执行失败：{exc}"
                ),
            )

        if completed.returncode != 0:
            return Observation(
                outcome="error",
                detail=completed.stderr.strip(),
            )

        changes = (
            completed.stdout.strip()
        )

        if changes:
            return Observation(
                outcome="dirty",
                output=changes,
                detail=(
                    "工作区存在未提交的修改："
                    f"{changes[:500]}"
                ),
            )

        return Observation(
            outcome="clean",
            detail="Git 工作区干净",
        )


def main() -> int:
    """加载任务、执行评估并保存报告。"""

    parser = argparse.ArgumentParser(
        description="Day 16 离线能力评估"
    )

    parser.add_argument(
        "--project",
        required=True,
        type=Path,
        help="可信的本地实验项目根目录",
    )

    parser.add_argument(
        "--cases",
        type=Path,
        default=Path(
            "evaluations/day16_cases.json"
        ),
        help="评估数据集 JSON 文件",
    )

    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="评估结果 JSON 文件",
    )

    args = parser.parse_args()

    project = args.project.resolve(
        strict=True
    )

    if not project.is_dir():
        parser.error(
            "项目路径不是目录"
        )

    cases = load_cases(args.cases)

    executor = OfflineEvaluationExecutor(
        project
    )

    print(
        "===== Day 16 离线评估开始 ====="
    )
    print(f"实验项目：{project}")
    print(f"评估任务：{len(cases)}")
    print("执行方式：offline")
    print("真实模型 API 请求：0")
    print()

    report = evaluate(
        cases,
        executor,
        mode="offline_local_tools",
    )

    save_report(
        report,
        args.output,
    )

    data = report.to_dict()

    print(
        "===== 逐项评估结果 ====="
    )

    for result in report.results:
        status = (
            "PASS"
            if result.passed
            else "FAIL"
        )

        print(
            f"[{status}] "
            f"{result.case_id}: "
            f"{result.actual}"
        )

        if not result.passed:
            print(
                f"       原因："
                f"{result.reason}"
            )

    print("\n===== 评估汇总 =====")
    print(
        f"评估时间：{report.timestamp}"
    )
    print(
        f"时区：{report.timezone}"
    )
    print(
        f"任务总数：{report.total}"
    )
    print(
        f"通过数量：{report.passed}"
    )
    print(
        f"失败数量：{report.failed}"
    )
    print(
        "成功率："
        f"{report.success_rate:.2f}%"
    )

    print("\n分类统计：")

    for category, stats in sorted(
        data["categories"].items()
    ):
        print(
            f"  {category}: "
            f"{stats['passed']}/"
            f"{stats['total']} "
            f"({stats['success_rate']:.2f}%)"
        )

    print(
        f"\n报告已保存："
        f"{args.output}"
    )

    # 有失败也先保存报告，再返回非零退出码。
    return (
        0
        if report.failed == 0
        else 1
    )


if __name__ == "__main__":
    sys.exit(main())
```

## 7.3 代码解析：`__call__()`

执行器定义了：

```python
def __call__(
    self,
    case: EvaluationCase,
) -> Observation:
```

Python 对象实现 `__call__()` 后，就可以像函数一样调用。

例如：

```python
executor = OfflineEvaluationExecutor(
    project
)

result = executor(case)
```

这样刚好满足：

```python
evaluate(
    cases,
    executor,
)
```

对执行器的要求。

这就是前面依赖注入设计在真实项目中的应用。

## 7.4 代码解析：真实权限策略

代码：

```python
self.policy = PermissionPolicy(
    self.project_root
)
```

复用了 Day 13 的权限策略。

访问前调用：

```python
decision = self.policy.authorize(
    "read_file",
    target,
)
```

例如：

```text
README.md
```

属于允许访问的目标。

而：

```text
../README.md
```

属于试图访问工作区外路径。

评估时必须依赖权限策略的真实判断。

不能写：

```python
if case.expected == "denied":
    return Observation(outcome="denied")
```

因为这相当于直接把答案写进执行器，根本没有验证安全功能。

### 一个需要特别注意的边界

目前 `_execute_read()` 对拒绝场景主要验证的是：

```python
PermissionPolicy.authorize()
```

对合法读取场景则会继续调用真正的 LangChain 仓库工具。

因此：

**本次三个拒绝场景验证的是实际权限策略，而不是恶意输入直接穿过整条工具链的完整渗透测试。**

不能因此声称已经完成全部安全测试。

另外，权限异常识别采用了异常名称兼容方式。

这种方法适合当前 Demo，但在以后工程完善时，更推荐直接捕获 Day 13 明确定义的权限异常类型，减少误分类风险。

## 7.5 代码解析：真实仓库工具

```python
self.tools = {
    tool.name: tool
    for tool in create_secure_repository_tools(
        self.project_root
    )
}
```

这里将 LangChain 工具列表转换为字典。

原本可能是：

```text
[
  inspect_repository,
  read_repository_file
]
```

转换后：

```python
{
    "inspect_repository": ...,
    "read_repository_file": ...,
}
```

就能根据名称访问：

```python
self.tools[
    "read_repository_file"
].invoke(
    {"path": case.target}
)
```

这里确实调用的是我们开发的真实仓库工具。

不是直接调用：

```python
Path(...).read_text()
```

绕过工具层。

## 7.6 代码解析：pytest 白名单

```python
ALLOWED_PYTEST_TARGETS = {
    "regression_bugfix": "...",
    "feature_freeship": "...",
    "full_regression": "...",
}
```

为什么需要白名单？

因为评估任务来自 JSON 文件。

不能允许 JSON 中随便写一个命令，然后直接执行。

我们要求：

```python
allowed_target = (
    ALLOWED_PYTEST_TARGETS.get(
        case.case_id
    )
)
```

并确认：

```python
case.target == allowed_target
```

只有任务 ID 和测试路径都匹配，才能执行。

这可以防止评估数据随意指定其他 pytest 目标。

不过白名单只限制了测试选择，并不限制被测试代码自身的全部行为。

**pytest 本质上仍然会执行 Python 代码。**

所以本次只用于自己创建的可信实验仓库。

## 7.7 代码解析：`subprocess.run()`

核心代码：

```python
completed = subprocess.run(
    command,
    cwd=self.project_root,
    env=environment,
    capture_output=True,
    text=True,
    timeout=60,
    check=False,
)
```

逐项解释：

`command`：

使用参数列表，而不是拼接 Shell 字符串。

`cwd`：

指定子进程工作目录为实验仓库。

`env`：

指定子进程的环境变量。

`capture_output=True`：

捕获标准输出和标准错误。

`text=True`：

将输出解码成字符串。

`timeout=60`：

最多等待 60 秒，超时抛出异常。

`check=False`：

即使命令退出码非零，也先返回结果，由我们判断成功或失败。

这里没有使用 `shell=True`，可以避免不必要的 Shell 字符串解析。

**但 `shell=False` 不能把不可信 Python 代码变成安全代码。**

## 7.8 代码解析：pytest 退出码

```python
if completed.returncode == 0:
    return Observation(
        outcome="passed",
        ...
    )
```

这里遵循常见命令行程序的约定：

```text
退出码 0：命令成功
非零：命令未成功
```

但是具体失败原因还要查看输出。

例如：

```text
1 failed
```

与：

```text
ModuleNotFoundError
```

都可能产生非零退出码，但原因不同。

所以我们保存：

```python
output[-1000:]
```

帮助后续分析。

## 7.9 代码解析：Git 工作区检查

执行：

```bash
git status --porcelain --untracked-files=all
```

如果没有输出：

```text
工作区干净
```

如果出现：

```text
 M src/order_pricing/pricing.py
?? temp.py
```

说明存在修改或未跟踪文件。

本次用它检查评估结束后实验仓库的状态。

但要注意：

**工作区干净，不等于能够证明执行过程中没有任何文件曾被修改。**

例如某个操作修改了文件，又恢复成原样，`git status` 不一定能提供完整过程证据。

更严格的完整性评估，可以使用执行前后的文件哈希比较。

---

# 八、第五阶段：运行真实离线评估

## 8.1 先检查实验仓库

```bash
cd "$LAB_ROOT"

git status --short

git branch --show-current
```

确认 Day 15 的功能已经合并，并且工作区干净。

再运行：

```bash
python -m pytest -v
```

应该看到 Day 14 和 Day 15 的十个业务测试通过。

## 8.2 返回 Agent 主项目

```bash
cd "$AGENT_ROOT"
```

确认模块可以正常导入：

```bash
python -c "from ai_software_dev_agent.evaluation import evaluate; from ai_software_dev_agent.security import PermissionPolicy; from ai_software_dev_agent.secure_tools import create_secure_repository_tools; print('模块导入成功')"
```

## 8.3 验证评估集加载

```bash
python - <<'PY'
from pathlib import Path

from ai_software_dev_agent.evaluation import (
    load_cases,
)

cases = load_cases(
    Path("evaluations/day16_cases.json")
)

print(f"评估任务总数：{len(cases)}")

for case in cases:
    print(
        f"{case.case_id:<24}"
        f"{case.kind:<12}"
        f"{case.expected}"
    )

assert len(cases) == 10

print("Day 16 评估数据加载成功")
PY
```

预期：

```text
评估任务总数：10
Day 16 评估数据加载成功
```

## 8.4 执行真实评估

```bash
python examples/day16_offline_evaluation.py \
  --project "$LAB_ROOT" \
  --cases evaluations/day16_cases.json \
  --output "$DAY16_STATE_DIR/day16-report.json"
```

### 本次实际结果

你已经运行并验证成功：

```text
[PASS] read_readme: allowed
[PASS] read_pricing: allowed
[PASS] read_tests: allowed
[PASS] deny_parent_path: denied
[PASS] deny_absolute_path: denied
[PASS] deny_secret_file: denied
[PASS] regression_bugfix: passed
[PASS] feature_freeship: passed
[PASS] full_regression: passed
[PASS] workspace_integrity: clean
```

汇总：

```text
任务总数：10
通过数量：10
失败数量：0
成功率：100.00%
```

### 分类结果

| 类别 | 通过 / 总数 |
|---|---:|
| Repository | 3/3 |
| Security | 3/3 |
| Regression | 2/2 |
| Feature | 1/1 |
| Safety | 1/1 |
| **合计** | **10/10** |

注意：

这里的 100% 是固定离线评估集的任务通过率。

不能将它写成：

```text
AI Agent 自主开发成功率 100%
```

因为本次没有运行真实模型的自主分析与自主生成补丁流程。

## 8.5 查看 JSON 结果

```bash
python -m json.tool \
  "$DAY16_STATE_DIR/day16-report.json"
```

报告包括：

```text
timestamp
timezone
mode
total
passed
failed
success_rate
categories
failures
results
```

结果应来自真实执行，不能手动调整通过率。

---

# 九、第六阶段：生成 Markdown 评估报告

JSON 方便机器处理，但不适合直接阅读。

因此增加一个报告导出模块。

## 9.1 创建文件

```bash
touch src/ai_software_dev_agent/evaluation_report.py

vim src/ai_software_dev_agent/evaluation_report.py
```

## 9.2 完整代码：`evaluation_report.py`

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


def validate_report(
    data: dict[str, Any],
) -> None:
    """检查报告汇总数据是否与逐项结果一致。"""

    results = data["results"]

    total = len(results)

    passed = sum(
        1
        for result in results
        if result["passed"]
    )

    failed = total - passed

    if (
        data["total"] != total
        or data["passed"] != passed
        or data["failed"] != failed
    ):
        raise ValueError(
            "评估报告的总数或通过数量不一致"
        )

    expected_rate = (
        round(
            passed / total * 100,
            2,
        )
        if total
        else 0.0
    )

    if abs(
        data["success_rate"]
        - expected_rate
    ) > 0.001:
        raise ValueError(
            "评估报告的成功率不一致"
        )

    # 检查失败案例列表是否完整。
    actual_failures = {
        result["case_id"]
        for result in results
        if not result["passed"]
    }

    recorded_failures = {
        result["case_id"]
        for result in data["failures"]
    }

    if (
        actual_failures
        != recorded_failures
    ):
        raise ValueError(
            "失败案例列表与实际结果不一致"
        )

    # 检查分类是否与实际结果一致。
    categories = data["categories"]

    actual_categories = {
        result["category"]
        for result in results
    }

    if (
        set(categories)
        != actual_categories
    ):
        raise ValueError(
            "评估分类与实际结果不一致"
        )

    for category, stats in categories.items():
        category_results = [
            result
            for result in results
            if (
                result["category"]
                == category
            )
        ]

        category_passed = sum(
            1
            for result in category_results
            if result["passed"]
        )

        if (
            stats["total"]
            != len(category_results)
            or stats["passed"]
            != category_passed
        ):
            raise ValueError(
                f"分类统计不一致：{category}"
            )


def render_markdown_report(
    data: dict[str, Any],
) -> str:
    """根据真实 JSON 结果生成 Markdown。"""

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
        status = (
            "PASS"
            if result["passed"]
            else "FAIL"
        )

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
        lines.append(
            "本次评估没有失败案例。"
        )
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
    """将 JSON 报告转换为 Markdown。"""

    parser = argparse.ArgumentParser(
        description=(
            "将 Day 16 JSON 评估报告导出为 Markdown"
        )
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
        args.input.read_text(
            encoding="utf-8"
        )
    )

    markdown = render_markdown_report(
        data
    )

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    args.output.write_text(
        markdown,
        encoding="utf-8",
    )

    print(
        "Markdown 评估报告已生成："
        f"{args.output}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

## 9.3 代码解析：职责分离

这里主要分为三个函数。

`markdown_cell()`：

负责处理 Markdown 表格中的特殊字符。

`validate_report()`：

负责验证 JSON 统计结果是否一致。

`render_markdown_report()`：

负责将合法的统计数据组织成 Markdown。

此外：

`main()`：

负责命令行参数解析、读取 JSON、写入 Markdown。

为什么这样设计？

因为以后如果报告内容需要调整，只需要修改渲染部分。

如果要增加统计规则，只需要调整验证逻辑。

如果要修改命令行参数，也不需要影响评分系统。

这就是单一职责原则在一个小型模块中的实际体现。

## 9.4 代码解析：转义 Markdown

例如任务失败原因是：

```text
权限工具出错 | 需要调查
```

如果直接写入 Markdown 表格：

```markdown
| 权限工具出错 | 需要调查 |
```

竖线会被当成表格列分隔符。

因此：

```python
.replace("|", r"\|")
```

将竖线转义。

另外：

```python
.replace("\n", " ")
```

防止文本中的换行破坏表格布局。

注意：

本项目采用的是简单 Markdown 转义工具，适合当前受控报告数据，并不是完整的 Markdown 安全处理库。

## 9.5 代码解析：数据一致性

假设真实结果为：

```text
总数：10
通过：9
失败：1
```

但 JSON 写成：

```text
成功率：100%
```

这是错误的。

所以要重新计算：

```python
expected_rate = round(
    passed / total * 100,
    2,
)
```

并与 JSON 中的统计值比较。

这可以避免生成自相矛盾的报告。

### 当前实现的边界

目前代码检查了：

- 总任务数。
- 通过和失败数量。
- 总成功率。
- 失败案例 ID 集合。
- 分类与分类任务数量。

但没有对每个类别的 `success_rate` 单独重新核算，也没有全面验证所有字段类型。

因此当前实现适用于我们自己生成的报告。

后续如果要接收外部 JSON，可进一步增加 Schema 校验和更严格的统计一致性验证。

---

# 十、第七阶段：测试 Markdown 报告生成

## 10.1 创建文件

```bash
touch tests/test_evaluation_report.py

vim tests/test_evaluation_report.py
```

## 10.2 完整代码：`test_evaluation_report.py`

```python
"""Day 16：Markdown 评估报告测试。"""

from copy import deepcopy

import pytest

from ai_software_dev_agent.evaluation_report import (
    render_markdown_report,
)


@pytest.fixture
def sample_report() -> dict:
    """构造含成功和失败案例的报告。"""

    failed_case = {
        "case_id": "deny_secret_file",
        "category": "security",
        "expected": "denied",
        "actual": "error",
        "passed": False,
        "reason": (
            "权限工具出错 | 需要调查"
        ),
    }

    return {
        "timestamp": (
            "2026-11-24 15:27:30.123"
        ),
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
        "failures": [
            failed_case
        ],
    }


def test_render_markdown_summary(
    sample_report: dict,
) -> None:
    """Markdown 正确展示总体统计。"""

    markdown = render_markdown_report(
        sample_report
    )

    assert (
        "评估任务总数 | 2"
        in markdown
    )
    assert (
        "通过任务数 | 1"
        in markdown
    )
    assert (
        "失败任务数 | 1"
        in markdown
    )
    assert (
        "离线成功率 | 50.00%"
        in markdown
    )
    assert (
        "Asia/Shanghai"
        in markdown
    )


def test_render_markdown_failure_details(
    sample_report: dict,
) -> None:
    """保留失败案例及原因。"""

    markdown = render_markdown_report(
        sample_report
    )

    assert (
        "deny_secret_file"
        in markdown
    )
    assert (
        "实际结果：`error`"
        in markdown
    )

    assert (
        r"权限工具出错 \| 需要调查"
        in markdown
    )


def test_render_markdown_without_failures(
    sample_report: dict,
) -> None:
    """全部通过时显示没有失败案例。"""

    data = deepcopy(
        sample_report
    )

    success = data["results"][0]

    data["results"] = [
        success
    ]
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

    markdown = render_markdown_report(
        data
    )

    assert (
        "离线成功率 | 100.00%"
        in markdown
    )

    assert (
        "本次评估没有失败案例"
        in markdown
    )


def test_reject_inconsistent_success_rate(
    sample_report: dict,
) -> None:
    """统计数据错误时拒绝生成报告。"""

    data = deepcopy(
        sample_report
    )

    # 明知通过率应为 50%，故意改为 100%。
    data["success_rate"] = 100.0

    with pytest.raises(
        ValueError,
        match="成功率不一致",
    ):
        render_markdown_report(
            data
        )
```

## 10.3 代码解析：`@pytest.fixture`

```python
@pytest.fixture
def sample_report():
    ...
```

它为多个测试提供一份固定的测试数据。

这样每个测试都不需要重新编写完整的 JSON 报告。

例如：

```python
def test_render_markdown_summary(
    sample_report,
):
    ...
```

pytest 会自动提供 Fixture 的返回值。

## 10.4 代码解析：`deepcopy()`

我们在测试中使用：

```python
data = deepcopy(sample_report)
```

为什么不直接写：

```python
data = sample_report
```

因为 `sample_report` 包含嵌套字典和列表。

直接赋值不会复制数据，而是让两个变量指向同一份对象。

使用：

```python
deepcopy()
```

可以创建独立副本。

这样修改：

```python
data["results"] = [success]
```

不会意外影响原有对象。

## 10.5 为什么要人为构造失败报告？

当前真实离线评估是：

```text
10 passed
0 failed
```

如果只用真实报告测试，就只能验证成功场景。

但评估系统更重要的能力之一是：

**发生失败时，是否仍能正确输出失败原因。**

所以我们构造：

```text
预期：denied
实际：error
```

并检查：

- 成功率是否为 50%。
- 失败任务是否出现。
- 错误原因是否保留。
- Markdown 特殊字符是否正确处理。

这种方法属于使用确定性测试数据验证异常分支。

## 10.6 运行测试

```bash
python -m pytest \
  tests/test_evaluation_report.py \
  -v
```

预期：

```text
4 passed
```

再运行 Day 16 的全部专项测试：

```bash
python -m pytest \
  tests/test_evaluation.py \
  tests/test_evaluation_report.py \
  -v
```

预期：

```text
11 passed
```

注意：

这里的 11 个测试是 Day 16 新增的专项测试，不代表整个 Agent 项目只有 11 个测试。

---

# 十一、第八阶段：生成真实评估报告

## 11.1 生成 Markdown

使用之前真实运行得到的 JSON：

```bash
python -m ai_software_dev_agent.evaluation_report \
  --input "$DAY16_STATE_DIR/day16-report.json" \
  --output "$DAY16_STATE_DIR/day16-report.md"
```

预期：

```text
Markdown 评估报告已生成：...
```

## 11.2 查看结果

```bash
cat "$DAY16_STATE_DIR/day16-report.md"
```

应该能看到：

```text
# Day 16｜AI Software Development Agent 离线评估报告

评估任务总数：10
通过任务数：10
失败任务数：0
离线成功率：100.00%
```

实际文件中这些内容会出现在 Markdown 表格里。

失败案例部分：

```text
本次评估没有失败案例。
```

## 11.3 为什么不直接手写 Markdown？

如果手动分别填写 JSON 和 Markdown，可能出现：

```text
JSON：90%
Markdown：100%
```

而我们的设计是：

```text
真实执行
    ↓
生成唯一 JSON 结果
    ↓
验证 JSON
    ↓
转换 Markdown
```

这样两份报告对应的是同一次评估。

---

# 十二、第九阶段：保存评估基线

## 12.1 复制实际评估结果

在 Agent 项目根目录：

```bash
mkdir -p evaluations/reports
```

复制 JSON：

```bash
cp \
  "$DAY16_STATE_DIR/day16-report.json" \
  evaluations/reports/day16-offline-baseline.json
```

复制 Markdown：

```bash
cp \
  "$DAY16_STATE_DIR/day16-report.md" \
  evaluations/reports/day16-offline-baseline.md
```

注意：

**不要为了让结果好看而手动修改报告中的 `passed`、`failed` 或 `success_rate`。**

评估基线应该忠实记录真实运行结果。

## 12.2 检查文件

```bash
ls -l evaluations/reports/
```

验证 JSON：

```bash
python -m json.tool \
  evaluations/reports/day16-offline-baseline.json \
  > /dev/null
```

查看 Markdown：

```bash
cat evaluations/reports/day16-offline-baseline.md
```

## 12.3 提交前检查敏感信息

```bash
grep -n -E \
  '/Users/|sk-|Bearer |api[_-]?key' \
  evaluations/reports/day16-offline-baseline.json \
  evaluations/reports/day16-offline-baseline.md
```

如果没有匹配结果，`grep` 退出码为 1，属于正常现象。

但这只是辅助检查。

还要人工确认没有：

- API Key。
- 本机隐私路径。
- 账户或 Token 信息。
- 不适合公开的完整错误输出。

---

# 十三、Day 16 的完整验收过程

今天的测试可以分成四个层次。

| 层次 | 验证内容 | 是否调用真实 API |
|---|---|---|
| 第一层 | 评估集 JSON 加载 | 否 |
| 第二层 | 评分和报告单元测试 | 否 |
| 第三层 | 真实本地仓库工具与 pytest | 否 |
| 第四层 | 真实模型自主调用工具 | 本次未执行 |

## 13.1 第一层：JSON 格式

```bash
python -m json.tool \
  evaluations/day16_cases.json \
  > /dev/null
```

## 13.2 第二层：单元测试

```bash
python -m pytest \
  tests/test_evaluation.py \
  tests/test_evaluation_report.py \
  -v
```

预期：

```text
11 passed
```

## 13.3 第三层：真实离线评估

```bash
python examples/day16_offline_evaluation.py \
  --project "$LAB_ROOT" \
  --cases evaluations/day16_cases.json \
  --output "$DAY16_STATE_DIR/day16-report.json"
```

本次已验证：

```text
10/10
100%
```

## 13.4 第四层：真实模型评估

本次不执行。

原因：

此前 OpenRouter 免费请求额度不足，而且多数工程组件可以通过离线方式稳定验证。

但必须明确：

没有调用真实模型，就不能证明模型能够：

- 独立理解任意需求。
- 自主选择正确工具。
- 自主定位未知 Bug。
- 自主生成合理补丁。
- 在不同项目上稳定完成开发任务。

这部分属于本次评估尚未覆盖的能力。

---

# 十四、常见错误与 Debug

## 14.1 JSON 格式错误

表现：

```text
JSONDecodeError
```

检查：

```bash
python -m json.tool \
  evaluations/day16_cases.json
```

常见原因：

- 字符串用了单引号。
- 多写了逗号。
- JSON 中存在注释。
- 括号没有正确闭合。

## 14.2 重复任务 ID

表现：

```text
ValueError: 重复的任务 ID
```

检查：

```bash
grep -n '"id"' \
  evaluations/day16_cases.json
```

确认每一个任务 ID 唯一。

## 14.3 合法读取失败

可能原因：

- 目标文件不存在。
- Day 15 代码还没有合并。
- 路径不符合 Day 13 安全策略。
- `contains` 与真实文件内容不一致。
- 仓库工具返回了错误信息。

可以检查：

```bash
grep -n 'FREESHIP' \
  "$LAB_ROOT/src/order_pricing/pricing.py"
```

以及：

```bash
grep -n 'test_unknown_coupon' \
  "$LAB_ROOT/tests/test_pricing.py"
```

## 14.4 安全评估出现 `error`

例如：

```text
deny_secret_file

expected: denied
actual: error
```

先检查实际权限异常：

```bash
grep -n -E \
  'def authorize|raise |class .*Error' \
  src/ai_software_dev_agent/security.py
```

重点判断：

- 是否确实命中权限策略。
- 是否抛出了明确的权限异常。
- 是否只是文件不存在。
- 是否存在评估器错误。

不能把任意异常都当成成功拒绝。

## 14.5 pytest 评估失败

先在实验仓库独立运行：

```bash
cd "$LAB_ROOT"

python -m pytest -v
```

如果业务测试确实失败，说明可能是业务代码回归。

如果业务测试通过，但离线评估失败，则重点检查：

- `ALLOWED_PYTEST_TARGETS`。
- subprocess 的工作目录。
- 当前 Python 解释器。
- `pyproject.toml`。
- 环境变量。
- 具体退出码。

## 14.6 Python 模块导入失败

例如：

```text
ModuleNotFoundError:
No module named 'ai_software_dev_agent'
```

确认：

```bash
cd "$AGENT_ROOT"

source .venv/bin/activate

which python
```

再确认包是否在当前虚拟环境中正确安装。

如果项目原本采用可编辑安装，可以根据已有项目配置执行：

```bash
python -m pip install -e .
```

不要因为导入失败就随意修改 `sys.path`，应先检查当前环境和项目布局。

## 14.7 Git 工作区不干净

检查：

```bash
cd "$LAB_ROOT"

git status --short
```

如果有输出，要先确认哪些文件发生了修改。

不要为了让评估通过直接删除文件。

应当分析：

- 是否是正常开发产生的修改。
- 是否是测试产生的未忽略文件。
- 是否存在意外写入。
- 是否需要提交或恢复这些文件。

## 14.8 Markdown 生成失败

检查输入 JSON：

```bash
python -m json.tool \
  "$DAY16_STATE_DIR/day16-report.json"
```

如果出现：

```text
ValueError: 评估报告的成功率不一致
```

应检查评分结果和 JSON 内容，而不是直接关闭 `validate_report()`。

## 14.9 评估报告与真实结果不一致

检查：

```text
total
passed
failed
success_rate
categories
results
failures
```

确认：

```text
passed + failed = total
```

以及：

```text
success_rate = passed / total × 100
```

尤其注意：

**评估框架本身也需要测试，不能假设评估系统永远正确。**

---

# 十五、Day 16 的主要架构收获

## 15.1 数据、执行、评分、展示要分开

今天最重要的设计：

```text
Evaluation Dataset
       ↓
Offline Executor
       ↓
Observation
       ↓
Evaluation Logic
       ↓
Evaluation Report
       ↓
JSON / Markdown
```

每一层只负责自己的工作。

这样才能做到：

- 容易测试。
- 容易定位问题。
- 容易替换执行器。
- 容易增加新的评估任务。
- 容易保存历史结果。

## 15.2 测试替身不等于真实集成验证

Fake Executor 适合测试评分逻辑。

真实 Offline Executor 适合测试本地工具和业务流程。

真实模型评估适合验证自主推理与工具选择能力。

三者验证的是不同的问题，不能互相替代。

## 15.3 正确区分预期和观察

错误设计：

```python
if case.expected == "passed":
    return Observation(
        outcome="passed"
    )
```

因为这样永远可以得到 100%，却没有实际验证任何功能。

正确设计：

```text
评估集提供预期
执行器提供观察
评分器负责比较
```

评估结果才有可信度。

## 15.4 失败案例比单纯的分数更有价值

例如：

```text
通过率：90%
```

只能说明有任务失败。

但：

```text
case_id: deny_parent_path
expected: denied
actual: allowed
```

能够直接说明：

工作区路径限制可能存在回归。

因此必须保留逐项结果和失败原因。

## 15.5 评估集越小，结论越需要克制

本次十条任务全部通过。

但这不代表：

```text
Agent 的所有能力都已经验证完成。
```

它只表示：

**当前固定的十个离线场景符合预期。**

如果未来要提高评估覆盖率，可以进一步增加更多真实问题、复杂仓库以及多轮任务。

这不是今天必须完成的内容，避免偏离 Day 16 原计划。

---

# 十六、Day 16 最终成果

## 16.1 本次新增文件

```text
evaluations/day16_cases.json

src/ai_software_dev_agent/evaluation.py

tests/test_evaluation.py

examples/day16_offline_evaluation.py

src/ai_software_dev_agent/evaluation_report.py

tests/test_evaluation_report.py
```

## 16.2 本次生成文件

```text
evaluations/reports/day16-offline-baseline.json

evaluations/reports/day16-offline-baseline.md
```

## 16.3 本次学习文档

```text
docs/Day16-Agent-Evaluation.md
```

## 16.4 测试结果

| 检查项目 | 结果 |
|---|---|
| 评估框架单元测试 | 7 passed |
| Markdown 报告单元测试 | 预期 4 passed，需以最终执行为准 |
| Day 16 专项测试 | 预期 11 passed，需以最终执行为准 |
| 实际离线评估 | 10/10 |
| 离线任务通过率 | 100% |
| 真实模型 API 请求 | 0 |

## 16.5 以后如何复用？

以后修改 Agent 的仓库读取、安全策略或者执行器后，重新运行：

```bash
python examples/day16_offline_evaluation.py \
  --project "$LAB_ROOT" \
  --cases evaluations/day16_cases.json \
  --output "$DAY16_STATE_DIR/day16-report-new.json"
```

再与保存的 Day 16 基线比较。

注意：

这是一套固定评估集。

当实验仓库发生新的功能变更时，也要检查评估集与业务需求是否仍然匹配。

---

# 十七、Day 16 总结

今天我们没有继续增加复杂的 Agent 工具，而是开始思考一个更重要的工程问题：

**如何判断自己的 Agent 是否可靠？**

本日完成了：

1. 创建固定评估数据集。
2. 建立评估任务与观察结果的数据模型。
3. 实现加载、校验、评分和成功率统计。
4. 编写评分模块的单元测试。
5. 开发真实离线评估执行器。
6. 复用 Day 13 的权限策略与仓库工具。
7. 复用 Day 14、Day 15 的真实业务测试。
8. 生成 JSON 评估结果。
9. 实现 Markdown 报告导出。
10. 编写报告模块的自动化测试。
11. 保存可重复使用的评估基线。

### 本日最重要的认识

**一个可靠的 Agent 项目，不仅要具备执行任务的能力，还要具备验证自己、发现失败和解释结果的能力。**

本次十个离线评估任务全部通过。

我们可以据此确认当前这些固定工具与业务场景的表现，但仍需明确真实模型自主开发能力尚未被本次离线评估完整覆盖。

Day 16 的成果会成为 Day 17 工程完善与 CI 的基础。

---

# 十八、最终执行顺序与验收

以下步骤安排在**保存完整学习文档之后、Git 提交之前**。

## 18.1 保存学习文档

先创建文件：

```bash
cd "$AGENT_ROOT"

mkdir -p docs

vim docs/Day16-Agent-Evaluation.md
```

将本文档完整保存到对应文件。

注意：

这里的命令用于保存学习文档。

前面已经创建、运行成功的代码文件不需要重新覆盖一次。

## 18.2 执行 Day 16 专项测试

```bash
python -m pytest \
  tests/test_evaluation.py \
  tests/test_evaluation_report.py \
  -v
```

预期：

```text
11 passed
```

如果失败，先修复问题，不跳过测试。

## 18.3 执行全项目 pytest

```bash
python -m pytest -v
```

要求：

全部现有测试通过。

不允许为了完成 Day 16 而删除 Day 01～Day 15 的旧测试。

## 18.4 Ruff 代码检查

```bash
python -m ruff check .
```

预期：

```text
All checks passed!
```

格式检查：

```bash
python -m ruff format --check .
```

如果需要自动修复：

```bash
python -m ruff check . --fix

python -m ruff format .
```

然后重新执行：

```bash
python -m pytest -v

python -m ruff check .

python -m ruff format --check .
```

不要只执行自动修复命令而不重新验证。

## 18.5 检查评估报告

```bash
test -f evaluations/reports/day16-offline-baseline.json

test -f evaluations/reports/day16-offline-baseline.md

python -m json.tool \
  evaluations/reports/day16-offline-baseline.json \
  > /dev/null
```

查看统计结果：

```bash
python - <<'PY'
import json
from pathlib import Path

path = Path(
    "evaluations/reports/"
    "day16-offline-baseline.json"
)

data = json.loads(
    path.read_text(
        encoding="utf-8"
    )
)

print("总任务数：", data["total"])
print("通过数量：", data["passed"])
print("失败数量：", data["failed"])
print("成功率：", data["success_rate"])
print("时区：", data["timezone"])
print("评估模式：", data["mode"])

assert data["total"] == 10
assert data["passed"] == 10
assert data["failed"] == 0
assert data["success_rate"] == 100.0
assert data["mode"] == "offline_local_tools"

print("Day 16 基线验证通过")
PY
```

## 18.6 Git 状态检查

```bash
git status --short

git diff --check

git branch --show-current
```

确认当前分支符合预期。

## 18.7 暂存 Day 16 文件

```bash
git add \
  evaluations/day16_cases.json \
  evaluations/reports/day16-offline-baseline.json \
  evaluations/reports/day16-offline-baseline.md \
  examples/day16_offline_evaluation.py \
  src/ai_software_dev_agent/evaluation.py \
  src/ai_software_dev_agent/evaluation_report.py \
  tests/test_evaluation.py \
  tests/test_evaluation_report.py \
  docs/Day16-Agent-Evaluation.md
```

检查暂存内容：

```bash
git diff --cached --stat

git diff --cached --check

git status --short
```

检查是否存在无关文件或敏感信息。

## 18.8 Git 提交

确认后执行：

```bash
git commit -m "feat: add offline agent evaluation and reports"
```

如果当前处于 `main`：

```bash
git push origin main
```

如果位于其他功能分支，则按实际分支执行推送，不要强制修改分支历史。

## 18.9 最终检查

```bash
git log -1 --oneline

git status
```

如果工作区干净，且 pytest、Ruff、评估报告均通过，则 Day 16 正式完成。

---

# 十九、最终检查清单

- [ ] `day16_cases.json` 包含 10 条任务。
- [ ] `evaluation.py` 完整实现加载、评分和统计。
- [ ] `test_evaluation.py` 的 7 个测试通过。
- [ ] `day16_offline_evaluation.py` 可实际运行。
- [ ] 真实离线评估结果为 10/10。
- [ ] `evaluation_report.py` 可导出 Markdown。
- [ ] `test_evaluation_report.py` 的 4 个测试通过。
- [ ] JSON 和 Markdown 基线均已保存。
- [ ] `Day16-Agent-Evaluation.md` 文档已保存。
- [ ] 全量 pytest 通过。
- [ ] Ruff check 通过。
- [ ] Ruff format --check 通过。
- [ ] Git 提交及推送完成。

**Day 16 最终结论：建立了一套可重复执行、可以记录失败案例、能够生成报告的离线 Agent 能力评估体系。**

下一学习日继续原定计划：

**Day 17｜工程完善与 CI。**