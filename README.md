# AI Software Development Agent

一个基于 **Python、LangChain 和 LangGraph** 构建的 AI 软件开发智能体学习项目。

项目围绕真实 Python 工程开发场景，逐步实现代码仓库探索、需求分析、开发任务规划、工具调用、持久化会话、代码修改、人工审批、安全限制与自动化评估等能力。

本项目的重点不只是调用大模型，而是探索如何将模型、工具、工作流、安全机制与工程测试结合起来，形成一个可维护的软件开发 Agent。

> 项目性质：个人工程学习与实践项目，目前不是生产级自主编程系统。

## 1. 项目目标

本项目希望逐步实现一个能够辅助 Python 软件开发的智能体。

主要目标包括：

- 理解并探索本地 Python 项目。
- 根据用户需求生成开发计划。
- 通过工具读取和分析代码。
- 使用 LangChain 组织模型与工具调用。
- 使用 LangGraph 编排多步骤工作流。
- 支持多轮对话与会话恢复。
- 预览文件修改，并在人工批准后应用。
- 对文件访问和命令执行设置安全限制。
- 通过 pytest、Ruff 和离线评估验证工程能力。

## 2. 已实现的主要能力

### 2.1 仓库探索

能够检查指定项目的文件结构，并通过已有仓库工具读取文件、搜索代码等。

仓库工具为后续代码理解、问题分析和任务规划提供基础。

### 2.2 开发任务规划

支持使用模型分析开发需求，并生成结构化的开发步骤。

实际规划效果依赖模型服务提供方、模型能力及任务复杂度。

### 2.3 LangChain + LangGraph Agent

使用 LangChain 提供的模型与工具调用能力，结合 LangGraph 组织工作流。

支持多步骤任务执行，但复杂任务仍可能遇到模型能力不足、工具重复调用或执行步数限制等问题。

### 2.4 持久化聊天

通过 SQLite Checkpoint 保存会话状态。

支持多轮聊天、指定会话 ID，以及在后续进程中恢复已有会话。

### 2.5 人工审批与代码修改

在修改文件前生成 Diff 预览，等待人工明确批准。

文件修改流程结合：

- LangGraph interrupt / resume。
- SQLite Checkpoint。
- CodeEditor。
- 文件版本哈希检查。

未获得批准时，不应直接应用待审批修改。

### 2.6 安全与隔离

通过 PermissionPolicy 限制仓库读取范围。

通过受限仓库工具执行合法的文件读取。

通过 RestrictedCheckRunner 执行预定义检查，并记录审计信息。

**安全说明：** 当前受限执行器不是操作系统级沙箱，不应将其用于运行来源不可信的任意代码。

### 2.7 离线能力评估

Day 16 实现了一套固定评估集与报告系统。

目前覆盖：

- 合法仓库读取。
- 路径越界与敏感文件访问拒绝。
- Bug 修复回归测试。
- 新功能回归测试。
- Git 工作区状态检查。

Day 16 的十条离线评估任务全部通过。

这一结果只代表指定离线任务的执行表现，不代表真实大模型自主软件开发的整体成功率。

## 3. 技术栈

| 技术 | 用途 |
|---|---|
| Python 3.13 | 主要开发语言 |
| LangChain | 模型接入与工具调用 |
| LangGraph | Agent 工作流与状态管理 |
| SQLite | 会话与审批状态持久化 |
| Pydantic | 结构化数据及参数校验 |
| pytest | 自动化测试 |
| Ruff | 静态代码检查与格式检查 |
| Git / GitHub | 版本管理 |
| GitHub Actions | 持续集成 |

具体依赖版本以 `pyproject.toml` 和实际安装环境为准。

## 4. 环境要求

建议使用：

- Python 3.13
- Git
- macOS 或 Linux
- Python 虚拟环境

其他 Python 版本的兼容性以 `pyproject.toml` 的要求和实际测试结果为准。

## 5. 安装与运行

### 5.1 克隆项目

从项目的 GitHub 仓库克隆源码，进入仓库根目录。

### 5.2 创建虚拟环境

```bash
python3.13 -m venv .venv

source .venv/bin/activate
```

如果本机的 `python3` 已经是符合项目要求的版本，也可以根据实际环境使用 `python3`。

### 5.3 安装项目

