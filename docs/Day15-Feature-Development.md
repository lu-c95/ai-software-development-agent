# Day 15｜功能开发实战：新增 FREESHIP 优惠码

**所属项目：** AI Software Development Agent

**学习主题：** Feature Development（功能开发）

**实验仓库：** `day14-bugfix-lab`

**开发方式：** 手动编码、测试先行、人工审批、离线集成验证

**真实模型 API 请求：** 0 次

---

## 一、今日目标

Day 15 是原定 18 天计划中的功能开发实战。

Day 14 的任务是修复已经存在的 Bug，而 Day 15 的任务是在现有项目上根据新需求开发功能。

本日通过电商订单结算示例，学习完整的软件功能开发流程：

1. 理解新需求。
2. 明确验收标准。
3. 创建 Git 功能分支。
4. 编写新功能测试。
5. 观察失败测试（Red）。
6. 制定最小实现方案。
7. 使用 HITL 人工审批修改。
8. 运行自动化测试（Green）。
9. 执行离线集成验证。
10. 整理文档并通过 GitHub Pull Request 合并。

本次不使用真实大模型 API。模型产生修改建议的环节由确定性方案替代，但仓库工具、审批、文件编辑、pytest 和 Ruff 均使用真实实现。

---

## 二、项目与需求

继续使用 Day 14 已经建立的独立实验仓库：

```text
day14-bugfix-lab/
├── .gitignore
├── README.md
├── pyproject.toml
├── src/
│   └── order_pricing/
│       ├── __init__.py
│       └── pricing.py
└── tests/
    └── test_pricing.py
```

### 2.1 已有功能

订单结算原本支持：

- 多个商品累计金额。
- 商品小计达到 100 元免运费。
- 不足 100 元收取 10 元运费。
- `SAVE10` 优惠码给商品金额打九折。
- 运费不参与商品折扣。
- 使用 `Decimal` 计算并保留两位小数。

### 2.2 新功能

增加 `FREESHIP` 优惠码。

业务规则：

1. 使用 `FREESHIP` 时，订单免运费。
2. 该优惠码不改变商品金额。
3. 满 100 元免运费的原有规则不变。
4. 原有 `SAVE10` 功能不变。
5. 未知优惠码不产生优惠。
6. 一次结算只接受一个优惠码。

### 2.3 验收案例

| 商品小计 | 优惠码 | 应付金额 |
|---|---|---|
| 50.00 | 无 | 60.00 |
| 50.00 | SAVE10 | 55.00 |
| 50.00 | FREESHIP | 50.00 |
| 100.00 | FREESHIP | 100.00 |
| 50.00 | UNKNOWN | 60.00 |

---

## 三、第一阶段：创建功能分支

在实验仓库中执行：

```bash
git switch main
git switch -c feat/day15-freeship-coupon
```

检查：

```bash
git branch --show-current
```

预期：

```text
feat/day15-freeship-coupon
```

### 为什么使用功能分支？

功能开发可能经历多次测试、修改、审查。

如果直接在 `main` 上开发，中途的未完成状态容易混入主分支。

Feature Branch 将功能开发独立出来，便于：

- 组织代码变更。
- 发起 Pull Request。
- 检查 Diff。
- 讨论和审查。
- 在确认通过后合并。

真实企业项目中，功能分支和 Pull Request 是常见的协作方式。

---

## 四、第二阶段：测试先行（Red）

先明确测试要求，然后编写测试，再实现功能。

在原有六个测试的基础上新增三个 `FREESHIP` 测试。

首次运行：

```bash
python -m pytest tests/test_pricing.py -k "freeship" -v
```

实际结果：

```text
1 passed, 2 failed
```

运行完整测试：

```bash
python -m pytest -v
```

实际结果：

```text
7 passed, 2 failed
```

### 为什么会失败？

此前代码只识别：

```python
if coupon == "SAVE10":
    subtotal = subtotal * DISCOUNT_RATE
```

