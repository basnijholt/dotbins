"""End-to-end tests for dotbins."""

from __future__ import annotations

import os
import tarfile
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from dotbins.cli import _update_tools
from dotbins.config import Config, _config_from_dict
from dotbins.utils import log


def create_dummy_archive(
    dest_path: Path,
    binary_names: str | list[str],
    archive_type: str = "tar.gz",
    binary_content: str = "#!/usr/bin/env echo\n",
) -> None:
    """Create a dummy archive file with provided binary names inside.

    Args:
        dest_path: Path where the archive will be created
        binary_names: Single binary name or list of binary names to include
        archive_type: Type of archive to create ("tar.gz", "zip", "tar.bz2")
        binary_content: Content to put in the binary files

    """
    if isinstance(binary_names, str):
        binary_names = [binary_names]

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        bin_dir = tmp_path
        bin_dir.mkdir(exist_ok=True)

        created_files = []
        for binary in binary_names:
            # Create the binary file
            bin_file = bin_dir / binary
            bin_file.write_text(binary_content)
            bin_file.chmod(0o755)
            created_files.append(bin_file)

        # Create the archive
        assert archive_type == "tar.gz"
        with tarfile.open(dest_path, "w:gz") as tar:
            for file_path in created_files:
                archive_path = file_path.relative_to(tmp_path)
                tar.add(file_path, arcname=str(archive_path))


def create_mock_release_info(
    tool_name: str,
    version: str = "1.2.3",
    platforms: list[str] | None = None,
    architectures: list[str] | None = None,
    archive_type: str = "tar.gz",
) -> dict[str, Any]:
    """Create mock GitHub release information for a tool.

    Args:
        tool_name: Name of the tool
        version: Version string (without 'v' prefix)
        platforms: List of platforms (defaults to ['linux', 'darwin'])
        architectures: List of architectures (defaults to ['amd64', 'arm64'])
        archive_type: Archive file extension

    Returns:
        Dict with release information matching GitHub API format

    """
    if platforms is None:
        platforms = ["linux", "darwin"]
    if architectures is None:
        architectures = ["amd64", "arm64"]

    assets = []
    for platform in platforms:
        for arch in architectures:
            asset_name = f"{tool_name}-{version}-{platform}_{arch}.{archive_type}"
            assets.append(
                {"name": asset_name, "browser_download_url": f"https://example.com/{asset_name}"},
            )

    return {"tag_name": f"v{version}", "name": f"{tool_name} {version}", "assets": assets}


def run_e2e_test(
    tools_dir: Path,
    tool_configs: dict[str, dict[str, Any]],
    platforms: dict[str, list[str]] | None = None,
    filter_tools: list[str] | None = None,
    filter_platform: str | None = None,
    filter_arch: str | None = None,
    force: bool = False,
) -> Config:
    """Run an end-to-end test with the given configuration.

    Args:
        tools_dir: Temporary directory to use for tools
        tool_configs: Dictionary of tool configurations
        platforms: Platform configuration (defaults to linux/amd64)
        filter_tools: List of tools to update (all if None)
        filter_platform: Platform to filter updates for
        filter_arch: Architecture to filter updates for
        force: Whether to force updates

    Returns:
        The Config object used for the test

    """
    if platforms is None:
        platforms = {"linux": ["amd64"]}

    # Build the raw config dict
    raw_config = {"tools_dir": str(tools_dir), "platforms": platforms, "tools": tool_configs}

    config = _config_from_dict(raw_config)

    def mock_latest_release(repo: str) -> dict[str, Any]:
        tool_name = repo.split("/")[-1]
        return create_mock_release_info(tool_name)

    def mock_download_func(url: str, destination: str) -> str:
        # Extract tool name from URL
        parts = url.split("/")[-1].split("-")
        tool_name = parts[0]

        # Create a dummy archive with the right name
        create_dummy_archive(Path(destination), tool_name)
        return destination

    with (
        patch("dotbins.config.latest_release_info", side_effect=mock_latest_release),
        patch("dotbins.download.download_file", side_effect=mock_download_func),
    ):
        # Run the update
        _update_tools(
            config=config,
            tools=filter_tools or [],
            platform=filter_platform,
            architecture=filter_arch,
            current=False,
            force=force,
            shell_setup=False,
        )

    return config


def verify_binaries_installed(
    config: Config,
    expected_tools: list[str] | None = None,
    platform: str | None = None,
    arch: str | None = None,
) -> None:
    """Verify that binaries were installed as expected.

    Args:
        config: The Config object used for the test
        expected_tools: List of tools to check (all tools in config if None)
        platform: Platform to check (all platforms in config if None)
        arch: Architecture to check (all architectures for the platform if None)

    """
    if expected_tools is None:
        expected_tools = list(config.tools.keys())
    platforms_to_check = [platform] if platform else list(config.platforms.keys())
    for check_platform in platforms_to_check:
        archs_to_check = [arch] if arch else config.platforms.get(check_platform, [])
        for check_arch in archs_to_check:
            bin_dir = config.bin_dir(check_platform, check_arch)
            for tool_name in expected_tools:
                tool_config = config.tools[tool_name]
                for binary_name in tool_config.binary_name:
                    binary_path = bin_dir / binary_name
                    assert binary_path.exists()
                    assert os.access(binary_path, os.X_OK)


