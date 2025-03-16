"""Tests for the analyze functionality of dotbins."""

import os
from pathlib import Path
from typing import Any, Callable
from unittest.mock import MagicMock, patch

import pytest
import yaml
from _pytest.capture import CaptureFixture

from dotbins import analyze
from dotbins.config import ToolConfig, build_tool_config
from dotbins.download import extract_archive


@pytest.fixture
def mock_assets() -> list[dict[str, str]]:
    """Create mock assets for testing."""
    return [
        {
            "name": "tool-1.0.0-linux_x86_64.tar.gz",
            "browser_download_url": "https://example.com/1",
        },
        {
            "name": "tool-1.0.0-linux_aarch64.tar.gz",
            "browser_download_url": "https://example.com/2",
        },
        {
            "name": "tool-1.0.0-darwin_x86_64.tar.gz",
            "browser_download_url": "https://example.com/3",
        },
        {
            "name": "tool-1.0.0-darwin_arm64.tar.gz",
            "browser_download_url": "https://example.com/4",
        },
        {
            "name": "tool-1.0.0-windows_x86_64.zip",
            "browser_download_url": "https://example.com/5",
        },
        {"name": "checksums.txt", "browser_download_url": "https://example.com/6"},
    ]


@pytest.fixture
def mock_release(mock_assets: list[dict[str, str]]) -> dict[str, Any]:
    """Create a mock release for testing."""
    return {
        "tag_name": "v1.0.0",
        "name": "Release 1.0.0",
        "assets": mock_assets,
    }


def test_get_platform_assets(mock_assets: list[dict[str, str]]) -> None:
    """Test filtering assets by platform."""
    # Constants for expected counts
    expected_linux_assets = 2
    expected_macos_assets = 2

    linux_assets = analyze.get_platform_assets(mock_assets, "linux")
    assert len(linux_assets) == expected_linux_assets
    assert all("linux" in a["name"] for a in linux_assets)

    macos_assets = analyze.get_platform_assets(mock_assets, "macos")
    assert len(macos_assets) == expected_macos_assets
    assert all("darwin" in a["name"] for a in macos_assets)

    unknown_assets = analyze.get_platform_assets(mock_assets, "unknown")
    assert len(unknown_assets) == 0


def test_get_arch_assets(mock_assets: list[dict[str, str]]) -> None:
    """Test filtering assets by architecture."""
    # Constants for expected counts
    expected_amd64_assets = 3
    expected_arm64_assets = 2  # Includes both arm64 and aarch64 assets

    amd64_assets = analyze.get_arch_assets(mock_assets, "amd64")
    assert len(amd64_assets) == expected_amd64_assets
    assert all("x86_64" in a["name"] for a in amd64_assets)

    arm64_assets = analyze.get_arch_assets(mock_assets, "arm64")
    assert len(arm64_assets) == expected_arm64_assets
    # Check for either arm64 or aarch64 in name
    assert all("arm64" in a["name"] or "aarch64" in a["name"] for a in arm64_assets)

    unknown_assets = analyze.get_arch_assets(mock_assets, "unknown")
    assert len(unknown_assets) == 0


def test_find_sample_asset(mock_assets: list[dict[str, str]]) -> None:
    """Test finding a suitable sample asset."""
    sample = analyze._find_sample_asset(mock_assets)
    assert sample is not None
    assert sample["name"] == "tool-1.0.0-linux_x86_64.tar.gz"

    # Test with no suitable assets
    no_sample = analyze._find_sample_asset([{"name": "checksums.txt"}])
    assert no_sample is None


