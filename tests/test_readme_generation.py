"""Tests for README generation functionality."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from dotbins.config import Config
from dotbins.readme import generate_readme_content, write_readme_file


@pytest.fixture
def mock_config(tmp_path: Path) -> Config:
    """Create a mock Config object for testing."""
    return Config.from_dict(
        {
            "tools_dir": str(tmp_path),
            "tools": {
                "tool1": {"repo": "owner1/repo1"},
                "tool2": {"repo": "owner2/repo2", "tag": "v1.0.0"},
            },
            "platforms": {
                "linux": ["amd64", "arm64"],
                "macos": ["arm64"],
            },
        },
    )


@patch("dotbins.readme.current_platform")
def test_generate_readme_content(mock_current_platform: MagicMock, mock_config: Config) -> None:
    """Test that README content is correctly generated."""
    # Mock the current platform
    mock_current_platform.return_value = ("macos", "arm64")

    # Mock lock_file_handler.get_tool_info on the instance
    mock_config._lock_file.get_tool_info = MagicMock(  # type: ignore[method-assign]
        side_effect=lambda tool, _platform, _arch: (
            {"tag": "v0.1.0", "updated_at": "2023-01-01T12:00:00"}
            if tool == "tool1"
            else {"tag": "v1.0.0", "updated_at": "2023-01-02T14:30:00"}
        ),
    )

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

    # Check table headers and rows
    assert (
        "| Tool  | Repository   | Tag (Version) | Updated    | Platforms & Architectures |"
        in content
    )
    assert (
        "| :---- | :----------- | :------------ | :--------- | :------------------------ |"
        in content
    )
    assert (
        "| tool1 | owner1/repo1 | v0.1.0        | 2023-01-01 | linux/amd64, linux/arm64, macos/arm64 |"
        in content
    )
    assert (
        "| tool2 | owner2/repo2 | v1.0.0        | 2023-01-02 | linux/amd64, linux/arm64, macos/arm64 |"
        in content
    )

    # Check usage section
    assert "## Usage" in content


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
    mock_config._lock_file.get_tool_info = MagicMock(  # type: ignore[method-assign]
        side_effect=lambda tool, _platform, _arch: (
            {
                "tag": "v1.0.0",  # Use v prefix
                "updated_at": "2023-01-01",
            }
            if tool == "tool1"
            else None
        ),
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


def test_generate_readme_no_tools(tmp_path: Path) -> None:
    """Test README generation with no tools configured."""
    config = Config.from_dict({"tools_dir": str(tmp_path), "tools": {}})
    # Mock lock_file_handler
    lock_file_handler = MagicMock()
    lock_file_handler.get_tool_info.return_value = None
    config._lock_file = lock_file_handler

    content = generate_readme_content(config)
    assert "**No tools are currently configured or installed.**" in content


def test_generate_readme_tool_not_installed(mock_config: Config) -> None:
    """Test README generation when some tools have no lock file info."""
    # Mock lock_file_handler to return None for tool1
    # Patch the method on the instance
    mock_config._lock_file.get_tool_info = MagicMock(  # type: ignore[method-assign]
        side_effect=lambda tool, _platform, _arch: (
            None if tool == "tool1" else {"tag": "v1.0.0", "updated_at": "2023-01-02T14:30:00"}
        ),
    )

    content = generate_readme_content(mock_config)

    # Check table headers and rows
    assert (
        "| Tool  | Repository   | Tag (Version) | Updated    | Platforms & Architectures |"
        in content
    )
    assert (
        "| :---- | :----------- | :------------ | :--------- | :------------------------ |"
        in content
    )
    # Expect tool1 to show as Not installed
    assert (
        "| tool1 | owner1/repo1 | Not installed | N/A        | *linux/amd64* (missing), *linux/arm64* (missing), *macos/arm64* (missing) |"
        in content
    )
    assert (
        "| tool2 | owner2/repo2 | v1.0.0        | 2023-01-02 | linux/amd64, linux/arm64, macos/arm64 |"
        in content
    )

    # Check usage section
    assert "## Usage" in content


def test_generate_readme_with_shell_code(mock_config: Config) -> None:
    """Test README generation includes tool-specific shell configurations."""
    mock_config.tools["tool1"].shell_code = {"bash": "echo tool1"}
    mock_config.tools["tool2"].shell_code = {"zsh": "alias t2=tool2"}
    # Mock lock_file_handler method on the instance
    mock_config._lock_file.get_tool_info = MagicMock(  # type: ignore[method-assign]
        return_value={"tag": "v0.1.0", "updated_at": "2023-01-01T12:00:00"},
    )

    content = generate_readme_content(mock_config)

    assert "## Tool-Specific Configurations" in content
    assert "### tool1" in content
    assert "```bash" in content
    assert "echo tool1" in content
    assert "### tool2" in content
    assert "```zsh" in content
    assert "alias t2=tool2" in content


def test_generate_readme_write_file(mock_config: Config, tmp_path: Path) -> None:
    """Test that generate_readme calls write_readme_file."""
    # Ensure config points to tmp_path
    with patch("dotbins.config.Config.tools_dir", new_callable=lambda: tmp_path):
        mock_config.tools_dir = tmp_path
    # Mock lock_file_handler method on the instance
    mock_config._lock_file.get_tool_info = MagicMock(  # type: ignore[method-assign]
        return_value={"tag": "v0.1.0", "updated_at": "2023-01-01T12:00:00"},
    )

    with patch("dotbins.readme.write_readme_file") as mock_write:
        mock_config.generate_readme(write_file=True, verbose=False)
        mock_write.assert_called_once_with(mock_config, verbose=False)

    with patch("dotbins.readme.write_readme_file") as mock_write:
        mock_config.generate_readme(write_file=False, verbose=True)
        mock_write.assert_not_called()
