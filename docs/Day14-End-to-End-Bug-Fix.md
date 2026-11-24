# Day 14｜完整 Bug 修复实战

**项目：AI Software Development Agent**

**学习日期：2026-11-24**

**学习主题：端到端 Bug 修复、Agent 工具集成、人工审批、测试与审计**

**执行方式：真实工具 + 离线确定性 Demo，避免消耗大模型 API**

**最终验收状态：通过**

---

## 一、今日学习目标

Day 14 严格按照原定 18 天计划，进行完整 Bug 修复实战。

目标不是继续增加一个孤立的工具，而是组合前面已经开发的能力：

- 仓库读取。
- Bug 分析。
- 最小修改方案。
- 人工审批。
- 文件安全编辑。
- pytest 自动化测试。
- Ruff 代码检查。
- 受控执行与审计。

由于 OpenRouter 的免费模型额度有限，本次实战采用确定性离线 Demo 验证主要工程流程。

**需要区分：本次离线分析是规则模拟，不能替代真实大模型自主推理能力的验证。**

---

## 二、实验项目

使用独立仓库：

```text
02-AI-Agent-Engineering/
├── ai-software-development-agent/
└── day14-bugfix-lab/
    ├── README.md
    ├── pyproject.toml
    ├── src/
    │   └── order_pricing/
    │       ├── __init__.py
    │       └── pricing.py
    └── tests/
        └── test_pricing.py
```

### 业务规则

项目模拟电商订单金额结算。

1. 商品小计等于各商品单价乘数量后求和。
2. 商品小计不足 100 元，运费为 10 元。
3. 商品小计达到 100 元，免运费。
4. `SAVE10` 优惠码将商品金额打九折。
5. 运费不参与折扣。
6. 免运费门槛依据优惠前的商品小计。
7. 使用 `Decimal` 处理金额，最终保留两位小数。

### 报告的 Bug

商品金额：

```text
50.00 元
```

运费：

```text
10.00 元
```

优惠码：

```text
SAVE10
```

实际结算结果：

```text
54.00 元
```

预期：

```text
55.00 元
```

---

## 三、第一阶段：复现 Bug

建立示例仓库，添加结算代码和六个 pytest 用例。

执行：

```bash
python -m pytest -v
```

**真实结果：**

```text
5 passed, 1 failed
```

失败用例：

```text
test_coupon_does_not_discount_shipping
```

实际值：

```python
Decimal("54.00")
```

预期值：

```python
Decimal("55.00")
```

这意味着 Bug 可以通过自动化测试稳定复现。

### 为什么先复现？

不能只根据用户描述就直接改代码。

应先：

1. 明确业务要求。
2. 检查现有实现。
3. 编写或确认失败测试。
4. 运行测试并观察失败。
5. 确定失败可重复。

之后再定位原因。

这体现了 Red → Green → Refactor 的基本工作思想。

---

## 四、第二阶段：分析根因

### 4.1 原始错误代码

```python
# 计算订单总金额。
total = subtotal + shipping

# 用户提供 SAVE10 优惠码时应用九折。
if coupon == "SAVE10":
    total = total * DISCOUNT_RATE
```

### 4.2 问题分析

代码首先计算：

```python
total = subtotal + shipping
```

把商品金额和运费相加。

然后：

```python
total = total * DISCOUNT_RATE
```

给总额打九折。

这样就错误地把运费也纳入折扣范围。

### 4.3 为什么得到 54.00？

商品金额为：

```text
50.00
```

运费为：

```text
10.00
```

错误计算：

```text
(50.00 + 10.00) × 0.90 = 54.00
```

### 4.4 为什么正确结果是 55.00？

根据业务规则，先对商品金额打折，再加上原运费：

```text
50.00 × 0.90 + 10.00 = 55.00
```

所以根本原因不是 `Decimal` 的精度问题，而是：

**优惠折扣应用到了错误的金额范围。**

### 4.5 本次离线分析方式

通过 Day 13 的真实工具：

```python
create_secure_repository_tools(project)
```

调用：

```text
inspect_repository
read_repository_file
```

读取：

```text
README.md
src/order_pricing/pricing.py
tests/test_pricing.py
```

然后使用事先定义的确定性规则检查：

- README 是否声明运费不参与优惠。
- 源码是否先计算商品与运费的合计。
- 优惠是否应用到了合计金额。
- 测试是否要求结果为 55.00。

由于不调用大模型，这一步能够稳定复现，但只能验证已定义的错误模式。

---

## 五、最小修复方案

### 修改原则

只改变优惠计算与运费合计的顺序。

不修改：

- 商品数据结构。
- 商品数量校验。
- 负价格校验。
- 免运费门槛。
- `Decimal` 金额表示。
- 最终金额精度。

### 修复代码

```python
# 优惠码只作用于商品金额，运费不参与折扣。
if coupon == "SAVE10":
    subtotal = subtotal * DISCOUNT_RATE

# 商品优惠计算完成后再计入运费。
total = subtotal + shipping
```

