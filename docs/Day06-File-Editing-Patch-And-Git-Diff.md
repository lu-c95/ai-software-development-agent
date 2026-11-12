# Day 06 — File Editing, Patch & Git Diff（文件修改、补丁与差异检查）

## 1. 当天目标与完成成果

### 1.1 学习目标

Day 05 已经实现了可以读取代码仓库的 LangChain Agent（智能体）。

Day 06 的目标是在不破坏原有功能的前提下，增加**安全修改代码文件**的基础能力。

具体目标：

1. 理解 File Editing（文件编辑）、Patch（补丁）、Diff（差异）与 Git Diff。
2. 实现受约束的 Python 文件编辑组件。
3. 在修改前生成 Unified Diff（统一差异格式）。
4. 使用 SHA-256 检查文件是否在预览后发生变化。
5. 使用临时文件和 `os.replace()` 实现原子替换。
6. 为 CLI 增加 `edit` 子命令。
7. 修改文件前要求用户明确输入 `yes`。
8. 编写 pytest 自动化测试。
9. 使用独立 Git 仓库验收真实修改。

### 1.2 完成成果

本日已完成：

- 新增 `CodeEditor` 类。
- 实现精确文本替换。
- 实现只读修改预览。
- 实现文件版本检查。
- 限制可编辑的文件路径和类型。
- 实现受控文件写入。
- 新增 `ai-dev-agent edit` 命令。
- 实现人工确认与取消。
- 通过自动化测试。
- 通过正式 CLI 和 Git Diff 验收。

**当前文件修改能力由用户通过 CLI 主动触发，尚未作为工具交给 AI Agent 自动调用。**

---

## 2. 项目环境与文件结构

### 2.1 进入项目

执行：

```bash
cd "/Users/lc/Documents/公子路的长期成长计划/02-AI-Agent-Engineering/ai-software-development-agent"
```

激活虚拟环境：

```bash
source .venv/bin/activate
```

验证：

```bash
which python
which python3

python --version

python -c 'import sys; print(sys.executable)'
```

检查 Python 路径是否属于当前项目的 `.venv`。

### 2.2 文件变化

本日新增和修改的文件：

```text
ai-software-development-agent/
├── src/
│   └── ai_software_dev_agent/
│       ├── agent.py
│       ├── cli.py              # 修改：新增 edit 命令
│       ├── editor.py           # 新增：代码安全编辑组件
│       ├── model.py
│       ├── planning.py
│       ├── repository.py
│       └── tools.py
├── tests/
│   ├── test_agent.py
│   ├── test_cli.py             # 修改：增加编辑命令测试
│   ├── test_editor.py          # 新增：文件修改测试
│   ├── test_model.py
│   ├── test_planning.py
│   ├── test_repository.py
│   └── test_tools.py
├── docs/
│   └── Day06-File-Editing-Patch-And-Git-Diff.md
└── pyproject.toml
```

本日涉及四个 Python 文件：

| 文件 | 类型 | 职责 |
|---|---|---|
| `editor.py` | 新增 | 预览、验证、应用文件修改 |
| `test_editor.py` | 新增 | 编辑器单元测试 |
| `cli.py` | 修改 | 增加 `edit` 命令 |
| `test_cli.py` | 修改 | 增加 CLI 编辑测试 |

继续复用 Day 02 的 `RepositoryExplorer`。

本日使用 Python 标准库和项目现有依赖，无需新增第三方依赖。

---

## 3. 基础概念：File Editing、Patch 与 Diff

### 3.1 File Editing（文件编辑）

最直接的 Python 文件修改方法：

```python
from pathlib import Path

path = Path("demo.py")

content = path.read_text(encoding="utf-8")

updated = content.replace(
    "return a+b",
    "return a + b",
)

path.write_text(updated, encoding="utf-8")
```

虽然简单，但有几个问题：

1. 如果相同代码出现多次，可能修改多个位置。
2. 如果路径不安全，可能修改仓库之外的文件。
3. 如果文件已被其他程序改变，可能覆盖新的内容。
4. 修改前没有展示具体差异。
5. 写入失败时可能产生不完整文件。

因此本日没有直接使用这种方式，而是设计一个独立的 `CodeEditor`。

### 3.2 Patch（补丁）

Patch 描述需要怎样修改文件。

本日采用的是**精确文本替换**：

```text
目标文件：demo.py

旧内容：
return a+b

新内容：
return a + b
```

这可以理解为一种简单的补丁操作。

它不同于完整的 Unified Diff Patch 或 Git Patch：本日没有实现多文件补丁、补丁格式解析、上下文定位或自动合并。

### 3.3 Diff（差异）

假设原代码：

```python
def add(a, b):
    return a + b
```

修改后：

```python
def add(a, b):
    return a + b
```

Unified Diff 表示为：

```diff
--- a/demo.py
+++ b/demo.py
@@ -1,2 +1,2 @@
 def add(a, b):
-    return a+b
+    return a + b
```

含义：

| 标记 | 作用 |
|---|---|
| `---` | 原文件 |
| `+++` | 修改后的文件 |
| `@@` | 差异所在行范围 |
| `-` | 删除的原内容 |
| `+` | 新增的内容 |
| 普通上下文行 | 帮助理解修改位置 |

本日使用：

```python
difflib.unified_diff(...)
```

来生成预览。

### 3.4 Git Diff

`git diff` 主要用于比较 Git 中不同状态或版本之间的差异。

例如：

```bash
git diff -- demo.py
```

通常查看工作区相对于暂存区的变化。

如果文件已经暂存：

```bash
git diff --cached -- demo.py
```

查看暂存内容相对于 `HEAD` 的变化。

本日先建立独立 Git 基准版本，再使用 `git diff` 验证文件修改的实际结果。

### 3.5 本日整体流程

```text
用户指定文件与替换内容
           ↓
检查路径和文件
           ↓
读取原文件
           ↓
检查旧代码是否恰好匹配一次
           ↓
生成新内容
           ↓
计算 SHA-256
           ↓
生成 Unified Diff
           ↓
展示预览
           ↓
用户输入 yes？
      ┌────┴────┐
      否        是
      ↓         ↓
    取消     再次检查文件
                ↓
            原子替换
                ↓
             Git Diff
```

