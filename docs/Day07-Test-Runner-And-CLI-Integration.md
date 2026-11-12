# Day 07 — Test Runner & CLI Integration（测试执行器与命令行集成）

## 1. 今日学习目标与完成成果

### 1.1 学习目标

在 Day 06 实现安全代码修改之后，进一步实现 Test Runner（测试执行器），让程序能够调用 pytest 验证代码修改是否正确。

今天的主要目标：

1. 学习 Python `subprocess`（子进程管理）。
2. 使用当前 Python 解释器启动 pytest。
3. 理解 Exit Code（退出码）及 pytest 的不同执行状态。
4. 实现 Timeout（超时控制）。
5. 使用 Dataclass（数据类）保存结构化测试结果。
6. 限制测试目标路径与可执行命令。
7. 收集 stdout（标准输出）、stderr（标准错误）和执行耗时。
8. 为 CLI 新增 `test` 命令。
9. 编写自动化测试并使用独立项目进行真实验收。
10. 解决 pytest 收集测试类时产生的 Warning。

### 1.2 今日完成结果

已完成：

- 新增 `TestRunner` 类。
- 实现 pytest 子进程执行。
- 实现执行超时处理。
- 实现 `passed`、`failed`、`no_tests`、`error`、`timeout` 五种状态。
- 实现测试目标路径检查。
- 实现输出长度限制。
- 新增 `ai-dev-agent test` 命令。
- 支持指定目标文件和超时时间。
- 显示 pytest 退出码、执行耗时及标准输出。
- 测试失败时 CLI 返回非零退出码。
- 修复 `PytestCollectionWarning`。
- 通过完整自动化测试和正式 CLI 验收。

本日没有调用真实大模型，不消耗模型 API 额度。

---

## 2. 开发环境与文件结构

### 2.1 进入项目

```bash
cd "/Users/lc/Documents/公子路的长期成长计划/02-AI-Agent-Engineering/ai-software-development-agent"
```

激活虚拟环境：

```bash
source .venv/bin/activate
```

检查：

```bash
which python
which python3

python --version

python -c 'import sys; print(sys.executable)'
```

判断当前解释器是否位于项目 `.venv/bin/`。

检查 pytest：

```bash
python -m pytest --version
```

### 2.2 本日文件变化

```text
ai-software-development-agent/
├── src/
│   └── ai_software_dev_agent/
│       ├── agent.py
│       ├── cli.py                 # 修改：新增 test 子命令
│       ├── editor.py
│       ├── model.py
│       ├── planning.py
│       ├── repository.py
│       ├── test_runner.py         # 新增：pytest 测试执行器
│       └── tools.py
├── tests/
│   ├── test_agent.py
│   ├── test_cli.py                # 修改：新增 test 命令测试
│   ├── test_editor.py
│   ├── test_model.py
│   ├── test_planning.py
│   ├── test_repository.py
│   ├── test_test_runner.py        # 新增：执行器测试
│   └── test_tools.py
├── docs/
│   └── Day07-Test-Runner-And-CLI-Integration.md
└── pyproject.toml
```

本日涉及四个 Python 文件：

| 文件 | 变更类型 | 主要职责 |
|---|---|---|
| `test_runner.py` | 新增 | 安全约束、执行 pytest、收集结果 |
| `test_test_runner.py` | 新增 | 测试执行器的正常与异常路径 |
| `cli.py` | 修改 | 增加 `test` 命令与结果展示 |
| `test_cli.py` | 修改 | 增加测试执行命令的集成测试 |

---

## 3. 基础概念：subprocess（子进程）

### 3.1 为什么需要 subprocess？

此前我们在终端手动执行：

```bash
python -m pytest -v
```

但 AI 软件开发 Agent 将来需要能够自动验证自己修改的代码。

因此，我们需要让一个 Python 程序启动另一个进程运行 pytest。

Python 标准库 `subprocess` 就是用于管理子进程的模块。

示例：

```python
import subprocess

result = subprocess.run(
    ["python", "-m", "pytest", "-q"],
    capture_output=True,
    text=True,
)
```

这里：

- 当前程序是父进程（Parent Process）。
- pytest 所在的程序是子进程（Child Process）。
- 父进程等待子进程结束，再获取运行结果。

### 3.2 `subprocess.run()` 的常用参数

```python
result = subprocess.run(
    command,
    cwd=project,
    capture_output=True,
    text=True,
    timeout=30,
    check=False,
    shell=False,
)
```

| 参数 | 作用 |
|---|---|
| `command` | 要执行的程序及其参数 |
| `cwd` | 子进程工作目录 |
| `capture_output=True` | 捕获标准输出和错误输出 |
| `text=True` | 将捕获结果表示为字符串 |
| `timeout=30` | 最多等待 30 秒 |
| `check=False` | 非零退出码不自动抛出 `CalledProcessError` |
| `shell=False` | 不通过 Shell 解释命令 |

其中：

```python
shell = False
```

可以避免将整段用户输入交给 Shell 解释。

但必须注意：**不通过 Shell 不代表子进程中的代码没有危险。pytest 本身会执行 Python 测试代码。**

### 3.3 为什么使用 `sys.executable`？

我们没有直接写：

```python
command = ("python", "-m", "pytest")
```

而是使用：

```python
import sys

command = (
    sys.executable,
    "-m",
    "pytest",
)
```

`sys.executable` 返回当前 Python 解释器路径。

例如：

```text
/项目目录/.venv/bin/python
```

这样可以尽量保证子进程继续使用当前虚拟环境。

但它不会自动使用目标项目自己的虚拟环境。当前 Test Runner 适合执行与本项目解释器兼容的测试，后续仍需扩展目标项目解释器选择功能。

### 3.4 什么是 Exit Code（退出码）？

子进程退出时，通常会返回一个整数。

通常：

```text
0：成功
非 0：没有成功完成
```

但 pytest 对退出码有更具体的定义：

| pytest 退出码 | 含义 | 本日状态 |
|---|---|---|
| `0` | 测试全部通过 | `passed` |
| `1` | 有测试失败 | `failed` |
| `2` | 测试执行被中断 | `error` |
| `3` | pytest 内部错误 | `error` |
| `4` | pytest 用法错误 | `error` |
| `5` | 没有收集到测试 | `no_tests` |
| `6` | 警告被设置为错误等情况 | `error` |

这里需要区分：

**pytest 能正常运行，不等于测试通过。**

例如 pytest 成功启动并执行 10 个测试，其中 2 个失败，它仍然会以退出码 `1` 结束。

### 3.5 为什么不使用 `pytest.main()`？

pytest 也提供：

```python
import pytest

pytest.main(["-q"])
```

但本日更适合使用独立子进程，因为：

- 可以更清楚地控制进程生命周期。
- 可以获取子进程退出码。
- 可以捕获标准输出和错误输出。
- 可以设置执行超时。
- 可以减少 pytest 与当前程序之间的部分进程内状态干扰。

不过这只是进程分离，不是安全沙箱。

---

## 4. 第一阶段：实现 Test Runner

### 4.1 创建 `test_runner.py`

先执行创建命令：

```bash
touch src/ai_software_dev_agent/test_runner.py
```

打开文件：

```bash
nano src/ai_software_dev_agent/test_runner.py
```

### 4.2 `test_runner.py` 完整代码

```python
"""受控执行 pytest，并返回结构化测试结果。"""

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


# 默认运行时间为 30 秒，最多允许 120 秒。
DEFAULT_TIMEOUT_SECONDS = 30
MAX_TIMEOUT_SECONDS = 120

# 控制最终展示的输出长度，保留结尾的 pytest 汇总。
MAX_OUTPUT_CHARS = 16_000

TestStatus = Literal[
    "passed",
    "failed",
    "no_tests",
    "error",
    "timeout",
]


class TestRunnerError(ValueError):
    """测试执行参数或目标仓库不符合要求。"""


@dataclass(frozen=True)
class TestRunResult:
    """一次 pytest 执行产生的结构化结果。"""

    status: TestStatus
    exit_code: int | None
    stdout: str
    stderr: str
    duration_seconds: float
    command: tuple[str, ...]

    @property
    def passed(self) -> bool:
        """只有 pytest 退出码为 0 才表示通过。"""

        return self.status == "passed"


class TestRunner:
    """只允许在指定项目的 tests 目录内执行 pytest。"""

    def __init__(self, project: Path) -> None:
        root = project.expanduser().resolve()

        if not root.is_dir():
            raise TestRunnerError("项目目录不存在或不是目录")

        tests_root = root / "tests"

        if tests_root.is_symlink() or not tests_root.is_dir():
            raise TestRunnerError("项目必须包含非符号链接的 tests 目录")

        self.root = root
        self.tests_root = tests_root

    def _validate_target(self, target: str) -> str:
        """仅允许选择 tests 目录内的测试文件或子目录。"""

        if not target.strip():
            raise TestRunnerError("测试目标路径不能为空")

        relative = Path(target)

        if (
            relative.is_absolute()
            or ".." in relative.parts
            or not relative.parts
            or relative.parts[0] != "tests"
            or any(part.startswith(".") for part in relative.parts)
        ):
            raise TestRunnerError("测试目标必须是 tests 目录内的相对路径")

        current = self.root

        # 拒绝路径任意组成部分为符号链接。
        for part in relative.parts:
            current = current / part

            if current.is_symlink():
                raise TestRunnerError("测试目标路径不允许包含符号链接")

        resolved = current.resolve()

        if not resolved.is_relative_to(self.tests_root):
            raise TestRunnerError("测试目标超出 tests 目录")

        if not resolved.exists():
            raise TestRunnerError("指定的测试目标不存在")

        if resolved.is_file():
            # 当前只允许直接选择 pytest 命名规范的测试文件。
            if not resolved.name.startswith("test_") or resolved.suffix != ".py":
                raise TestRunnerError("仅允许选择 test_*.py 测试文件")

        elif not resolved.is_dir():
            raise TestRunnerError("测试目标必须是普通文件或目录")

        return relative.as_posix()

    @staticmethod
    def _limit_output(output: str | bytes | None) -> str:
        """规范化输出，并保留过长输出的末尾部分。"""

        if output is None:
            return ""

        # TimeoutExpired 捕获的输出可能仍然是 bytes。
        if isinstance(output, bytes):
            output = output.decode(
                "utf-8",
                errors="replace",
            )

        if len(output) <= MAX_OUTPUT_CHARS:
            return output

        omitted = len(output) - MAX_OUTPUT_CHARS

        return f"[输出已截断，省略前 {omitted} 个字符]\n{output[-MAX_OUTPUT_CHARS:]}"

    def run(
        self,
        target: str = "tests",
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> TestRunResult:
        """运行指定 pytest 目标，返回结果而非直接抛出测试失败。"""

        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, int)
            or not 1 <= timeout_seconds <= MAX_TIMEOUT_SECONDS
        ):
            raise TestRunnerError("超时时间必须是 1～120 秒之间的整数")

        safe_target = self._validate_target(target)

        # 固定命令格式，不允许用户传入任意 Shell 命令。
        command = (
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "--",
            safe_target,
        )

        # 去掉会额外改变 pytest 命令行行为的环境选项。
        # 这不是完整的进程或环境隔离。
        env = os.environ.copy()
        env.pop("PYTEST_ADDOPTS", None)
        env.pop("PYTEST_PLUGINS", None)

        started = time.perf_counter()

        try:
            completed = subprocess.run(
                command,
                cwd=self.root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
                stdin=subprocess.DEVNULL,
                check=False,
                shell=False,
                env=env,
            )

        except subprocess.TimeoutExpired as exc:
            elapsed = time.perf_counter() - started

            return TestRunResult(
                status="timeout",
                exit_code=None,
                stdout=self._limit_output(exc.stdout),
                stderr=self._limit_output(exc.stderr),
                duration_seconds=elapsed,
                command=command,
            )

        except OSError as exc:
            elapsed = time.perf_counter() - started

            return TestRunResult(
                status="error",
                exit_code=None,
                stdout="",
                stderr=str(exc),
                duration_seconds=elapsed,
                command=command,
            )

        elapsed = time.perf_counter() - started

        # pytest 的退出码与结果状态明确对应。
        if completed.returncode == 0:
            status: TestStatus = "passed"
        elif completed.returncode == 1:
            status = "failed"
        elif completed.returncode == 5:
            status = "no_tests"
        else:
            status = "error"

        return TestRunResult(
            status=status,
            exit_code=completed.returncode,
            stdout=self._limit_output(completed.stdout),
            stderr=self._limit_output(completed.stderr),
            duration_seconds=elapsed,
            command=command,
        )
```

