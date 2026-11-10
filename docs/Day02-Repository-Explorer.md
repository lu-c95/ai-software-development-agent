# Day 02 — Repository Explorer（代码仓库探索）

## 1. 当天目标

开发 Repository Explorer（代码仓库探索器），为后续 AI Software Development Agent 提供代码仓库的基础访问能力。

实现三个核心功能：

| 功能 | Python 方法 | CLI 命令 |
|---|---|---|
| 扫描仓库文件 | `list_files()` | `inspect` |
| 读取文件内容 | `read_file()` | `read` |
| 搜索代码关键词 | `search()` | `search` |

同时增加路径、文件类型、文件大小等基础访问限制。

**设计原则：CLI 负责接收命令和展示结果，RepositoryExplorer 负责实际文件操作。**

后续 LangChain Tools（工具）可以直接复用 `RepositoryExplorer`，不需要重新实现文件访问逻辑。

## 2. 项目结构与文件创建

### 2.1 文件结构变化

```text
ai-software-development-agent/
├── src/
│   └── ai_software_dev_agent/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py               # 修改
│       └── repository.py        # 新增
├── tests/
│   ├── test_cli.py              # 修改
│   └── test_repository.py       # 新增
├── docs/
│   ├── Development-Plan.md
│   ├── Day01-Project-Setup.md
│   └── Day02-Repository-Explorer.md  # 新增
├── pyproject.toml
└── README.md
```

### 2.2 创建目录与文件

在项目根目录执行：

```bash
mkdir -p src/ai_software_dev_agent tests docs

touch src/ai_software_dev_agent/repository.py
touch tests/test_repository.py
touch docs/Day02-Repository-Explorer.md
```

`cli.py` 和 `test_cli.py` 已在 Day 01 创建，本次直接修改。

### 2.3 文件职责

| 文件 | 主要职责 |
|---|---|
| `repository.py` | 实现仓库扫描、文件读取、关键词搜索及访问校验 |
| `cli.py` | 增加 `inspect`、`read`、`search` 命令 |
| `test_repository.py` | 验证文件操作及访问边界 |
| `test_cli.py` | 验证新增 CLI 命令的行为 |

本次不增加第三方依赖，使用 Python 标准库 `os`、`pathlib` 和 `dataclasses` 实现核心功能。

---

## 3. repository.py — 仓库探索核心模块

### 3.1 完整代码

文件：`src/ai_software_dev_agent/repository.py`

