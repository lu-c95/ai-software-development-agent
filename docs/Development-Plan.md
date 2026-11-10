# AI Software Development Agent — Development Plan（项目开发计划）

## 1. 项目概述

**项目名称：** AI Software Development Agent（AI 软件开发智能体）

**项目定位：** AI Agent 工程开发路线中的第 4 个综合项目

**核心技术：** Python + LangChain + LangGraph

**计划周期：** 18 个学习日（约 3～4 周，可适当延长）

**开发方式：** 手动编码、逐步理解、工程实践与测试验证，不使用 Codex 代替开发

**最终目标：** 开发一个支持多轮交互、代码仓库分析、任务规划、代码修改、测试执行、错误恢复和人工审批的 AI 软件开发智能体，形成可以用于 GitHub、简历和面试展示的完整项目。

## 2. 十八天开发计划总览

| Day | 核心主题 | 开发重点与最终产物 |
|---|---|---|
| **01** | Project Setup（项目初始化） | `src/`、CLI、pytest、Ruff、Git；完成标准 Python 工程骨架 |
| **02** | Repository Explorer（代码仓库探索） | 目录扫描、文件读取、代码搜索与路径限制；实现仓库探索工具 |
| **03** | LangChain Model Integration（模型集成） | Chat Model、Messages、Prompt Template；完成模型适配层 |
| **04** | LangChain Tools & Planning（工具与规划） | Tools、Pydantic、Structured Output；实现结构化任务规划 |
| **05** | LangChain Agent & Interactive CLI（智能体与持续交互） | `create_agent`、多轮消息、CLI 交互循环、`/exit`；实现可持续对话的基础 Agent |
| **06** | Code Editing & Diff（代码修改与差异） | 受限文件编辑、Patch、Git Diff；实现安全代码修改工具 |
| **07** | Test Runner & Verification（测试执行与验证） | pytest、Ruff、subprocess、超时处理；实现自动验证工具 |
| **08** | LangGraph Fundamentals（工作流基础） | StateGraph、State、Node、Edge；搭建有状态工作流 |
| **09** | LangChain + LangGraph Integration（框架集成） | 整合仓库探索、规划、修改、验证；完成端到端开发流程 |
| **10** | Conditional Routing & Recovery（路由与错误恢复） | Conditional Edges、失败分析、有限重试；建立自动修复循环 |
| **11** | Conversation Memory & Persistence（会话记忆与持久化） | Checkpoint、SQLite、`thread_id`、会话恢复；实现跨重启的多轮对话 |
| **12** | Human-in-the-loop（人工审批） | Interrupt、Command、审批与恢复；实现修改前人工确认 |
| **13** | Safety & Isolation（安全与隔离） | 完善文件权限、命令限制、执行隔离、操作日志；建立安全边界 |
| **14** | Bug Fixing Practice（Bug 修复实战） | 真实示例仓库分析、Bug 定位、代码修复、测试验证 |
| **15** | Feature Development Practice（功能开发实战） | 自然语言需求、小型功能实现、测试补充、用户交互 |
| **16** | Evaluation（智能体能力评估） | 评估集、回归测试、成功率、失败场景；形成能力评估报告 |
| **17** | CI & Documentation（持续集成与文档） | GitHub Actions、README、架构说明、安装与使用文档 |
| **18** | Release & Portfolio（发布与求职展示） | 完整演示、项目总结、简历项目描述、面试技术准备 |

### 阶段划分

| 阶段 | 时间 | 主要目标 |
|---|---|---|
| 工程基础 | Day 01–02 | 建立项目结构和代码仓库探索能力 |
| LangChain | Day 03–05 | 掌握模型、工具、Agent 和基础多轮交互 |
| 软件开发工具 | Day 06–07 | 实现代码修改、差异检查与自动测试 |
| LangGraph | Day 08–12 | 掌握状态工作流、框架集成、错误恢复、持久化和人工审批 |
| 工程实战与交付 | Day 13–18 | 安全完善、真实任务、评估、CI 与求职展示 |

---

## 3. 核心功能设计

### 3.1 软件开发能力

智能体最终支持以下流程：

**自然语言需求 → 仓库分析 → 任务规划 → 人工确认 → 代码修改 → 测试验证 → 失败修复 → 结果报告**

要求：

- 能够读取和搜索指定 Python 项目。
- 能根据用户需求生成结构化开发计划。
- 只能在授权范围内读取和修改代码。
- 能展示 Git Diff，执行 pytest 和 Ruff。
- 测试失败时能够分析原因并有限次数重试。
- 能输出修改文件、验证结果和执行报告。

### 3.2 多轮交互与会话管理

采用 CLI REPL（交互式读取、执行、输出循环）实现持续对话。

目标支持：