---

## 4. 第一阶段：实现 CodeEditor

### 4.1 创建 `editor.py`

在项目根目录执行：

```bash
touch src/ai_software_dev_agent/editor.py
```

打开文件：

```bash
nano src/ai_software_dev_agent/editor.py
```

也可以使用 IDE 编辑。

### 4.2 `editor.py` 完整代码

文件：`src/ai_software_dev_agent/editor.py`

```python
"""安全预览并应用代码文件的文本修改。"""

import difflib
import hashlib
import os
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path

from ai_software_dev_agent.repository import RepositoryExplorer


MAX_FILE_BYTES = 256 * 1024


class FileEditError(ValueError):
    """文件修改不符合安全约束或应用条件。"""


@dataclass(frozen=True)
class EditPreview:
    """一次准备好的文件修改方案。"""

    path: str
    old_text: str
    new_text: str
    original_sha256: str
    diff: str


class CodeEditor:
    """为指定仓库提供受约束的代码修改能力。"""

    def __init__(self, project: Path) -> None:
        # 复用 Day 02 的仓库检查与只读访问能力。
        self.explorer = RepositoryExplorer(project)
        self.root = Path(self.explorer.root).resolve()

    def _resolve_target(self, file_path: str) -> Path:
        """检查路径是否属于仓库内允许修改的 Python 文件。"""

        relative = Path(file_path)

        if not file_path.strip() or relative.is_absolute() or ".." in relative.parts:
            raise FileEditError("必须提供仓库内的相对文件路径")

        # 第一版禁止访问隐藏目录、隐藏文件和非 Python 文件。
        if (
            any(part.startswith(".") for part in relative.parts)
            or relative.suffix != ".py"
        ):
            raise FileEditError("当前仅允许修改非隐藏目录中的 .py 文件")

        target = self.root

        # 拒绝路径任一组成部分为符号链接。
        for part in relative.parts:
            target = target / part

            if target.is_symlink():
                raise FileEditError("不允许通过符号链接修改文件")

        resolved = target.resolve()

        if not resolved.is_relative_to(self.root):
            raise FileEditError("目标文件超出仓库根目录")

        if not resolved.is_file():
            raise FileEditError("目标文件不存在或不是普通文件")

        # 继续经过已有的 RepositoryExplorer 读取限制。
        self.explorer.read_file(relative.as_posix())

        return resolved

    def _read_file(self, file_path: str) -> tuple[Path, bytes, str]:
        """读取原始字节，避免意外改变文件换行符。"""

        target = self._resolve_target(file_path)
        data = target.read_bytes()

        if len(data) > MAX_FILE_BYTES:
            raise FileEditError("文件大小超过允许的限制")

        if b"\x00" in data:
            raise FileEditError("不允许修改二进制文件")

        try:
            content = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise FileEditError("仅支持 UTF-8 编码的文本文件") from exc

        return target, data, content

    @staticmethod
    def _make_diff(path: str, before: str, after: str) -> str:
        """生成供人审查的 Unified Diff（统一差异格式）。"""

        return "".join(
            difflib.unified_diff(
                before.splitlines(keepends=True),
                after.splitlines(keepends=True),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
            )
        )

    def preview_replace(
        self,
        file_path: str,
        old_text: str,
        new_text: str,
    ) -> EditPreview:
        """预览一次精确替换，不修改磁盘文件。"""

        if not old_text:
            raise FileEditError("旧代码片段不能为空")

        if old_text == new_text:
            raise FileEditError("新旧代码相同，没有实际修改")

        relative_path = Path(file_path).as_posix()
        _, original_bytes, original = self._read_file(relative_path)

        count = original.count(old_text)

        if count != 1:
            raise FileEditError(f"旧代码片段必须恰好匹配一次，实际匹配 {count} 次")

        updated = original.replace(old_text, new_text, 1)

        if len(updated.encode("utf-8")) > MAX_FILE_BYTES:
            raise FileEditError("修改后的文件超过大小限制")

        diff = self._make_diff(relative_path, original, updated)

        return EditPreview(
            path=relative_path,
            old_text=old_text,
            new_text=new_text,
            original_sha256=hashlib.sha256(original_bytes).hexdigest(),
            diff=diff,
        )

    def apply(self, preview: EditPreview) -> None:
        """核对原始版本后，原子替换目标文件。"""

        target, original_bytes, original = self._read_file(preview.path)

        current_sha256 = hashlib.sha256(original_bytes).hexdigest()

        # 防止预览完成后，文件已被其他操作修改。
        if current_sha256 != preview.original_sha256:
            raise FileEditError("文件在预览后已发生变化，请重新生成预览")

        if (
            not preview.old_text
            or preview.old_text == preview.new_text
            or original.count(preview.old_text) != 1
        ):
            raise FileEditError("补丁内容不符合精确替换要求")

        updated = original.replace(
            preview.old_text,
            preview.new_text,
            1,
        )

        updated_bytes = updated.encode("utf-8")

        if len(updated_bytes) > MAX_FILE_BYTES:
            raise FileEditError("修改后的文件超过大小限制")

        # 检查预览对象是否与实际修改内容一致。
        expected_diff = self._make_diff(
            preview.path,
            original,
            updated,
        )

        if expected_diff != preview.diff:
            raise FileEditError("补丁内容与预览差异不一致")

        # 临时文件与目标文件位于同一目录，以便原子替换。
        fd, temp_name = tempfile.mkstemp(
            prefix=".agent-edit-",
            suffix=".tmp",
            dir=target.parent,
        )

        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(updated_bytes)
                stream.flush()
                os.fsync(stream.fileno())

            # 保留原文件的基本权限位。
            original_mode = stat.S_IMODE(target.stat().st_mode)
            os.chmod(temp_name, original_mode)

            # 写回前再次检查是否发生外部修改。
            latest_sha256 = hashlib.sha256(target.read_bytes()).hexdigest()

            if latest_sha256 != preview.original_sha256:
                raise FileEditError("文件在写入前发生变化，已取消修改")

            os.replace(temp_name, target)

        finally:
            # 如果应用失败，清理未完成的临时文件。
            if os.path.exists(temp_name):
                os.unlink(temp_name)
```