```python
"""安全地探索指定的 Python 项目仓库。"""

import os
from dataclasses import dataclass
from pathlib import Path


# 只处理允许的代码和文本文件类型。
ALLOWED_SUFFIXES = frozenset({".py", ".toml", ".md", ".txt", ".json", ".yaml", ".yml"})

# 跳过虚拟环境、缓存、版本控制及运行时目录。
IGNORED_DIRS = frozenset(
    {
        ".git",
        ".venv",
        ".idea",
        ".vscode",
        ".runtime",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        "node_modules",
        "build",
        "dist",
        "data",
        "logs",
        "workspace",
    }
)

MAX_FILES = 500
MAX_FILE_BYTES = 64 * 1024


class RepositoryError(ValueError):
    """仓库或文件不满足访问规则时抛出的异常。"""


@dataclass(frozen=True)
class SearchHit:
    """一条代码搜索结果。"""

    path: str
    line_number: int
    line: str


class RepositoryExplorer:
    """只读的代码仓库探索工具。"""

    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve()

        if not self.root.is_dir():
            raise RepositoryError(f"项目目录不存在或不是文件夹：{self.root}")

    def list_files(self) -> list[str]:
        """遍历仓库，返回允许探索的文件相对路径。"""

        found: list[str] = []

        for current_dir, dirnames, filenames in os.walk(self.root, followlinks=False):
            current = Path(current_dir)

            # 原地过滤子目录，阻止进入忽略目录及目录符号链接。
            dirnames[:] = sorted(
                name
                for name in dirnames
                if name not in IGNORED_DIRS
                and not name.startswith(".")
                and not (current / name).is_symlink()
            )

            for name in sorted(filenames):
                file_path = current / name

                if name.startswith(".") or file_path.is_symlink():
                    continue

                if file_path.suffix.lower() not in ALLOWED_SUFFIXES:
                    continue

                found.append(file_path.relative_to(self.root).as_posix())

                if len(found) > MAX_FILES:
                    raise RepositoryError(
                        f"仓库文件超过 {MAX_FILES} 个，请缩小探索范围"
                    )

        return sorted(found)

    def _allowed_file(self, relative_path: str) -> Path:
        """检查目标文件是否满足读取规则。"""

        given_path = Path(relative_path)

        if given_path.is_absolute():
            raise RepositoryError("只能使用相对于项目根目录的路径")

        path = (self.root / given_path).resolve()

        if not path.is_relative_to(self.root):
            raise RepositoryError("文件不在指定项目目录内")

        relative = path.relative_to(self.root)

        if any(part in IGNORED_DIRS for part in relative.parts):
            raise RepositoryError("不允许访问已忽略的目录")

        if any(part.startswith(".") for part in relative.parts):
            raise RepositoryError("不允许访问隐藏文件或目录")

        if path.suffix.lower() not in ALLOWED_SUFFIXES:
            raise RepositoryError("不支持该文件类型")

        if not path.is_file():
            raise RepositoryError(f"文件不存在：{relative_path}")

        if path.stat().st_size > MAX_FILE_BYTES:
            raise RepositoryError(f"文件超过 {MAX_FILE_BYTES} 字节限制")

        return path

    def read_file(self, relative_path: str) -> str:
        """读取允许访问的 UTF-8 文本文件。"""

        path = self._allowed_file(relative_path)

        try:
            return path.read_text(encoding="utf-8")
        except (UnicodeError, OSError) as exc:
            raise RepositoryError(f"文件读取失败：{relative_path}") from exc

    def search(self, keyword: str, limit: int = 20) -> list[SearchHit]:
        """搜索关键词，返回文件路径、行号与匹配内容。"""

        if not keyword.strip():
            raise RepositoryError("搜索关键词不能为空")

        if not 1 <= limit <= 100:
            raise RepositoryError("搜索结果数量必须在 1 到 100 之间")

        hits: list[SearchHit] = []
        needle = keyword.casefold()

        for relative_path in self.list_files():
            try:
                content = self.read_file(relative_path)
            except RepositoryError:
                # 跳过超过大小限制或无法读取的文件。
                continue

            for number, line in enumerate(content.splitlines(), start=1):
                if needle in line.casefold():
                    hits.append(
                        SearchHit(
                            relative_path,
                            number,
                            line.strip()[:160],
                        )
                    )

                    if len(hits) >= limit:
                        return hits

        return hits
```

### 3.2 核心实现解释

#### 3.2.1 定义访问规则

```python
ALLOWED_SUFFIXES = frozenset({".py", ".toml", ".md", ".txt", ".json", ".yaml", ".yml"})

MAX_FILES = 500
MAX_FILE_BYTES = 64 * 1024
```

通过白名单限制允许处理的文件类型，避免扫描图片、压缩包和其他不需要的文件。

`frozenset` 是不可变集合，适合保存运行期间不需要修改的配置常量。

`MAX_FILES` 限制扫描结果数量；`MAX_FILE_BYTES` 限制单文件读取大小，避免将大量无关内容交给后续模型处理。

#### 3.2.2 初始化仓库对象

```python
def __init__(self, root: Path) -> None:
    self.root = root.expanduser().resolve()

    if not self.root.is_dir():
        raise RepositoryError(f"项目目录不存在或不是文件夹：{self.root}")
```

主要完成两个操作：

1. 将用户传入的仓库路径转换为规范化绝对路径。
2. 检查指定目录是否存在。

如果初始化失败，直接抛出 `RepositoryError`，避免后续工具在无效目录上继续执行。

#### 3.2.3 扫描文件：list_files()

核心流程：

```text
项目根目录
    ↓
os.walk() 递归遍历
    ↓
过滤忽略目录与符号链接
    ↓
过滤隐藏文件与不支持的后缀
    ↓
转换为仓库相对路径
    ↓
检查文件数量上限
    ↓
返回排序后的文件列表
```