def test_find_executables(tmp_path: Path) -> None:
    """Test finding executable files in a directory."""
    # Create test executable files
    bin_dir = os.path.join(tmp_path, "bin")
    os.makedirs(bin_dir)

    exe_path1 = os.path.join(tmp_path, "tool")
    with open(exe_path1, "w") as f:
        f.write("#!/bin/sh\necho test")
    os.chmod(exe_path1, 0o700)  # More restrictive permissions

    exe_path2 = os.path.join(bin_dir, "tool-helper")
    with open(exe_path2, "w") as f:
        f.write("#!/bin/sh\necho helper")
    os.chmod(exe_path2, 0o700)  # More restrictive permissions

    # Create a non-executable file
    non_exe = os.path.join(tmp_path, "README")
    with open(non_exe, "w") as f:
        f.write("Documentation")

    # Constants for expected counts
    expected_executables = 2

    executables = analyze.find_executables(tmp_path)
    assert len(executables) == expected_executables
    assert "tool" in executables
    assert os.path.join("bin", "tool-helper") in executables


def test_determine_binary_path() -> None:
    """Test determining the binary path from executables."""
    # Case 1: Exact name match
    executables = ["bin/other", "tool", "lib/helper"]
    path = analyze.determine_binary_path(executables, "tool")
    assert path == "tool"

    # Case 2: Executable in bin/ directory
    executables = ["lib/helper", "bin/tool", "other"]
    path = analyze.determine_binary_path(executables, "different-name")
    assert path == "bin/tool"  # Should be fixed by our update to determine_binary_path

    # Case 3: Fallback to first executable
    executables = ["lib/some-exe", "other-exe"]
    path = analyze.determine_binary_path(executables, "different-name")
    assert path == "lib/some-exe"

    # Case 4: No executables
    path = analyze.determine_binary_path([], "tool")
    assert path is None


def test_generate_tool_config(mock_release: dict[str, Any]) -> None:
    """Test generating tool configuration."""
    # Test with binary path
    config = analyze.generate_tool_config(
        "test/repo",
        "tool",
        mock_release,
        "bin/tool",
    )
    assert isinstance(config, ToolConfig)
    assert config.repo == "test/repo"
    assert config.extract_binary is True
    assert config.binary_name == ["tool"]
    assert config.binary_path == ["*/tool"]
    assert config.arch_map
    assert config.asset_patterns
    assert isinstance(config.asset_patterns, dict)
    assert config.asset_patterns["linux"] is not None
    assert config.asset_patterns["macos"] is not None

    # Test without binary path
    config = analyze.generate_tool_config(
        "test/repo",
        "tool",
        mock_release,
        None,
    )
    assert not config.binary_path

    # Test with binary path containing version
    config = analyze.generate_tool_config(
        "test/repo",
        "tool",
        mock_release,
        "tool-1.0.0/bin/tool",
    )
    assert config.binary_path == ["*/bin/tool"]


def test_generate_platform_specific_patterns(mock_release: dict[str, Any]) -> None:
    """Test generating platform-specific asset patterns."""
    patterns = analyze.generate_platform_specific_patterns(mock_release)
    assert "linux" in patterns
    assert "macos" in patterns
    assert patterns["linux"] == "tool-{version}-{platform}_{arch}.tar.gz"
    assert patterns["macos"] == "tool-{version}-{platform}_{arch}.tar.gz"


def test_generate_single_pattern(mock_release: dict[str, Any]) -> None:
    """Test generating a single asset pattern."""
    pattern = analyze.generate_single_pattern(mock_release)
    # The function should not replace "linux" with "{platform}" for our test
    assert pattern == "tool-{version}-{platform}_{arch}.tar.gz"

    # Test with empty assets
    empty_release = {"tag_name": "v1.0.0", "assets": []}
    with pytest.raises(ValueError, match="No assets found in the release."):
        analyze.generate_single_pattern(empty_release)