---

## 5. `CodeEditor` 核心实现讲解

### 5.1 为什么单独创建 `CodeEditor`？

Day 02 的 `RepositoryExplorer` 主要负责只读操作：

```python
explorer.list_files()
explorer.read_file(...)
explorer.search(...)
```

Day 06 的 `CodeEditor` 负责：

```python
editor.preview_replace(...)
editor.apply(...)
```

两者职责不同。

我们没有将写操作直接塞入原来的只读类，而是新建专门的编辑组件。

好处：

- 职责清楚。
- 方便独立测试。
- 可以单独限制写入权限。
- 后续 Agent 工具可以复用该组件。
- 不会因为增加编辑功能而破坏原有只读接口。

### 5.2 `EditPreview` 为什么使用 Dataclass？

```python
@dataclass(frozen=True)
class EditPreview:
    path: str
    old_text: str
    new_text: str
    original_sha256: str
    diff: str
```

`@dataclass` 可以自动生成初始化方法等常用功能。

`frozen=True` 表示对象创建后，不允许直接重新赋值字段。

例如：

```python
preview.path = "other.py"
```

会报错。

它使预览对象相对稳定，但并不等同于完整的防篡改机制。程序仍可以创建新的预览对象，因此 `apply()` 需要自行校验关键字段。

### 5.3 路径安全检查

```python
relative = Path(file_path)
```

首先将用户输入转换为路径对象。

拒绝：

```python
relative.is_absolute()
```

可以防止用户直接指定仓库外部的绝对路径。

拒绝：

```python
".." in relative.parts
```

可以阻止常见的父目录越界路径。

例如：

```text
../private.py
```

还需要检查：

```python
target.is_symlink()
```

因为符号链接可能指向仓库之外的文件。

最后：

```python
resolved.is_relative_to(self.root)
```

检查解析后的目标是否仍然属于仓库。

本日还限制只允许修改非隐藏路径下的 `.py` 文件。

这是一套基础文件路径安全限制。它不提供对恶意并发改变目录项的完整防护，后续若开放给不可信用户或高权限 Agent，需要更严格的文件系统操作方式。

### 5.4 为什么只允许匹配一次？

```python
count = original.count(old_text)

if count != 1:
    raise FileEditError(...)
```

假设文件中存在：

```python
def first():
    return 1


def second():
    return 1
```

如果用户只要求：

```text
return 1 → return 2
```

程序无法判断究竟要修改哪个函数。

所以我们规定：

- 匹配 0 次：拒绝。
- 匹配 1 次：允许继续。
- 匹配 2 次或更多：拒绝。

这种策略牺牲了一部分灵活性，但减少了初期误修改风险。

### 5.5 为什么需要生成 Diff？

核心代码：

```python
difflib.unified_diff(
    before.splitlines(keepends=True),
    after.splitlines(keepends=True),
    fromfile=f"a/{path}",
    tofile=f"b/{path}",
)
```

`difflib` 是 Python 标准库中的文本差异处理模块。

参数解释：

| 参数 | 作用 |
|---|---|
| `before` | 修改前文本 |
| `after` | 修改后文本 |
| `splitlines(keepends=True)` | 按行拆分，同时保留换行符 |
| `fromfile` | 原文件显示名称 |
| `tofile` | 新文件显示名称 |

生成 Diff 的主要目的是**人工审查修改内容**，并不代表文件已经写入。

### 5.6 SHA-256 与乐观并发控制

预览时：

```python
hashlib.sha256(original_bytes).hexdigest()
```

生成文件的 SHA-256 摘要。

应用时：

```python
current_sha256 = hashlib.sha256(original_bytes).hexdigest()
```

重新计算。

如果两者不相同：

```python
raise FileEditError("文件在预览后已发生变化，请重新生成预览")
```

场景：

```text
10:00 用户预览 demo.py
10:01 其他程序修改 demo.py
10:02 用户确认原来的修改
```

由于文件已经发生变化，旧预览不应直接覆盖新内容。

这是一种简化的 Optimistic Concurrency Control（乐观并发控制）。

其基本思想是：

> 先假设不会发生冲突，到真正写入时再检查版本是否仍然一致。

本日使用的文件 SHA-256 就充当了版本指纹。

它并非完整的文件锁，也不能消除最终检查与替换之间的全部竞争窗口。

### 5.7 为什么使用临时文件？

核心代码：

```python
fd, temp_name = tempfile.mkstemp(
    prefix=".agent-edit-",
    suffix=".tmp",
    dir=target.parent,
)
```

首先在目标文件的同一目录创建临时文件。

然后：

```python
with os.fdopen(fd, "wb") as stream:
    stream.write(updated_bytes)
    stream.flush()
    os.fsync(stream.fileno())
```

将更新内容写入临时文件。

最后：

```python
os.replace(temp_name, target)
```

用临时文件替换目标文件。

相较于直接在目标文件上边写边覆盖，这种方式可以避免普通写入失败导致目标文件只剩部分内容。

在支持原子重命名替换的本地文件系统中，成功的替换操作通常不会暴露半成品文件。

本日实现仍然没有覆盖文件锁、完整元数据继承、断电后目录持久化等所有生产级要求。

### 5.8 为什么保留文件权限？

```python
original_mode = stat.S_IMODE(target.stat().st_mode)

os.chmod(temp_name, original_mode)
```

如果旧文件有特定权限，替换后应尽量保留基本权限位。

不过这里仅保留权限位，没有完整复制扩展属性、ACL 或其他文件系统元数据。

### 5.9 为什么保留原始字节？

```python
data = target.read_bytes()

content = data.decode("utf-8")
```

这样可以避免通过文本模式读取时，意外改变换行符。