---

## 5. Test Runner 关键代码讲解

### 5.1 为什么使用 Dataclass？

```python
@dataclass(frozen=True)
class TestRunResult:
```

这是为了让每一次测试执行，都返回统一的数据结构。

字段含义：

| 字段 | 类型 | 说明 |
|---|---|---|
| `status` | `TestStatus` | 执行状态 |
| `exit_code` | `int \| None` | pytest 进程退出码 |
| `stdout` | `str` | 标准输出 |
| `stderr` | `str` | 标准错误 |
| `duration_seconds` | `float` | 实际经过时间 |
| `command` | `tuple[str, ...]` | 执行的命令及参数 |

使用示例：

```python
result = runner.run()

print(result.status)
print(result.exit_code)
print(result.duration_seconds)
```

这种设计比直接返回一段终端文字更适合工程项目。

以后 LangGraph 工作流可以直接判断：

```python
if result.passed:
    ...
```

而不用解析终端字符串中的 `passed` 或 `failed`。

### 5.2 `Literal` 有什么作用？

```python
TestStatus = Literal[
    "passed",
    "failed",
    "no_tests",
    "error",
    "timeout",
]
```

`Literal` 是 Python 类型标注的一种方式。

它表示这个变量预期只能使用列出的几个固定值。

例如：

```python
status: TestStatus = "passed"
```

符合类型约定。

但：

```python
status: TestStatus = "unknown"
```

不符合类型约定。

注意：`Literal` 本身主要为类型检查器提供信息，不会自动阻止所有运行时非法赋值。

如果未来需要严格运行时校验，可以结合 Pydantic 或 `Enum` 等机制。

### 5.3 `@property` 有什么用？

代码：

```python
@property
def passed(self) -> bool:
    return self.status == "passed"
```

让调用方可以写：

```python
result.passed
```

而不需要：

```python
result.passed()
```

`@property` 将方法包装成类似属性的访问形式。

这里的 `passed` 是根据 `status` 计算出的派生属性，不需要单独存储。

### 5.4 为什么限制测试路径？

`TestRunner` 允许：

```text
tests
tests/test_math.py
tests/unit
tests/unit/test_math.py
```

拒绝：

```text
../outside.py
/tmp/outside.py
src/example.py
.env
tests/../outside.py
```

原因是 Test Runner 不应该成为任意路径执行入口。

检查：

```python
relative.is_absolute()
```

拒绝绝对路径。

检查：

```python
".." in relative.parts
```

拒绝父目录路径组件。

检查：

```python
relative.parts[0] != "tests"
```

要求目标以 `tests` 目录开头。

同时对路径组成部分进行符号链接检查，并确认最终路径位于 `tests` 内部。

这是一套教学阶段的路径约束，不是针对恶意文件系统并发变化的完整安全防护。

### 5.5 `relative.as_posix()` 是什么意思？

这是今天单独补充的重要知识点。

首先：

```python
from pathlib import Path

relative = Path("tests") / "unit" / "test_math.py"
```

`relative` 是 `Path` 对象。

执行：

```python
result = relative.as_posix()
```

得到：

```text
tests/unit/test_math.py
```

并且：

```python
type(result)
```

是：

```python
str
```

因此：

**`Path.as_posix()` 的作用是把 Path 对象转换成使用正斜杠 `/` 的路径字符串。**

它与其他方法的区别：

| 表达式 | 功能 |
|---|---|
| `relative.as_posix()` | 使用 `/` 表示的路径字符串 |
| `str(relative)` | 按当前平台习惯转换为字符串 |
| `relative.resolve()` | 解析绝对路径 |
| `relative.name` | 取得文件名 |
| `relative.suffix` | 取得扩展名 |
| `relative.parts` | 取得路径组成部分的元组 |

在 macOS 上，`str(relative)` 和 `relative.as_posix()` 通常看不出区别，因为 macOS 本身也使用 `/`。

但在 Windows 上，`as_posix()` 可以统一使用 `/`。

本日用途：

```python
return relative.as_posix()
```

路径检查完成后，把路径转换成统一格式的字符串，作为 subprocess 命令参数。

注意：

`as_posix()` 不会自动将路径转换成绝对路径，也不提供安全验证。安全检查是在调用它之前完成的。

### 5.6 `time.perf_counter()` 是什么意思？

`perf_counter` 是 Performance Counter（性能计数器）的缩写。

它用于精确测量一段操作所经过的时间。

示例：

```python
import time

start = time.perf_counter()

time.sleep(1.5)

end = time.perf_counter()

elapsed = end - start

print(f"执行耗时：{elapsed:.2f} 秒")
```

输出类似：

```text
执行耗时：1.50 秒
```

关键点：

```python
start = time.perf_counter()
```

记录开始时的计数值。

```python
end = time.perf_counter()
```

记录结束时的计数值。

两者相减得到经过时间，单位为秒。

这个函数的返回值不是日期时间戳，通常不应该单独解释其数值。

主要用途是计算时间间隔。

#### 与其他时间函数的区别

| 函数 | 用途 |
|---|---|
| `time.time()` | 获取当前 Unix 时间戳 |
| `time.perf_counter()` | 高精度测量经过时间 |
| `time.process_time()` | 测量当前进程消耗的 CPU 时间，不包括等待或休眠 |

例如：

```python
time.sleep(1)
```

虽然进程没有持续占用 CPU，但实际经过了约一秒。

`perf_counter()` 会把这段等待时间计入耗时。

这正符合我们的需求，因为用户关心的是：

> 从启动 pytest 到最终得到结果，我等待了多久？

本日代码：

```python
started = time.perf_counter()

completed = subprocess.run(...)

elapsed = time.perf_counter() - started
```

计算 pytest 子进程的实际运行耗时。

### 5.7 为什么使用 `time.perf_counter()` 而不是 `time.time()`？

`time.time()` 主要表示当前时间戳，可能受到系统时钟调整影响。

`perf_counter()` 使用适合测量时间间隔的高精度单调计时器。

因此统计代码耗时通常优先选择：

```python
time.perf_counter()
```

而不是：

```python
time.time()
```

### 5.8 `stdin=subprocess.DEVNULL` 的作用

```python
stdin = subprocess.DEVNULL
```

表示不给测试进程提供正常的交互式标准输入。

这样测试中如果意外调用：

```python
input("请输入：")
```

就不会无限等待用户从主 CLI 输入内容。

它不能阻止测试代码执行其他文件操作、网络请求或创建子进程。

### 5.9 `PYTEST_ADDOPTS` 与 `PYTEST_PLUGINS`

本日代码：

```python
env = os.environ.copy()

env.pop("PYTEST_ADDOPTS", None)
env.pop("PYTEST_PLUGINS", None)
```

两个环境变量分别可能影响 pytest 的额外参数与插件加载。

我们从子进程环境中去掉它们，减少外部配置对固定命令的影响。

不过，pytest 仍可能通过其他方式加载插件和项目配置。

因此这不是完全隔离的运行环境。

### 5.10 为什么使用 `--`？

```python
command = (
    sys.executable,
    "-m",
    "pytest",
    "-q",
    "--",
    safe_target,
)
```

`--` 通常用于表示选项结束。

后面的 `safe_target` 按位置参数处理。

即使如此，仍需要在构造命令之前对 `safe_target` 进行校验，不能单纯依赖 `--` 作为安全机制。

### 5.11 为什么对 stdout 截断？

测试失败可能产生很长的 Traceback（异常回溯）。

为了避免 CLI 一次输出太多内容，设置：

```python
MAX_OUTPUT_CHARS = 16_000
```