关键代码：

```python
for current_dir, dirnames, filenames in os.walk(
    self.root, followlinks=False
):
```

其中：

- `current_dir`：当前遍历的目录。
- `dirnames`：当前目录中的子目录名称。
- `filenames`：当前目录中的文件名称。
- `followlinks=False`：不跟随目录符号链接递归。

通过：

```python
dirnames[:] = sorted(...)
```

原地修改子目录列表，阻止 `os.walk()` 继续进入 `.venv/`、`.git/` 等目录。

通过：

```python
file_path.relative_to(self.root).as_posix()
```

把绝对路径转换为相对仓库根目录的路径。

例如：

```text
绝对路径：
/Users/test/project/src/main.py

返回：
src/main.py
```

使用相对路径可以减少环境依赖，也方便后续传递给 Agent。

#### 3.2.4 文件校验：_allowed_file()

该方法集中完成文件访问规则检查。

```python
path = (self.root / given_path).resolve()

if not path.is_relative_to(self.root):
    raise RepositoryError("文件不在指定项目目录内")
```

其核心目的是防止 Path Traversal（路径遍历），例如利用 `../` 访问其他项目的文件。

还会继续检查：

- 是否位于忽略目录中。
- 是否包含隐藏文件或目录。
- 文件类型是否受支持。
- 文件是否存在。
- 文件大小是否超限。

这样 `read_file()` 无需重复编写这些检查。

注意：当前通过解析路径来做基础保护，仍存在文件系统并发变化等潜在风险，不应将其当作完整沙箱。

另外，扫描会跳过文件符号链接，但直接读取指向仓库内部的符号链接仍可能通过校验。后续需要统一两种操作的行为。

#### 3.2.5 读取文件：read_file()

```python
def read_file(self, relative_path: str) -> str:
    path = self._allowed_file(relative_path)

    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeError, OSError) as exc:
        raise RepositoryError(f"文件读取失败：{relative_path}") from exc
```

流程：

**文件路径 → 校验权限和类型 → 读取 UTF-8 内容 → 返回字符串。**

`read_text()` 一次性读取文本内容，因此先检查文件大小。

`except` 捕获文件读取、解码过程中可能发生的异常，再转换为统一的业务异常，便于 CLI 处理。

其中 `raise ... from exc` 会保留原始异常的因果关系，方便调试。

#### 3.2.6 搜索关键词：search()

核心过程：

```python
needle = keyword.casefold()

for relative_path in self.list_files():
    try:
        content = self.read_file(relative_path)
    except RepositoryError:
        continue

    for number, line in enumerate(content.splitlines(), start=1):
        if needle in line.casefold():
            hits.append(
                SearchHit(
                    relative_path,
                    number,
                    line.strip()[:160],
                )
            )
```

实现步骤：

1. 校验关键词和搜索数量限制。
2. 将关键词转换为适合不区分大小写比较的形式。
3. 获取仓库中的文件列表。
4. 逐个读取允许的文本文件。
5. 将文件内容按行拆分，逐行查找关键词。
6. 生成包含路径、行号和内容的 `SearchHit`。
7. 达到结果数量上限后立即返回。

`SearchHit`：

```python
@dataclass(frozen=True)
class SearchHit:
    path: str
    line_number: int
    line: str
```

例如：

```python
SearchHit(
    path="src/main.py",
    line_number=10,
    line="def main():",
)
```

使用结构化对象而不是普通字符串，后续 LangChain Tool 可以直接访问各字段。

当前搜索属于关键词搜索，不是语义搜索；超大或无法解码的文件也可能被跳过，因此不保证覆盖仓库中的所有内容。

---

## 4. cli.py — 接入仓库探索功能

### 4.1 完整代码

文件：`src/ai_software_dev_agent/cli.py`

