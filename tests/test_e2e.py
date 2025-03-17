"""End-to-end tests for dotbins."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable
from unittest.mock import patch

import pytest

from dotbins.config import Config, _config_from_dict
from dotbins.utils import log


def _create_mock_release_info(
    tool_name: str,
    version: str = "1.2.3",
    platforms: list[str] | None = None,
    architectures: list[str] | None = None,
    archive_type: str = "tar.gz",
) -> dict[str, Any]:
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
    create_dummy_archive: Callable,
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
        create_dummy_archive: The create_dummy_archive fixture
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
        return _create_mock_release_info(tool_name)

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
        config.update_tools(
            tools=filter_tools,
            platform=filter_platform,
            architecture=filter_arch,
            force=force,
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


def test_simple_tool_update(
    tmp_path: Path,
    create_dummy_archive: Callable,
) -> None:
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
    config = run_e2e_test(
        tools_dir=tmp_path,
        tool_configs=tool_configs,
        create_dummy_archive=create_dummy_archive,
    )
    verify_binaries_installed(config)


def test_multiple_tools_with_filtering(
    tmp_path: Path,
    create_dummy_archive: Callable,
) -> None:
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
        create_dummy_archive=create_dummy_archive,
    )

    # Verify that only tool1 was installed
    verify_binaries_installed(
        config,
        expected_tools=["tool1"],
        platform="linux",
    )  # Specify Linux only


def test_auto_detect_binary(
    tmp_path: Path,
    create_dummy_archive: Callable,
) -> None:
    """Test that the binary is auto-detected."""
    tool_configs = {
        "mytool": {
            "repo": "fakeuser/mytool",
            "asset_patterns": "mytool-{version}-linux_{arch}.tar.gz",
        },
    }
    config = run_e2e_test(
        tools_dir=tmp_path,
        tool_configs=tool_configs,
        create_dummy_archive=create_dummy_archive,
    )
    verify_binaries_installed(config)


def test_auto_detect_binary_and_asset_patterns(
    tmp_path: Path,
    create_dummy_archive: Callable,
) -> None:
    """Test that the binary is auto-detected."""
    tool_configs = {
        "mytool": {"repo": "fakeuser/mytool"},
    }
    config = run_e2e_test(
        tools_dir=tmp_path,
        tool_configs=tool_configs,
        create_dummy_archive=create_dummy_archive,
    )
    verify_binaries_installed(config)


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
def test_e2e_update_tools(
    tmp_path: Path,
    raw_config: dict,
    create_dummy_archive: Callable,
) -> None:
    """Shows an end-to-end test.

    This test:
    - Builds a Config from a dict
    - Mocks out `latest_release_info` to produce predictable asset names
    - Mocks out `download_file` so we skip real network usage
    - Calls `config.update_tools` directly
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
        config.update_tools()

    verify_binaries_installed(config)


def test_e2e_update_tools_skip_up_to_date(tmp_path: Path) -> None:
    """Demonstrates a scenario where we have a single tool that is already up-to-date.

    - We populate the VersionStore with the exact version returned by mocked GitHub releases.
    - The `config.update_tools` call should skip downloading or extracting anything.
    """
    raw_config = {
        "tools_dir": str(tmp_path),
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
    }

    config = _config_from_dict(raw_config)
    config.tools_dir = tmp_path  # Ensures we respect the fixture path

    # Pre-populate version_store with version='1.2.3' so it should SKIP
    config.version_store.update_tool_info(
        tool="mytool",
        platform="linux",
        arch="amd64",
        version="1.2.3",
    )

    def mock_latest_release_info(repo: str) -> dict:  # noqa: ARG001
        return {
            "tag_name": "v1.2.3",
            "assets": [
                {
                    "name": "mytool-1.2.3-linux_amd64.tar.gz",
                    "browser_download_url": "https://example.com/mytool-1.2.3-linux_amd64.tar.gz",
                },
            ],
        }

    def mock_download_file(url: str, destination: str) -> str:
        # This won't be called at all if the skip logic works
        log(f"MOCK download_file from {url} -> {destination}", "error")
        msg = "This should never be called if skip is working."
        raise RuntimeError(msg)

    with (
        patch("dotbins.config.latest_release_info", side_effect=mock_latest_release_info),
        patch("dotbins.download.download_file", side_effect=mock_download_file),
    ):
        config.update_tools()

    # If everything is skipped, no new binary is downloaded,
    # and the existing version_store is unchanged.
    stored_info = config.version_store.get_tool_info("mytool", "linux", "amd64")
    assert stored_info is not None
    assert stored_info["version"] == "1.2.3"