超过限制时：

```python
output[-MAX_OUTPUT_CHARS:]
```

保留最后部分。

因为 pytest 通常在输出末尾包含失败汇总。

但要注意：

本日先捕获完整子进程输出，再进行截断，所以这只是**返回结果的显示限制**，并不是子进程的内存或输出配额限制。

### 5.12 超时限制的边界

```python
timeout = timeout_seconds
```

可以防止直接子进程无限运行。

但如果 pytest 测试自己创建了子进程，`subprocess.run()` 的超时并不保证清理所有后代进程。

因此：

**Test Runner 只能运行你信任的本地 Python 项目测试。它目前不是安全沙箱。**

---

## 6. 第一阶段：编写 Test Runner 测试

### 6.1 创建测试文件

执行：

```bash
touch tests/test_test_runner.py
```

打开：

```bash
nano tests/test_test_runner.py
```

### 6.2 `test_test_runner.py` 完整最终代码

这里采用已解决 Warning 的导入别名形式。

```python
"""Test Runner 的执行结果、路径限制与超时测试。"""

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from ai_software_dev_agent.test_runner import (
    MAX_OUTPUT_CHARS,
    TestRunner as Runner,
    TestRunnerError as RunnerError,
)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """创建一个带 tests 目录的独立项目。"""

    (tmp_path / "tests").mkdir()
    return tmp_path


def write_test(
    project: Path,
    filename: str,
    source: str,
) -> Path:
    """在临时项目中创建测试文件。"""

    target = project / "tests" / filename
    target.write_text(source, encoding="utf-8")
    return target


def test_runner_reports_passed(project: Path) -> None:
    """pytest 成功时，返回 passed 和退出码 0。"""

    write_test(
        project,
        "test_math.py",
        "def test_add():\n    assert 1 + 1 == 2\n",
    )

    runner = Runner(project)
    result = runner.run()

    assert result.status == "passed"
    assert result.passed is True
    assert result.exit_code == 0
    assert "1 passed" in result.stdout
    assert result.duration_seconds >= 0


def test_runner_reports_failed(project: Path) -> None:
    """断言失败时，应返回 failed 而不是抛出异常。"""

    write_test(
        project,
        "test_math.py",
        "def test_add():\n    assert 1 + 1 == 3\n",
    )

    runner = Runner(project)
    result = runner.run()

    assert result.status == "failed"
    assert result.passed is False
    assert result.exit_code == 1
    assert "1 failed" in result.stdout


def test_runner_reports_no_tests(project: Path) -> None:
    """没有测试时，不能错误地报告通过。"""

    runner = Runner(project)
    result = runner.run()

    assert result.status == "no_tests"
    assert result.passed is False
    assert result.exit_code == 5


def test_runner_runs_specific_test_file(project: Path) -> None:
    """指定测试文件时，不应运行其他测试文件。"""

    write_test(
        project,
        "test_success.py",
        "def test_success():\n    assert True\n",
    )

    write_test(
        project,
        "test_failure.py",
        "def test_failure():\n    assert False\n",
    )

    runner = Runner(project)

    result = runner.run(
        target="tests/test_success.py",
    )

    assert result.passed is True
    assert result.exit_code == 0
    assert result.command[-1] == "tests/test_success.py"


@pytest.mark.parametrize(
    "target",
    [
        "../outside.py",
        "/tmp/outside.py",
        "tests/../outside.py",
        "src/test_other.py",
        "",
    ],
)
def test_runner_rejects_unsafe_target(
    project: Path,
    target: str,
) -> None:
    """拒绝仓库外路径和不属于 tests 的目标。"""

    runner = Runner(project)

    with pytest.raises(RunnerError):
        runner.run(target=target)


def test_runner_rejects_missing_target(
    project: Path,
) -> None:
    """测试目标不存在时，不应启动 pytest。"""

    runner = Runner(project)

    with pytest.raises(
        RunnerError,
        match="测试目标不存在",
    ):
        runner.run(target="tests/test_missing.py")


def test_runner_rejects_non_test_file(
    project: Path,
) -> None:
    """不能将普通 Python 文件直接作为测试目标。"""

    write_test(
        project,
        "helper.py",
        "value = 42\n",
    )

    runner = Runner(project)

    with pytest.raises(
        RunnerError,
        match="test_",
    ):
        runner.run(target="tests/helper.py")


def test_runner_rejects_symlink(
    project: Path,
) -> None:
    """测试目标路径不能经过符号链接。"""

    real_file = write_test(
        project,
        "test_real.py",
        "def test_real():\n    assert True\n",
    )

    link = project / "tests" / "test_link.py"
    link.symlink_to(real_file)

    runner = Runner(project)

    with pytest.raises(
        RunnerError,
        match="符号链接",
    ):
        runner.run(target="tests/test_link.py")


def test_runner_rejects_missing_tests_directory(
    tmp_path: Path,
) -> None:
    """没有 tests 目录时，创建执行器就应失败。"""

    with pytest.raises(
        RunnerError,
        match="tests 目录",
    ):
        Runner(tmp_path)


@pytest.mark.parametrize(
    "timeout",
    [0, -1, 121, True],
)
def test_runner_rejects_invalid_timeout(
    project: Path,
    timeout: Any,
) -> None:
    """超时时间必须是规定范围内的整数。"""

    runner = Runner(project)

    with pytest.raises(
        RunnerError,
        match="超时时间",
    ):
        runner.run(timeout_seconds=timeout)


def test_runner_reports_timeout(
    project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """超时时应返回 timeout，并保留已有输出。"""

    def fake_run(
        *args: Any,
        **kwargs: Any,
    ) -> None:
        raise subprocess.TimeoutExpired(
            cmd=args[0],
            timeout=kwargs["timeout"],
            output=b"partial output",
            stderr=b"execution timed out",
        )

    monkeypatch.setattr(
        "ai_software_dev_agent.test_runner.subprocess.run",
        fake_run,
    )

    runner = Runner(project)
    result = runner.run(timeout_seconds=2)

    assert result.status == "timeout"
    assert result.passed is False
    assert result.exit_code is None
    assert "partial output" in result.stdout
    assert "execution timed out" in result.stderr


def test_runner_reports_process_start_error(
    project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """子进程无法启动时应返回 error。"""

    def fake_run(
        *args: Any,
        **kwargs: Any,
    ) -> None:
        raise OSError("模拟子进程启动失败")

    monkeypatch.setattr(
        "ai_software_dev_agent.test_runner.subprocess.run",
        fake_run,
    )

    runner = Runner(project)
    result = runner.run()

    assert result.status == "error"
    assert result.exit_code is None
    assert "模拟子进程启动失败" in result.stderr


def test_runner_uses_fixed_pytest_command(
    project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """使用固定的命令参数，不经过 Shell。"""

    captured: dict[str, Any] = {}

    def fake_run(
        command: tuple[str, ...],
        **kwargs: Any,
    ) -> subprocess.CompletedProcess[str]:
        captured["command"] = command
        captured["kwargs"] = kwargs

        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout="1 passed",
            stderr="",
        )

    monkeypatch.setenv(
        "PYTEST_ADDOPTS",
        "--maxfail=1",
    )
    monkeypatch.setenv(
        "PYTEST_PLUGINS",
        "some_plugin",
    )

    monkeypatch.setattr(
        "ai_software_dev_agent.test_runner.subprocess.run",
        fake_run,
    )

    runner = Runner(project)
    result = runner.run()

    assert result.passed is True

    assert captured["command"] == (
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "--",
        "tests",
    )

    options = captured["kwargs"]

    assert options["shell"] is False
    assert options["cwd"] == project.resolve()
    assert options["stdin"] == subprocess.DEVNULL
    assert "PYTEST_ADDOPTS" not in options["env"]
    assert "PYTEST_PLUGINS" not in options["env"]


def test_runner_truncates_large_output(
    project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """输出过长时，保留结尾的 pytest 总结。"""

    def fake_run(
        command: tuple[str, ...],
        **kwargs: Any,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout="x" * 20_000 + "\n1 passed\n",
            stderr="",
        )

    monkeypatch.setattr(
        "ai_software_dev_agent.test_runner.subprocess.run",
        fake_run,
    )

    runner = Runner(project)
    result = runner.run()

    assert result.status == "passed"
    assert result.stdout.startswith("[输出已截断")
    assert result.stdout.endswith("1 passed\n")
    assert len(result.stdout) < MAX_OUTPUT_CHARS + 100
```

### 6.3 测试内容说明

本日的 Test Runner 测试包括：

| 测试场景 | 验证内容 |
|---|---|
| 正常测试 | 返回 `passed` |
| 断言失败 | 返回 `failed` |
| 没有测试 | 返回 `no_tests` |
| 指定文件 | 只执行目标文件 |
| 非法路径 | 拒绝运行 |
| 文件不存在 | 拒绝运行 |
| 非测试文件 | 拒绝运行 |
| 符号链接 | 拒绝目标 |
| 缺少 `tests` 目录 | 创建执行器失败 |
| 非法超时时间 | 拒绝执行 |
| 子进程超时 | 返回 `timeout` |
| 启动失败 | 返回 `error` |
| 命令参数检查 | 验证固定 pytest 命令及 `shell=False` |
| 过长输出 | 保留末尾汇总 |

部分测试通过 `pytest.mark.parametrize` 扩展成多个独立用例。

按本日测试设计，第一阶段新增 21 个测试用例。

### 6.4 为什么部分测试使用真实 pytest？

例如：

```python
runner = Runner(project)

result = runner.run()
```

测试会真正创建子进程、运行 pytest 并获取结果。

这样可以验证：

```text
TestRunner
    ↓
subprocess.run()
    ↓
pytest
    ↓
CompletedProcess
    ↓
TestRunResult
```

整条调用链是否工作正常。

这类测试不仅验证单个函数逻辑，还验证多个组件能否协同运行。

### 6.5 为什么超时测试使用 Mock？

真实编写死循环会让测试变慢，还可能造成残留进程。

因此我们使用：

```python
monkeypatch.setattr(
    "ai_software_dev_agent.test_runner.subprocess.run",
    fake_run,
)
```