```python
"""AI 软件开发智能体的命令行入口。"""

import argparse
from pathlib import Path

from ai_software_dev_agent import __version__
from ai_software_dev_agent.repository import RepositoryError, RepositoryExplorer


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

    # 定义 CLI 子命令。
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

    # 所有子命令共用项目目录参数。
    for command_parser in (
        doctor_parser,
        inspect_parser,
        read_parser,
        search_parser,
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

    return parser


def main(argv: list[str] | None = None) -> int:
    """解析命令并执行对应功能。"""

    parser = build_parser()
    args = parser.parse_args(argv)

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
        # 业务异常转换成用户能够理解的命令行错误。
        parser.error(str(exc))

    return 0
```

### 4.2 主要修改及原因

#### 4.2.1 新增三个子命令

原来只有：

```bash
ai-dev-agent doctor --project .
```

现在增加：

```bash
ai-dev-agent inspect --project .

ai-dev-agent read --project . --path src/main.py

ai-dev-agent search --project . --query "def main"
```

通过 `argparse` 的 `add_parser()` 注册不同功能。

每个子命令只负责声明输入参数，具体的文件操作由 `RepositoryExplorer` 完成。

#### 4.2.2 统一处理项目路径

```python
for command_parser in (
    doctor_parser,
    inspect_parser,
    read_parser,
    search_parser,
):
    command_parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="目标项目目录",
    )
```

避免为每个子命令重复编写相同参数。

`Path.cwd()` 获取当前工作目录，没有传入 `--project` 时默认使用该目录。

#### 4.2.3 根据子命令调用业务方法

例如：

```python
elif args.command == "search":
    hits = explorer.search(
        args.query,
        limit=args.limit,
    )
```

这里不直接实现搜索逻辑，而是调用核心模块。

以后模型需要搜索代码时，也能复用同一个方法。

#### 4.2.4 统一异常处理

```python
except RepositoryError as exc:
    parser.error(str(exc))
```

`RepositoryExplorer` 负责判断什么操作不合法；CLI 负责把错误展示给用户。

`parser.error()` 通常以退出码 `2` 结束程序。

这种设计使业务逻辑与命令行输出相互独立，方便测试和扩展。

### 4.3 核心调用链

以搜索命令为例：

```bash
ai-dev-agent search --project . --query "def main"
```

```text
用户输入
   ↓
cli.main()
   ↓
build_parser() 解析参数
   ↓
RepositoryExplorer(project)
   ↓
search(keyword)
   ├── list_files()
   ├── read_file()
   │     └── _allowed_file()
   └── SearchHit
   ↓
CLI 输出路径、行号、匹配内容
```

---

## 5. 测试代码与验证

### 5.1 test_repository.py — 完整代码

文件：`tests/test_repository.py`