def test_e2e_update_tools_partial_skip_and_update(
    tmp_path: Path,
    create_dummy_archive: Callable,
) -> None:
    """Partial skip & update.

    Demonstrates:
    - 'mytool' is already up-to-date => skip
    - 'othertool' is on an older version => must update.
    """
    raw_config = {
        "tools_dir": str(tmp_path),
        "platforms": {"linux": ["amd64"]},
        "tools": {
            "mytool": {
                "repo": "fakeuser/mytool",
                "extract_binary": True,
                "binary_name": "mybinary",
                "binary_path": "mybinary",
                "asset_patterns": "mytool-{version}-linux_{arch}.tar.gz",
            },
            "othertool": {
                "repo": "fakeuser/othertool",
                "extract_binary": True,
                "binary_name": "otherbin",
                "binary_path": "otherbin",
                "asset_patterns": "othertool-{version}-linux_{arch}.tar.gz",
            },
        },
    }

    config = _config_from_dict(raw_config)
    config.tools_dir = tmp_path

    # Mark 'mytool' as already up-to-date
    config.version_store.update_tool_info(
        tool="mytool",
        platform="linux",
        arch="amd64",
        version="2.0.0",
    )

    # Mark 'othertool' as older so it gets updated
    config.version_store.update_tool_info(
        tool="othertool",
        platform="linux",
        arch="amd64",
        version="1.0.0",
    )

    def mock_latest_release_info(repo: str) -> dict:
        if "mytool" in repo:
            return {
                "tag_name": "v2.0.0",
                "assets": [
                    {
                        "name": "mytool-2.0.0-linux_amd64.tar.gz",
                        "browser_download_url": "https://example.com/mytool-2.0.0-linux_amd64.tar.gz",
                    },
                ],
            }
        return {
            "tag_name": "v2.0.0",
            "assets": [
                {
                    "name": "othertool-2.0.0-linux_amd64.tar.gz",
                    "browser_download_url": "https://example.com/othertool-2.0.0-linux_amd64.tar.gz",
                },
            ],
        }

    def mock_download_file(url: str, destination: str) -> str:
        # Only called for 'othertool' if skip for 'mytool' works
        if "mytool" in url:
            msg = "Should not download mytool if up-to-date!"
            raise RuntimeError(msg)
        create_dummy_archive(Path(destination), binary_names="otherbin")
        return destination

    with (
        patch("dotbins.config.latest_release_info", side_effect=mock_latest_release_info),
        patch("dotbins.download.download_file", side_effect=mock_download_file),
    ):
        config.update_tools()

    # 'mytool' should remain at version 2.0.0, unchanged
    mytool_info = config.version_store.get_tool_info("mytool", "linux", "amd64")
    assert mytool_info is not None
    assert mytool_info["version"] == "2.0.0"  # no change

    # 'othertool' should have been updated to 2.0.0
    other_info = config.version_store.get_tool_info("othertool", "linux", "amd64")
    assert other_info is not None
    assert other_info["version"] == "2.0.0"
    # And the binary should now exist:
    other_bin = config.bin_dir("linux", "amd64") / "otherbin"
    assert other_bin.exists(), "otherbin was not downloaded/extracted correctly."
    assert os.access(other_bin, os.X_OK), "otherbin should be executable."