例如 Windows 风格换行：

```text
\r\n
```

如果不小心全部转换为：

```text
\n
```

Git Diff 中可能出现大量与业务无关的变更。

本日通过 `read_bytes()` 与 UTF-8 解码保留原始换行格式。

---

## 6. 第一阶段：编写编辑器自动化测试

### 6.1 创建文件

执行：

```bash
touch tests/test_editor.py
```

打开：

```bash
nano tests/test_editor.py
```

### 6.2 `test_editor.py` 完整代码

```python
"""代码修改、Diff 预览与安全写入测试。"""

from dataclasses import replace
from pathlib import Path

import pytest

from ai_software_dev_agent.editor import (
    CodeEditor,
    FileEditError,
)


@pytest.fixture
def sample_file(tmp_path: Path) -> Path:
    """创建每个测试使用的独立 Python 文件。"""

    target = tmp_path / "demo.py"
    target.write_text(
        "def add(a, b):\n    return a+b\n",
        encoding="utf-8",
    )
    return target


def test_preview_does_not_modify_file(
    tmp_path: Path,
    sample_file: Path,
) -> None:
    """预览时只能生成差异，不能修改文件。"""

    editor = CodeEditor(tmp_path)
    before = sample_file.read_bytes()

    preview = editor.preview_replace(
        "demo.py",
        "return a+b",
        "return a + b",
    )

    assert sample_file.read_bytes() == before
    assert preview.path == "demo.py"
    assert "-    return a+b" in preview.diff
    assert "+    return a + b" in preview.diff
    assert "--- a/demo.py" in preview.diff
    assert "+++ b/demo.py" in preview.diff


def test_apply_changes_file(
    tmp_path: Path,
    sample_file: Path,
) -> None:
    """应用补丁后应完成预期替换。"""

    editor = CodeEditor(tmp_path)

    preview = editor.preview_replace(
        "demo.py",
        "return a+b",
        "return a + b",
    )

    editor.apply(preview)

    assert sample_file.read_text(encoding="utf-8") == (
        "def add(a, b):\n    return a + b\n"
    )


def test_rejects_missing_old_text(
    tmp_path: Path,
    sample_file: Path,
) -> None:
    """找不到旧代码片段时不能修改文件。"""

    editor = CodeEditor(tmp_path)

    with pytest.raises(FileEditError, match="实际匹配 0 次"):
        editor.preview_replace(
            "demo.py",
            "return a - b",
            "return a + b",
        )

    assert "return a+b" in sample_file.read_text()


def test_rejects_ambiguous_match(tmp_path: Path) -> None:
    """旧代码片段出现多次时拒绝猜测修改位置。"""

    target = tmp_path / "demo.py"
    target.write_text(
        "def first():\n    return 1\n\ndef second():\n    return 1\n",
        encoding="utf-8",
    )

    editor = CodeEditor(tmp_path)

    with pytest.raises(FileEditError, match="实际匹配 2 次"):
        editor.preview_replace(
            "demo.py",
            "return 1",
            "return 2",
        )


def test_rejects_no_op(
    tmp_path: Path,
    sample_file: Path,
) -> None:
    """没有实际变化的替换应被拒绝。"""

    editor = CodeEditor(tmp_path)

    with pytest.raises(FileEditError, match="没有实际修改"):
        editor.preview_replace(
            "demo.py",
            "return a+b",
            "return a+b",
        )


@pytest.mark.parametrize(
    "file_path",
    [
        "../outside.py",
        "/tmp/outside.py",
        ".venv/demo.py",
        ".env",
        "README.md",
    ],
)
def test_rejects_disallowed_paths(
    tmp_path: Path,
    file_path: str,
) -> None:
    """拒绝越界路径、隐藏文件和非 Python 文件。"""

    editor = CodeEditor(tmp_path)

    with pytest.raises(FileEditError):
        editor.preview_replace(
            file_path,
            "old",
            "new",
        )


def test_rejects_symlink(tmp_path: Path) -> None:
    """不允许通过符号链接修改文件。"""

    real_file = tmp_path / "real.py"
    real_file.write_text("value = 1\n", encoding="utf-8")

    link = tmp_path / "link.py"
    link.symlink_to(real_file)

    editor = CodeEditor(tmp_path)

    with pytest.raises(FileEditError, match="符号链接"):
        editor.preview_replace(
            "link.py",
            "value = 1",
            "value = 2",
        )


def test_rejects_stale_preview(
    tmp_path: Path,
    sample_file: Path,
) -> None:
    """预览后原文件变化时不能覆盖新内容。"""

    editor = CodeEditor(tmp_path)

    preview = editor.preview_replace(
        "demo.py",
        "return a+b",
        "return a + b",
    )

    # 模拟其他程序在预览后修改了文件。
    sample_file.write_text(
        "def add(a, b):\n    return a - b\n",
        encoding="utf-8",
    )

    with pytest.raises(FileEditError, match="发生变化"):
        editor.apply(preview)

    assert "return a - b" in sample_file.read_text()


def test_rejects_modified_preview(
    tmp_path: Path,
    sample_file: Path,
) -> None:
    """预览内容不一致时不允许应用。"""

    editor = CodeEditor(tmp_path)

    preview = editor.preview_replace(
        "demo.py",
        "return a+b",
        "return a + b",
    )

    invalid_preview = replace(
        preview,
        diff="被修改过的差异内容",
    )

    with pytest.raises(FileEditError, match="预览差异不一致"):
        editor.apply(invalid_preview)

    assert "return a+b" in sample_file.read_text()


def test_rejects_oversized_update(
    tmp_path: Path,
    sample_file: Path,
) -> None:
    """替换后超过大小限制时不能写入。"""

    editor = CodeEditor(tmp_path)

    with pytest.raises(FileEditError, match="超过大小限制"):
        editor.preview_replace(
            "demo.py",
            "return a+b",
            "x" * (256 * 1024 + 1),
        )

    assert "return a+b" in sample_file.read_text()


def test_preserves_line_endings(tmp_path: Path) -> None:
    """修改时应保留文件原有的 CRLF 换行符。"""

    target = tmp_path / "demo.py"
    target.write_bytes(b"def add(a, b):\r\n    return a+b\r\n")

    editor = CodeEditor(tmp_path)

    preview = editor.preview_replace(
        "demo.py",
        "return a+b",
        "return a + b",
    )

    editor.apply(preview)

    assert target.read_bytes() == (b"def add(a, b):\r\n    return a + b\r\n")
```

