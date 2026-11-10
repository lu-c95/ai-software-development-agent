# AI Software Development Agent

一个基于 Python 的 AI 软件开发智能体项目。

目标是让智能体能够理解代码仓库、规划开发任务、修改代码、执行测试，并提供可审查的开发结果。

## Current Stage（当前阶段）

Day 01：项目初始化、CLI 入口及基础测试。

目前尚未接入大模型，也不支持自动修改代码。

## Requirements（环境要求）

- Python >= 3.11

## Installation（安装）

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e ".[dev]"
```

## Usage（运行）

```bash
ai-dev-agent --help
ai-dev-agent doctor --project .
```

或者：

```bash
python -m ai_software_dev_agent doctor --project .
```

## Testing（测试）

```bash
python -m pytest
python -m ruff check .
```

## Documentation（文档）

每日学习与开发记录位于 `docs/`。