"""安全地探索指定的 Python 项目仓库。"""

import os
from dataclasses import dataclass
from pathlib import Path

# 只分析常见代码与文本文件，避免读取不支持的文件类型。
ALLOWED_SUFFIXES = frozenset({".py", ".toml", ".md", ".txt", ".json", ".yaml", ".yml"})

# 不需要扫描的工程目录及运行时目录。
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
    """目标仓库或文件不满足当前工具的访问规则。"""


@dataclass(frozen=True)
class SearchHit:
    """一条代码搜索结果。"""

    path: str
    line_number: int
    line: str


class RepositoryExplorer:
    """仅在指定仓库内读取允许的文本文件，不进行任何修改。"""

    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve()

        if not self.root.is_dir():
            raise RepositoryError(f"项目目录不存在或不是文件夹：{self.root}")

    def list_files(self) -> list[str]:
        """扫描仓库文件，跳过忽略目录及符号链接。"""

        found: list[str] = []

        for current_dir, dirnames, filenames in os.walk(self.root, followlinks=False):
            current = Path(current_dir)

            # 原地裁剪子目录，防止进入缓存、虚拟环境及目录符号链接。
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
        """检查文件的实际路径、类型与大小。"""

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
        """读取仓库内允许的 UTF-8 文本文件。"""

        path = self._allowed_file(relative_path)

        try:
            return path.read_text(encoding="utf-8")
        except (UnicodeError, OSError) as exc:
            raise RepositoryError(f"文件读取失败：{relative_path}") from exc

    def search(self, keyword: str, limit: int = 20) -> list[SearchHit]:
        """在允许的文本文件内逐行搜索关键词，不区分大小写。"""

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
                # 大文件、无法解码的文件不参与本次搜索。
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