当优惠码为 `FREESHIP` 时，不会改变运费。

例如商品小计为 50 元：

```text
原实现：50 + 10 = 60
新需求：50 + 0  = 50
```

因此失败测试准确暴露了尚未实现的新功能。

### 为什么三个测试中有一个已经通过？

因为商品小计达到 100 元时，原有逻辑本来就免运费。

这说明该测试既验证新功能，也验证与原有规则的兼容性。

测试先行不要求所有新增测试都必须失败；关键是新增功能中尚未满足的行为能够被测试明确识别。

---

## 五、第三阶段：最小功能实现

### 5.1 修改前

```python
if coupon == "SAVE10":
    subtotal = subtotal * DISCOUNT_RATE
```

### 5.2 修改后

```python
if coupon == "SAVE10":
    subtotal = subtotal * DISCOUNT_RATE
elif coupon == "FREESHIP":
    # FREESHIP 只免除运费，不改变商品小计。
    shipping = Decimal("0.00")
```

### 为什么使用 elif？

`coupon` 是一个字符串，一次只表示一个优惠码。

两个分支互斥：

- 当 `coupon == "SAVE10"` 时，仅商品金额打折。
- 当 `coupon == "FREESHIP"` 时，仅运费归零。
- 其他值不执行优惠处理。

`elif` 明确表达“只选择其中一种优惠”。

### 为什么不重写整个函数？

现有的商品小计、运费门槛和 `Decimal` 精度处理已经正确。

本次只增加一个优惠码判断分支即可满足新需求。

这是 Minimal Change（最小必要变更）的原则。

变更越集中，越容易审查和测试，也越不容易造成不相关的回归。

---

## 六、完整最终源码

文件：

`src/order_pricing/pricing.py`

```python
"""订单金额结算模块。"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


FREE_SHIPPING_THRESHOLD = Decimal("100.00")
SHIPPING_FEE = Decimal("10.00")
DISCOUNT_RATE = Decimal("0.90")
MONEY_PRECISION = Decimal("0.01")


@dataclass(frozen=True)
class OrderItem:
    """订单中的单项商品。"""

    name: str
    unit_price: Decimal
    quantity: int


def checkout_total(
    items: list[OrderItem],
    coupon: str | None = None,
) -> Decimal:
    """根据商品和优惠码计算订单最终应付金额。"""

    if not items:
        return Decimal("0.00")

    # 验证商品价格与购买数量是否合法。
    for item in items:
        if item.unit_price < 0:
            raise ValueError("商品单价不能为负数")

        if item.quantity <= 0:
            raise ValueError("商品数量必须大于零")

    # 累计所有商品的金额。
    subtotal = sum(
        (item.unit_price * item.quantity for item in items),
        Decimal("0.00"),
    )

    # 运费根据优惠前商品小计计算。
    if subtotal >= FREE_SHIPPING_THRESHOLD:
        shipping = Decimal("0.00")
    else:
        shipping = SHIPPING_FEE

    # 不同优惠码之间互斥。
    if coupon == "SAVE10":
        # 商品金额九折，运费不参与折扣。
        subtotal = subtotal * DISCOUNT_RATE
    elif coupon == "FREESHIP":
        # 只免除运费，不改变商品小计。
        shipping = Decimal("0.00")

    # 将优惠后的商品金额和运费相加。
    total = subtotal + shipping

    # 最终金额采用四舍五入并保留两位小数。
    return total.quantize(
        MONEY_PRECISION,
        rounding=ROUND_HALF_UP,
    )
```

### 关键说明

**1. `Decimal`**

货币计算使用 `Decimal` 可以避免普通二进制浮点数的部分表示误差。

例如：

```python
Decimal("0.1") + Decimal("0.2")
```

得到精确的十进制结果：

```text
0.3
```

**2. `subtotal` 与 `shipping` 分开处理**

商品金额与运费代表不同的业务概念。

把它们分开，可以明确哪些费用参加折扣，哪些费用不参加。

