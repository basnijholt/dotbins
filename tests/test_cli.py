"""Integration tests for the dotbins module."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

from dotbins import cli
from dotbins.config import Config, build_tool_config

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_initialization(
    tmp_path: Path,
) -> None:
    """Test the 'init' command."""
    # Create a config with our test directories
    config = Config(
        tools_dir=tmp_path / "tools",
        platforms={"linux": ["amd64", "arm64"], "macos": ["arm64"]},
    )

    # Call initialize with the config
    cli._initialize(config=config)

    # Check if directories were created - only for valid platform/arch combinations
    platform_archs = [("linux", "amd64"), ("linux", "arm64"), ("macos", "arm64")]

    for platform, arch in platform_archs:
        assert (tmp_path / "tools" / platform / arch / "bin").exists()

    # Also verify that macos/amd64 does NOT exist
    assert not (tmp_path / "tools" / "macos" / "amd64" / "bin").exists()


def test_list_tools(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test the 'list' command."""
    # Create a test tool configuration
    test_tool_config = build_tool_config(
        tool_name="test-tool",
        raw_data={
            "repo": "test/tool",
            "extract_archive": True,
            "binary_name": "test-tool",
            "binary_path": "test-tool",
            "asset_patterns": "test-tool-{version}-{platform}_{arch}.tar.gz",
        },
    )

    # Create config with our test tools
    config = Config(
        tools={"test-tool": test_tool_config},
        tools_dir=tmp_path / "tools",
    )

    # Directly call the list_tools function
    cli._list_tools(config)

    # Check if tool was listed
    captured = capsys.readouterr()
    assert "test-tool" in captured.out
    assert "test/tool" in captured.out


def test_cli_no_command(capsys: pytest.CaptureFixture[str]) -> None:
    """Test running CLI with no command."""
    with patch.object(sys, "argv", ["dotbins"]):
        cli.main()

    # Should show help
    captured = capsys.readouterr()
    assert "Usage: dotbins" in captured.out


def test_cli_tools_dir_override(tmp_path: Path) -> None:
    """Test overriding tools directory via CLI."""
    custom_dir = tmp_path / "custom_tools"

    # Mock config loading to return a predictable config
    def mock_load_config(
        *args: Any,  # noqa: ARG001
        **kwargs: Any,  # noqa: ARG001
    ) -> Config:
        return Config(
            tools_dir=tmp_path / "default_tools",
            platforms={"linux": ["amd64"]},
        )

    # Patch config loading
    with (
        patch.object(Config, "from_file", mock_load_config),
        patch.object(sys, "argv", ["dotbins", "--tools-dir", str(custom_dir), "init"]),
    ):
        cli.main()

    # Check if directories were created in the custom location
    assert (custom_dir / "linux" / "amd64" / "bin").exists()


def test_cli_argument_parsing() -> None:
    """Test CLI argument parsing for readme and no-readme options."""
    parser = cli.create_parser()

    # Test readme command
    args = parser.parse_args(["readme"])
    assert args.command == "readme"

    # Test sync with --no-readme
    args = parser.parse_args(["sync", "--no-readme"])
    assert args.command == "sync"
    assert args.no_readme is True

    # Test sync without --no-readme (default)
    args = parser.parse_args(["sync"])
    assert args.command == "sync"
    assert args.no_readme is False
