"""Integration tests for the dotbins module."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any, Callable
from unittest.mock import MagicMock, patch

import pytest

from dotbins import cli
from dotbins.config import Config, build_tool_config

if TYPE_CHECKING:
    from pathlib import Path

    from _pytest.capture import CaptureFixture
    from _pytest.monkeypatch import MonkeyPatch


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
    capsys: CaptureFixture[str],
) -> None:
    """Test the 'list' command."""
    # Create a test tool configuration
    test_tool_config = build_tool_config(
        tool_name="test-tool",
        raw_data={
            "repo": "test/tool",
            "extract_binary": True,
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


def test_update_tools(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    mock_github_api: Any,  # noqa: ARG001
) -> None:
    """Test updating tools."""
    # Set up test tools directory
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)

    # Create mock config
    config = MagicMock(spec=Config)

    # Mock the update_tools method to return a successful result
    config.update_tools.return_value = (
        1,
        {
            "updated": [
                {
                    "tool": "test-tool1",
                    "platform": "linux",
                    "arch": "amd64",
                    "version": "1.0.0",
                    "old_version": "none",
                },
            ],
            "skipped": [
                {
                    "tool": "test-tool2",
                    "platform": "linux",
                    "arch": "amd64",
                    "version": "1.0.0",
                    "reason": "Already up-to-date",
                },
            ],
            "failed": [],
        },
    )

    # Call update_tools through the CLI function
    updated_count, summary = cli._update_tools(
        config=config,
        tools=["test-tool1", "test-tool2"],
        platform="linux",
        architecture="amd64",
        current=False,
        force=False,
        shell_setup=False,
        generate_readme=False,
        copy_config_file=False,
    )

    # Verify config.update_tools was called with the correct parameters
    config.update_tools.assert_called_once_with(
        ["test-tool1", "test-tool2"],
        "linux",
        "amd64",
        False,
        False,
        False,
        False,
    )

    # Verify results
    assert updated_count == 1
    assert "updated" in summary
    assert "skipped" in summary
    assert "failed" in summary
    assert len(summary["updated"]) == 1
    assert len(summary["skipped"]) == 1
    assert len(summary["failed"]) == 0
    assert summary["updated"][0]["tool"] == "test-tool1"
    assert summary["skipped"][0]["tool"] == "test-tool2"


def test_cli_no_command(capsys: CaptureFixture[str]) -> None:
    """Test running CLI with no command."""
    with patch.object(sys, "argv", ["dotbins"]):
        cli.main()

    # Should show help
    captured = capsys.readouterr()
    assert "usage: dotbins" in captured.out


def test_cli_unknown_tool() -> None:
    """Test updating an unknown tool."""
    with (
        pytest.raises(SystemExit),
        patch.object(sys, "argv", ["dotbins", "update", "unknown-tool"]),
        patch.object(
            Config,
            "from_file",
            return_value=Config(),
        ),
    ):
        cli.main()


def test_cli_tools_dir_override(tmp_path: Path) -> None:
    """Test overriding tools directory via CLI."""
    custom_dir = tmp_path / "custom_tools"

    # Mock config loading to return a predictable config
    def mock_load_config(
        *args: Any,  # noqa: ARG001
        **kwargs: Any,  # noqa: ARG001
    ) -> Config:
        return Config(
            tools_dir=tmp_path / "default_tools",  # Default dir
            platforms={"linux": ["amd64"]},  # Use new format
        )

    # Patch config loading
    with (
        patch.object(Config, "from_file", mock_load_config),
        patch.object(sys, "argv", ["dotbins", "--tools-dir", str(custom_dir), "init"]),
    ):
        cli.main()

    # Check if directories were created in the custom location
    assert (custom_dir / "linux" / "amd64" / "bin").exists()


def test_update_tool(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    mock_github_api: Any,  # noqa: ARG001
    create_dummy_archive: Callable,
) -> None:
    """Test updating a specific tool."""
    # Create mock config
    config = MagicMock(spec=Config)

    # Mock the update_tools method to return a successful result
    config.update_tools.return_value = (
        1,
        {
            "updated": [
                {
                    "tool": "test-tool",
                    "platform": "linux",
                    "arch": "amd64",
                    "version": "1.0.0",
                    "old_version": "none",
                },
            ],
            "skipped": [],
            "failed": [],
        },
    )

    # Call update_tools through the CLI function
    updated_count, summary = cli._update_tools(
        config=config,
        tools=["test-tool"],
        platform="linux",
        architecture="amd64",
        current=False,
        force=False,
        shell_setup=False,
        generate_readme=False,
        copy_config_file=False,
    )

    # Verify config.update_tools was called with the correct parameters
    config.update_tools.assert_called_once_with(
        ["test-tool"],
        "linux",
        "amd64",
        False,
        False,
        False,
        False,
    )

    # Verify results
    assert updated_count == 1
    assert "updated" in summary
    assert "skipped" in summary
    assert "failed" in summary
    assert len(summary["updated"]) == 1
    assert summary["updated"][0]["tool"] == "test-tool"