这样先计算商品折扣，再加入运费。

对于没有优惠码的订单，`subtotal` 不变，原有结果也不变。

### 为什么不移动运费判断？

原有代码先根据商品小计计算运费：

```python
if subtotal >= FREE_SHIPPING_THRESHOLD:
    shipping = Decimal("0.00")
else:
    shipping = SHIPPING_FEE
```

这段逻辑正确地使用优惠前金额，因此无需修改。

---

## 六、修复后的完整 `pricing.py`

文件：

```text
day14-bugfix-lab/src/order_pricing/pricing.py
```

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
    """订单中的一项商品。"""

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

    # 拒绝非法商品数据。
    for item in items:
        if item.unit_price < 0:
            raise ValueError("商品单价不能为负数")

        if item.quantity <= 0:
            raise ValueError("商品数量必须大于零")

    # 汇总商品小计。
    subtotal = sum(
        (
            item.unit_price * item.quantity
            for item in items
        ),
        Decimal("0.00"),
    )

    # 按优惠前商品小计判断免运费门槛。
    if subtotal >= FREE_SHIPPING_THRESHOLD:
        shipping = Decimal("0.00")
    else:
        shipping = SHIPPING_FEE

    # 优惠码只作用于商品金额，运费不参与折扣。
    if coupon == "SAVE10":
        subtotal = subtotal * DISCOUNT_RATE

    # 商品优惠计算完成后再计入运费。
    total = subtotal + shipping

    # 最终金额保留两位小数。
    return total.quantize(
        MONEY_PRECISION,
        rounding=ROUND_HALF_UP,
    )
```

### 关键知识点

`subtotal` 是商品小计。

`shipping` 是运费。

`DISCOUNT_RATE` 是折扣比例。

`total` 是用户最终应付金额。

把不同职责的金额区分开，有助于避免将折扣错误应用到运费等其他费用上。

---

## 七、完整业务测试

文件：

```text
day14-bugfix-lab/tests/test_pricing.py
```

```python
"""订单结算的业务规则和 Bug 回归测试。"""

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

    result = checkout_total(items)

    assert result == Decimal("60.00")


def test_free_shipping_at_threshold() -> None:
    """商品小计达到 100 元后免运费。"""

    items = [
        OrderItem(
            name="商品B",
            unit_price=Decimal("50.00"),
            quantity=2,
        )
    ]

    result = checkout_total(items)

    assert result == Decimal("100.00")


def test_coupon_with_free_shipping() -> None:
    """免运费订单使用优惠码后商品金额打九折。"""

    items = [
        OrderItem(
            name="商品C",
            unit_price=Decimal("60.00"),
            quantity=2,
        )
    ]

    result = checkout_total(items, coupon="SAVE10")

    assert result == Decimal("108.00")


def test_multiple_items_subtotal() -> None:
    """验证多商品累计与运费。"""

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

    result = checkout_total(items)

    assert result == Decimal("62.40")


def test_invalid_quantity_is_rejected() -> None:
    """数量为零时必须拒绝。"""

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
    """优惠码只影响商品金额，不影响运费。"""

    items = [
        OrderItem(
            name="商品G",
            unit_price=Decimal("25.00"),
            quantity=2,
        )
    ]

    result = checkout_total(items, coupon="SAVE10")

    # 50 × 0.90 + 10 = 55
    assert result == Decimal("55.00")
```

这六个测试分别检查正常结算、免运费、优惠码、多商品、非法输入和本次回归问题。

原先失败的测试应在修复后变为通过。

---

## 八、Day 12 人工审批的实际应用

本次不是直接覆盖源码。

执行流程：

```text
准备 old_text 和 new_text
           ↓
检查 old_text 唯一匹配
           ↓
edit-approval prepare
           ↓
生成 Diff
           ↓
LangGraph interrupt()
           ↓
SQLite 保存审批状态
           ↓
edit-approval review
           ↓
人工输入 yes
           ↓
恢复 Checkpoint
           ↓
校验原文件 SHA-256
           ↓
CodeEditor.apply()
           ↓
返回 applied
```

这样可以复用 Day 12 已经完成的：

- 人工审批节点。
- SQLite Checkpointer。
- 跨进程恢复。
- Diff 预览。
- 文件版本冲突检查。
- 安全文件替换。

**即使本次没有真实模型参与，也仍然能验证审批和修改模块的实际行为。**

---

## 九、第三阶段：验证修复

### 9.1 原失败用例

```bash
python -m pytest \
  tests/test_pricing.py::test_coupon_does_not_discount_shipping \
  -v
```

预期：

```text
1 passed
```

### 9.2 全部业务测试

```bash
python -m pytest -v
```

预期：

```text
6 passed
```

### 9.3 Ruff

```bash
python -m ruff check .

