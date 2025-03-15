"""Integration tests for the dotbins module."""

import shutil
import sys
import tempfile
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import yaml
from _pytest.capture import CaptureFixture
from _pytest.monkeypatch import MonkeyPatch

from dotbins import cli
from dotbins.config import Config, ToolConfig


class TestIntegration:
    """Integration tests for dotbins."""


@pytest.fixture
def tmp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdirname:
        yield Path(tmpdirname)


def test_initialization(
    tmp_dir: Path,
) -> None:
    """Test the 'init' command."""
    # Create a config with our test directories
    config = Config(
        tools_dir=tmp_dir / "tools",
        platforms={"linux": ["amd64", "arm64"], "macos": ["arm64"]},
        tools={},
    )

    # Call initialize with the config
    cli._initialize(None, config=config)

    # Check if directories were created - only for valid platform/arch combinations
    platform_archs = [("linux", "amd64"), ("linux", "arm64"), ("macos", "arm64")]

    for platform, arch in platform_archs:
        assert (tmp_dir / "tools" / platform / arch / "bin").exists()

    # Also verify that macos/amd64 does NOT exist
    assert not (tmp_dir / "tools" / "macos" / "amd64" / "bin").exists()


def test_list_tools(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    """Test the 'list' command."""
    # Create a test tool configuration
    test_tool_config = ToolConfig(
        tool_name="test-tool",
        repo="test/tool",
        extract_binary=True,
        binary_name="test-tool",
        binary_path="test-tool",
        asset_patterns="test-tool-{version}-{platform}_{arch}.tar.gz",
    )

    # Create config with our test tools
    config = Config(
        tools={"test-tool": test_tool_config},
        tools_dir=tmp_path / "tools",
    )

    # Directly call the list_tools function
    cli._list_tools(None, config)

    # Check if tool was listed
    captured = capsys.readouterr()
    assert "test-tool" in captured.out
    assert "test/tool" in captured.out


def test_update_tool(
    tmp_dir: Path,
    monkeypatch: MonkeyPatch,
    mock_github_api: Any,  # noqa: ARG001
) -> None:
    """Test updating a specific tool."""
    # Set up mock environment
    test_tool_config = ToolConfig(
        tool_name="test-tool",
        repo="test/tool",
        extract_binary=True,
        binary_name="test-tool",
        binary_path="*",
        asset_patterns={
            "linux": "test-tool-{version}-{platform}_{arch}.tar.gz",
            "macos": "test-tool-{version}-{platform}_{arch}.tar.gz",
        },
        platform_map={"macos": "darwin"},
    )

    # Create config with our test tool - use new format
    config = Config(
        tools_dir=tmp_dir / "tools",
        platforms={"linux": ["amd64"]},  # Just linux/amd64 for this test
        tools={"test-tool": test_tool_config},
    )

    # Create a test binary tarball
    _create_test_tarball(tmp_dir / "test_binary.tar.gz", "test-tool")

    # Mock the download_file function to use our test tarball
    def mock_download_file(_url: str, destination: str) -> str:
        shutil.copy(tmp_dir / "test_binary.tar.gz", destination)
        return destination

    # Mock download and extraction to avoid actual downloads
    monkeypatch.setattr("dotbins.download.download_file", mock_download_file)

    # Create a mock args object
    mock_args = MagicMock()
    mock_args.tools = ["test-tool"]
    mock_args.platform = "linux"  # Specify platform to avoid skipping
    mock_args.architecture = "amd64"
    mock_args.force = False
    mock_args.shell_setup = False
    mock_args.current = False

    # Directly call update_tools
    cli._update_tools(mock_args, config)

    # Check if binary was installed
    assert (tmp_dir / "tools" / "linux" / "amd64" / "bin" / "test-tool").exists()


def _create_test_tarball(path: Path, binary_name: str) -> None:
    """Create a test tarball with a binary inside."""
    import tarfile

    # Create a temporary directory
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a dummy binary file
        binary_path = Path(tmpdir) / binary_name
        with open(binary_path, "w") as f:
            f.write("#!/bin/sh\necho 'Hello from test tool'\n")

        # Make it executable
        binary_path.chmod(0o755)  # nosec: B103

        # Create tarball
        with tarfile.open(path, "w:gz") as tar:
            tar.add(binary_path, arcname=binary_name)


def test_analyze_tool(
    capsys: CaptureFixture[str],
    mock_github_api: Any,  # noqa: ARG001
) -> None:
    """Test analyzing a GitHub repo for release patterns."""
    # Run analyze command
    # We need to patch sys.exit to prevent it from actually exiting in the test
    with (
        patch.object(sys, "argv", ["dotbins", "analyze", "test/tool"]),
        patch.object(sys, "exit"),
    ):
        cli.main()

    # Check output
    captured = capsys.readouterr()
    assert "Analyzing releases for test/tool" in captured.out
    assert "Suggested configuration for YAML tools file" in captured.out

    # Check for proper YAML format
    assert "tool:" in captured.out  # The key should be output
    assert "repo: test/tool" in captured.out
    assert "extract_binary: true" in captured.out

    # Make sure the output is in valid YAML format
    yaml_text = captured.out.split("Suggested configuration for YAML tools file:")[
        1
    ].strip()
    yaml.safe_load(yaml_text)


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
            "load_from_file",
            return_value=Config(tools={}),
        ),
    ):
        cli.main()


def test_cli_tools_dir_override(tmp_dir: Path) -> None:
    """Test overriding tools directory via CLI."""
    custom_dir = tmp_dir / "custom_tools"

    # Mock config loading to return a predictable config
    def mock_load_config(
        *args: Any,  # noqa: ARG001
        **kwargs: Any,  # noqa: ARG001
    ) -> Config:
        return Config(
            tools_dir=tmp_dir / "default_tools",  # Default dir
            platforms={"linux": ["amd64"]},  # Use new format
            tools={},
        )

    # Patch config loading
    with (
        patch.object(Config, "load_from_file", mock_load_config),
        patch.object(sys, "argv", ["dotbins", "--tools-dir", str(custom_dir), "init"]),
    ):
        cli.main()

    # Check if directories were created in the custom location
    assert (custom_dir / "linux" / "amd64" / "bin").exists()