### 6.3 测试重点

| 测试 | 验证内容 |
|---|---|
| 预览不写文件 | Preview 不产生副作用 |
| 应用补丁 | Apply 能精确修改 |
| 原内容不存在 | 拒绝错误匹配 |
| 匹配多次 | 拒绝不明确的修改 |
| 新旧内容相同 | 拒绝无意义修改 |
| 非法路径 | 不允许越界及不支持的文件 |
| 符号链接 | 拒绝通过符号链接修改 |
| 过期预览 | 防止覆盖较新的文件内容 |
| 预览不一致 | 防止应用与预览不同的补丁 |
| 文件大小 | 拒绝超限修改 |
| 换行格式 | 保留 CRLF |

### 6.4 `pytest.fixture` 的作用

```python
@pytest.fixture
def sample_file(tmp_path: Path) -> Path:
```

`fixture`（测试夹具）用于准备可复用的测试环境。

本例负责创建临时 `demo.py`，供多个测试使用。

`tmp_path` 是 pytest 提供的临时路径对象，各测试可以在隔离目录中进行文件操作，不影响正式代码仓库。

### 6.5 `pytest.mark.parametrize` 的作用

```python
@pytest.mark.parametrize(
    "file_path",
    [
        "../outside.py",
        "/tmp/outside.py",
        ".venv/demo.py",
        ".env",
        "README.md",
    ],
)
```

参数化测试会让同一个测试函数分别使用不同输入。

这里一个测试函数对应五个独立测试用例。

它非常适合检查：

- 不同路径输入。
- 不同确认内容。
- 不同非法参数。
- 多种边界条件。

### 6.6 执行测试

执行：

```bash
python -m pytest tests/test_editor.py -v
```

本阶段设计 11 个测试函数，其中路径检查参数化为 5 个用例，因此共计 **15 个测试用例**。

实际结果：测试通过。

---

## 7. 第二阶段：将编辑功能接入 CLI

### 7.1 为什么要接入 CLI？

第一阶段已经可以在 Python 中使用：

```python
editor = CodeEditor(project)

preview = editor.preview_replace(
    "demo.py",
    "return a+b",
    "return a + b",
)

print(preview.diff)

editor.apply(preview)
```

但实际使用时，不希望每次都需要写临时 Python 脚本。

所以本阶段新增：

```bash
ai-dev-agent edit \
  --project <项目目录> \
  --path <文件路径> \
  --old <旧内容> \
  --new <新内容>
```

并在真正写入前进行人工确认。

### 7.2 修改已有 `cli.py`

先打开文件：

```bash
nano src/ai_software_dev_agent/cli.py
```

这是已有文件，不需要 `touch` 或重新创建。

### 7.3 `cli.py` 完整代码

文件：`src/ai_software_dev_agent/cli.py`

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