@patch("dotbins.analyze.download_file")
@patch("dotbins.analyze.extract_archive")
@patch("dotbins.analyze.find_executables")
def test_download_and_find_binary(
    mock_find_executables: MagicMock,
    mock_extract: MagicMock,
    mock_download: MagicMock,
) -> None:
    """Test downloading and finding binary path."""
    mock_find_executables.return_value = ["tool", "bin/tool"]
    mock_download.return_value = "/secure/temp/file.tar.gz"

    # Create an actual mock asset that we'll use
    mock_asset = {
        "name": "tool-1.0.0-linux_x86_64.tar.gz",
        "browser_download_url": "https://example.com/tool.tar.gz",  # Change URL to something requests_mock can handle
    }

    # Use secure temporary paths
    with patch("tempfile.NamedTemporaryFile") as mock_temp_file:
        mock_temp_file.return_value.__enter__.return_value.name = "/secure/temp/file.tar.gz"
        with patch("tempfile.mkdtemp", return_value="/secure/temp/extracted"):
            result = analyze._download_and_find_binary(mock_asset, "tool")

    assert mock_download.called
    assert mock_extract.called
    assert mock_find_executables.called
    assert result == ["tool", "bin/tool"]


@patch("dotbins.analyze.latest_release_info")
@patch("dotbins.analyze._find_sample_asset")
@patch("dotbins.analyze._download_and_find_binary")
@patch("dotbins.analyze.generate_tool_config")
@patch("dotbins.analyze._print_assets_info")
def test_analyze_tool(
    mock_print_assets: MagicMock,
    mock_gen_config: MagicMock,
    mock_download_find: MagicMock,
    mock_find_sample: MagicMock,
    mock_get_release: MagicMock,
    capsys: CaptureFixture[str],
) -> None:
    """Test the analyze_tool function."""
    mock_release = {
        "tag_name": "v1.0.0",
        "name": "Release 1.0.0",
        "assets": [
            {"name": "test.tar.gz", "browser_download_url": "https://example.com"},
        ],
    }
    mock_get_release.return_value = mock_release

    mock_find_sample.return_value = {
        "name": "test.tar.gz",
        "browser_download_url": "https://example.com",
    }
    mock_download_find.return_value = "bin/tool"

    tool_config = build_tool_config(
        tool_name="tool",
        raw_data={
            "repo": "test/repo",
            "extract_binary": True,
            "binary_name": "tool",
            "binary_path": "bin/tool",
            "asset_patterns": "test-{version}.tar.gz",
        },
    )
    mock_gen_config.return_value = tool_config

    # Call the function
    analyze.analyze_tool(repo="test/repo", name="tool")

    # Check results
    mock_get_release.assert_called_once_with("test/repo")
    mock_print_assets.assert_called_once()
    mock_find_sample.assert_called_once()
    mock_download_find.assert_called_once()
    mock_gen_config.assert_called_once()

    # Check the output contains YAML
    captured = capsys.readouterr()
    assert "Suggested configuration for YAML tools file:" in captured.out

    # Verify we can parse the output as valid YAML
    yaml_section = captured.out.split("Suggested configuration for YAML tools file:")[1].strip()
    parsed = yaml.safe_load(yaml_section)
    assert "tool" in parsed
    assert ToolConfig("tool", **parsed["tool"]) == tool_config


def test_extract_archive(tmp_path: Path, create_dummy_archive: Callable) -> None:
    """Test extracting different archive types."""
    # Test with zip file
    zip_path = tmp_path / "test.zip"
    create_dummy_archive(dest_path=zip_path, binary_names="test-binary", archive_type="zip")

    extract_dir = tmp_path / "extract_zip"
    extract_dir.mkdir()
    extract_archive(zip_path, extract_dir)
    assert os.path.exists(extract_dir / "test-binary")

    # Test with unsupported format
    unsupported_path = tmp_path / "test.bin"
    with open(unsupported_path, "w") as f:
        f.write("binary content")

    extract_dir = tmp_path / "extract_unsupported"
    extract_dir.mkdir()
    with pytest.raises(ValueError, match="Unsupported archive format"):
        extract_archive(unsupported_path, extract_dir)