```python
"""仓库探索工具测试。"""

from pathlib import Path

import pytest

from ai_software_dev_agent.repository import RepositoryError, RepositoryExplorer


def test_list_files_ignores_cache_and_binary(tmp_path: Path) -> None:
    """扫描时应跳过虚拟环境与不支持的文件。"""

    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("print('ok')\n", encoding="utf-8")

    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "private.py").write_text("secret", encoding="utf-8")

    (tmp_path / "image.png").write_bytes(b"\x00\x01")

    assert RepositoryExplorer(tmp_path).list_files() == ["app/main.py"]


def test_read_file(tmp_path: Path) -> None:
    """应该正确读取 UTF-8 文件及中文内容。"""

    (tmp_path / "main.py").write_text("hello = '你好'\n", encoding="utf-8")

    assert RepositoryExplorer(tmp_path).read_file("main.py") == ("hello = '你好'\n")


def test_read_rejects_outside_path(tmp_path: Path) -> None:
    """不允许通过相对路径访问项目外部。"""

    with pytest.raises(
        RepositoryError,
        match="不在指定项目目录内",
    ):
        RepositoryExplorer(tmp_path).read_file("../outside.py")


def test_read_rejects_symlink_outside(tmp_path: Path) -> None:
    """符号链接指向项目外部时应被拒绝。"""

    outside = tmp_path.parent / "external.py"
    (tmp_path / "link.py").symlink_to(outside)

    with pytest.raises(
        RepositoryError,
        match="不在指定项目目录内",
    ):
        RepositoryExplorer(tmp_path).read_file("link.py")


def test_read_rejects_ignored_directory(tmp_path: Path) -> None:
    """不允许读取运行时数据目录。"""

    (tmp_path / ".runtime").mkdir()
    (tmp_path / ".runtime" / "record.json").write_text("{}", encoding="utf-8")

    with pytest.raises(
        RepositoryError,
        match="不允许访问已忽略的目录",
    ):
        RepositoryExplorer(tmp_path).read_file(".runtime/record.json")


def test_read_rejects_oversized_file(tmp_path: Path) -> None:
    """超过单文件大小限制时应拒绝读取。"""

    (tmp_path / "large.txt").write_text(
        "x" * (64 * 1024 + 1),
        encoding="utf-8",
    )

    with pytest.raises(RepositoryError, match="超过"):
        RepositoryExplorer(tmp_path).read_file("large.txt")


def test_search_returns_line_numbers(tmp_path: Path) -> None:
    """搜索应返回正确的文件、行号和内容。"""

    (tmp_path / "main.py").write_text(
        "hello\nDef Main():\npass\n",
        encoding="utf-8",
    )

    hits = RepositoryExplorer(tmp_path).search("def main")

    assert [(hit.path, hit.line_number, hit.line) for hit in hits] == [
        ("main.py", 2, "Def Main():")
    ]


def test_search_rejects_empty_keyword(tmp_path: Path) -> None:
    """空关键词不应该触发全仓库搜索。"""

    with pytest.raises(
        RepositoryError,
        match="不能为空",
    ):
        RepositoryExplorer(tmp_path).search("  ")


def test_hidden_directories_are_not_scanned_or_read(
    tmp_path: Path,
) -> None:
    """隐藏目录不允许被扫描或读取。"""

    hidden_dir = tmp_path / ".private"
    hidden_dir.mkdir()

    (hidden_dir / "note.py").write_text(
        "private = True\n",
        encoding="utf-8",
    )

    explorer = RepositoryExplorer(tmp_path)

    assert explorer.list_files() == []

    with pytest.raises(
        RepositoryError,
        match="隐藏文件或目录",
    ):
        explorer.read_file(".private/note.py")
```

### 5.2 test_cli.py — 完整代码

文件：`tests/test_cli.py`

保留 Day 01 的四个测试，新增三个命令测试。

```python
"""CLI 命令行功能测试。"""

from pathlib import Path

import pytest

from ai_software_dev_agent.cli import main


def test_doctor_accepts_existing_directory(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """有效项目目录应该检查成功。"""

    result = main(["doctor", "--project", str(tmp_path)])
    output = capsys.readouterr().out

    assert result == 0
    assert "项目目录检查通过" in output
    assert str(tmp_path.resolve()) in output


def test_doctor_rejects_missing_directory(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """不存在的项目目录应该被拒绝。"""

    missing_path = tmp_path / "missing"

    with pytest.raises(SystemExit) as exc_info:
        main(["doctor", "--project", str(missing_path)])

    assert exc_info.value.code == 2
    assert "项目目录不存在" in capsys.readouterr().err


def test_doctor_uses_current_directory_by_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """未指定项目目录时使用当前工作目录。"""

    monkeypatch.chdir(tmp_path)

    result = main(["doctor"])
    output = capsys.readouterr().out

    assert result == 0
    assert str(tmp_path.resolve()) in output


def test_help_displays_doctor_command(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """帮助信息应该包含 doctor 命令。"""

    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])

    assert exc_info.value.code == 0
    assert "doctor" in capsys.readouterr().out


def test_inspect_lists_files(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """CLI 应该能列出仓库代码文件。"""

    (tmp_path / "a.py").write_text("pass\n", encoding="utf-8")

    result = main(
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
    """CLI 应该能显示指定文件内容。"""

    (tmp_path / "a.py").write_text(
        "value = 42\n",
        encoding="utf-8",
    )

    result = main(
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
    """CLI 应该能显示带行号的搜索结果。"""

    (tmp_path / "a.py").write_text(
        "def main():\n    pass\n",
        encoding="utf-8",
    )

    result = main(
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
```

### 5.3 测试重点解释

本次总共 16 个测试：9 个仓库探索测试，加上 7 个 CLI 测试。

