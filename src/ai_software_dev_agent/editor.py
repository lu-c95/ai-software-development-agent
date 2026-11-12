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
