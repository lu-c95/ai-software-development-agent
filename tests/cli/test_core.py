"""CLI 统一入口与命令注册测试。"""

import pytest

from ai_software_dev_agent import cli


def test_main_help_lists_all_existing_commands(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """重构后，原有八个子命令都应继续存在。"""

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--help"])

    assert exc_info.value.code == 0

    output = capsys.readouterr().out

    for command in (
        "doctor",
        "inspect",
        "read",
        "search",
        "ask",
        "plan",
        "chat",
        "edit",
        "test",
    ):
        assert command in output


def test_main_requires_subcommand() -> None:
    """不提供子命令时仍应报告参数错误。"""

    with pytest.raises(SystemExit) as exc_info:
        cli.main([])

    assert exc_info.value.code == 2