重点理解三个测试设计。

**1. 使用 tmp_path 避免污染真实项目**

```python
def test_read_file(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text(
        "hello = '你好'\n",
        encoding="utf-8",
    )
```

`tmp_path` 是 pytest 提供的 Fixture（测试夹具），会生成独立临时目录。

测试时先创建临时项目，再调用真实的业务方法，不需要修改开发仓库。

**2. 验证非法操作必须被拒绝**

```python
with pytest.raises(
    RepositoryError,
    match="不在指定项目目录内",
):
    RepositoryExplorer(tmp_path).read_file("../outside.py")
```

这里验证的是安全边界，而不是正常读取功能。

当路径越界时，程序必须抛出预期异常。

**3. 测试具体结果，而不仅是是否执行成功**

```python
assert [(hit.path, hit.line_number, hit.line) for hit in hits] == [
    ("main.py", 2, "Def Main():")
]
```

该断言同时验证：

- 搜索不区分大小写。
- 返回正确的路径。
- 行号从 1 开始。
- 返回正确的匹配内容。

测试执行：

```bash
python -m pytest tests/test_repository.py -v
python -m pytest tests/test_cli.py -v
python -m pytest -v
```

实际测试结果：**16 passed**。

---

## 6. 当天疑问与知识补充

### 6.1 Path.cwd() 是什么意思？

`cwd` 是 Current Working Directory（当前工作目录）。

```python
from pathlib import Path

print(Path.cwd())
```

假设在终端中进入：

```bash
cd ~/Documents/my-project
```

再运行 Python：

```python
print(Path.cwd())
```

可能输出：

```text
/Users/test/Documents/my-project
```

**它获取的是程序运行时的当前工作目录，不一定是 Python 源文件所在的目录。**

在本项目中：

```python
default = Path.cwd()
```

表示不指定 `--project` 时，默认使用当前工作目录。

### 6.2 expanduser() 和 resolve() 分别是什么意思？

`expanduser()` 用于展开用户主目录 `~`。

例如：

```python
path = Path("~/Documents/project")

print(path.expanduser())
```

结果类似：

```text
/Users/test/Documents/project
```

`resolve()` 用于将路径转换为规范化绝对路径，并解析符号链接。

例如当前工作目录为 `/Users/test/project`：

```python
path = Path("./src/../tests/test_cli.py")

print(path.resolve())
```

结果：

```text
/Users/test/project/tests/test_cli.py
```

因为：

- `.` 表示当前目录。
- `..` 表示上一级目录。
- `resolve()` 会消除这些相对路径成分，并解析符号链接。

因此：

```python
self.root = root.expanduser().resolve()
```

的执行顺序是：

```text
输入路径
   ↓
expanduser() 展开 ~
   ↓
resolve() 解析为绝对路径
   ↓
保存为项目根目录
```

例如：

```python
root = Path("~/Documents/project")

result = root.expanduser().resolve()
```

最终得到统一的绝对路径，便于后续文件操作。

### 6.3 is_relative_to() 是什么意思？为什么与 resolve() 配合？

`is_relative_to()` 用于判断一个路径是否位于另一个路径之下，或者与其相同。

例如：

```python
root = Path("/Users/test/project")

path1 = Path("/Users/test/project/main.py")
path2 = Path("/Users/test/other/secret.py")

print(path1.is_relative_to(root))  # True
print(path2.is_relative_to(root))  # False
```

在项目中：

```python
path = (self.root / given_path).resolve()

if not path.is_relative_to(self.root):
    raise RepositoryError("文件不在指定项目目录内")
```

假设：

```text
root = /Users/test/project
given_path = ../other/secret.py
```

执行 `resolve()` 后：

```text
/Users/test/other/secret.py
```

此时：

```python
path.is_relative_to(root)
```

返回 `False`，因此拒绝访问。

**两者的区别：**

- `resolve()`：将路径解析为实际的规范化绝对路径。
- `is_relative_to()`：判断解析后的路径是否属于允许的目录范围。

`is_relative_to()` 本身不会自动解析符号链接，所以这里需要先调用 `resolve()`。