模拟：

```python
raise subprocess.TimeoutExpired(...)
```

然后验证 Test Runner 是否正确处理这个异常。

这种方式能验证异常分支，但不等于已经覆盖真实进程树清理的所有问题。

---

## 7. 真实 Debug：PytestCollectionWarning

### 7.1 问题现象

在运行：

```bash
python -m pytest tests/test_test_runner.py -v
```

时，出现两条 Warning：

```text
PytestCollectionWarning:
cannot collect test class 'TestRunner'
because it has a __init__ constructor

PytestCollectionWarning:
cannot collect test class 'TestRunnerError'
because it has a __init__ constructor
```

对应文件：

```text
src/ai_software_dev_agent/test_runner.py
```

分别指向：

```python
class TestRunner:
```

以及：

```python
class TestRunnerError(ValueError):
```

用户确认当时测试通过，但存在这两条收集警告。

### 7.2 为什么会出现？

最初在测试文件中直接导入：

```python
from ai_software_dev_agent.test_runner import (
    MAX_OUTPUT_CHARS,
    TestRunner,
    TestRunnerError,
)
```

pytest 在收集测试时，会检查测试模块中的对象。

默认情况下，以 `Test` 开头的类名可能被 pytest 当作测试类候选对象。

所以导入到测试模块中的：

```text
TestRunner
TestRunnerError
```

触发了 pytest 的测试类收集规则。

但是：

```python
class TestRunner:
    def __init__(self, project: Path): ...
```

具有构造函数。

`TestRunnerError` 继承了异常类的构造行为，也不是有效的 pytest 测试类。

因此 pytest 发出 Warning。

注意：

**这不是 TestRunner 的业务实现错误，而是测试模块中导入对象的命名与 pytest 收集规则发生了冲突。**

### 7.3 修复方式

打开已有文件：

```bash
nano tests/test_test_runner.py
```

将原来：

```python
from ai_software_dev_agent.test_runner import (
    MAX_OUTPUT_CHARS,
    TestRunner,
    TestRunnerError,
)
```

修改为：

```python
from ai_software_dev_agent.test_runner import (
    MAX_OUTPUT_CHARS,
    TestRunner as Runner,
    TestRunnerError as RunnerError,
)
```

然后将测试文件中的：

```python
TestRunner(project)
```

统一改为：

```python
Runner(project)
```

将：

```python
pytest.raises(TestRunnerError)
```

改为：

```python
pytest.raises(RunnerError)
```

### 7.4 为什么别名能够解决问题？

```python
TestRunner as Runner
```

表示导入的仍然是原来的 `TestRunner` 类，但在当前模块中的名称是 `Runner`。

原对象没有发生变化。

`as` 是 Python 的 Import Alias（导入别名）语法。

因为：

```text
Runner
RunnerError
```

不再以 `Test` 开头，所以不会因为名称触发 pytest 的默认测试类收集规则。

### 7.5 修复后验证

执行：

```bash
python -m pytest tests/test_test_runner.py -v
```

然后：

```bash
python -m pytest -v
```

实际结果：

- 测试通过。
- 原先两条 `PytestCollectionWarning` 消失。

### 7.6 这次 Debug 的收获

1. pytest 不只收集测试函数，还会根据命名规则识别测试类。
2. 导入到测试模块中的普通类，也可能触发 pytest 的收集规则。
3. `Test` 前缀适合测试类，但并不是所有业务类都需要被 pytest 收集。
4. 导入别名可以解决当前命名冲突。
5. 不建议为了消除这两条 Warning 就直接关闭所有 pytest 警告。

---

## 8. 第二阶段：集成正式 CLI

### 8.1 为什么需要 `ai-dev-agent test`？

第一阶段已经能够：

```python
runner = TestRunner(project)

result = runner.run(
    target="tests",
    timeout_seconds=30,
)
```

但我们希望用户可以直接运行：

```bash
ai-dev-agent test --project .
```

这样无需每次手动编写 Python 脚本。

也让未来的开发工作流拥有一个标准的测试执行入口。

### 8.2 修改已有 `cli.py`

执行：

```bash
nano src/ai_software_dev_agent/cli.py
```

这是 Day 01 就存在的文件，不需要重新创建。

本日保留之前八个子命令，并新增第九个命令：

```text
test
```

### 8.3 `cli.py` 完整代码

