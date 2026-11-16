"""Day 13：软件开发 Agent 的最小权限访问策略。"""

from dataclasses import dataclass
from pathlib import Path


class PermissionDenied(PermissionError):
    """工具操作未获得授权，或目标违反安全策略。"""


# 第一阶段允许读取的项目路径。
# 模型无法通过工具参数修改这份允许列表。
ALLOWED_READ_ROOTS = (
    "src",
    "tests",
    "docs",
    "README.md",
    "pyproject.toml",
)

# 拒绝访问的敏感文件名称。
DENIED_FILE_NAMES = frozenset(
    {
        "credentials.json",
        "secrets.json",
        "secrets.toml",
        "token.json",
        "id_rsa",
        "id_ed25519",
        "authorized_keys",
    }
)

# 典型私钥、证书及本地数据库文件扩展名。
DENIED_SUFFIXES = frozenset(
    {
        ".pem",
        ".key",
        ".p12",
        ".pfx",
        ".sqlite",
        ".sqlite3",
        ".db",
    }
)


@dataclass(frozen=True)
class PermissionPolicy:
    """只允许安全范围内的只读仓库操作。"""

    project_root: Path
    max_read_bytes: int = 64 * 1024

    def __post_init__(self) -> None:
        """初始化策略时校验受信任的项目根目录。"""

        root = self.project_root.expanduser().resolve()

        if not root.is_dir():
            raise ValueError(f"项目目录不存在：{root}")

        if (
            isinstance(self.max_read_bytes, bool)
            or not isinstance(self.max_read_bytes, int)
            or self.max_read_bytes <= 0
        ):
            raise ValueError("文件读取上限必须是正整数")

        # dataclass(frozen=True) 不允许普通属性赋值，
        # 初始化阶段通过 object.__setattr__ 保存规范化路径。
        object.__setattr__(self, "project_root", root)

    def authorize(
        self,
        action: str,
        relative_path: str | None = None,
    ) -> Path:
        """验证工具操作；没有显式允许的操作全部拒绝。"""

        # 目前只有读取文件是开放的工具权限。
        if action != "read_file":
            raise PermissionDenied(
                f"操作未授权：{action}。当前策略只允许受限制的文件读取。"
            )

        if not isinstance(relative_path, str) or not relative_path.strip():
            raise PermissionDenied("文件路径不能为空")

        relative = Path(relative_path)

        # 禁止绝对路径、根目录自身和路径穿越。
        if (
            relative.is_absolute()
            or relative == Path(".")
            or ".." in relative.parts
            or "\x00" in relative_path
        ):
            raise PermissionDenied("文件路径必须是安全的项目内相对路径")

        # 默认拒绝隐藏文件及隐藏目录，例如 .env、.git、.venv。
        if any(part.startswith(".") for part in relative.parts):
            raise PermissionDenied("禁止访问隐藏文件或隐藏目录")

        # 显式拒绝典型凭据、私钥与数据库文件。
        name = relative.name.casefold()

        if name in DENIED_FILE_NAMES or relative.suffix.casefold() in DENIED_SUFFIXES:
            raise PermissionDenied("禁止访问敏感文件")

        # 必须匹配完整路径组成部分，不能用字符串 startswith。
        # 避免 src-private/ 被错误识别为 src/。
        allowed = any(
            relative == Path(root) or Path(root) in relative.parents
            for root in ALLOWED_READ_ROOTS
        )

        if not allowed:
            raise PermissionDenied("路径不在允许读取的范围内")

        # 逐级拒绝符号链接，包括指向仓库内的符号链接。
        # 第一阶段采用保守策略，不尝试判断每个链接是否可信。
        current = self.project_root

        for part in relative.parts:
            current = current / part

            if current.is_symlink():
                raise PermissionDenied("不允许通过符号链接访问文件")

        target = current.resolve()

        # 解析后仍需确认目标位于项目根目录内。
        if target == self.project_root or not target.is_relative_to(self.project_root):
            raise PermissionDenied("目标文件超出项目根目录")

        if not target.is_file():
            raise FileNotFoundError(f"目标不是已存在的普通文件：{target}")

        return target

    def read_text(self, relative_path: str) -> str:
        """经过授权后读取 UTF-8 文本，并限制返回数据大小。"""

        target = self.authorize("read_file", relative_path)

        # 多读取一个字节，以确认文件是否超过限制。
        # 不使用 read_bytes() 直接加载可能很大的整个文件。
        with target.open("rb") as file:
            content = file.read(self.max_read_bytes + 1)

        if len(content) > self.max_read_bytes:
            raise PermissionDenied(f"文件超过最大读取限制：{self.max_read_bytes} 字节")

        try:
            return content.decode("utf-8")

        except UnicodeDecodeError as exc:
            raise PermissionDenied("只允许读取 UTF-8 文本文件") from exc