### 6.4 为什么使用 dirnames[:] = ...？

这是为了真正控制 `os.walk()` 接下来扫描哪些目录。

先看普通列表赋值：

```python
a = ["src", ".venv"]
b = a

a = ["src"]

print(a)  # ["src"]
print(b)  # ["src", ".venv"]
```

`a = ["src"]` 创建新列表并重新绑定变量，并没有修改原来的列表。

再看切片赋值：

```python
a = ["src", ".venv"]
b = a

a[:] = ["src"]

print(a)  # ["src"]
print(b)  # ["src"]
```

`a[:] = ...` 是原地修改列表对象。

假设项目目录为：

```text
project/
├── src/
│   └── main.py
├── .venv/
│   └── library.py
└── README.md
```

执行：

```python
for current_dir, dirnames, filenames in os.walk("project"):
    print(dirnames)
```

第一次遍历时，`dirnames` 可能是：

```python
["src", ".venv"]
```

如果只写：

```python
dirnames = ["src"]
```

不会改变 `os.walk()` 保存的原列表，它仍可能继续进入 `.venv/`。

正确写法：

```python
dirnames[:] = ["src"]
```

修改了原列表，`os.walk()` 后续只会继续扫描 `src/`。

注意：这种控制依赖 `os.walk()` 默认的 `topdown=True` 模式。

### 6.5 file_path.suffix.lower() 是什么意思？

`suffix` 获取文件最后一个后缀，`lower()` 将字符串转换为小写。

例如：

```python
path = Path("Main.PY")

print(path.suffix)  # .PY
print(path.suffix.lower())  # .py
```

本项目通过：

```python
if file_path.suffix.lower() not in ALLOWED_SUFFIXES:
    continue
```

过滤文件类型。

这样 `main.py` 和 `Main.PY` 都能够被识别为 Python 文件。

需要注意：

```python
Path("archive.tar.gz").suffix
```

只会返回：

```text
.gz
```

而不是 `.tar.gz`。

另外，文件后缀合法不代表内容一定是正确的文本，因此还需要读取和解码检查。

### 6.6 path.stat().st_size 是什么意思？

`stat()` 用于获取文件元数据。

`st_size` 表示文件大小，单位为字节（Byte）。

例如：

```python
path = Path("main.py")

print(path.stat().st_size)
```

假设文件大小为 100 字节，则返回：

```text
100
```

在项目中：

```python
MAX_FILE_BYTES = 64 * 1024

if path.stat().st_size > MAX_FILE_BYTES:
    raise RepositoryError("文件超过大小限制")
```

64 × 1024 = 65,536 字节，即 64 KiB。

注意：**字节数不一定等于字符数。**

例如：

```python
text = "你好"

print(len(text))  # 2
print(len(text.encode("utf-8")))  # 6
```

因为两个汉字在 UTF-8 编码下通常占 6 字节。

### 6.7 keyword.casefold() 是什么意思？

`casefold()` 用于大小写归一化，适合进行不区分大小写的字符串匹配。

例如：

```python
keyword = "def main"
line = "Def Main():"

print(keyword.casefold() in line.casefold())
```

结果：

```text
True
```

`casefold()` 与 `lower()` 有什么区别？

普通英文中通常效果相近：

```python
"HELLO".lower()  # "hello"
"HELLO".casefold()  # "hello"
```

但部分 Unicode 字符不同：

```python
"Straße".lower()  # "straße"
"Straße".casefold()  # "strasse"
```

因此，`casefold()` 更适合一般 Unicode 文本的不区分大小写匹配。

本项目通过：

```python
needle = keyword.casefold()

if needle in line.casefold():
```

实现关键词搜索。

注意：这仍然是普通字符串搜索，不具备代码语义理解能力。

### 6.8 path.read_text(encoding="utf-8") 是什么意思？可以直接读取文件吗？

**可以，它能够直接读取整个文本文件，并返回 Python 字符串。**

假设 `hello.txt` 的内容是：

```text
你好，Python
```

执行：

```python
path = Path("hello.txt")

content = path.read_text(encoding="utf-8")

print(content)
```

输出：