```python
"""AI 软件开发智能体的命令行入口。"""

import argparse
import sys
from pathlib import Path

from langchain_core.exceptions import OutputParserException
from langchain_core.messages import BaseMessage, ToolMessage
from langchain_core.runnables import Runnable
from openai import APIStatusError, OpenAIError
from pydantic import ValidationError

from ai_software_dev_agent import __version__
from ai_software_dev_agent.agent import (
    AgentExecutionError,
    build_development_agent,
    run_agent_turn,
)
from ai_software_dev_agent.editor import CodeEditor, FileEditError
from ai_software_dev_agent.model import (
    ModelConfigError,
    create_chat_model,
    generate_answer,
    load_model_settings,
)
from ai_software_dev_agent.planning import (
    PlanningError,
    generate_development_plan,
)
from ai_software_dev_agent.repository import (
    RepositoryError,
    RepositoryExplorer,
)
from ai_software_dev_agent.test_runner import (
    DEFAULT_TIMEOUT_SECONDS,
    TestRunner,
    TestRunnerError,
)


def describe_api_error(status_code: int) -> str:
    """将常见 HTTP 错误转换为容易理解的提示。"""

    reasons = {
        400: "请求参数错误或模型不支持该功能",
        401: "API Key 无效或没有访问权限",
        404: "模型不存在或当前不可用",
        429: "平台限流或模型访问量过大",
    }

    return reasons.get(
        status_code,
        "请检查模型服务状态和请求配置",
    )


def build_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器。"""

    parser = argparse.ArgumentParser(
        prog="ai-dev-agent",
        description="AI Software Development Agent",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="检查目标项目目录",
    )

    inspect_parser = subparsers.add_parser(
        "inspect",
        help="列出项目中的代码文件",
    )

    read_parser = subparsers.add_parser(
        "read",
        help="读取指定代码文件",
    )

    search_parser = subparsers.add_parser(
        "search",
        help="搜索代码关键词",
    )

    ask_parser = subparsers.add_parser(
        "ask",
        help="使用 LangChain 调用聊天模型",
    )

    plan_parser = subparsers.add_parser(
        "plan",
        help="生成结构化软件开发计划",
    )

    chat_parser = subparsers.add_parser(
        "chat",
        help="与能够探索代码仓库的 Agent 持续对话",
    )

    edit_parser = subparsers.add_parser(
        "edit",
        help="预览并确认一次 Python 代码修改",
    )

    # Day 07：新增 pytest 测试执行命令。
    test_parser = subparsers.add_parser(
        "test",
        help="在指定项目中受控执行 pytest",
    )

    # 需要指定仓库的命令统一支持 --project。
    for command_parser in (
        doctor_parser,
        inspect_parser,
        read_parser,
        search_parser,
        chat_parser,
        edit_parser,
        test_parser,
    ):
        command_parser.add_argument(
            "--project",
            type=Path,
            default=Path.cwd(),
            help="目标项目目录",
        )

    read_parser.add_argument(
        "--path",
        required=True,
        help="相对项目根目录的文件路径",
    )

    search_parser.add_argument(
        "--query",
        required=True,
        help="搜索关键词",
    )

    search_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="最多返回的结果数",
    )

    ask_parser.add_argument(
        "--question",
        required=True,
        help="发送给模型的问题",
    )

    plan_parser.add_argument(
        "--task",
        required=True,
        help="需要制定计划的软件开发任务",
    )

    # Day 06：安全文件编辑参数。
    edit_parser.add_argument(
        "--path",
        required=True,
        help="相对项目根目录的 Python 文件路径",
    )

    edit_parser.add_argument(
        "--old",
        required=True,
        help="需要精确匹配的旧代码片段",
    )

    edit_parser.add_argument(
        "--new",
        required=True,
        help="替换后的新代码片段",
    )

    # Day 07：固定 pytest 目标与超时参数。
    test_parser.add_argument(
        "--target",
        default="tests",
        help="tests 目录或其中的 test_*.py 文件",
    )

    test_parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="执行超时秒数，范围 1～120，默认 30",
    )

    return parser


def run_test_command(
    project: Path,
    target: str,
    timeout_seconds: int,
) -> int:
    """调用 TestRunner，并展示结构化 pytest 执行结果。"""

    try:
        runner = TestRunner(project)

        result = runner.run(
            target=target,
            timeout_seconds=timeout_seconds,
        )

    except (TestRunnerError, OSError) as exc:
        print(
            f"测试参数或目标错误：{exc}",
            file=sys.stderr,
        )
        return 2

    # 将内部状态转换为用户更容易理解的文字。
    status_labels = {
        "passed": "通过",
        "failed": "测试失败",
        "no_tests": "未发现测试",
        "error": "执行错误",
        "timeout": "执行超时",
    }

    status_label = status_labels[result.status]

    print(f"测试状态：{result.status}（{status_label}）")

    # 超时或进程启动失败时，可能没有 pytest 退出码。
    exit_code = str(result.exit_code) if result.exit_code is not None else "无"

    print(f"pytest 退出码：{exit_code}")
    print(f"执行耗时：{result.duration_seconds:.2f} 秒")

    if result.stdout:
        print("\n=== pytest 标准输出 ===")
        print(
            result.stdout,
            end="" if result.stdout.endswith("\n") else "\n",
        )

    if result.stderr:
        print("\n=== pytest 错误输出 ===", file=sys.stderr)
        print(
            result.stderr,
            end="" if result.stderr.endswith("\n") else "\n",
            file=sys.stderr,
        )

    # 只有全部通过才向调用方返回 0。
    # 其他情况统一返回非零，便于后续工作流检测失败。
    return 0 if result.passed else 1


def run_edit_command(
    project: Path,
    file_path: str,
    old_text: str,
    new_text: str,
) -> int:
    """预览差异，获取用户确认，然后安全应用修改。"""

    try:
        editor = CodeEditor(project)

        preview = editor.preview_replace(
            file_path,
            old_text,
            new_text,
        )

    except (FileEditError, RepositoryError, OSError) as exc:
        print(
            f"无法生成修改预览：{exc}",
            file=sys.stderr,
        )
        return 1

    print(f"目标文件：{preview.path}")
    print("=== 修改预览（尚未写入）===")

    print(
        preview.diff,
        end="" if preview.diff.endswith("\n") else "\n",
    )

    try:
        confirmation = input("\n输入 yes 确认写入，其他任意输入取消：").strip()

    except (EOFError, KeyboardInterrupt):
        print("\n已取消修改，文件未写入。")
        return 0

    if confirmation != "yes":
        print("已取消修改，文件未写入。")
        return 0

    try:
        editor.apply(preview)

    except (FileEditError, RepositoryError, OSError) as exc:
        print(
            f"应用补丁失败：{exc}",
            file=sys.stderr,
        )
        return 1

    print(f"修改完成：{preview.path}")

    return 0


def run_chat_session(
    agent: Runnable,
    project: Path,
) -> int:
    """启动持续对话，并维护当前进程内的消息历史。"""

    history: list[BaseMessage] = []

    print("AI Software Development Agent")
    print(f"当前项目：{project.expanduser().resolve()}")
    print("输入 /help 查看命令，输入 /exit 退出。")

    while True:
        try:
            question = input("\n你：").strip()

        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            return 0

        if not question:
            continue

        if question == "/exit":
            print("再见！")
            return 0

        if question == "/help":
            print("/help  查看帮助")
            print("/new   清空当前对话历史")
            print("/exit  退出交互式 CLI")
            continue

        if question == "/new":
            history = []
            print("已清空当前对话历史。")
            continue

        if question.startswith("/"):
            print("未知命令，请输入 /help 查看可用命令。")
            continue

        try:
            answer, updated_history = run_agent_turn(
                agent,
                history,
                question,
            )

        except APIStatusError as exc:
            print(
                f"模型请求失败：HTTP {exc.status_code}，"
                f"{describe_api_error(exc.status_code)}。",
                file=sys.stderr,
            )
            continue

        except OpenAIError as exc:
            print(
                f"模型请求失败：{type(exc).__name__}。",
                file=sys.stderr,
            )
            continue

        except RecursionError:
            print(
                "Agent 达到执行步数上限，本轮历史未保存，请尝试简化问题。",
                file=sys.stderr,
            )
            continue

        except (
            AgentExecutionError,
            ModelConfigError,
            RepositoryError,
            ValidationError,
        ) as exc:
            print(
                f"Agent 执行失败：{exc}",
                file=sys.stderr,
            )
            continue

        except KeyboardInterrupt:
            print("\n本轮请求已中断，可以继续输入。")
            continue

        # 仅展示本轮新增的工具执行消息。
        new_messages = updated_history[len(history) :]

        for message in new_messages:
            if isinstance(message, ToolMessage):
                tool_name = message.name or "未知工具"
                print(f"[工具返回] {tool_name}")

        history = updated_history

        print(f"Agent：{answer}")


def main(argv: list[str] | None = None) -> int:
    """解析命令并执行对应功能。"""

    parser = build_parser()
    args = parser.parse_args(argv)

    # Day 07：独立执行 pytest，不依赖模型 API。
    if args.command == "test":
        return run_test_command(
            project=args.project,
            target=args.target,
            timeout_seconds=args.timeout,
        )

    # Day 06：安全文件修改。
    if args.command == "edit":
        return run_edit_command(
            project=args.project,
            file_path=args.path,
            old_text=args.old,
            new_text=args.new,
        )

    # Day 05：交互式 Agent。
    if args.command == "chat":
        try:
            settings = load_model_settings()
            model = create_chat_model(settings)

            agent = build_development_agent(
                model,
                args.project,
            )

        except (ModelConfigError, RepositoryError) as exc:
            parser.error(str(exc))

        return run_chat_session(agent, args.project)

    # Day 03、Day 04：普通问答和结构化规划。
    if args.command in ("ask", "plan"):
        try:
            settings = load_model_settings()
            model = create_chat_model(settings)

            if args.command == "ask":
                answer = generate_answer(
                    model,
                    args.question,
                )
                print(answer)

            else:
                plan = generate_development_plan(
                    model,
                    args.task,
                )
                print(plan.model_dump_json(indent=2))

        except ModelConfigError as exc:
            parser.error(str(exc))

        except (
            PlanningError,
            ValidationError,
            OutputParserException,
        ) as exc:
            print(
                f"开发计划结构化生成失败：{type(exc).__name__}。",
                file=sys.stderr,
            )
            return 1

        except APIStatusError as exc:
            print(
                f"模型请求失败：HTTP {exc.status_code}，"
                f"{describe_api_error(exc.status_code)}。",
                file=sys.stderr,
            )
            return 1

        except OpenAIError as exc:
            print(
                f"模型请求失败：{type(exc).__name__}。",
                file=sys.stderr,
            )
            return 1

        return 0

    # Day 01、Day 02：仓库探索命令。
    try:
        explorer = RepositoryExplorer(args.project)

        if args.command == "doctor":
            print(f"项目目录检查通过：{explorer.root}")
            print("当前模式：仅进行目录检查，不修改任何文件。")

        elif args.command == "inspect":
            files = explorer.list_files()
            print(f"找到 {len(files)} 个可探索文件：")

            for path in files:
                print(path)

        elif args.command == "read":
            content = explorer.read_file(args.path)
            print(content, end="")

        elif args.command == "search":
            hits = explorer.search(
                args.query,
                limit=args.limit,
            )

            print(f"找到 {len(hits)} 条匹配结果：")

            for hit in hits:
                print(f"{hit.path}:{hit.line_number}: {hit.line}")

    except RepositoryError as exc:
        parser.error(str(exc))

    return 0
```

---

## 9. CLI 集成代码讲解

### 9.1 新增 `test` 命令

```python
test_parser = subparsers.add_parser(
    "test",
    help="在指定项目中受控执行 pytest",
)
```

支持：

```text
--project
--target
--timeout
```

例如：

```bash
ai-dev-agent test \
  --project . \
  --target tests/test_agent.py \
  --timeout 30
```

参数含义：

| 参数 | 默认值 | 作用 |
|---|---|---|
| `--project` | 当前目录 | 目标项目根目录 |
| `--target` | `tests` | pytest 目标 |
| `--timeout` | `30` | 最多执行秒数 |

### 9.2 为什么单独创建 `run_test_command()`？

```python
def run_test_command(
    project: Path,
    target: str,
    timeout_seconds: int,
) -> int:
```

职责：

1. 创建 Test Runner。
2. 执行测试。
3. 将内部状态转换为用户容易理解的输出。
4. 展示退出码和耗时。
5. 展示 stdout 与 stderr。
6. 返回 CLI 退出码。

我们继续采用分层结构：

```text
main()
  └── run_test_command()
         └── TestRunner.run()
                └── subprocess.run()
                       └── pytest
```

这样 CLI 不需要了解 pytest 子进程的具体实现细节。

后续 LangGraph 工作流也可以直接复用 `TestRunner.run()`。

### 9.3 CLI 退出码与 pytest 退出码的区别

例如：

```text
pytest 退出码：5
```

表示 pytest 没有收集到任何测试。

但 CLI 最终返回：

```text
1
```

因为我们只在：

```python
result.passed is True
```

时返回 `0`。

本日 CLI 退出码设计：

| CLI 退出码 | 含义 |
|---|---|
| `0` | 测试通过 |
| `1` | 测试失败、无测试、执行错误或超时 |
| `2` | 参数或测试目标不合法 |

因此：

**CLI 对外提供的是统一执行结果，pytest 原始退出码保留用于诊断。**

### 9.4 为什么使用 stdout 与 stderr？

Test Runner 返回：

```python
result.stdout
result.stderr
```

CLI 分别打印。

标准输出用于显示测试结果及汇总：

```text
=== pytest 标准输出 ===
...
2 passed in ...
```

标准错误用于显示额外的诊断信息：

```text
=== pytest 错误输出 ===
...
```

两者区分后，未来可以分别记录日志或导出报告。

### 9.5 为什么显示执行耗时？

```python
print(f"执行耗时：{result.duration_seconds:.2f} 秒")
```

`:.2f` 表示按照两位小数展示浮点数。

例如：

```python
duration = 1.23456
print(f"{duration:.2f}")
```

输出：

```text
1.23
```

这只影响显示格式，不会修改 `TestRunResult` 中保存的原始浮点数。

---

## 10. 第二阶段：修改 CLI 自动化测试

### 10.1 打开已有文件

执行：

```bash
nano tests/test_cli.py
```

保留 Day 01～Day 06 的测试，再增加 Day 07 的测试。

### 10.2 `test_cli.py` 完整代码