def test_e2e_update_tools_force_re_download(tmp_path: Path, create_dummy_archive: Callable) -> None:
    """Force a re-download.

    Scenario:
    - 'mytool' is already up to date at version 1.2.3
    - We specify `force=True` => it MUST redownload
    """
    raw_config = {
        "tools_dir": str(tmp_path),
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
    }
    config = _config_from_dict(raw_config)

    # Mark 'mytool' as installed at 1.2.3
    config.version_store.update_tool_info("mytool", "linux", "amd64", "1.2.3")
    tool_info = config.version_store.get_tool_info("mytool", "linux", "amd64")
    assert tool_info is not None
    original_updated_at = tool_info["updated_at"]

    # Mock release & download
    def mock_latest_release_info(repo: str) -> dict:  # noqa: ARG001
        return {
            "tag_name": "v1.2.3",
            "assets": [
                {
                    "name": "mytool-1.2.3-linux_amd64.tar.gz",
                    "browser_download_url": "https://example.com/mytool-1.2.3-linux_amd64.tar.gz",
                },
            ],
        }

    downloaded_urls = []

    def mock_download_file(url: str, destination: str) -> str:
        downloaded_urls.append(url)
        create_dummy_archive(Path(destination), binary_names="mybinary")
        return destination

    with (
        patch("dotbins.config.latest_release_info", side_effect=mock_latest_release_info),
        patch("dotbins.download.download_file", side_effect=mock_download_file),
    ):
        # Force a re-download, even though we're "up to date"
        config.update_tools(
            tools=["mytool"],
            platform="linux",
            architecture="amd64",
            force=True,  # Key point: forcing
        )

    # Verify that the download actually happened (1 item in the list)
    assert len(downloaded_urls) == 1, "Expected exactly one forced download."
    assert "mytool-1.2.3-linux_amd64.tar.gz" in downloaded_urls[0]

    # The version store should remain '1.2.3', but `updated_at` changes
    tool_info = config.version_store.get_tool_info("mytool", "linux", "amd64")
    assert tool_info is not None
    assert tool_info["version"] == "1.2.3"
    # Check that updated_at changed from the original
    assert tool_info["updated_at"] != original_updated_at


def test_e2e_update_tools_specific_platform(tmp_path: Path, create_dummy_archive: Callable) -> None:
    """Update a specific platform.

    Scenario: We have a config with 'linux' & 'macos', but only request updates for 'macos'
    => Only macOS assets are fetched and placed in the correct bin dir.
    """
    raw_config = {
        "tools_dir": str(tmp_path),
        "platforms": {
            "linux": ["amd64", "arm64"],
            "macos": ["arm64"],
        },
        "tools": {
            "mytool": {
                "repo": "fakeuser/mytool",
                "extract_binary": True,
                "binary_name": "mybinary",
                "binary_path": "mybinary",
                "asset_patterns": {
                    "linux": {
                        "amd64": "mytool-{version}-linux_amd64.tar.gz",
                        "arm64": "mytool-{version}-linux_arm64.tar.gz",
                    },
                    "macos": {
                        "arm64": "mytool-{version}-darwin_arm64.tar.gz",
                    },
                },
            },
        },
    }
    config = _config_from_dict(raw_config)

    def mock_latest_release_info(repo: str) -> dict:  # noqa: ARG001
        return {
            "tag_name": "v1.0.0",
            "assets": [
                {
                    "name": "mytool-1.0.0-linux_amd64.tar.gz",
                    "browser_download_url": "https://example.com/mytool-1.0.0-linux_amd64.tar.gz",
                },
                {
                    "name": "mytool-1.0.0-linux_arm64.tar.gz",
                    "browser_download_url": "https://example.com/mytool-1.0.0-linux_arm64.tar.gz",
                },
                {
                    "name": "mytool-1.0.0-darwin_arm64.tar.gz",
                    "browser_download_url": "https://example.com/mytool-1.0.0-darwin_arm64.tar.gz",
                },
            ],
        }

    downloaded_files = []

    def mock_download_file(url: str, destination: str) -> str:
        downloaded_files.append(url)
        # Each call uses the same tar generation but with different binary content
        create_dummy_archive(Path(destination), binary_names="mybinary")
        return destination

    with (
        patch("dotbins.config.latest_release_info", side_effect=mock_latest_release_info),
        patch("dotbins.download.download_file", side_effect=mock_download_file),
    ):
        # Only update macOS => We expect only the darwin_arm64 asset
        config.update_tools(platform="macos")

    # Should only have downloaded the darwin_arm64 file
    assert len(downloaded_files) == 1
    assert "mytool-1.0.0-darwin_arm64.tar.gz" in downloaded_files[0]

    # Check bin existence
    macos_bin = config.bin_dir("macos", "arm64")
    assert (macos_bin / "mybinary").exists(), "mybinary should be in macos/arm64/bin"

    # Meanwhile the linux bins should NOT exist
    linux_bin_amd64 = config.bin_dir("linux", "amd64")
    linux_bin_arm64 = config.bin_dir("linux", "arm64")
    assert not (linux_bin_amd64 / "mybinary").exists()
    assert not (linux_bin_arm64 / "mybinary").exists()
