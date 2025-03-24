"""Tests for README generation functionality."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from dotbins.config import Config
from dotbins.readme import generate_readme_content, write_readme_file


@pytest.fixture
def mock_config() -> Config:
    """Create a mock Config object for testing."""
    config = MagicMock(spec=Config)
    config.tools_dir = Path("/home/user/.dotbins")
    config.platforms = {"linux": ["amd64", "arm64"], "macos": ["arm64"]}

    # Mock tools
    tool1 = MagicMock()
    tool1.tool_name = "tool1"
    tool1.repo = "user/tool1"
    tool1.binary_name = ["tool1"]

    tool2 = MagicMock()
    tool2.tool_name = "tool2"
    tool2.repo = "user/tool2"
    tool2.binary_name = ["tool2"]

    config.tools = {"tool1": tool1, "tool2": tool2}

    # Mock version store
    version_store = MagicMock()
    version_store.get_tool_info.side_effect = lambda tool, _platform, _arch: (
        {
            "version": "1.0.0",
            "updated_at": "2023-01-01",
        }
        if tool in ["tool1", "tool2"]
        else None
    )

    config.version_store = version_store

    # Mock bin_dir to return a non-existent directory
    config.bin_dir.return_value = MagicMock()
    config.bin_dir.return_value.exists.return_value = False

    return config


@patch("dotbins.readme.current_platform")
def test_generate_readme_content(mock_current_platform: MagicMock, mock_config: Config) -> None:
    """Test that README content is correctly generated."""
    # Mock the current platform
    mock_current_platform.return_value = ("macos", "arm64")

    # Patch os.path.expanduser to return a fixed path for testing
    with (
        patch("os.path.expanduser", return_value="/home/user"),
        patch("pathlib.Path.exists", return_value=False),
        patch("pathlib.Path.stat", return_value=MagicMock(st_size=1024)),
    ):
        # Ensure config_path is None to generate "Configuration file not found"
        mock_config.config_path = None

        # Generate content
        content = generate_readme_content(mock_config)

    # Verify expected sections are in the content
    assert "# 🛠️ dotbins Tool Collection" in content
    assert (
        "[![dotbins](https://img.shields.io/badge/powered%20by-dotbins-blue.svg?style=flat-square)]"
        in content
    )
    assert "## 📋 Table of Contents" in content
    assert "- [What is dotbins?](#-what-is-dotbins)" in content
    assert "## 📦 What is dotbins?" in content
    assert "## 🔍 Installed Tools" in content
    assert "## 📊 Tool Statistics" in content
    assert "📦" in content
    assert "Tools" in content
    assert "Total Size" in content
    assert (
        "| Tool | Total Size | Avg Size per Architecture |" in content
    )  # Check for new table header
    assert "| :--- | :-------- | :------------------------ |" in content
    assert "## 💻 Shell Integration" in content
    assert "For **Bash**:" in content
    assert "For **Zsh**:" in content
    assert "For **Fish**:" in content
    assert "For **Nushell**:" in content
    assert "## 🔄 Installing and Updating Tools" in content
    assert "## 🚀 Quick Commands" in content
    assert "## 📁 Configuration File" in content
    assert "Configuration file not found" in content

    # Check if tools are in the content
    assert "[tool1]" in content
    assert "[tool2]" in content
    assert "user/tool1" in content
    assert "user/tool2" in content
    assert "1.0.0" in content

    # Verify home directory replacement
    assert "/home/user" not in content

    # Check platform information
    assert "linux (amd64, arm64)" in content
    assert "macos (arm64)" in content

    # Verify date format
    # Should format 2023-01-01 to something like Jan 01, 2023
    assert "Jan 01, 2023" in content


def test_write_readme_file() -> None:
    """Test that README file is correctly written."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # Create mock config
        config = MagicMock(spec=Config)
        config.tools_dir = tmp_path

        # Mock generate_readme_content to return a simple string
        with patch("dotbins.readme.generate_readme_content", return_value="# Test README"):
            # Call the function
            write_readme_file(config, print_content=True, write_file=True, verbose=True)

            # Check if file was created
            readme_path = tmp_path / "README.md"
            assert readme_path.exists()

            # Check content
            with open(readme_path) as f:
                content = f.read()
                assert content == "# Test README"


@patch("dotbins.readme.current_platform")
def test_readme_with_missing_tools(mock_current_platform: MagicMock, mock_config: Config) -> None:
    """Test README generation when some tools have no version info."""
    # Mock the current platform
    mock_current_platform.return_value = ("macos", "arm64")

    # Update mock to return None for tool2
    mock_config.version_store.get_tool_info.side_effect = lambda tool, _platform, _arch: (  # type: ignore[attr-defined]
        {
            "version": "1.0.0",
            "updated_at": "2023-01-01",
        }
        if tool == "tool1"
        else None
    )

    # Generate content
    content = generate_readme_content(mock_config)

    # Verify tool1 is in the content
    assert "[tool1]" in content

    # tool2 should still be in the tools list but might not appear in the table
    # as it has no installation info


@patch("dotbins.readme.current_platform")
def test_readme_with_home_path_replacement(
    mock_current_platform: MagicMock,
    mock_config: Config,
) -> None:
    """Test that home paths are correctly replaced with $HOME."""
    # Mock the current platform
    mock_current_platform.return_value = ("macos", "arm64")

    # Set up a path with a real home directory
    with patch("os.path.expanduser", return_value="/home/testuser"):
        # Set the tools directory path to include the home path
        mock_config.tools_dir = Path("/home/testuser/some/path")

        # Generate content
        content = generate_readme_content(mock_config)

        # Verify home directory is replaced
        assert "$HOME/some/path" in content
        assert "/home/testuser/some/path" not in content


@patch("dotbins.readme.current_platform")
def test_readme_table_formatting(mock_current_platform: MagicMock, mock_config: Config) -> None:
    """Test that the table in the README is correctly formatted."""
    # Mock the current platform
    mock_current_platform.return_value = ("macos", "arm64")

    # Generate content
    content = generate_readme_content(mock_config)

    # Check table headers
    assert "| Tool | Repository | Version | Updated | Platforms & Architectures |" in content
    assert "| :--- | :--------- | :------ | :------ | :------------------------ |" in content

    # Verify bullet separator is used between platforms
    assert " • " in content


def test_write_readme_file_handles_exception(
    capsys: pytest.CaptureFixture,
) -> None:
    """Test that write_readme_file properly handles exceptions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir)

        # Create mock config
        config = MagicMock(spec=Config)
        config.tools_dir = Path("/non/existent/path")  # Path that doesn't exist

        # Mock generate_readme_content to return a simple string
        with (
            patch("dotbins.readme.generate_readme_content", return_value="# Test README"),
        ):
            # Call the function
            write_readme_file(config, verbose=True)

            # Verify exception is logged
            captured = capsys.readouterr()
            out = captured.out
            assert "No such file or directory" in out, out