```bash
python -m pip install -e .
```

安装开发检查工具：

```bash
python -m pip install pytest ruff
```

如果项目已在 `pyproject.toml` 中定义开发依赖组，应优先使用对应安装方式。

### 5.4 查看 CLI

```bash
ai-dev-agent --help
```

检查环境：

```bash
ai-dev-agent doctor
```

查看聊天命令：

```bash
ai-dev-agent chat --help
```

查看代码修改审批命令：

```bash
ai-dev-agent edit-approval --help
```

查看 Agent 工作流命令：

```bash
ai-dev-agent agent-workflow --help
```

具体参数请以当前 CLI 的 `--help` 输出为准。

## 6. 模型 API 配置

项目支持通过已配置的模型服务提供方调用大模型。

使用真实模型前，需要按当前模型配置模块的要求设置：

- API Key。
- API Base URL。
- 模型名称。
- 其他必要参数。

不要将真实 API Key 提交到 GitHub。

免费模型的可用性和请求额度可能发生变化。曾出现模型下线返回 404、免费额度耗尽返回 429 等情况。

因此，日常 pytest 和 CI 测试优先使用 Mock、Fake 或其他离线方式。

需要真实模型参与的集成测试单独进行。

## 7. 常用检查命令

运行全部自动化测试：

```bash
python -m pytest -v
```

Ruff 静态检查：

```bash
python -m ruff check .
```

Ruff 格式检查：

```bash
python -m ruff format --check .
```

自动修复部分 Ruff 问题：

```bash
python -m ruff check . --fix
```

格式化代码：

```bash
python -m ruff format .
```

自动修复或格式化后，需要重新执行测试和检查。

## 8. 离线 Agent 评估

Day 16 的固定评估集位于：

```text
evaluations/day16_cases.json
```

离线执行器：

```text
examples/day16_offline_evaluation.py
```

在仓库根目录执行：

```bash
python examples/day16_offline_evaluation.py \
  --project /path/to/trusted-lab-project \
  --cases evaluations/day16_cases.json \
  --output /tmp/day16-report.json
```

其中 `--project` 应指向可信的本地实验项目。

当前评估集针对 Day 14/15 的订单结算实验仓库设计，不适用于任意 Python 项目。

评估基线保存于：

```text
evaluations/reports/
```

## 9. CI 持续集成

GitHub Actions 工作流位于：

```text
.github/workflows/ci.yml
```

主要执行：

- Python 环境准备。
- 项目依赖安装。
- Ruff Check。
- Ruff Format Check。
- pytest 全量测试。

CI 不应依赖个人 OpenRouter API Key。

目前的 CI 主要验证离线自动化测试，不包含需要独立实验仓库的完整 Day 16 评估执行。

## 10. 实战项目

### Day 14：Bug 修复实战

使用独立 Python 订单结算项目，复现优惠码错误地影响运费的问题。

通过失败测试、根因分析、最小补丁和人工审批完成修复，并使用 pytest 进行回归验证。

### Day 15：功能开发实战

为同一实验项目新增 `FREESHIP` 免运费优惠码。

采用测试先行方式，经过人工审批应用最小修改，最终十个业务测试通过。

这两个实战主要使用离线确定性方式验证工具与工程流程。

真实模型自主完成任务的能力需要独立验证。

## 11. 架构文档

详细架构与模块职责参见：

[Architecture.md](docs/Architecture.md)

学习过程中形成的阶段记录保存在 `docs/` 目录。

## 12. 当前限制

项目仍处于工程学习阶段，主要限制包括：

- 大模型能力和服务可用性会影响实际 Agent 行为。
- 多步工具调用可能受到执行步数限制。
- CLI 的单行输入方式不适合直接粘贴多行任务文本。
- 受控执行器不是完整的 OS 沙箱。
- 当前离线评估集规模有限，不能代表任意开发任务的成功率。
- 尚未把所有自主开发场景都验证为稳定可用。

## 13. 项目定位

本项目用于持续学习和展示 Python 工程开发、Agent 工作流、工具集成、安全控制、自动化测试与软件开发实践。

重点是理解每个模块的作用，并通过真实编码和测试逐步提升工程能力。

不应将本项目描述为已经达到生产级、能够完全自主替代开发人员的软件开发系统。