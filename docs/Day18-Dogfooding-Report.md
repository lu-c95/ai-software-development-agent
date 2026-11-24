# Day 18｜AI Software Development Agent Dogfooding 实战报告

## 1. 任务概述

**项目：** AI Software Development Agent

**任务类型：** 自身项目 Bug 修复

**开发分支：** `fix/day18-evaluation-category-rate`

**目标模块：** `src/ai_software_dev_agent/evaluation_report.py`

**对应测试：** `tests/test_evaluation_report.py`

**执行方式：** 真实离线工具调用 + LangGraph HITL 人工审批

**真实大模型 API 请求：** 0 次

### Dogfooding 的含义

Dogfooding 指开发者使用自己开发的产品完成实际工作，以验证产品可用性并发现问题。

本次使用 Agent 自己的仓库读取工具、代码编辑审批工作流及受控检查工具，修复 Agent 自己的源码。

## 2. 真实问题

Day 16 开发的 `validate_report()` 已经能够检查：

- 报告总任务数。
- 整体通过数量和失败数量。
- 整体成功率。
- 失败案例列表。
- 各分类的任务总数和通过数。

但是它没有验证**每个分类自己的成功率**。

例如一个分类包含：

```json
{
  "total": 1,
  "passed": 0,
  "success_rate": 100.0
}
```

实际成功率应为 `0.0%`，而不是 `100.0%`。

原有实现没有拒绝这样的数据，可能生成统计结果不一致的 Markdown 报告。

## 3. 预期行为

分类成功率必须满足：

\[
\text{分类成功率}=
\frac{\text{分类通过数量}}{\text{分类任务总数}}
\times100\%
\]

结果保留两位小数。

如果报告中的分类成功率与计算值不一致，应抛出 `ValueError`。

原有合法报告仍然能够正常导出。

## 4. 测试先行：Red

在 `tests/test_evaluation_report.py` 中新增：

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

运行：

```bash
python -m pytest \
  tests/test_evaluation_report.py \
  -k "category_success_rate" \
  -v
```

实际观察：新增测试失败。

失败证明当前实现尚未满足新增的校验要求。

## 5. Agent 自身工具调用

### 5.1 读取自身代码

使用：

```python
create_secure_repository_tools(project)
```

获取 `inspect_repository` 和 `read_repository_file`。

通过 LangChain 工具接口读取：

```text
src/ai_software_dev_agent/evaluation_report.py
tests/test_evaluation_report.py
```

读取结果验证通过。

### 5.2 准备修改

使用 `old_text` 和 `new_text` 构造最小代码补丁。

第一次检查出现：

```text
旧代码匹配次数：0
```

排查后发现准备的旧代码文本与当前源码的格式不同。Ruff 格式化后的 `raise ValueError(...)` 是单行形式。

本次使用的是精确文本替换，因此缩进、换行和代码格式都会影响匹配。

调整 `old_text` 与实际源码一致后：

```text
旧代码匹配次数：1
```

重新通过匹配检查。

### 5.3 HITL 人工审批

通过 CLI：

```text
ai-dev-agent edit-approval prepare
ai-dev-agent edit-approval review
```

执行：

1. 生成代码 Diff。
2. 保存等待审批的工作流状态。
3. 人工检查修改。
4. 输入 `yes`。
5. 恢复工作流。
6. 验证原文件版本。
7. 应用修改。

最终审批状态：

```text
applied
```

实际源码发生了相应变化。

## 6. 修复内容

核心新增代码：

```python
# 根据分类的真实通过数量重新计算成功率。
expected_category_rate = round(
    category_passed / len(category_results) * 100,
    2,
)

# 分类成功率与实际结果不一致时拒绝生成报告。
if abs(stats["success_rate"] - expected_category_rate) > 0.001:
    raise ValueError(f"分类成功率不一致：{category}")
```

保留原有分类总数和通过数量检查。

不修改 `EvaluationCase`、`Observation` 或评分执行器的公共接口。

## 7. 修复结果：Green

修复后：

| 验证 | 结果 |
|---|---|
| 新增分类成功率测试 | 通过 |
| 报告模块测试 | 5 passed |
| Day 16 相关专项测试 | 12 passed |
| 历史合法 JSON 报告重新导出 | 通过 |
| 全项目 pytest | 通过 |
| Ruff Check | 通过 |
| Ruff Format Check | 通过 |
| 受控检查执行器 | 三项检查通过 |
| JSONL 审计日志 | 格式验证通过 |
| Day 16 固定离线评估 | 10/10 |

**全项目 pytest 的实际测试总数：** 以 `final-pytest.log` 中的结果填写，不推测具体数量。

## 8. 真实执行证据

本次过程产生或使用以下证据：

| 证据 | 用途 |
|---|---|
| Git Diff | 验证源码和测试的真实修改 |
| 修改前、后 SHA-256 | 辅助验证文件变化 |
| HITL 审批状态与任务 ID | 证明进行了人工审批 |
| pytest 输出 | 证明 Red → Green |
| Ruff 输出 | 验证代码质量 |
| `checks-summary.json` | 保存受控检查结果 |
| `audit.jsonl` | 保存检查执行审计 |
| `day18-regression-report.json` | 保存离线回归评估 |

原始审计日志、审批数据库与本机路径保存在本地，不直接提交到公开仓库。

## 9. 关键 Debug 经验

### 问题：旧代码匹配次数为 0

**现象：**

精确文本替换找不到预期代码。

**原因：**

准备的补丁文本与实际源码的代码格式不同。

**解决：**

先读取实际文件，检查缩进和换行，再修正 `old_text`，确认唯一匹配后才执行审批。

**工程经验：**

文本替换工具依赖源代码格式。必须配合唯一匹配检查、Diff 预览和版本校验。

不应在匹配失败时强制执行修改。

## 10. 能力验证结论

本次 Dogfooding 实际验证了：

- Agent 仓库工具能够读取自身源码。
- HITL 工作流能够对自身仓库发起并完成文件修改。
- 人工审批与文件校验流程可以正常执行。
- 修改后的测试从失败转为通过。
- 受控检查工具可以检查自身项目。
- 审计和评估模块能够保留执行记录。

### 尚未验证的能力

本次补丁由开发者明确制定，没有由真实大模型自主生成。

因此尚不能声称：

- 大模型自主发现并理解了该 Bug。
- 大模型自主生成了正确补丁。
- 大模型自主完成了全部 Agent Loop。
- Agent 已经具备生产级自主软件开发能力。

本次验证的结论应准确表述为：

**AI Software Development Agent 的真实离线工具链，已在自身仓库完成一次具有代码修改、人工审批、回归测试和审计证据的 Bug 修复实战。**

## 11. 后续工作

在 GitHub CI 通过并合并本次修复后，将其作为项目第一个学习里程碑发布。

后续可增加真实模型驱动的端到端评估，以进一步验证自主任务规划、工具选择和补丁生成能力。