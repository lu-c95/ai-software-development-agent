
# Day 01 — Project Setup & Architecture（项目初始化与架构设计）

## 1. 当天目标

初始化 AI Software Development Agent（AI 软件开发智能体）项目，完成独立 Python 工程环境、CLI 命令行入口与基础测试。

本项目最终目标是让 Agent 能够理解代码仓库、规划开发任务、修改代码、执行测试并输出可审查的结果。

Day 01 暂不接入大模型，不实现自动代码修改。

## 2. 项目结构

```text
ai-software-development-agent/
├── src/
│   └── ai_software_dev_agent/
│       ├── __init__.py
│       ├── __main__.py
│       └── cli.py
├── tests/
│   └── test_cli.py
├── docs/
│   └── Day01-Project-Setup.md
├── pyproject.toml
├── .gitignore
└── README.md
```

说明：

- `src/`：放置项目源码，采用 src Layout（源码目录布局）。
- `__init__.py`：标记 Python 包，记录项目版本。
- `__main__.py`：支持 `python -m ai_software_dev_agent`。
- `cli.py`：命令行解析、参数校验与命令执行。
- `tests/`：自动化测试。
- `docs/`：每日学习和工程记录。
- `pyproject.toml`：项目元数据、依赖、构建与工具配置。
- `.gitignore`：排除虚拟环境、缓存、密钥和运行时文件。

## 3. 新增文件及核心实现

### 3.1 pyproject.toml

关键配置：

```toml
[project]
name = "ai-software-development-agent"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = []

[project.scripts]
ai-dev-agent = "ai_software_dev_agent.cli:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.ruff]
target-version = "py311"
```

关键理解：

1. `requires-python` 声明最低支持的 Python 版本。
2. `target-version` 设置 Ruff 的目标语法版本。
3. `[project.scripts]` 将命令行名称映射到 Python 函数。
4. `pip install -e ".[dev]"` 用可编辑模式安装项目及开发依赖。

当前实际开发环境是 Python 3.13.15。

配置 `>=3.11` 和 `py311` 不会改变当前使用的解释器版本，只表示兼容性目标。目前仅通过 Python 3.13.15 环境验证，不能据此证明所有声明版本均兼容。

### 3.2 CLI 命令行入口

`cli.py` 包含两个核心函数：

- `build_parser()`：使用 argparse 创建命令行解析器，注册子命令和参数。
- `main(argv)`：解析参数，执行指定功能，并返回退出码。

目前支持：

```bash
ai-dev-agent --help
ai-dev-agent --version
ai-dev-agent doctor --project .
```

`doctor` 命令执行：

1. 获取 `--project` 指定的路径，默认使用当前工作目录。
2. 通过 `Path.expanduser().resolve()` 转换成绝对路径。
3. 使用 `is_dir()` 检查目录是否存在。
4. 成功时输出路径并返回 `0`。
5. 目录无效时通过 `parser.error()` 报错，进程退出码为 `2`。

当前 `doctor` 只进行目录检查，不访问或修改目标代码文件。

### 3.3 __main__.py

核心入口：

```python
from ai_software_dev_agent.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
```

支持模块启动：

```bash
python -m ai_software_dev_agent doctor --project .
```

两种启动方式的区别：

- `ai-dev-agent`：通过项目安装时注册的命令行入口运行。
- `python -m ai_software_dev_agent`：通过 Python 模块执行入口运行。

两者最终都调用 `cli.main()`。

## 4. 核心调用链

```text
终端输入
    ↓
ai-dev-agent / python -m
    ↓
cli.main()
    ↓
build_parser()
    ↓
argparse 解析参数
    ↓
doctor 命令分支
    ↓
解析项目路径 → 校验目录
    ↓
打印检查结果 / 错误信息
    ↓
返回退出码
```

设计原则：

CLI 只承担参数解析与交互入口的职责。

后续新增 Agent、Repository Explorer（代码仓库探索工具）和其他业务模块时，应通过独立模块实现，避免把所有逻辑写进 `cli.py`。

## 5. 测试与验证

使用 pytest，测试文件为 `tests/test_cli.py`。

覆盖四个场景：

1. 有效项目目录检查成功。
2. 不存在的目录检查失败。
3. 不指定项目目录时使用当前工作目录。
4. `--help` 正确显示子命令。

实际测试结果：4 项测试已通过。

测试使用的 pytest Fixture（测试夹具）：

- `tmp_path`：提供独立临时目录，避免污染真实项目。
- `capsys`：捕获标准输出和标准错误。
- `monkeypatch`：临时修改工作目录，测试结束后恢复。

关键结论：

测试文件操作工具时，应优先使用临时目录，而不是直接操作真实项目文件。

## 6. 当天关键命令

### 6.1 虚拟环境

首次创建：

```bash
python3 -m venv .venv
```

日常激活与验证：

```bash
source .venv/bin/activate
which python
python -c 'import sys; print(sys.executable)'
python --version
```

### 6.2 安装项目

```bash
python3 -m pip install -e ".[dev]"
```

### 6.3 功能验证

```bash
ai-dev-agent --help
ai-dev-agent --version
ai-dev-agent doctor --project .
python -m ai_software_dev_agent doctor --project .
```

### 6.4 自动测试

```bash
python -m pytest tests/test_cli.py -v
```

### 6.5 最终工程检查

```bash
python -m pytest
python -m ruff check .
```

## 7. Debug

当天未出现需要记录的实际运行错误。

关于 Python 3.13.15 与配置中 3.11 / py311 的差异，属于兼容性配置理解问题，并非程序运行故障。

## 8. 非阻塞事项

- 尚未在 Python 3.11、3.12 环境中实际验证兼容性。
- 后续可通过 GitHub Actions 配置多版本测试。
- 当前仅支持 `doctor` 目录检查，尚未实现 Agent、文件编辑或模型调用。

## 9. 最值得理解的三个知识点

### 9.1 src Layout 与 Editable Install（可编辑安装）

`src/` 将项目源码与仓库根目录分离。

使用 `pip install -e ".[dev]"` 后，修改源码通常无需重新安装包。

优势是更容易发现错误的导入和打包配置，便于长期工程维护。

### 9.2 CLI 与业务逻辑分离

CLI 接收命令和参数，业务模块完成具体工作。

后续软件开发 Agent 应保持以下分工：

```text
CLI → Agent → 工具 → 执行结果
```

这是项目逐步扩展时的重要架构原则。

### 9.3 自动化测试是 Agent 的基础能力

软件开发 Agent 不仅要能够修改代码，还必须验证修改结果。

测试应覆盖：

- 正常操作
- 异常操作
- 默认行为
- 边界情况

尤其要避免测试直接修改用户真实项目。

Day 01 的重点不是功能复杂度，而是搭建可测试、可维护、可扩展的软件工程基础。
