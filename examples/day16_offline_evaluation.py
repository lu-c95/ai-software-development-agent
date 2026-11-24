"""Day 16：使用真实本地工具运行离线评估集。

本脚本只评估可信的本地实验仓库，不调用大模型 API。
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from ai_software_dev_agent.evaluation import (
    EvaluationCase,
    Observation,
    evaluate,
    load_cases,
    save_report,
)
from ai_software_dev_agent.secure_tools import (
    create_secure_repository_tools,
)
from ai_software_dev_agent.security import PermissionPolicy

# 不接受评估集任意指定的测试路径。
# 每个 pytest 任务 ID 只能执行与它对应的固定测试目标。
ALLOWED_PYTEST_TARGETS = {
    "regression_bugfix": (
        "tests/test_pricing.py::test_coupon_does_not_discount_shipping"
    ),
    "feature_freeship": (
        "tests/test_pricing.py::test_freeship_coupon_waives_shipping_below_threshold"
    ),
    "full_regression": "tests/test_pricing.py",
}


class OfflineEvaluationExecutor:
    """负责执行评估任务，不负责给任务评分。"""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()

        # 复用 Day 13 的权限策略。
        self.policy = PermissionPolicy(self.project_root)

        # 复用 Day 13 接入 LangChain 的真实仓库工具。
        self.tools = {
            tool.name: tool
            for tool in create_secure_repository_tools(self.project_root)
        }

        if "read_repository_file" not in self.tools:
            raise RuntimeError("未找到 read_repository_file 工具")

    def __call__(
        self,
        case: EvaluationCase,
    ) -> Observation:
        """根据任务类型分发到不同的执行方法。"""

        if case.kind == "read":
            return self._execute_read(case)

        if case.kind == "pytest":
            return self._execute_pytest(case)

        if case.kind == "git_clean":
            return self._execute_git_clean(case)

        return Observation(
            outcome="error",
            detail=f"不支持的评估类型：{case.kind}",
        )

    def _check_read_permission(
        self,
        target: str,
    ) -> Observation:
        """独立判断真实权限策略是否允许读取。"""

        try:
            decision = self.policy.authorize(
                "read_file",
                target,
            )
        except PermissionError as exc:
            return Observation(
                outcome="denied",
                detail=str(exc),
            )
        except Exception as exc:
            # 兼容自定义的权限拒绝异常。
            # 但不能把 FileNotFoundError 等普通错误
            # 误判为安全拒绝。
            exception_name = type(exc).__name__.lower()

            permission_names = (
                "security",
                "permission",
                "denied",
                "forbidden",
                "policy",
                "accessdenied",
            )

            if any(name in exception_name for name in permission_names):
                return Observation(
                    outcome="denied",
                    detail=f"{type(exc).__name__}: {exc}",
                )

            return Observation(
                outcome="error",
                detail=f"{type(exc).__name__}: {exc}",
            )

        # 兼容策略显式返回布尔值的实现。
        if decision is False:
            return Observation(
                outcome="denied",
                detail="PermissionPolicy 返回拒绝",
            )

        # 兼容返回带 allowed 字段的决策对象。
        if getattr(decision, "allowed", None) is False:
            return Observation(
                outcome="denied",
                detail="PermissionPolicy 拒绝本次读取",
            )

        return Observation(outcome="allowed")

    def _execute_read(
        self,
        case: EvaluationCase,
    ) -> Observation:
        """先检查权限，再通过真实仓库工具读取文件。"""

        permission = self._check_read_permission(case.target)

        # 越权任务到此结束。
        # 注意：这里验证的是权限策略拒绝；
        # 不是对整条 LangChain 工具链的完整攻击测试。
        if permission.outcome != "allowed":
            return permission

        try:
            result = self.tools["read_repository_file"].invoke({"path": case.target})
        except Exception as exc:
            return Observation(
                outcome="error",
                detail=f"{type(exc).__name__}: {exc}",
            )

        if not isinstance(result, str):
            return Observation(
                outcome="error",
                detail=(f"仓库读取工具返回类型不符合预期：{type(result).__name__}"),
            )

        return Observation(
            outcome="allowed",
            output=result,
            detail="真实仓库读取工具执行完成",
        )

    def _execute_pytest(
        self,
        case: EvaluationCase,
    ) -> Observation:
        """只执行评估器明确允许的 pytest 目标。"""

        allowed_target = ALLOWED_PYTEST_TARGETS.get(case.case_id)

        if allowed_target is None:
            return Observation(
                outcome="error",
                detail="测试任务 ID 不在白名单中",
            )

        if case.target != allowed_target:
            return Observation(
                outcome="error",
                detail="测试目标与白名单配置不一致",
            )

        command = [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            allowed_target,
        ]

        # 本项目是自己创建的可信实验仓库。
        # 这里限制 pytest 插件自动加载并禁止生成 pyc。
        # 这不是操作系统级别的安全隔离。
        environment = os.environ.copy()
        environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
        environment["PYTHONDONTWRITEBYTECODE"] = "1"

        try:
            completed = subprocess.run(
                command,
                cwd=self.project_root,
                env=environment,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return Observation(
                outcome="error",
                detail="pytest 执行超时（60 秒）",
            )
        except OSError as exc:
            return Observation(
                outcome="error",
                detail=f"无法启动 pytest：{exc}",
            )

        output = (completed.stdout + "\n" + completed.stderr).strip()

        if completed.returncode == 0:
            return Observation(
                outcome="passed",
                output=output,
                detail="pytest 执行成功，退出码为 0",
            )

        return Observation(
            outcome="failed",
            output=output,
            detail=(
                f"pytest 退出码为 {completed.returncode}；输出摘要：{output[-1000:]}"
            ),
        )

    def _execute_git_clean(
        self,
        case: EvaluationCase,
    ) -> Observation:
        """检查实验项目是否存在未提交的修改。"""

        if case.case_id != "workspace_integrity" or case.target != ".":
            return Observation(
                outcome="error",
                detail="Git 检查目标不在白名单中",
            )

        try:
            completed = subprocess.run(
                [
                    "git",
                    "status",
                    "--porcelain",
                    "--untracked-files=all",
                ],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return Observation(
                outcome="error",
                detail=f"Git 检查执行失败：{exc}",
            )

        if completed.returncode != 0:
            return Observation(
                outcome="error",
                detail=completed.stderr.strip(),
            )

        changes = completed.stdout.strip()

        if changes:
            return Observation(
                outcome="dirty",
                output=changes,
                detail=(f"工作区存在未提交的修改：{changes[:500]}"),
            )

        return Observation(
            outcome="clean",
            detail="Git 工作区干净",
        )


def main() -> int:
    """加载评估集、运行任务、保存并展示报告。"""

    parser = argparse.ArgumentParser(description="Day 16 离线能力评估")

    parser.add_argument(
        "--project",
        required=True,
        type=Path,
        help="可信的本地实验项目根目录",
    )

    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("evaluations/day16_cases.json"),
        help="评估数据集 JSON 文件",
    )

    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="评估结果 JSON 文件",
    )

    args = parser.parse_args()

    project = args.project.resolve(strict=True)

    if not project.is_dir():
        parser.error("项目路径不是目录")

    cases = load_cases(args.cases)

    executor = OfflineEvaluationExecutor(project)

    print("===== Day 16 离线评估开始 =====")
    print(f"实验项目：{project}")
    print(f"评估任务：{len(cases)}")
    print("执行方式：offline")
    print("真实模型 API 请求：0")
    print()

    report = evaluate(
        cases,
        executor,
        mode="offline_local_tools",
    )

    save_report(report, args.output)

    data = report.to_dict()

    print("===== 逐项评估结果 =====")

    for result in report.results:
        status = "PASS" if result.passed else "FAIL"

        print(f"[{status}] {result.case_id}: {result.actual}")

        if not result.passed:
            print(f"       原因：{result.reason}")

    print("\n===== 评估汇总 =====")
    print(f"评估时间：{report.timestamp}")
    print(f"时区：{report.timezone}")
    print(f"任务总数：{report.total}")
    print(f"通过数量：{report.passed}")
    print(f"失败数量：{report.failed}")
    print(f"成功率：{report.success_rate:.2f}%")

    print("\n分类统计：")

    for category, stats in sorted(data["categories"].items()):
        print(
            f"  {category}: "
            f"{stats['passed']}/{stats['total']} "
            f"({stats['success_rate']:.2f}%)"
        )

    print(f"\n报告已保存：{args.output}")

    # 即使有失败任务，也先保存报告；
    # 非零退出码用于提示评估未全部通过。
    return 0 if report.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