```python
"""CLI 命令行功能测试。"""

import json
from pathlib import Path

import pytest
from langchain_core.language_models import FakeListChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from ai_software_dev_agent import cli
from ai_software_dev_agent.agent import AgentExecutionError
from ai_software_dev_agent.model import ModelConfigError, ModelSettings
from ai_software_dev_agent.planning import (
    DevelopmentPlan,
    PlanningError,
    PlanStep,
)
from ai_software_dev_agent.test_runner import (
    TestRunResult as RunnerResult,
)


# ==========================================================
# Day 01：项目检查
# ==========================================================


def test_doctor_accepts_existing_directory(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = cli.main(["doctor", "--project", str(tmp_path)])
    output = capsys.readouterr().out

    assert result == 0
    assert "项目目录检查通过" in output
    assert str(tmp_path.resolve()) in output


def test_doctor_rejects_missing_directory(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    missing_path = tmp_path / "missing"

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["doctor", "--project", str(missing_path)])

    assert exc_info.value.code == 2
    assert "项目目录不存在" in capsys.readouterr().err


def test_doctor_uses_current_directory_by_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)

    result = cli.main(["doctor"])
    output = capsys.readouterr().out

    assert result == 0
    assert str(tmp_path.resolve()) in output


def test_help_displays_doctor_command(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--help"])

    assert exc_info.value.code == 0
    assert "doctor" in capsys.readouterr().out


# ==========================================================
# Day 02：仓库探索
# ==========================================================


def test_inspect_lists_files(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "a.py").write_text(
        "pass\n",
        encoding="utf-8",
    )

    result = cli.main(
        [
            "inspect",
            "--project",
            str(tmp_path),
        ]
    )

    assert result == 0
    assert "a.py" in capsys.readouterr().out


def test_read_displays_file(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "a.py").write_text(
        "value = 42\n",
        encoding="utf-8",
    )

    result = cli.main(
        [
            "read",
            "--project",
            str(tmp_path),
            "--path",
            "a.py",
        ]
    )

    assert result == 0
    assert "value = 42" in capsys.readouterr().out


def test_search_displays_matches(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "a.py").write_text(
        "def main():\n    pass\n",
        encoding="utf-8",
    )

    result = cli.main(
        [
            "search",
            "--project",
            str(tmp_path),
            "--query",
            "def main",
        ]
    )

    assert result == 0
    assert "a.py:1: def main():" in capsys.readouterr().out


# ==========================================================
# Day 03：模型问答
# ==========================================================


def test_ask_uses_fake_model(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = ModelSettings(
        api_key="test-key",
        model_name="test-model",
        base_url="https://example.com/v1",
    )

    fake_model = FakeListChatModel(responses=["这是来自假模型的回答"])

    monkeypatch.setattr(
        cli,
        "load_model_settings",
        lambda: settings,
    )
    monkeypatch.setattr(
        cli,
        "create_chat_model",
        lambda _settings: fake_model,
    )

    result = cli.main(
        [
            "ask",
            "--question",
            "你好",
        ]
    )

    assert result == 0
    assert "这是来自假模型的回答" in capsys.readouterr().out


def test_ask_requires_question() -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["ask"])

    assert exc_info.value.code == 2


def test_ask_reports_missing_config(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def broken_settings() -> ModelSettings:
        raise ModelConfigError("缺少 API Key")

    monkeypatch.setattr(
        cli,
        "load_model_settings",
        broken_settings,
    )

    with pytest.raises(SystemExit) as exc_info:
        cli.main(
            [
                "ask",
                "--question",
                "你好",
            ]
        )

    assert exc_info.value.code == 2
    assert "缺少 API Key" in capsys.readouterr().err


# ==========================================================
# Day 04：结构化任务规划
# ==========================================================


def test_plan_outputs_structured_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = ModelSettings(
        api_key="test-key",
        model_name="test-model",
        base_url="https://example.com/v1",
    )

    expected_plan = DevelopmentPlan(
        goal="增加用户登录功能",
        steps=[
            PlanStep(
                title="检查项目",
                action="了解现有代码结构",
                verification="确认认证相关文件",
            ),
            PlanStep(
                title="实现功能",
                action="编写登录接口",
                verification="运行 pytest",
            ),
        ],
    )

    monkeypatch.setattr(
        cli,
        "load_model_settings",
        lambda: settings,
    )
    monkeypatch.setattr(
        cli,
        "create_chat_model",
        lambda _settings: object(),
    )
    monkeypatch.setattr(
        cli,
        "generate_development_plan",
        lambda _model, _task: expected_plan,
    )

    result = cli.main(
        [
            "plan",
            "--task",
            "增加用户登录功能",
        ]
    )

    assert result == 0

    output = json.loads(capsys.readouterr().out)

    assert output["goal"] == "增加用户登录功能"
    assert len(output["steps"]) == 2
    assert output["steps"][1]["verification"] == "运行 pytest"


def test_plan_requires_task() -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["plan"])

    assert exc_info.value.code == 2


def test_plan_reports_structured_output_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = ModelSettings(
        api_key="test-key",
        model_name="test-model",
        base_url="https://example.com/v1",
    )

    def broken_plan(_model: object, _task: str) -> None:
        raise PlanningError("模型没有返回开发计划")

    monkeypatch.setattr(
        cli,
        "load_model_settings",
        lambda: settings,
    )
    monkeypatch.setattr(
        cli,
        "create_chat_model",
        lambda _settings: object(),
    )
    monkeypatch.setattr(
        cli,
        "generate_development_plan",
        broken_plan,
    )

    result = cli.main(
        [
            "plan",
            "--task",
            "增加用户登录功能",
        ]
    )

    assert result == 1
    assert "结构化生成失败" in capsys.readouterr().err


# ==========================================================
# Day 05：Interactive CLI
# ==========================================================


def test_chat_command_builds_agent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = ModelSettings(
        api_key="test-key",
        model_name="test-model",
        base_url="https://example.com/v1",
    )

    fake_model = object()
    fake_agent = object()
    captured = {}

    def fake_build_agent(
        model: object,
        project: Path,
    ) -> object:
        captured["model"] = model
        captured["project"] = project
        return fake_agent

    def fake_session(
        agent: object,
        project: Path,
    ) -> int:
        captured["agent"] = agent
        captured["session_project"] = project
        return 0

    monkeypatch.setattr(
        cli,
        "load_model_settings",
        lambda: settings,
    )
    monkeypatch.setattr(
        cli,
        "create_chat_model",
        lambda _settings: fake_model,
    )
    monkeypatch.setattr(
        cli,
        "build_development_agent",
        fake_build_agent,
    )
    monkeypatch.setattr(
        cli,
        "run_chat_session",
        fake_session,
    )

    result = cli.main(
        [
            "chat",
            "--project",
            str(tmp_path),
        ]
    )

    assert result == 0
    assert captured["model"] is fake_model
    assert captured["agent"] is fake_agent
    assert captured["project"] == tmp_path
    assert captured["session_project"] == tmp_path


def test_chat_preserves_history_and_shows_tool(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    inputs = iter(
        [
            "读取 demo.py",
            "继续解释这个函数",
            "/exit",
        ]
    )

    monkeypatch.setattr(
        "builtins.input",
        lambda _prompt: next(inputs),
    )

    observed = []

    def fake_run_turn(
        _agent: object,
        history: list,
        question: str,
    ) -> tuple[str, list]:
        observed.append((question, len(history)))

        if question == "读取 demo.py":
            new_messages = [
                HumanMessage(content=question),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "read_repository_file",
                            "args": {"path": "demo.py"},
                            "id": "call-1",
                            "type": "tool_call",
                        }
                    ],
                ),
                ToolMessage(
                    content="def greet(): return 'hello'",
                    tool_call_id="call-1",
                    name="read_repository_file",
                ),
                AIMessage(content="已读取 demo.py"),
            ]
            return "已读取 demo.py", history + new_messages

        new_messages = [
            HumanMessage(content=question),
            AIMessage(content="这个函数返回 hello"),
        ]
        return "这个函数返回 hello", history + new_messages

    monkeypatch.setattr(
        cli,
        "run_agent_turn",
        fake_run_turn,
    )

    result = cli.run_chat_session(object(), tmp_path)
    output = capsys.readouterr().out

    assert result == 0
    assert observed == [
        ("读取 demo.py", 0),
        ("继续解释这个函数", 4),
    ]

    assert "[工具返回] read_repository_file" in output
    assert "这个函数返回 hello" in output


def test_chat_new_clears_history(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    inputs = iter(
        [
            "第一个问题",
            "/new",
            "第二个问题",
            "/exit",
        ]
    )

    monkeypatch.setattr(
        "builtins.input",
        lambda _prompt: next(inputs),
    )

    history_lengths = []

    def fake_run_turn(
        _agent: object,
        history: list,
        question: str,
    ) -> tuple[str, list]:
        history_lengths.append(len(history))

        updated = history + [
            HumanMessage(content=question),
            AIMessage(content="测试回答"),
        ]
        return "测试回答", updated

    monkeypatch.setattr(
        cli,
        "run_agent_turn",
        fake_run_turn,
    )

    result = cli.run_chat_session(object(), tmp_path)

    assert result == 0
    assert history_lengths == [0, 0]
    assert "已清空当前对话历史" in capsys.readouterr().out


def test_chat_help_and_unknown_command(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    inputs = iter(
        [
            "   ",
            "/help",
            "/unknown",
            "/exit",
        ]
    )

    monkeypatch.setattr(
        "builtins.input",
        lambda _prompt: next(inputs),
    )

    def unexpected_agent_call(
        _agent: object,
        _history: list,
        _question: str,
    ) -> None:
        raise AssertionError("不应该调用 Agent")

    monkeypatch.setattr(
        cli,
        "run_agent_turn",
        unexpected_agent_call,
    )

    result = cli.run_chat_session(object(), tmp_path)
    output = capsys.readouterr().out

    assert result == 0
    assert "/help" in output
    assert "/new" in output
    assert "/exit" in output
    assert "未知命令" in output


def test_chat_keeps_running_after_agent_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    inputs = iter(
        [
            "这次失败",
            "这次成功",
            "/exit",
        ]
    )

    monkeypatch.setattr(
        "builtins.input",
        lambda _prompt: next(inputs),
    )

    history_lengths = []

    def fake_run_turn(
        _agent: object,
        history: list,
        question: str,
    ) -> tuple[str, list]:
        history_lengths.append(len(history))

        if question == "这次失败":
            raise AgentExecutionError("模拟执行失败")

        updated = history + [
            HumanMessage(content=question),
            AIMessage(content="成功回答"),
        ]
        return "成功回答", updated

    monkeypatch.setattr(
        cli,
        "run_agent_turn",
        fake_run_turn,
    )

    result = cli.run_chat_session(object(), tmp_path)
    captured = capsys.readouterr()

    assert result == 0
    assert history_lengths == [0, 0]
    assert "模拟执行失败" in captured.err
    assert "成功回答" in captured.out


def test_chat_exits_on_eof(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def raise_eof(_prompt: str) -> str:
        raise EOFError

    monkeypatch.setattr(
        "builtins.input",
        raise_eof,
    )

    result = cli.run_chat_session(object(), tmp_path)

    assert result == 0
    assert "再见" in capsys.readouterr().out


# ==========================================================
# Day 06：File Editing & Git Diff
# ==========================================================


def test_edit_applies_after_exact_confirmation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target = tmp_path / "demo.py"
    target.write_text(
        "def add(a, b):\n    return a+b\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "builtins.input",
        lambda _prompt: "yes",
    )

    result = cli.main(
        [
            "edit",
            "--project",
            str(tmp_path),
            "--path",
            "demo.py",
            "--old",
            "return a+b",
            "--new",
            "return a + b",
        ]
    )

    output = capsys.readouterr().out

    assert result == 0
    assert "修改预览" in output
    assert "-    return a+b" in output
    assert "+    return a + b" in output
    assert "修改完成" in output

    assert target.read_text(encoding="utf-8") == ("def add(a, b):\n    return a + b\n")


@pytest.mark.parametrize(
    "confirmation",
    ["", "no", "YES"],
)
def test_edit_cancels_without_exact_yes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    confirmation: str,
) -> None:
    target = tmp_path / "demo.py"
    target.write_text(
        "value = 1\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "builtins.input",
        lambda _prompt: confirmation,
    )

    result = cli.main(
        [
            "edit",
            "--project",
            str(tmp_path),
            "--path",
            "demo.py",
            "--old",
            "value = 1",
            "--new",
            "value = 2",
        ]
    )

    output = capsys.readouterr().out

    assert result == 0
    assert "修改预览" in output
    assert "已取消修改" in output
    assert target.read_text(encoding="utf-8") == "value = 1\n"


def test_edit_rejects_unmatched_content(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target = tmp_path / "demo.py"
    target.write_text(
        "value = 1\n",
        encoding="utf-8",
    )

    result = cli.main(
        [
            "edit",
            "--project",
            str(tmp_path),
            "--path",
            "demo.py",
            "--old",
            "value = 999",
            "--new",
            "value = 2",
        ]
    )

    captured = capsys.readouterr()

    assert result == 1
    assert "实际匹配 0 次" in captured.err
    assert target.read_text(encoding="utf-8") == "value = 1\n"


def test_edit_rejects_unsafe_path(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = cli.main(
        [
            "edit",
            "--project",
            str(tmp_path),
            "--path",
            "../outside.py",
            "--old",
            "old",
            "--new",
            "new",
        ]
    )

    assert result == 1
    assert "无法生成修改预览" in capsys.readouterr().err


def test_edit_rejects_stale_preview(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target = tmp_path / "demo.py"
    target.write_text(
        "value = 1\n",
        encoding="utf-8",
    )

    def change_file_before_confirmation(_prompt: str) -> str:
        target.write_text(
            "value = 99\n",
            encoding="utf-8",
        )
        return "yes"

    monkeypatch.setattr(
        "builtins.input",
        change_file_before_confirmation,
    )

    result = cli.main(
        [
            "edit",
            "--project",
            str(tmp_path),
            "--path",
            "demo.py",
            "--old",
            "value = 1",
            "--new",
            "value = 2",
        ]
    )

    captured = capsys.readouterr()

    assert result == 1
    assert "文件在预览后已发生变化" in captured.err
    assert target.read_text(encoding="utf-8") == "value = 99\n"


def test_edit_cancels_on_eof(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target = tmp_path / "demo.py"
    target.write_text(
        "value = 1\n",
        encoding="utf-8",
    )

    def raise_eof(_prompt: str) -> str:
        raise EOFError

    monkeypatch.setattr(
        "builtins.input",
        raise_eof,
    )

    result = cli.main(
        [
            "edit",
            "--project",
            str(tmp_path),
            "--path",
            "demo.py",
            "--old",
            "value = 1",
            "--new",
            "value = 2",
        ]
    )

    assert result == 0
    assert target.read_text(encoding="utf-8") == "value = 1\n"
    assert "已取消修改" in capsys.readouterr().out


@pytest.mark.parametrize(
    "arguments",
    [
        ["--path", "demo.py", "--new", "changed"],
        ["--path", "demo.py", "--old", "original"],
    ],
)
def test_edit_requires_old_and_new_arguments(
    tmp_path: Path,
    arguments: list[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main(
            [
                "edit",
                "--project",
                str(tmp_path),
                *arguments,
            ]
        )

    assert exc_info.value.code == 2


def test_edit_help_displays_arguments(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["edit", "--help"])

    assert exc_info.value.code == 0

    output = capsys.readouterr().out

    assert "--project" in output
    assert "--path" in output
    assert "--old" in output
    assert "--new" in output


# ==========================================================
# Day 07：Test Runner CLI
# ==========================================================


@pytest.fixture
def pytest_demo(tmp_path: Path) -> Path:
    """准备一个用于 CLI 集成测试的临时仓库。"""

    (tmp_path / "tests").mkdir()
    return tmp_path


def write_demo_test(
    project: Path,
    filename: str,
    source: str,
) -> None:
    """创建临时 pytest 测试文件。"""

    (project / "tests" / filename).write_text(
        source,
        encoding="utf-8",
    )


def test_test_command_reports_passed(
    pytest_demo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """CLI 应正确展示成功测试的状态与退出码。"""

    write_demo_test(
        pytest_demo,
        "test_success.py",
        "def test_success():\n    assert 2 + 2 == 4\n",
    )

    result = cli.main(
        [
            "test",
            "--project",
            str(pytest_demo),
        ]
    )

    output = capsys.readouterr().out

    assert result == 0
    assert "测试状态：passed（通过）" in output
    assert "pytest 退出码：0" in output
    assert "执行耗时：" in output
    assert "1 passed" in output


def test_test_command_reports_failed(
    pytest_demo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """测试断言失败时，CLI 应返回非零退出码。"""

    write_demo_test(
        pytest_demo,
        "test_failure.py",
        "def test_failure():\n    assert 1 == 2\n",
    )

    result = cli.main(
        [
            "test",
            "--project",
            str(pytest_demo),
        ]
    )

    output = capsys.readouterr().out

    assert result == 1
    assert "测试状态：failed（测试失败）" in output
    assert "pytest 退出码：1" in output
    assert "1 failed" in output


def test_test_command_reports_no_tests(
    pytest_demo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """没有收集到测试不应该返回成功。"""

    result = cli.main(
        [
            "test",
            "--project",
            str(pytest_demo),
        ]
    )

    output = capsys.readouterr().out

    assert result == 1
    assert "测试状态：no_tests（未发现测试）" in output
    assert "pytest 退出码：5" in output


def test_test_command_runs_specific_file(
    pytest_demo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """指定单个测试文件时不运行其他失败测试。"""

    write_demo_test(
        pytest_demo,
        "test_success.py",
        "def test_success():\n    assert True\n",
    )

    write_demo_test(
        pytest_demo,
        "test_failure.py",
        "def test_failure():\n    assert False\n",
    )

    result = cli.main(
        [
            "test",
            "--project",
            str(pytest_demo),
            "--target",
            "tests/test_success.py",
            "--timeout",
            "30",
        ]
    )

    output = capsys.readouterr().out

    assert result == 0
    assert "1 passed" in output
    assert "测试状态：passed" in output


def test_test_command_rejects_unsafe_target(
    pytest_demo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """不允许通过 CLI 指定 tests 目录以外的目标。"""

    result = cli.main(
        [
            "test",
            "--project",
            str(pytest_demo),
            "--target",
            "../outside.py",
        ]
    )

    captured = capsys.readouterr()

    assert result == 2
    assert "测试参数或目标错误" in captured.err


def test_test_command_rejects_invalid_timeout(
    pytest_demo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """超时时间超出范围时不能启动 pytest。"""

    result = cli.main(
        [
            "test",
            "--project",
            str(pytest_demo),
            "--timeout",
            "121",
        ]
    )

    captured = capsys.readouterr()

    assert result == 2
    assert "超时时间" in captured.err


def test_test_command_reports_timeout(
    pytest_demo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """测试执行超时时，CLI 应显示超时状态。"""

    def fake_run(
        _self: object,
        target: str,
        timeout_seconds: int,
    ) -> RunnerResult:
        return RunnerResult(
            status="timeout",
            exit_code=None,
            stdout="已收集部分测试输出",
            stderr="模拟执行超时",
            duration_seconds=2.0,
            command=("python", "-m", "pytest", target),
        )

    monkeypatch.setattr(
        cli.TestRunner,
        "run",
        fake_run,
    )

    result = cli.main(
        [
            "test",
            "--project",
            str(pytest_demo),
            "--timeout",
            "2",
        ]
    )

    captured = capsys.readouterr()

    assert result == 1
    assert "测试状态：timeout（执行超时）" in captured.out
    assert "pytest 退出码：无" in captured.out
    assert "执行耗时：2.00 秒" in captured.out
    assert "已收集部分测试输出" in captured.out
    assert "模拟执行超时" in captured.err


def test_test_command_reports_execution_error(
    pytest_demo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """测试子进程无法运行时，CLI 应展示错误。"""

    def fake_run(
        _self: object,
        target: str,
        timeout_seconds: int,
    ) -> RunnerResult:
        return RunnerResult(
            status="error",
            exit_code=None,
            stdout="",
            stderr="模拟子进程启动失败",
            duration_seconds=0.1,
            command=("python", "-m", "pytest", target),
        )

    monkeypatch.setattr(
        cli.TestRunner,
        "run",
        fake_run,
    )

    result = cli.main(
        [
            "test",
            "--project",
            str(pytest_demo),
        ]
    )

    captured = capsys.readouterr()

    assert result == 1
    assert "测试状态：error（执行错误）" in captured.out
    assert "模拟子进程启动失败" in captured.err


def test_test_command_help_displays_options(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """test 帮助信息应列出目标与超时参数。"""

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["test", "--help"])

    assert exc_info.value.code == 0

    output = capsys.readouterr().out

    assert "--project" in output
    assert "--target" in output
    assert "--timeout" in output
```