def describe_api_error(status_code: int) -> str:
    """将常见 HTTP 错误转换成易理解的提示。"""

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

    # Day 06：新增安全编辑命令。
    edit_parser = subparsers.add_parser(
        "edit",
        help="预览并确认一次 Python 代码修改",
    )

    # 需要指定仓库的命令统一提供 --project。
    for command_parser in (
        doctor_parser,
        inspect_parser,
        read_parser,
        search_parser,
        chat_parser,
        edit_parser,
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

    # 编辑必须明确给出目标文件和替换内容。
    edit_parser.add_argument(
        "--path",
        required=True,
        help="相对项目根目录的 Python 文件路径",
    )

    edit_parser.add_argument(
        "--old",
        required=True,
        help="需要被精确匹配的旧代码片段",
    )

    edit_parser.add_argument(
        "--new",
        required=True,
        help="替换后的新代码片段",
    )

    return parser


def run_edit_command(
    project: Path,
    file_path: str,
    old_text: str,
    new_text: str,
) -> int:
    """预览差异，获取用户确认，然后安全应用修改。"""

    # 先生成预览，不立即修改文件。
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

    # 必须显式输入 yes 才允许执行写操作。
    try:
        confirmation = input("\n输入 yes 确认写入，其他任意输入取消：").strip()

    except (EOFError, KeyboardInterrupt):
        print("\n已取消修改，文件未写入。")
        return 0

    if confirmation != "yes":
        print("已取消修改，文件未写入。")
        return 0

    # 确认之后调用已有组件，重新检查原始文件版本。
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
    """启动持续对话，并在当前进程内维护消息历史。"""

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

        # 只显示本轮新增的工具结果。
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

    # Day 06：安全文件修改，不需要模型 API。
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

## 8. CLI 编辑流程讲解

### 8.1 新增 `edit` 子命令

```python
edit_parser = subparsers.add_parser(
    "edit",
    help="预览并确认一次 Python 代码修改",
)
```

该命令接收：

```text
--project：项目目录
--path：文件相对路径
--old：需要替换的旧代码
--new：替换后的新代码
```

例如：

```bash
ai-dev-agent edit \
  --project ./example-repo \
  --path demo.py \
  --old "return a+b" \
  --new "return a + b"
```

### 8.2 为什么单独使用 `run_edit_command()`？

```python
def run_edit_command(
    project: Path,
    file_path: str,
    old_text: str,
    new_text: str,
) -> int:
```

这个函数负责 CLI 的交互流程：

1. 创建 `CodeEditor`。
2. 生成修改预览。
3. 打印 Diff。
4. 等待用户确认。
5. 调用 `apply()`。
6. 输出修改结果。

这样可以把**用户交互**与**文件修改实现**分开。

`CodeEditor` 不需要关心用户如何输入 `yes`。

CLI 也不需要重新实现文件路径检查、SHA-256 或原子替换。

### 8.3 为什么要求输入 `yes`？

核心代码：

```python
confirmation = input("\n输入 yes 确认写入，其他任意输入取消：").strip()
```

然后：

```python
if confirmation != "yes":
    print("已取消修改，文件未写入。")
    return 0
```

因此：

| 用户输入 | 行为 |
|---|---|
| `yes` | 应用补丁 |
| `no` | 取消 |
| 直接回车 | 取消 |
| `YES` | 取消 |
| Ctrl+C | 取消 |
| Ctrl+D | 取消 |

这是本日实现的 CLI 显式确认机制。

它并不是后续 Day 12 要学习的 Agent Human-in-the-Loop（人在回路中）工作流审批，但体现了类似的基本安全原则：**写入前必须让用户看到并确认具体变更。**

### 8.4 为什么确认之后还需要再次检查？

即使用户输入 `yes`，也不能直接相信之前的文件状态。

```python
editor.apply(preview)
```

内部会重新读取当前文件并检查 SHA-256。

如果文件在预览后已经改变，会拒绝写入。

因此人工确认和版本校验解决的是两个不同的问题：

- 人工确认：用户是否同意这次修改。
- 版本校验：这次修改是否仍然适用于当前文件。

### 8.5 为什么 `edit` 不调用模型？

在 `main()` 中：

```python
if args.command == "edit":
    return run_edit_command(...)
```

该分支不会调用：

```python
load_model_settings()
create_chat_model()
```

因此：

- 不需要 API Key。
- 不消耗模型 Token。
- 不依赖 OpenRouter 在线状态。
- 文件修改由用户提供精确替换内容。

本日不允许模型直接产生并执行写文件命令。

---

## 9. 第二阶段：增加 CLI 自动化测试

### 9.1 修改已有文件

`tests/test_cli.py` 是之前已经创建的文件，因此本日直接修改。

打开：

```bash
nano tests/test_cli.py
```

新增 Day 06 的测试，同时保留之前已经通过的全部测试。

### 9.2 `test_cli.py` 完整代码

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
    """输入精确的 yes 后，才允许执行实际写入。"""

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
    """没有输入精确的 yes 时不能修改文件。"""

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
    """找不到指定旧代码时，不能进入确认或写入阶段。"""

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
    """CLI 不能绕过 CodeEditor 的文件路径限制。"""

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
    """预览后文件被外部修改时，应拒绝覆盖。"""

    target = tmp_path / "demo.py"
    target.write_text(
        "value = 1\n",
        encoding="utf-8",
    )

    def change_file_before_confirmation(_prompt: str) -> str:
        # 模拟用户查看预览期间，其他程序修改了文件。
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
    """确认阶段输入流结束时，文件必须保持不变。"""

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
    """--old、--new 均是必填参数。"""

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
    """edit 帮助信息必须说明全部编辑参数。"""

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["edit", "--help"])

    assert exc_info.value.code == 0

    output = capsys.readouterr().out

    assert "--project" in output
    assert "--path" in output
    assert "--old" in output
    assert "--new" in output
```

### 9.3 新增测试说明

本阶段新增 8 个测试函数。

其中：

- 用户确认测试参数化为 3 种输入。
- 参数缺失测试参数化为 2 种输入。

因此新增 **11 个 pytest 测试用例**。

| 测试 | 验证内容 |
|---|---|
| `test_edit_applies_after_exact_confirmation` | 输入 `yes` 后写入文件 |
| `test_edit_cancels_without_exact_yes` | 非精确确认不会写入 |
| `test_edit_rejects_unmatched_content` | 旧内容不存在时拒绝修改 |
| `test_edit_rejects_unsafe_path` | 路径保护不能被 CLI 绕过 |
| `test_edit_rejects_stale_preview` | 文件变化后拒绝覆盖 |
| `test_edit_cancels_on_eof` | 输入结束时取消 |
| `test_edit_requires_old_and_new_arguments` | 参数必须完整 |
| `test_edit_help_displays_arguments` | CLI 帮助信息正确 |

### 9.4 为什么必须检查实际文件内容？

例如：

```python
assert target.read_text(encoding="utf-8") == ("def add(a, b):\n    return a + b\n")
```

不能只根据：

```text
修改完成
```

判断成功。

打印成功消息只是程序行为，文件真正发生预期变化才是验收结果。

同样，当用户取消时，也必须验证文件没有变化。

### 9.5 为什么模拟外部修改？

测试中：

```python
def change_file_before_confirmation(_prompt: str) -> str:
    target.write_text(
        "value = 99\n",
        encoding="utf-8",
    )
    return "yes"
```

模拟：

1. CLI 展示预览。
2. 另一个程序修改文件。
3. 用户确认旧补丁。
4. 编辑器重新检查文件版本。
5. 编辑器拒绝覆盖。

然后验证：

```python
assert target.read_text(encoding="utf-8") == "value = 99\n"
```

这个断言确保更新后的文件内容没有被旧补丁覆盖。

---

## 10. 自动化测试与结果

### 10.1 编辑器单元测试

执行：

```bash
python -m pytest tests/test_editor.py -v
```

预期 15 个测试用例。

实际结果：通过。

### 10.2 CLI 回归测试

执行：

```bash
python -m pytest tests/test_cli.py -v
```

实际结果：通过。

### 10.3 编辑器与 CLI 联合测试

执行：

```bash
python -m pytest \
  tests/test_editor.py \
  tests/test_cli.py \
  -v
