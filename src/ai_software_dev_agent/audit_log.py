"""Day 13：为受控操作提供最小化 JSONL 审计日志。"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

# 项目涉及的日期、时间默认采用中国大陆标准时间。
CHINA_TIMEZONE = ZoneInfo("Asia/Shanghai")


AuditOutcome = Literal[
    "denied",
    "started",
    "finished",
    "timeout",
    "error",
]


@dataclass(frozen=True)
class AuditLogger:
    """记录操作结果，不记录源码、凭据或命令输出。"""

    path: Path
    project_root: Path

    def __post_init__(self) -> None:
        """规范化路径，禁止把审计日志写进项目仓库。"""

        root = self.project_root.expanduser().resolve()
        path = self.path.expanduser().resolve()

        if path.is_relative_to(root):
            raise ValueError("审计日志必须保存在项目目录之外")

        object.__setattr__(self, "path", path)
        object.__setattr__(self, "project_root", root)

    def record(
        self,
        operation: str,
        outcome: AuditOutcome,
        *,
        returncode: int | None = None,
        reason: str | None = None,
    ) -> None:
        """按照北京时间追加 JSONL 审计事件。"""

        # 明确采用 Asia/Shanghai，不依赖计算机的本地时区。
        now = datetime.now(CHINA_TIMEZONE)

        event = {
            # 北京时间，精确到毫秒，固定保留三位小数。
            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "timezone": "Asia/Shanghai",
            "operation": operation,
            "outcome": outcome,
            "returncode": returncode,
            "reason": reason,
        }

        self.path.parent.mkdir(parents=True, exist_ok=True)

        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")