### 10.3 CLI 测试重点

本阶段新增九项测试：

| 测试 | 验证目标 |
|---|---|
| 测试通过 | 返回 CLI 退出码 `0` |
| 测试失败 | 返回 CLI 退出码 `1` |
| 没有测试 | 返回 `no_tests` |
| 指定测试文件 | 只执行对应文件 |
| 非法路径 | 返回 CLI 退出码 `2` |
| 非法超时值 | 拒绝执行 |
| 执行超时 | 展示 `timeout` 状态 |
| 进程错误 | 展示 `error` 状态 |
| 帮助命令 | 包含全部参数 |

这里将：

```python
TestRunResult as RunnerResult
```

用于避免再次出现测试类名称误收集的 Warning。

---

## 11. 自动化测试执行与结果

### 11.1 第一阶段测试

```bash
python -m pytest tests/test_test_runner.py -v
```

用户确认：

- 测试通过。
- 曾出现两条 `PytestCollectionWarning`。
- 采用导入别名修复后，Warning 消失。
- 再次运行测试仍然通过。

### 11.2 第二阶段 CLI 测试

```bash
python -m pytest tests/test_cli.py -v
```

结果：通过。

### 11.3 联合测试

```bash
python -m pytest \
  tests/test_test_runner.py \
  tests/test_cli.py \
  -v
```