| 功能 | 预期行为 |
|---|---|
| 连续提问 | 回答一个问题后不自动退出 |
| 上下文理解 | 能理解针对前面问题的追问和补充要求 |
| 主动退出 | 输入 `/exit` 正常结束 |
| 新建会话 | 输入 `/new` 开始独立会话 |
| 帮助命令 | 输入 `/help` 查看交互指令 |
| 会话持久化 | 退出后保留已经提交的对话状态 |
| 会话恢复 | 通过 Session ID（会话标识）恢复之前的上下文 |
| 人工审批 | 在对话中批准或拒绝待执行的修改 |

基本交互形式：

```bash
ai-dev-agent chat --project ./demo-project
```

恢复指定会话的目标形式：

```bash
ai-dev-agent chat --project ./demo-project --session <session-id>
```

以上是预期接口，具体参数以实际开发与测试结果为准。

Day 05 先实现同一进程内的持续对话；Day 11 再实现持久化和跨进程恢复。

应区分会话历史与开发任务状态，避免把新的用户追问错误地当作已经批准的文件修改操作。

### 3.3 LangChain 与 LangGraph 分工

**LangChain：AI 能力层**

- 模型调用与消息管理。
- Prompt（提示词）组织。
- Tools（工具）封装。
- Structured Output（结构化输出）。
- Agent 模型推理与工具调用。

**LangGraph：工作流编排层**

- 开发任务执行状态。
- 节点和条件路由。
- 错误恢复与有限重试。
- Checkpoint（检查点）和会话持久化。
- Human-in-the-loop（人工审批）。

避免重复实现两套独立的 Agent Loop。

---

## 4. 技术方案

| 技术 | 主要用途 |
|---|---|
| Python | 核心开发语言 |
| LangChain | 模型集成、Tools、Agent 和结构化输出 |
| LangGraph | 工作流、状态、持久化、错误恢复和人工审批 |
| argparse | CLI 命令与交互入口 |
| Pydantic | 结构化数据与参数校验 |
| pathlib | 文件与路径操作 |
| subprocess | 受控命令执行 |
| SQLite | 本地会话及检查点持久化 |
| Git | 变更追踪与 Git Diff |
| pytest | 自动化测试 |
| Ruff | 代码质量检查与格式检查 |
| GitHub Actions | 持续集成及 Python 兼容性验证 |

大模型优先复用当前已能正常使用的模型服务。

第一版优先支持中小型 Python 仓库，不额外开发 Web 前端或复杂多智能体系统。

## 5. 每日开发规范

固定顺序：

**明确目标 → 检查环境 → 编写代码 → 功能测试 → 理解原理 → 学习文档 → 最终校验 → 成果验收 → Git 提交**

主要要求：

1. 每天只推进一个明确的开发阶段。
2. Python 文件优先提供完整最终代码，再解释实现与设计原因。
3. 新技术或英文术语首次出现时提供中文解释。
4. 优先使用 `tests/` 下的 pytest。
5. 每天最终执行完整 pytest、Ruff Lint 和 Ruff Format 检查。
6. 学习文档统一放在 `docs/DayXX-*.md`，使用易于复制的渲染后 Markdown。
7. Debug 只记录真实问题、实际命令和验证过程。
8. 每天必须亲自验证新增功能，确认后再 Git 提交。
9. 不为赶进度而跳过核心知识或工程验证。
10. 项目周期可以根据实际情况延长。

## 6. 最终项目验收标准

### 6.1 Agent 功能

- [ ] 支持持续多轮对话、主动退出、新建及恢复会话。
- [ ] 能结合历史上下文理解后续开发要求。
- [ ] 能理解、搜索和分析 Python 代码仓库。
- [ ] 能生成结构化开发任务计划。
- [ ] 能在授权范围内修改代码并展示差异。
- [ ] 能执行测试、分析失败并有限次数修复。
- [ ] 支持人工审批和危险操作拦截。
- [ ] 能输出完整、可审查的任务执行报告。

### 6.2 工程质量

- [ ] LangChain 与 LangGraph 职责清晰、架构合理。
- [ ] 核心功能具备自动化测试及异常处理。
- [ ] 具备会话持久化、状态管理和恢复能力。
- [ ] 文件操作和命令执行受到明确限制。
- [ ] 有可复现的真实开发任务及评估结果。
- [ ] README、架构文档和使用说明完整。
- [ ] GitHub Actions 能够执行自动化检查。

### 6.3 求职成果

- 完整的 GitHub 软件开发 Agent 项目。
- 可以持续交互的真实软件开发演示。
- 一份核心架构与技术设计说明。
- 一套真实任务评估结果。
- 可用于简历和技术面试的项目总结。

---

## 7. 项目完成原则

**不以严格完成 18 天任务为目标，而以掌握真实 AI Agent 工程开发能力为目标。**

LangChain 和 LangGraph 的学习应服务于真实工程实现，不单纯为了增加技术栈。

最终项目应能够在明确的安全边界内，通过持续对话协助用户完成代码分析、修改、验证和修复，并提供可复现、可解释的结果。