```text
你好，Python
```

与传统写法类似：

```python
with open("hello.txt", "r", encoding="utf-8") as f:
    content = f.read()
```

`read_text()` 内部会打开、读取并关闭文件。

其中：

```python
encoding = "utf-8"
```

指定使用 UTF-8 编码解码文件内容。

注意：`read_text()` 会一次性将整个文件读入内存。因此对于超大文件，通常更适合逐行读取，而不是一次读取全部内容。

本项目先通过 `stat().st_size` 检查文件大小，再执行读取。

### 6.9 `file_path.relative_to(self.root).as_posix()` 是什么意思？

这行代码包含两个方法：

- `relative_to()`：计算相对于指定目录的路径。
- `as_posix()`：将路径转换为统一使用 `/` 分隔的字符串。

**整体作用：将文件绝对路径转换为相对于项目根目录的路径，并返回字符串。**

#### 1. `relative_to()`：转换为相对路径

假设项目结构：

```text
/Users/test/my-project/
├── src/
│   └── main.py
└── tests/
    └── test_main.py
```

示例：

```python
from pathlib import Path

root = Path("/Users/test/my-project")
file_path = Path("/Users/test/my-project/src/main.py")

result = file_path.relative_to(root)

print(result)  # src/main.py
print(type(result))  # <class 'pathlib.PosixPath'>（macOS/Linux）
```

`relative_to(root)` 表示以 `root` 为基准，计算目标文件的相对路径。

注意：

- 返回值仍然是 `Path` 对象。
- 如果目标路径不属于 `root`，会抛出 `ValueError`。
- 不会自动判断文件是否存在，也不会解析符号链接。

#### 2. `as_posix()`：转换为统一格式的字符串

示例：

```python
path = Path("src/main.py")

result = path.as_posix()

print(result)  # src/main.py
print(type(result))  # <class 'str'>
```

不同操作系统的路径分隔符可能不同：

| 操作系统 | 常见路径形式 |
|---|---|
| macOS / Linux | `src/main.py` |
| Windows | `src\main.py` |
| `as_posix()` | `src/main.py` |

因此，`as_posix()` 可以统一路径的字符串表示，方便后续 CLI、JSON 和 LangChain Tools 使用。

#### 3. 两个方法组合使用

Day 02 实际代码：

```python
found.append(file_path.relative_to(self.root).as_posix())
```

等价于：

```python
# 1. 计算相对于仓库根目录的路径
relative_path = file_path.relative_to(self.root)

# 2. 转换为使用 / 分隔的字符串
path_str = relative_path.as_posix()

# 3. 添加到文件列表
found.append(path_str)
```

转换过程：

```text
原始绝对路径：
/Users/test/my-project/src/main.py
            ↓
relative_to(self.root)
            ↓
src/main.py             # Path 对象
            ↓
as_posix()
            ↓
"src/main.py"           # str 字符串
```

**为什么这样设计？**

如果返回绝对路径：

```python
[
    "/Users/test/my-project/src/main.py",
    "/Users/test/my-project/tests/test_main.py",
]
```

路径包含本地环境信息，不方便在不同项目或设备之间使用。

转换成相对路径：

```python
[
    "src/main.py",
    "tests/test_main.py",
]
```

更加简洁，也便于后续 Agent 根据项目根目录定位文件。

#### 4. `relative_to()` 与 `is_relative_to()` 的区别

两个方法名称相似，但用途不同。

```python
root = Path("/Users/test/my-project")
path = Path("/Users/test/my-project/src/main.py")

# 计算相对路径
print(path.relative_to(root))
# src/main.py

# 判断是否位于指定目录内
print(path.is_relative_to(root))
# True
```

| 方法 | 作用 | 返回结果 |
|---|---|---|
| `relative_to(root)` | 计算相对路径 | `Path` 对象 |
| `is_relative_to(root)` | 判断路径是否属于指定目录 | `bool` |

**记忆方法：**

- `relative_to()`：我要得到相对路径。
- `is_relative_to()`：我要判断是不是这个目录下的路径。
- `as_posix()`：我要得到统一使用 `/` 的路径字符串。

---