结果：通过。

### 11.4 完整回归测试

```bash
python -m pytest -v
```

结果：通过。

按照此前课程测试数量：

```text
Day 06：75 项
Day 07 第一阶段：新增 21 项
Day 07 第二阶段：新增 9 项
```

预计总计：

```text
105 passed
```

用户已确认全部测试通过，但没有提供完整终端统计行，因此这里将 105 项记为按测试设计推算的数量，而不是虚构的终端原始输出。

---

## 12. 正式 CLI 验收

### 12.1 检查帮助命令

执行：

```bash
ai-dev-agent --help

ai-dev-agent test --help
```

当前 CLI 包含九个子命令：

```text
doctor
inspect
read
search
ask
plan
chat
edit
test
```

结果：通过。

### 12.2 创建独立测试仓库

先创建临时项目目录：

```bash
DEMO_DIR="$(mktemp -d)"
```

创建测试目录：

```bash
mkdir -p "$DEMO_DIR/tests"
```

创建正常测试文件：

```bash
cat > "$DEMO_DIR/tests/test_math.py" <<'PY'
def test_add():
    assert 1 + 1 == 2


def test_multiply():
    assert 2 * 3 == 6
PY
```

检查：

```bash
cat "$DEMO_DIR/tests/test_math.py"
```

### 12.3 实验一：正常执行

```bash
ai-dev-agent test \
  --project "$DEMO_DIR" \
  --timeout 30
```

预期：

```text
测试状态：passed（通过）
pytest 退出码：0
执行耗时：...

=== pytest 标准输出 ===
2 passed in ...
```

随后立即执行：

```bash
echo $?
```

预期：

```text
0
```

实际结果：通过。

### 12.4 实验二：指定测试文件

```bash
ai-dev-agent test \
  --project "$DEMO_DIR" \
  --target tests/test_math.py \
  --timeout 30
```

预期：两个测试通过。

实际结果：通过。

### 12.5 实验三：测试失败

创建失败测试文件：

```bash
cat > "$DEMO_DIR/tests/test_failure.py" <<'PY'
def test_failure():
    assert 1 == 2
PY
```

执行：

```bash
ai-dev-agent test \
  --project "$DEMO_DIR"
```

预期包含：

```text
测试状态：failed（测试失败）
pytest 退出码：1
```

终端汇总包含一个失败测试和两个通过测试。

紧接着：

```bash
echo $?
```

预期：

```text
1
```

实际结果：通过。

### 12.6 实验四：指定单个正常测试文件

即使项目中存在失败测试，也可以只运行：

```bash
ai-dev-agent test \
  --project "$DEMO_DIR" \
  --target tests/test_math.py
```

预期：返回 `passed`。

实际结果：通过。

### 12.7 实验五：没有测试

创建独立的空测试项目：

```bash
mkdir -p "$DEMO_DIR/empty-project/tests"
```

执行：

```bash
ai-dev-agent test \
  --project "$DEMO_DIR/empty-project"
```

预期：

```text
测试状态：no_tests（未发现测试）
pytest 退出码：5
```

CLI 最终返回：

```text
1
```

实际结果：通过。

### 12.8 实验六：非法路径

执行：

```bash
ai-dev-agent test \
  --project "$DEMO_DIR" \
  --target ../outside.py
```

预期：拒绝执行，CLI 返回退出码 `2`。

实际结果：通过。

### 12.9 清理临时项目

完成实验后，在创建 `DEMO_DIR` 的同一个终端执行：

```bash
test -n "${DEMO_DIR:-}" && test -d "$DEMO_DIR" && rm -r "$DEMO_DIR"
```

只删除本次创建的临时实验目录。

---

## 13. 本日测试与调试经验

### 13.1 正常测试与异常测试同样重要

对于 Test Runner，至少要覆盖：

```text
测试通过
测试失败
没有测试
进程启动失败
测试超时
非法输入
非法路径
```

不能只验证 pytest 成功时的情况。

### 13.2 测试失败不能直接当作程序异常

```python
result.status == "failed"
```

表示 pytest 正常执行，但有断言不通过。

而：

```python
result.status == "error"
```

表示测试执行过程中出现其他错误。

区分这两类结果，后续才能制定不同的处理策略。

### 13.3 CLI 应传递失败状态

例如：

```python
return 0 if result.passed else 1
```

这是为后续工作流做准备。

以后可以建立：

```text
修改代码
    ↓
运行测试
    ↓
测试通过？
   ├── 是 → 继续下一阶段
   └── 否 → 收集错误并决定是否修复
```

如果 CLI 不返回非零退出码，后续工作流就难以可靠识别测试失败。

### 13.4 为什么测试全部通过仍可能有 Warning？

pytest 的测试结果和警告是两种信息。

例如：

```text
105 passed, 2 warnings
```

表示测试断言全部通过，但执行过程存在值得注意的警告。

不应因为测试通过就忽略所有 Warning。

本日通过修复导入别名解决了已知的两条 Warning，而不是直接屏蔽全部警告。

---

## 14. 当前 Test Runner 的安全边界

本日做了以下约束：

- 只运行 pytest。
- 固定命令参数格式。
- 使用 `shell=False`。
- 只允许选择 `tests/` 目录内的目标。
- 不允许用户直接提供任意 pytest 选项。
- 拒绝路径中的符号链接。
- 设置最大超时。
- 不从交互终端读取子进程输入。

但是，以下能力尚未实现：

1. 容器沙箱。
2. 网络隔离。
3. 文件系统写入隔离。
4. CPU 和内存限制。
5. 对全部子进程树进行可靠清理。
6. 不可信 pytest 插件的完整隔离。
7. 跨项目 Python 解释器自动选择。
8. 测试输出的流式读取和实时展示。
9. 持久化测试执行记录。
10. 自动执行 Ruff 并生成统一质量报告。

特别重要：

**pytest 执行的是 Python 代码，路径检查和 `shell=False` 不能把不可信测试变成安全测试。**

当前版本用于自己信任的本地项目。

---

## 15. Day 01～Day 07 能力演进

```text
Day 01：项目初始化与 CLI
           ↓
Day 02：RepositoryExplorer
           ↓
Day 03：LangChain Chat Model
           ↓
Day 04：Tools + Structured Planning
           ↓
Day 05：Agent Loop + Interactive CLI
           ↓
Day 06：CodeEditor + Patch + Git Diff
           ↓
Day 07：TestRunner + pytest CLI
```

目前项目已经拥有：

- 代码仓库探索。
- 模型普通问答。
- 结构化开发计划。
- Agent 自动调用只读工具。
- 多轮交互式 CLI。
- 安全文件修改和差异预览。
- pytest 测试执行器。
- 测试状态、退出码、耗时与输出收集。

但这些能力仍然是相对独立的模块。

例如，当前 Agent 还不会自动完成：

```text
读取任务
   ↓
制定计划
   ↓
修改文件
   ↓
运行测试
   ↓
分析失败
   ↓
继续修复
```

后续需要通过 LangGraph 工作流与受控工具调用，将已有模块组织成完整的软件开发流程。

---

## 16. 今日最重要的五个知识点

### 第一：`subprocess.run()` 用于启动并管理子进程

不是在当前 Python 函数内部直接调用 pytest，而是启动一个独立的 pytest 进程。

### 第二：退出码是判断执行结果的重要依据

不要只依赖终端输出中的文字。

通过 `returncode` 可以区分测试通过、测试失败、没有测试和其他错误。

### 第三：`time.perf_counter()` 用于准确计算经过时间

它是性能计数器，不是日期时间戳。

通过结束值减去开始值，得到程序实际执行耗时。

### 第四：`Path.as_posix()` 用于统一路径字符串格式

它将 `Path` 转换为使用 `/` 的字符串，不会自动转换成绝对路径，也不提供安全校验。

### 第五：一个可用的 Test Runner 不只是运行 pytest

还应该具备：

```text
输入检查
    ↓
路径验证
    ↓
超时限制
    ↓
启动子进程
    ↓
收集结果
    ↓
状态分类
    ↓
向调用方返回成功或失败
```

---

## 17. 最终学习总结

Day 07 实现的核心，是把原本需要人工执行的 pytest 测试命令，封装成一个可复用、可检查结果的 Python 组件。

最终形成：

```text
TestRunner
    ├── 校验项目
    ├── 校验测试目标
    ├── 校验超时时间
    ├── 运行 pytest 子进程
    ├── 处理超时及执行错误
    ├── 获取 stdout、stderr 和 returncode
    └── 返回 TestRunResult
```

以及：

```text
ai-dev-agent test
    ↓
TestRunner.run()
    ↓
pytest 子进程
    ↓
TestRunResult
    ↓
CLI 展示状态、退出码和耗时
```

本日最重要的工程思想是：

> 对于软件开发 Agent，测试不是一段给人看的终端输出，而应该是一个具有明确状态、退出码、错误信息和执行时间的结构化结果。

这为后续的代码修改、测试验证和自动修复工作流提供了基础。