**3. 免运费门槛先于优惠码判断**

原业务规定：按照优惠前商品小计判断是否免运费。

因此，不能简单地先应用优惠码再决定普通运费，否则可能改变已有业务规则。

**4. `quantize()`**

最终将结果保留为两位小数：

```python
total.quantize(
    Decimal("0.01"),
    rounding=ROUND_HALF_UP,
)
```

本次没有修改已有金额精度逻辑。

---

## 七、完整业务测试

文件：

`tests/test_pricing.py`

以下为 Day 14 的六个测试和 Day 15 的四个测试。

```python
"""订单结算业务测试。"""

from decimal import Decimal

import pytest

from order_pricing.pricing import OrderItem, checkout_total


def test_order_without_coupon_includes_shipping() -> None:
    """未使用优惠码时正常收取运费。"""

    items = [
        OrderItem(
            name="商品A",
            unit_price=Decimal("25.00"),
            quantity=2,
        )
    ]

    assert checkout_total(items) == Decimal("60.00")


def test_free_shipping_at_threshold() -> None:
    """商品小计达到 100 元时免运费。"""

    items = [
        OrderItem(
            name="商品B",
            unit_price=Decimal("50.00"),
            quantity=2,
        )
    ]

    assert checkout_total(items) == Decimal("100.00")


def test_coupon_with_free_shipping() -> None:
    """原有 SAVE10 在免运费订单上仍然有效。"""

    items = [
        OrderItem(
            name="商品C",
            unit_price=Decimal("60.00"),
            quantity=2,
        )
    ]

    assert checkout_total(items, coupon="SAVE10") == Decimal("108.00")


def test_multiple_items_subtotal() -> None:
    """多个商品正确累加金额。"""

    items = [
        OrderItem(
            name="商品D",
            unit_price=Decimal("19.95"),
            quantity=2,
        ),
        OrderItem(
            name="商品E",
            unit_price=Decimal("12.50"),
            quantity=1,
        ),
    ]

    assert checkout_total(items) == Decimal("62.40")


def test_invalid_quantity_is_rejected() -> None:
    """商品数量为零时拒绝结算。"""

    items = [
        OrderItem(
            name="商品F",
            unit_price=Decimal("20.00"),
            quantity=0,
        )
    ]

    with pytest.raises(ValueError, match="商品数量"):
        checkout_total(items)


def test_coupon_does_not_discount_shipping() -> None:
    """SAVE10 优惠码不影响运费。"""

    items = [
        OrderItem(
            name="商品G",
            unit_price=Decimal("25.00"),
            quantity=2,
        )
    ]

    assert checkout_total(items, coupon="SAVE10") == Decimal("55.00")


def test_freeship_coupon_waives_shipping_below_threshold() -> None:
    """FREESHIP 免除不足 100 元订单的运费。"""

    items = [
        OrderItem(
            name="商品A",
            unit_price=Decimal("25.00"),
            quantity=2,
        )
    ]

    assert checkout_total(items, coupon="FREESHIP") == Decimal("50.00")


def test_freeship_coupon_preserves_multiple_items_subtotal() -> None:
    """FREESHIP 不改变多个商品的金额。"""

    items = [
        OrderItem(
            name="商品B",
            unit_price=Decimal("19.95"),
            quantity=2,
        ),
        OrderItem(
            name="商品C",
            unit_price=Decimal("12.50"),
            quantity=1,
        ),
    ]

    assert checkout_total(items, coupon="FREESHIP") == Decimal("52.40")


def test_freeship_coupon_at_existing_shipping_threshold() -> None:
    """已经满足免运费条件时，不产生额外优惠。"""

    items = [
        OrderItem(
            name="商品D",
            unit_price=Decimal("50.00"),
            quantity=2,
        )
    ]

    assert checkout_total(items, coupon="FREESHIP") == Decimal("100.00")


def test_unknown_coupon_keeps_original_price() -> None:
    """未知优惠码不影响原有金额。"""

    items = [
        OrderItem(
            name="商品H",
            unit_price=Decimal("25.00"),
            quantity=2,
        )
    ]

    assert checkout_total(items, coupon="UNKNOWN") == Decimal("60.00")
```