def test_simple_tool_update(tmp_path: Path) -> None:
    """Test updating a simple tool configuration."""
    tool_configs = {
        "mytool": {
            "repo": "fakeuser/mytool",
            "extract_binary": True,
            "binary_name": "mytool",
            "binary_path": "mytool",
            "asset_patterns": "mytool-{version}-{platform}_{arch}.tar.gz",
        },
    }
    config = run_e2e_test(tools_dir=tmp_path, tool_configs=tool_configs)
    verify_binaries_installed(config)


def test_multiple_tools_with_filtering(tmp_path: Path) -> None:
    """Test updating multiple tools with filtering."""
    tool_configs = {
        "tool1": {
            "repo": "fakeuser/tool1",
            "extract_binary": True,
            "binary_name": "tool1",
            "binary_path": "tool1",
            "asset_patterns": "tool1-{version}-{platform}_{arch}.tar.gz",
        },
        "tool2": {
            "repo": "fakeuser/tool2",
            "extract_binary": True,
            "binary_name": "tool2",
            "binary_path": "tool2",
            "asset_patterns": "tool2-{version}-{platform}_{arch}.tar.gz",
        },
    }

    # Run the test with filtering
    config = run_e2e_test(
        tools_dir=tmp_path,
        tool_configs=tool_configs,
        filter_tools=["tool1"],  # Only update tool1
        platforms={"linux": ["amd64", "arm64"]},  # Only test Linux platforms
    )

    # Verify that only tool1 was installed
    verify_binaries_installed(
        config,
        expected_tools=["tool1"],
        platform="linux",
    )  # Specify Linux only


@pytest.mark.parametrize(
    "raw_config",
    [
        # 1) Simple config with a single tool, single pattern
        {
            "tools_dir": "/fake/tools_dir",  # Will get overridden by fixture
            "platforms": {"linux": ["amd64"]},
            "tools": {
                "mytool": {
                    "repo": "fakeuser/mytool",
                    "extract_binary": True,
                    "binary_name": "mybinary",
                    "binary_path": "mybinary",
                    "asset_patterns": "mytool-{version}-linux_{arch}.tar.gz",
                },
            },
        },
        # 2) Config with multiple tools & multiple patterns
        {
            "tools_dir": "/fake/tools_dir",  # Overridden by fixture
            "platforms": {"linux": ["amd64", "arm64"]},
            "tools": {
                "mytool": {
                    "repo": "fakeuser/mytool",
                    "extract_binary": True,
                    "binary_name": "mybinary",
                    "binary_path": "mybinary",
                    "asset_patterns": {
                        "linux": {
                            "amd64": "mytool-{version}-linux_{arch}.tar.gz",
                            "arm64": "mytool-{version}-linux_{arch}.tar.gz",
                        },
                    },
                },
                "othertool": {
                    "repo": "fakeuser/othertool",
                    "extract_binary": True,
                    "binary_name": "otherbin",
                    "binary_path": "otherbin",
                    "asset_patterns": "othertool-{version}-{platform}_{arch}.tar.gz",
                },
            },
        },
    ],
)
def test_e2e_update_tools(tmp_path: Path, raw_config: dict) -> None:
    """Shows an end-to-end test.

    This test:
    - Builds a Config from a dict
    - Mocks out `latest_release_info` to produce predictable asset names
    - Mocks out `download_file` so we skip real network usage
    - Calls `_update_tools` directly
    - Verifies that the binaries are extracted into the correct location.
    """
    config = _config_from_dict(raw_config)
    config.tools_dir = tmp_path

    def mock_latest_release_info(repo: str) -> dict:
        tool_name = repo.split("/")[-1]
        return {
            "tag_name": "v1.2.3",
            "assets": [
                {
                    "name": f"{tool_name}-1.2.3-linux_amd64.tar.gz",
                    "browser_download_url": f"https://example.com/{tool_name}-1.2.3-linux_amd64.tar.gz",
                },
                {
                    "name": f"{tool_name}-1.2.3-linux_arm64.tar.gz",
                    "browser_download_url": f"https://example.com/{tool_name}-1.2.3-linux_arm64.tar.gz",
                },
            ],
        }

    def mock_download_file(url: str, destination: str) -> str:
        log(f"MOCKED download_file from {url} -> {destination}", "info")
        if "mytool" in url:
            create_dummy_archive(Path(destination), binary_names="mybinary")
        else:  # "othertool" in url
            create_dummy_archive(Path(destination), binary_names="otherbin")
        return destination

    with (
        patch("dotbins.config.latest_release_info", side_effect=mock_latest_release_info),
        patch("dotbins.download.download_file", side_effect=mock_download_file),
    ):
        _update_tools(config=config)

    verify_binaries_installed(config)