```

实际结果：通过。

### 10.4 完整项目测试

执行：

```bash
python -m pytest -v
```

按既有测试数量计算：

```text
Day 05：49 项
Day 06 第一阶段：15 项
Day 06 第二阶段：11 项
```

预计合计：

```text
75 passed
```

用户已确认全部测试通过。由于没有提供完整的终端统计日志，这里将 `75 passed` 记为按测试设计推算的数量，不伪造为实际逐字输出。

---

## 11. 正式 CLI 与 Git Diff 验收

### 11.1 为什么使用临时 Git 仓库？

如果只创建普通临时文件夹：

```bash
mktemp -d
```

它不是 Git 仓库。

直接运行：

```bash
git diff
```

就不能正常完成我们希望的 Git 工作区差异比较。

因此本次先初始化独立 Git 仓库，创建基准提交，再测试编辑命令。

这样既能观察真实 `git diff`，又不会污染正式项目的提交记录。

### 11.2 创建独立 Git 仓库

执行：

```bash
DEMO_DIR="$(mktemp -d)"
```

初始化 Git：

```bash
git -C "$DEMO_DIR" init -b main
```

参数说明：

- `-C`：让 Git 在指定目录下运行。
- `init`：初始化仓库。
- `-b main`：指定初始分支名称为 `main`。

### 11.3 创建测试文件

执行：

```bash
cat > "$DEMO_DIR/demo.py" <<'PY'
def add(a: int, b: int) -> int:
    return a+b
PY
```

这条命令同时完成文件创建与内容写入。

检查：

```bash
cat "$DEMO_DIR/demo.py"
```

### 11.4 创建基准提交

执行：

```bash
git -C "$DEMO_DIR" add demo.py
```

提交：

```bash
git -C "$DEMO_DIR" \
  -c user.name="Day06 Demo" \
  -c user.email="demo@example.invalid" \
  commit -m "test: baseline"
```

这里使用临时 Git 身份，仅作用于当前命令，不修改全局 Git 配置。

验证：

```bash
git -C "$DEMO_DIR" status --short
```

预期没有输出，说明当前工作区相对于基准版本没有变化。

### 11.5 实验一：预览并取消

执行：

```bash
ai-dev-agent edit \
  --project "$DEMO_DIR" \
  --path demo.py \
  --old "return a+b" \
  --new "return a + b"
```

CLI 先展示差异：

```diff
--- a/demo.py
+++ b/demo.py
@@ -1,2 +1,2 @@
 def add(a: int, b: int) -> int:
-    return a+b
+    return a + b
```

随后询问：

```text
输入 yes 确认写入，其他任意输入取消：
```

输入：

```text
no
```

检查原文件：

```bash
cat "$DEMO_DIR/demo.py"
```

检查 Git Diff：

```bash
git -C "$DEMO_DIR" diff -- demo.py
```

预期：

- 文件内容未改变。
- Git Diff 没有变化。

实际验收：通过。

这证明 Preview 和取消操作不会写入文件。

### 11.6 实验二：确认修改

再次执行：

```bash
ai-dev-agent edit \
  --project "$DEMO_DIR" \
  --path demo.py \
  --old "return a+b" \
  --new "return a + b"
```

这次输入：

```text
yes
```

CLI 完成写入。

检查：

```bash
cat "$DEMO_DIR/demo.py"
```

预期：

```python
def add(a: int, b: int) -> int:
    return a + b
```

实际验收：通过。

### 11.7 使用 `git diff` 验证

执行：

```bash
git -C "$DEMO_DIR" diff -- demo.py
```

预期看到：

```diff
--- a/demo.py
+++ b/demo.py
@@ -1,2 +1,2 @@
 def add(a: int, b: int) -> int:
-    return a+b
+    return a + b
```

这说明 Git 发现工作区与基准版本之间存在一处代码修改。

继续：

```bash
git -C "$DEMO_DIR" diff --check
```

该命令主要检查 Diff 中常见的空白问题，例如尾随空白，不负责判断 Python 代码逻辑是否正确。

再执行：

```bash
git -C "$DEMO_DIR" status --short
```

预期：

```text
 M demo.py
```

含义：

- `M`：文件已修改。
- 修改位于工作区，尚未暂存。

实际验收：通过。

### 11.8 实验三：旧内容不存在

执行：

```bash
ai-dev-agent edit \
  --project "$DEMO_DIR" \
  --path demo.py \
  --old "return a*b" \
  --new "return a * b"
```

因为当前文件中不存在：

```python
return a * b
```

预期报错：

```text
无法生成修改预览：旧代码片段必须恰好匹配一次，实际匹配 0 次
```

此时不会进入人工确认阶段，也不会修改文件。

实际验收：通过。

### 11.9 清理临时仓库

完成实验后，在创建 `DEMO_DIR` 的同一个终端执行：

```bash
test -n "${DEMO_DIR:-}" && test -d "$DEMO_DIR" && rm -r "$DEMO_DIR"
```

只删除本次临时 Git 仓库。

---

## 12. Debug 与异常实验记录

### 12.1 本日真实 Debug 情况

本日没有报告需要额外修改源码才能解决的真实程序故障。

两阶段的自动化测试和正式 CLI 验收均已通过。

因此不编造不存在的异常堆栈或修复过程。

不过，本日专门进行了多种错误路径实验，它们属于预期的异常验证。

### 12.2 实验一：旧代码不存在

执行：

```bash
ai-dev-agent edit \
  --project "$DEMO_DIR" \
  --path demo.py \
  --old "return a*b" \
  --new "return a * b"
```

验证目的：

确认旧代码不匹配时，编辑器拒绝生成可应用补丁。

预期错误：

```text
旧代码片段必须恰好匹配一次，实际匹配 0 次
```

结果：验证通过。

### 12.3 实验二：用户取消修改

执行：

```bash
ai-dev-agent edit \
  --project "$DEMO_DIR" \
  --path demo.py \
  --old "return a+b" \
  --new "return a + b"
```

在确认阶段输入：

```text
no
```

随后：

```bash
git -C "$DEMO_DIR" diff -- demo.py
```

验证目的：

确认取消操作不会产生文件变化。

结果：验证通过。

### 12.4 实验三：过期预览

使用 pytest：

```bash
python -m pytest \
  tests/test_editor.py::test_rejects_stale_preview \
  -v