### 测试覆盖总结

| 类型 | 测试数量 |
|---|---:|
| Day 14 原有业务测试 | 6 |
| Day 15 FREESHIP 测试 | 3 |
| Day 15 未知优惠码边界测试 | 1 |
| 合计 | 10 |

### Red → Green 结果

修改前：

```text
7 passed, 2 failed
```

修改后：

```text
10 passed
```

说明两个原本失败的新需求测试已经通过，原有测试也没有出现回归。

---

## 八、使用 Day 12 HITL 完成功能修改

本次继续复用：

```text
ai-dev-agent edit-approval prepare
ai-dev-agent edit-approval review
```

实际流程：

```text
准备 old_text / new_text
        ↓
检查原始代码唯一匹配
        ↓
生成代码 Diff
        ↓
LangGraph interrupt()
        ↓
SQLite 保存待审批状态
        ↓
人工审查并输入 yes
        ↓
Command(resume=True)
        ↓
校验原文件哈希
        ↓
CodeEditor.apply()
        ↓
状态为 applied
```

### 为什么这一步重要？

在真实软件开发中，即使 AI 能够自动生成代码，也不意味着它应该直接修改所有文件。

尤其是：

- 关键业务计算。
- 数据库结构。
- 身份认证。
- 文件删除。
- 生产环境配置。

这些操作都需要更明确的权限与审批规则。

本次虽采用离线补丁方案，但审批、Checkpoint、文件校验与修改执行使用的都是 Day 12 的真实代码。

---

## 九、离线 Agent 集成测试

### 9.1 仓库工具

通过：

```python
create_secure_repository_tools(project)
```

创建受限工具，并验证：

```text
inspect_repository
read_repository_file
```

能够读取：

```text
README.md
src/order_pricing/pricing.py
tests/test_pricing.py
```

随后检查读取结果中是否包含：

```text
SAVE10
FREESHIP
test_freeship_coupon
test_unknown_coupon
```

这能验证真实工具与实验仓库之间的集成。

### 9.2 受控检查与审计

通过 Day 13 的：

```python
RestrictedCheckRunner
```

依次执行：

```text
ruff_check
ruff_format_check
pytest
```

其中，执行 pytest 必须由人类明确设置审批参数。

受控执行器使用临时工作副本和受限操作列表。

它能降低误操作风险，但并非操作系统级安全沙箱，不应因此执行来源不可信的代码。

### 9.3 审计日志

检查 JSONL 日志是否记录操作、结果和退出码。

面向用户的时间记录遵守项目统一规范：

```text
YYYY-MM-DD HH:mm:ss.SSS
```

时区：

```text
Asia/Shanghai
```

如果需要展示带时区的机器格式，可以单独保留完整的带时区字段，但用户可读时间不应只精确到秒。

**离线工具与审计的实际最终结果以本地执行输出为准。**

### 9.4 离线验证的能力边界

本次真实执行的包括：

- 仓库工具调用。
- 代码修改预览。
- 人工审批。
- 文件写入。
- 自动化测试。
- 受控检查。
- 审计记录。

本次未完整验证：

- 模型独立理解需求。
- 模型自主选择工具。
- 模型自主生成新增功能补丁。

不能把确定性 Demo 的结论当作真实模型自主开发成功。

---

## 十、Debug 与排查方法

### 10.1 新功能测试仍然失败

检查：

```bash
grep -n -A 8 -B 5 \
  'coupon == "SAVE10"' \
  src/order_pricing/pricing.py
```

确认是否存在：

```python
elif coupon == "FREESHIP":
    shipping = Decimal("0.00")
```

同时确认该分支位于计算最终 `total` 之前。

### 10.2 人工审批失败

可能原因：