python -m ruff format --check .
```

预期两个检查均通过。

### 9.4 Day 13 受控执行器

通过：

```python
RestrictedCheckRunner
```

执行：

```text
ruff_check
ruff_format_check
pytest
```

在临时工作副本内进行检查。

同时输出：

```text
day14-audit.jsonl
```

用于记录执行事件。

最终验证结果应以实际运行结果为准，不提前声称通过。

---

## 十、今日实际遇到的 Debug 问题

### 10.1 OpenRouter 模型返回 404

错误：

```text
OpenAIModelNotFoundError: 404
```

原模型：

```text
cohere/north-mini-code:free
```

已经没有可用提供方。

解决方式：

改用当前可用的模型路由配置，并重新启动 Agent。

工程认识：

**模型供应商是外部依赖，模型不可用不代表 Agent 业务代码存在错误。**

### 10.2 多行 Markdown 被 CLI 当成多次提问

现象：

用户只粘贴了一段提示词，但 Agent 不断输出，并反复出现新的输入提示符。

原因：

当前聊天 CLI 使用单行：

```python
input()
```

将多行提示词一次粘贴到终端后，后续每一行可能继续被当成独立的用户消息。

临时解决：

- 终止旧会话。
- 使用新的会话 ID。
- 一次只粘贴一行提示词。
- 等待一次回答完成再输入下一条。

工程认识：

**终端交互能力必须与实际输入方式匹配。Markdown 本身不是问题，单行输入协议才是主要原因。**

### 10.3 OpenRouter 返回 429

错误：

```text
OpenAIRateLimitError: 429
Rate limit exceeded: free-models-per-day
```

原因：

免费模型账户请求额度耗尽。

一次 Agent 提问可能产生多次模型请求。

临时解决：

保留项目与测试结果，不反复重试，改用离线确定性 Demo 验证其他工程环节。

工程认识：

**测试 Agent 不应该全部依赖收费或限额的真实模型请求。**

### 10.4 为什么离线 Demo 有价值？

真实 API 适合验证：

- 模型是否会选择正确工具。
- 模型能否独立推理。
- 实际工具调用格式。
- 模型与 Provider 的兼容性。

离线 Demo 适合验证：

- 仓库工具执行。
- 权限策略。
- 文件修改。
- 人工审批。
- Checkpoint。
- pytest。
- Ruff。
- 审计日志。

两种测试应该互相补充，而不是互相代替。

---

## 十一、今日掌握的工程方法

### 11.1 Root Cause Analysis（根因分析）

不能只根据失败表象直接修改代码。

要分析：

```text
业务需求
   ↓
真实代码
   ↓
输入数据
   ↓
执行过程
   ↓
错误输出
   ↓
根本原因
```

本次根因是折扣应用范围错误。

### 11.2 Minimal Patch（最小补丁）

能通过调整少量必要逻辑修复的问题，不应该直接重写整个模块。

最小补丁更容易：

- 人工审查。
- 验证正确性。
- 降低回归风险。
- 追踪修改来源。
- 必要时回滚。

### 11.3 Regression Testing（回归测试）

不能只运行最初失败的一个用例。

还要确认其他规则没有受到影响。

本次使用六个业务测试完成回归验证。

### 11.4 Human-in-the-Loop

AI 给出的修改建议不能直接视为已授权的操作。

应该：

```text
分析 → 预览 → 审批 → 执行
```

批准时还需要确认文件没有发生变化。

### 11.5 Offline Integration Testing（离线集成测试）

对长期维护的 Agent 项目，应尽量将测试分成：

```text
单元测试
    ↓
离线工具集成测试
    ↓
离线工作流测试
    ↓
少量真实模型集成测试
```

只有确实需要验证模型能力时才使用真实 API。

这样可以降低成本，提高测试稳定性。

---

## 十二、Day 14 总结

本日按照原计划开展完整 Bug 修复实战。

使用订单金额计算示例，首先稳定复现错误，再通过受限仓库工具进行离线分析，使用 Day 12 的人工审批机制实施最小修改，最后用 pytest、Ruff 和 Day 13 的受控执行器验证。

通过这一流程，前面学习的能力开始形成协作关系：

| 已完成能力 | Day 14 实际用途 |
|---|---|
| 仓库读取工具 | 阅读真实项目源码与测试 |
| Agent 工具注册 | 为分析提供受限工具 |
| LangGraph Checkpoint | 保存待审批任务 |
| HITL | 对代码修改进行人工批准 |
| CodeEditor | 应用经过校验的补丁 |
| PermissionPolicy | 限制读取范围 |
| RestrictedCheckRunner | 在临时副本执行检查 |
| AuditLogger | 记录执行结果 |
| pytest | 复现及验证 Bug |
| Ruff | 代码质量检查 |

今天最重要的认识：

**一个可靠的软件开发 Agent，不只是能够给出修复建议，还必须能让修改被审查、被验证，并且能够清楚地区分真实执行结果与模拟测试结果。**

本次因免费 API 额度限制，独立模型推理环节未完整验证，但其余部分可以在离线环境中完成实际工程测试。

**Day 14 是否最终验收通过，以本地审批执行、pytest、Ruff 和 Git 检查结果为准。**