```

该测试先生成预览，再模拟其他程序修改文件：

```python
sample_file.write_text(
    "def add(a, b):\n    return a - b\n",
    encoding="utf-8",
)
```

之后应用旧预览，预期抛出：

```text
文件在预览后已发生变化，请重新生成预览
```

并确认新的文件内容没有被覆盖。

结果：验证通过。

### 12.5 实验四：非法路径

执行：

```bash
ai-dev-agent edit \
  --project "$DEMO_DIR" \
  --path ../outside.py \
  --old "old" \
  --new "new"
```

验证目的：

确保 CLI 不能绕过 CodeEditor 的路径限制。

预期结果：生成预览失败，文件不会被写入。

对应自动化测试通过。

### 12.6 本日 Debug 方法总结

对于文件编辑功能，排查顺序应为：

```text
1. 项目根目录是否正确？
          ↓
2. 目标文件是否允许访问？
          ↓
3. 旧代码是否恰好匹配一次？
          ↓
4. Diff 是否符合预期？
          ↓
5. 用户是否确认？
          ↓
6. 原始文件版本是否仍然一致？
          ↓
7. 文件是否成功写入？
          ↓
8. Git Diff 是否反映正确的变化？
```

这是比“只看是否打印修改成功”更可靠的排查方式。

---

## 13. `difflib` 与 Git Diff 的区别

虽然两者都能产生相似的差异格式，但用途不同。

| 对比 | `difflib.unified_diff()` | `git diff` |
|---|---|---|
| 实现来源 | Python 标准库 | Git |
| 输入 | 两份文本或行序列 | Git 管理的不同文件状态 |
| 是否要求 Git 仓库 | 否 | 通常需要，取决于调用方式 |
| 本日用途 | 修改前的差异预览 | 实际写入后的版本差异检查 |
| 是否自动应用修改 | 否 | 否 |

今天使用 `difflib` 在写入前生成预览。

使用 `git diff` 在写入后验证工作区发生的实际变化。

它们是互补关系，不需要二选一。

---

## 14. 本日重要的工程设计原则

### 14.1 预览和应用分离

```python
preview = editor.preview_replace(...)
```

只生成修改方案。

```python
editor.apply(preview)
```

才真正写入。

这样更容易实现人工审查和自动化测试。

### 14.2 默认拒绝不确定操作

当发生以下情况时，程序选择拒绝修改：

- 目标文件不允许访问。
- 旧代码匹配次数不是 1。
- 新旧内容完全相同。
- 文件版本变化。
- 补丁预览不一致。
- 文件超过大小限制。
- 用户未输入明确的确认内容。

对于拥有写入权限的程序，**不确定时不修改**是一项重要原则。

### 14.3 CLI 与业务逻辑分离

`cli.py` 负责：

- 参数解析。
- 展示 Diff。
- 询问用户是否确认。
- 输出执行结果。

`editor.py` 负责：

- 文件路径检查。
- 文本替换。
- SHA-256 版本检查。
- 临时文件写入。
- 原子替换。

这样能让同一个编辑器未来被其他入口复用，而不是与终端输入紧密绑定。

### 14.4 文件修改需要多层验证

```text
输入校验
   ↓
路径安全检查
   ↓
旧代码精确匹配
   ↓
生成 Diff
   ↓
用户确认
   ↓
SHA-256 版本校验
   ↓
安全写回
   ↓
Git Diff 验收
```

每层解决不同问题。

例如人工确认不能代替路径检查，SHA-256 也不能代替业务正确性测试。

### 14.5 自动化测试不应依赖真实模型

Day 06 的文件编辑功能不需要模型参与。

因此所有编辑测试都应在本地完成，不消耗 API 额度。

这也是将写文件组件与 LangChain Agent 分开的好处。

---

## 15. 本日能力边界与注意事项

当前支持：

- 修改已经存在的 Python 文件。
- 精确替换出现一次的代码片段。
- 生成 Unified Diff。
- 检查文件版本变化。
- 人工确认后写入。
- 利用 Git Diff 审查实际修改。

当前不支持：

- 创建新的业务 Python 文件。
- 修改非 `.py` 文件。
- 在一次请求中替换多个位置。
- 自动处理多文件补丁。
- 自动合并冲突。
- 保证全部恶意并发文件系统操作下的安全性。
- 自动检查修改后 Python 语法是否正确。
- 自动运行 pytest。
- 自动提交 Git。
- 模型直接调用文件写入工具。

另外，`--old` 与 `--new` 直接通过命令行参数传入，适合本日简单实验。

对于较大的多行补丁，未来可以考虑从 Patch 文件读取，减少 Shell 引号、换行及特殊字符造成的问题。

---

## 16. Day 06 总结

本日建立了一个从代码修改请求到最终差异验证的完整基础流程。

项目能力演进：

```text
Day 02：安全仓库探索
          ↓
Day 03：真实模型问答
          ↓
Day 04：工具调用与结构化规划
          ↓
Day 05：Agent 自动执行只读工具
          ↓
Day 06：安全代码修改与 Git Diff
```

今天最重要的三个知识点：

**第一，修改代码前应该明确展示变更内容。**

通过 `difflib.unified_diff()`，用户可以在写入之前看到具体修改。

**第二，不能直接覆盖可能已经变化的代码文件。**

使用 SHA-256 检查预览前后文件版本，避免常见的过期补丁覆盖。

**第三，功能正常与工程可靠是两个不同层次。**

能修改文件只是基本功能；路径限制、匹配校验、人工确认、临时文件写入、异常测试和 Git 差异检查，才让文件编辑能力逐渐具备工程可用性。

本日最终形成：

```text
CodeEditor
    ├── preview_replace()
    │       ├── 检查文件
    │       ├── 精确匹配旧内容
    │       ├── 生成新内容
    │       └── 生成 Unified Diff
    │
    └── apply()
            ├── 检查文件版本
            ├── 检查补丁一致性
            ├── 写入临时文件
            └── 替换目标文件
```

以及：

```text
ai-dev-agent edit
    ↓
预览差异
    ↓
输入 yes 确认
    ↓
受控写回
    ↓
Git Diff 检查
```

这些能力为后续构建更加完整的软件开发 Agent 提供了文件编辑基础。