- `old_text` 与文件当前内容不一致。
- 修改前原文件已经变化。
- 审批数据库路径不一致。
- `thread-id` 不一致。
- 文件不在允许修改的工作区范围内。

建议检查具体错误，并对当前文件重新生成审批任务，而不是跳过版本校验。

### 10.3 pytest 模块导入错误

确认在实验仓库根目录执行：

```bash
python -m pytest -v
```

并检查 `pyproject.toml` 中的 pytest 配置：

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

### 10.4 Ruff 格式检查失败

先查看：

```bash
python -m ruff format --check .
```

确实需要格式化时：

```bash
python -m ruff format .
```

然后重新运行 pytest 和 Ruff。

### 10.5 OpenRouter 额度不足

本次所有必要的功能和集成验收都使用本地工具，不需要反复请求真实模型。

正式模型集成测试应与常规离线测试区分，避免把有限 API 额度用于反复验证确定性行为。

---

## 十一、Git 功能分支与 Pull Request

本次使用：

```text
main
  └── feat/day15-freeship-coupon
```

推荐流程：

```text
创建功能分支
     ↓
开发功能、编写测试
     ↓
本地 pytest + Ruff 通过
     ↓
检查 Git Diff
     ↓
提交 feat Commit
     ↓
Push 功能分支
     ↓
GitHub Pull Request
     ↓
审查变更并合并到 main
     ↓
本地同步 main
```

推荐 Commit：

```text
feat: support FREESHIP coupon
```

Pull Request 标题：

```text
feat: add FREESHIP coupon support
```

Pull Request 应描述：

- 为什么需要增加免运费优惠码。
- 修改了什么文件。
- 是否影响原有 SAVE10 逻辑。
- 新增了哪些测试。
- pytest 和 Ruff 是否通过。

### 为什么不直接 push main？

功能分支加 Pull Request 能让每个功能成为独立、可审查的变更单元。

这也更接近团队中的日常开发过程。

---

## 十二、Day 15 总结

### 今天掌握了什么？

**1. 功能开发与 Bug 修复的区别**

Bug 修复是让现有行为重新符合原要求。

功能开发是根据新的业务需求扩展系统能力。

**2. 测试先行**

先将新需求写成测试，观察现有实现无法满足要求，再进行最小修改。

**3. 兼容性与回归**

新增优惠码不能破坏原来的 `SAVE10`、免运费门槛、商品累计与输入校验。

**4. 人工审批**

代码补丁要经过 Diff 审查和明确授权，才能真正写入文件。

**5. 离线集成测试**

不需要为了每次功能变更都消耗大模型 API。能够由本地确定性工具验证的部分应优先离线验证。

**6. Git 团队工作流**

通过功能分支、Pull Request 和主分支合并，使每次功能开发都有清晰的记录和审查边界。

### 今日成果

| 项目 | 结果 |
|---|---|
| 新功能 | FREESHIP 免运费优惠码 |
| 原有测试 | 6 个保留 |
| 新增测试 | 4 个 |
| 最终 pytest | 10 passed |
| Ruff | check 与 format --check 通过 |
| HITL | 人工审批后成功应用 |
| 模型 API | 0 次 |
| 离线仓库工具与受控执行 | 以本次最终验收输出为准 |
| GitHub PR | 以实际合并结果为准 |

### 今日最重要的认识

**真正的软件开发能力不只是写出新功能，而是能够把需求转化成测试，在不破坏现有功能的前提下安全地修改代码，并通过审查、验证和版本管理交付成果。**

Day 15 完成后，继续原定 18 天学习计划的下一项内容，不提前改变顺序。

---

## 十三、最终验收命令

实验仓库：

```bash
python -m pytest -v
python -m ruff check .
python -m ruff format --check .
git diff --check
git status
```

Agent 主项目：

```bash
python -m pytest -v
python -m ruff check .
python -m ruff format --check .
git status
```

完成全部检查并确认修改内容后，再执行 Git 提交与推送。