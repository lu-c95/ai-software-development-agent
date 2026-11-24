# AI Software Development Agent｜项目展示与面试材料

## 一、项目介绍

**项目名称：** AI Software Development Agent

**技术栈：** Python 3.13、LangChain、LangGraph、SQLite、Pydantic、pytest、Ruff、GitHub Actions

**项目类型：** 个人 AI Agent 工程实践项目

**项目定位：** 面向 Python 代码仓库的软件开发辅助 Agent。

项目围绕仓库探索、需求规划、多步骤工具调用、会话持久化、人工审批、安全访问控制和自动化评估构建。

通过实际开发，重点探索 AI Agent 与传统 Python 软件工程实践的结合方式。

## 二、项目核心模块

| 模块 | 技术 | 解决的问题 |
|---|---|---|
| CLI | Python | 命令行操作与功能分发 |
| 模型与工具 | LangChain | 模型交互和结构化工具调用 |
| 工作流 | LangGraph | 多步骤任务和状态管理 |
| 会话持久化 | SQLite Checkpoint | 多轮会话保存与恢复 |
| 人工审批 | LangGraph HITL | 文件修改前的人工授权 |
| 文件安全 | PermissionPolicy | 限制仓库访问范围 |
| 受控执行 | RestrictedCheckRunner | 执行预定义检查并审计 |
| 能力评估 | pytest、JSON、Markdown | 固定评估集与回归验证 |
| 持续集成 | GitHub Actions | 自动化测试和代码检查 |

## 三、可以放在简历中的项目描述

**AI Software Development Agent｜个人工程实践项目**

技术栈：Python、LangChain、LangGraph、SQLite、pytest、Ruff、GitHub Actions

- 基于 Python 构建模块化 CLI 软件开发辅助 Agent，集成代码仓库探索、结构化任务规划及模型工具调用能力。
- 使用 LangChain 封装工具调用，结合 LangGraph 实现有状态工作流，并通过 SQLite Checkpoint 支持会话持久化与恢复。
- 实现基于 LangGraph interrupt/resume 的 HITL 文件编辑审批流程，支持 Diff 预览、版本哈希校验及批准后应用修改。
- 设计仓库权限策略、受限检查执行器及 JSONL 审计机制，减少未经授权的文件操作。
- 建立离线能力评估框架，覆盖仓库读取、访问拒绝与业务回归等十条固定任务，完成 pytest、Ruff 与 GitHub Actions CI 集成。
- 使用 Agent 自身工具链对自身仓库完成一次真实 Bug 修复，并通过 Red/Green 测试、人工审批、审计日志和回归验证记录执行结果。

## 四、面试中的两分钟讲解

我做过一个基于 Python、LangChain 和 LangGraph 的 AI Software Development Agent 项目。

这个项目的核心目标，不只是调用大模型回答问题，而是把模型工具调用、工作流状态、代码仓库操作以及软件工程中的测试和安全控制整合起来。

在架构上，我将 CLI、仓库工具、Agent 工作流和评估模块分离。LangChain 主要用于模型与工具集成，LangGraph 主要负责有状态的流程控制。

其中，我重点实践了三个方面。

第一是会话持久化。我使用 SQLite Checkpoint 保存会话和工作流状态，使多轮交互及审批流程能够恢复。

第二是代码修改的安全控制。我实现了基于 Diff 的人工审批流程。文件修改不是直接写入，而是先生成预览，暂停工作流等待确认，批准后还要检查文件版本，最后才应用修改。

第三是工程质量。我建立了 pytest 和 Ruff 检查、GitHub Actions CI，以及一套包含十条任务的离线评估系统。

项目最后还进行了一次 Dogfooding：使用 Agent 自己的仓库工具读取自身代码，通过自己实现的审批流程修复一个评估统计 Bug，再运行测试和受控检查验证结果。

这个过程让我对 Python 工程开发、Agent 工具集成、状态管理和安全边界都有了更实际的理解。

目前真实模型的自主开发能力仍然需要更多测试，因此我把离线工具链验证和真实模型能力验证分开记录，没有将两者混为一谈。

## 五、建议重点准备的面试问题

### 1. LangChain 和 LangGraph 有什么区别？

LangChain 主要提供模型、消息和工具调用等抽象。

LangGraph 更关注有状态的多步骤工作流、流程控制、Checkpoint 和暂停恢复。

### 2. 为什么需要 HITL？

因为模型提出修改建议，不等于开发者已经授权执行。

HITL 可以将修改预览和实际写入分离，降低误操作风险。

### 3. 为什么需要 SQLite Checkpoint？

为了保存会话和工作流状态，支持跨进程恢复，而不是程序退出后就丢失上下文。

### 4. 如何防止 Agent 访问危险路径？

通过真实代码中的 PermissionPolicy 和受限仓库工具执行访问检查，而不能只依赖提示词约束。

### 5. 受控执行器是不是安全沙箱？

不是。

当前限制了操作范围和执行方式，但不能安全运行任意来源不可信的代码。

### 6. 怎样评估 Agent？

使用固定任务集、真实执行结果、预期比较、分类统计、失败案例和历史基线。

但离线工具评估与真实模型自主任务成功率必须区分。

### 7. Dogfooding 中遇到了什么实际问题？

使用精确文本替换准备补丁时，发现 Ruff 格式化导致目标代码的文本布局变化，旧代码匹配次数为零。

通过查看实际源码、重新准备匹配文本并验证唯一匹配，最终完成 HITL 审批修改。

这说明开发工具不仅需要生成补丁，还要具备修改前校验、Diff 审查与版本冲突处理。

## 六、项目当前限制

本项目属于个人工程实践项目，并非生产级自主编程系统。

真实模型在复杂任务上的自主规划、工具选择和代码修改能力，还需要更多端到端验证。

当前执行隔离也不属于完整的操作系统级安全沙箱。

项目展示以真实实现、实际测试和可复查的结果为依据。