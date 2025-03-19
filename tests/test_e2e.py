"""End-to-end tests for dotbins."""

from __future__ import annotations

import os
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, NoReturn
from unittest.mock import patch

import pytest
import requests

from dotbins.cli import _get_tool
from dotbins.config import Config, RawConfigDict, RawToolConfigDict, _config_from_dict
from dotbins.utils import current_platform, log


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
    tool_configs: dict[str, RawToolConfigDict],
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
    raw_config: RawConfigDict = {
        "tools_dir": str(tools_dir),
        "platforms": platforms,
        "tools": tool_configs,
    }

    config = _config_from_dict(raw_config)

    def mock_latest_release_info(repo: str, quiet: bool = False) -> dict:  # noqa: ARG001
        tool_name = repo.split("/")[-1]
        return _create_mock_release_info(tool_name)

    def mock_download_file(url: str, destination: str, verbose: bool) -> str:  # noqa: ARG001
        # Extract tool name from URL
        parts = url.split("/")[-1].split("-")
        tool_name = parts[0]

        # Create a dummy archive with the right name
        create_dummy_archive(Path(destination), tool_name)
        return destination

    with (
        patch("dotbins.config.latest_release_info", side_effect=mock_latest_release_info),
        patch("dotbins.download.download_file", side_effect=mock_download_file),
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
    tool_configs: dict[str, RawToolConfigDict] = {
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
    tool_configs: dict[str, RawToolConfigDict] = {
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
    tool_configs: dict[str, RawToolConfigDict] = {
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
    tool_configs: dict[str, RawToolConfigDict] = {
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
    raw_config: RawConfigDict,
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

    def mock_latest_release_info(repo: str, quiet: bool = False) -> dict:  # noqa: ARG001
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

    def mock_download_file(url: str, destination: str, verbose: bool) -> str:  # noqa: ARG001
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
    raw_config: RawConfigDict = {
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

    def mock_latest_release_info(repo: str, quiet: bool = False) -> dict:  # noqa: ARG001
        return {
            "tag_name": "v1.2.3",
            "assets": [
                {
                    "name": "mytool-1.2.3-linux_amd64.tar.gz",
                    "browser_download_url": "https://example.com/mytool-1.2.3-linux_amd64.tar.gz",
                },
            ],
        }

    def mock_download_file(url: str, destination: str, verbose: bool) -> str:  # noqa: ARG001
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
    raw_config: RawConfigDict = {
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

    def mock_latest_release_info(repo: str, quiet: bool = False) -> dict:  # noqa: ARG001
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

    def mock_download_file(url: str, destination: str, verbose: bool) -> str:  # noqa: ARG001
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
    assert other_bin.exists()
    assert os.access(other_bin, os.X_OK)

    # Check old version is recorded
    assert config._update_summary.updated[0].old_version == "1.0.0"
    assert config._update_summary.updated[0].version == "2.0.0"


def test_e2e_update_tools_force_re_download(tmp_path: Path, create_dummy_archive: Callable) -> None:
    """Force a re-download.

    Scenario:
    - 'mytool' is already up to date at version 1.2.3
    - We specify `force=True` => it MUST redownload
    """
    raw_config: RawConfigDict = {
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
    def mock_latest_release_info(repo: str, quiet: bool = False) -> dict:  # noqa: ARG001
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

    def mock_download_file(url: str, destination: str, verbose: bool) -> str:  # noqa: ARG001
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
    assert len(downloaded_urls) == 1
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
    raw_config: RawConfigDict = {
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
                "asset_patterns": {  # type: ignore[typeddict-item]
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

    def mock_latest_release_info(repo: str, quiet: bool = False) -> dict:  # noqa: ARG001
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

    def mock_download_file(url: str, destination: str, verbose: bool) -> str:  # noqa: ARG001
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
    assert (macos_bin / "mybinary").exists()

    # Meanwhile the linux bins should NOT exist
    linux_bin_amd64 = config.bin_dir("linux", "amd64")
    linux_bin_arm64 = config.bin_dir("linux", "arm64")
    assert not (linux_bin_amd64 / "mybinary").exists()
    assert not (linux_bin_arm64 / "mybinary").exists()


def test_get_tool_command(tmp_path: Path, create_dummy_archive: Callable) -> None:
    """Test the 'get' command."""
    dest_dir = tmp_path / "bin"
    dest_dir.mkdir(parents=True, exist_ok=True)
    platform, arch = current_platform()

    def mock_latest_release_info(repo: str, quiet: bool = False) -> dict:  # noqa: ARG001
        return {
            "tag_name": "v1.0.0",
            "assets": [
                {
                    "name": f"mytool-1.0.0-{platform}_{arch}.tar.gz",
                    "browser_download_url": f"https://example.com/mytool-1.0.0-{platform}_{arch}.tar.gz",
                },
            ],
        }

    def mock_download_file(url: str, destination: str, verbose: bool) -> str:  # noqa: ARG001
        create_dummy_archive(Path(destination), binary_names="mytool")
        return destination

    with (
        patch("dotbins.config.latest_release_info", side_effect=mock_latest_release_info),
        patch("dotbins.download.download_file", side_effect=mock_download_file),
    ):
        _get_tool(source="basnijholt/mytool", dest_dir=dest_dir)

    assert (dest_dir / "mytool").exists()


def test_get_tool_command_with_remote_config(
    tmp_path: Path,
    create_dummy_archive: Callable,
) -> None:
    """Test the 'get' command with a remote config URL.

    This tests the functionality to download a YAML configuration from a URL
    and install the tools defined in it.
    """
    dest_dir = tmp_path / "bin"
    dest_dir.mkdir(parents=True, exist_ok=True)
    platform, arch = current_platform()

    # Sample YAML configuration that would be fetched from a URL
    yaml_content = textwrap.dedent(
        f"""\
        tools_dir: {dest_dir!s}
        platforms:
            {platform}: [{arch}]
        tools:
            tool1:
                repo: fakeuser/tool1
            tool2:
                repo: fakeuser/tool2
        """,
    )

    # Create a mock response for requests.get
    @dataclass
    class MockResponse:
        content: bytes
        status_code: int = 200

        def raise_for_status(self) -> None:
            pass

    def mock_requests_get(
        url: str,
        timeout: int | None = None,  # noqa: ARG001
        **kwargs,  # noqa: ANN003, ARG001
    ) -> MockResponse:
        log(f"Mock HTTP GET for URL: {url}", "info")
        return MockResponse(yaml_content.encode("utf-8"))

    def mock_latest_release_info(repo: str, quiet: bool = False) -> dict:  # noqa: ARG001
        log(f"Getting release info for repo: {repo}", "info")
        tool_name = repo.split("/")[-1]
        return {
            "tag_name": "v1.0.0",
            "assets": [
                {
                    "name": f"{tool_name}-1.0.0-{platform}_{arch}.tar.gz",
                    "browser_download_url": f"https://example.com/{tool_name}-1.0.0-{platform}_{arch}.tar.gz",
                },
            ],
        }

    def mock_download_file(url: str, destination: str, verbose: bool) -> str:  # noqa: ARG001
        log(f"Downloading from {url} to {destination}", "info")
        tool_name = url.split("/")[-1].split("-")[0]
        log(f"Creating archive for {tool_name}", "info")
        create_dummy_archive(Path(destination), binary_names=tool_name)
        return destination

    with (
        patch("dotbins.utils.requests.get", side_effect=mock_requests_get),
        patch("dotbins.config.latest_release_info", side_effect=mock_latest_release_info),
        patch("dotbins.download.download_file", side_effect=mock_download_file),
    ):
        _get_tool(source="https://example.com/config.yaml", dest_dir=dest_dir)

    # Verify that both tools from the config were installed
    assert (dest_dir / "tool1").exists()
    assert (dest_dir / "tool2").exists()


@pytest.mark.parametrize("existing_config", [True, False])
@pytest.mark.parametrize("existing_config_with_content", [True, False])
def test_copy_config_file(
    tmp_path: Path,
    create_dummy_archive: Callable,
    existing_config: bool,
    existing_config_with_content: bool,
) -> None:
    """Test that the config file is copied to the tools directory."""
    dest_dir = tmp_path
    platform, arch = current_platform()
    yaml_content = textwrap.dedent(
        f"""\
        tools_dir: {dest_dir!s}
        platforms:
            {platform}: [{arch}]
        tools:
            tool1:
                repo: fakeuser/tool1
            tool2:
                repo: fakeuser/tool2
        """,
    )
    cfg_path = dest_dir / "tmp" / "dotbins.yaml"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    with cfg_path.open("w") as f:
        f.write(yaml_content)

    if existing_config:
        # Create a fake config file with nothing
        if existing_config_with_content:
            (dest_dir / "dotbins.yaml").write_text(yaml_content)
        else:
            (dest_dir / "dotbins.yaml").touch()

    config = Config.from_file(cfg_path)
    assert config.tools_dir == dest_dir
    assert config.platforms == {platform: [arch]}

    def mock_latest_release_info(repo: str, quiet: bool = False) -> dict:  # noqa: ARG001
        log(f"Getting release info for repo: {repo}", "info")
        tool_name = repo.split("/")[-1]
        return {
            "tag_name": "v1.0.0",
            "assets": [
                {
                    "name": f"{tool_name}-1.0.0-{platform}_{arch}.tar.gz",
                    "browser_download_url": f"https://example.com/{tool_name}-1.0.0-{platform}_{arch}.tar.gz",
                },
            ],
        }

    def mock_download_file(url: str, destination: str, verbose: bool) -> str:  # noqa: ARG001
        log(f"Downloading from {url} to {destination}", "info")
        tool_name = url.split("/")[-1].split("-")[0]
        log(f"Creating archive for {tool_name}", "info")
        create_dummy_archive(Path(destination), binary_names=tool_name)
        return destination

    with (
        patch("dotbins.config.latest_release_info", side_effect=mock_latest_release_info),
        patch("dotbins.download.download_file", side_effect=mock_download_file),
    ):
        config.update_tools(copy_config_file=True)

    # Should have been copied to the tools directory
    assert (dest_dir / "dotbins.yaml").exists()
    with (dest_dir / "dotbins.yaml").open("r") as f:
        assert f.read() == yaml_content


def test_update_nonexistent_platform(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test that updating a non-existent platform results in skipped entries in summary."""
    # Setup basic config file
    config_path = tmp_path / "dotbins.yaml"
    config_path.write_text(
        textwrap.dedent(
            f"""\
            tools_dir: {tmp_path!s}
            platforms:
                linux: ["amd64", "arm64"]
                macos: ["arm64"]
            tools:
                test-tool:
                    repo: owner/test-repo
                    binary_name: test-tool
            """,
        ),
    )
    config = Config.from_file(config_path)

    config.update_tools(platform="windows")
    captured = capsys.readouterr()
    assert "Skipping unknown platform: windows" in captured.out

    config.update_tools(architecture="nonexistent")
    captured = capsys.readouterr()
    assert "Skipping unknown architecture: nonexistent" in captured.out


def test_non_extract_with_multiple_binary_names(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test error handling when a non-extractable binary has multiple binary names specified.

    This tests the error path where:
    - extract_binary is set to False (use download directly)
    - More than one binary name is specified
    - The update should fail with a specific error in the summary
    """
    # Setup config with a tool that has extract_binary=False but multiple binary names
    config_path = tmp_path / "dotbins.yaml"
    config_path.write_text(
        textwrap.dedent(
            f"""\
            tools_dir: {tmp_path!s}
            platforms:
                linux: ["amd64"]
            tools:
                multi-bin-tool:
                    repo: owner/multi-bin-tool
                    extract_binary: false
                    binary_name:
                      - tool-bin1
                      - tool-bin2
            """,
        ),
    )
    config = Config.from_file(config_path)

    def mock_latest_release_info(repo: str, quiet: bool = False) -> dict:  # noqa: ARG001
        log(f"Getting release info for repo: {repo}", "info")
        return {
            "tag_name": "v1.0.0",
            "assets": [
                {
                    "name": "multi-bin-tool-1.0.0-linux_amd64.zip",
                    "browser_download_url": "https://example.com/multi-bin-tool-1.0.0-linux_amd64.zip",
                },
            ],
        }

    def mock_download_file(url: str, destination: str, verbose: bool) -> str:  # noqa: ARG001
        # Create a dummy file - this would normally be a binary file
        Path(destination).write_text("dummy binary content")
        return destination

    with (
        patch("dotbins.config.latest_release_info", side_effect=mock_latest_release_info),
        patch("dotbins.download.download_file", side_effect=mock_download_file),
    ):
        # Run the update which should fail for the multi-bin tool
        config.update_tools()

    # Capture the output
    captured = capsys.readouterr()

    # Verify that the appropriate error message was logged
    expected_error = "Expected exactly one binary name for multi-bin-tool, got 2"
    assert expected_error in captured.out

    # Check for the error message in the console output
    # The summary will be displayed at the end of the update process
    assert "Expected exactly one binary name" in captured.out
    assert "multi-bin-tool" in captured.out
    assert "linux/amd64" in captured.out

    # Verify that no binary files were created
    bin_dir = config.bin_dir("linux", "amd64")
    assert not (bin_dir / "tool-bin1").exists()
    assert not (bin_dir / "tool-bin2").exists()


def test_non_extract_single_binary_copy(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test successful handling of a non-extractable binary with a single binary name.

    This tests the success path where:
    - extract_binary is set to False (direct copy of downloaded file)
    - Exactly one binary name is specified
    - The binary should be copied directly to the destination
    """
    # Setup config with a tool that has extract_binary=False and a single binary name
    config_path = tmp_path / "dotbins.yaml"
    config_path.write_text(
        textwrap.dedent(
            f"""\
            tools_dir: {tmp_path!s}
            platforms:
                linux: ["amd64"]
            tools:
                single-bin-tool:
                    repo: owner/single-bin-tool
                    extract_binary: false
                    binary_name: tool-binary
            """,
        ),
    )
    config = Config.from_file(config_path)

    def mock_latest_release_info(repo: str, quiet: bool = False) -> dict:  # noqa: ARG001
        log(f"Getting release info for repo: {repo}", "info")
        return {
            "tag_name": "v1.0.0",
            "assets": [
                {
                    "name": "single-bin-tool-1.0.0-linux_amd64",
                    "browser_download_url": "https://example.com/single-bin-tool-1.0.0-linux_amd64",
                },
            ],
        }

    def mock_download_file(url: str, destination: str, verbose: bool) -> str:  # noqa: ARG001
        # Create a dummy binary file with executable content
        Path(destination).write_text("#!/bin/sh\necho 'Hello from tool-binary'")
        return destination

    with (
        patch("dotbins.config.latest_release_info", side_effect=mock_latest_release_info),
        patch("dotbins.download.download_file", side_effect=mock_download_file),
    ):
        # Run the update which should succeed for the single binary tool
        config.update_tools()

    # Capture the output
    captured = capsys.readouterr()

    # Verify successful messages in the output
    assert "Successfully processed single-bin-tool" in captured.out

    # Verify that the binary file was created with the correct name
    bin_dir = config.bin_dir("linux", "amd64")
    binary_path = bin_dir / "tool-binary"
    assert binary_path.exists()

    # Verify that the binary is executable
    assert os.access(binary_path, os.X_OK)

    # Verify the content was copied correctly
    assert "Hello from tool-binary" in binary_path.read_text()

    # Verify the version store was updated
    tool_info = config.version_store.get_tool_info("single-bin-tool", "linux", "amd64")
    assert tool_info is not None
    assert tool_info["version"] == "1.0.0"


def test_error_preparing_download(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test error handling when an exception occurs during download preparation.

    This tests the error path where:
    - An exception occurs while preparing the download task
    - The error should be logged and the update summary should be updated
    """
    # Setup basic config file

    config = Config.from_dict(
        {
            "tools_dir": str(tmp_path),
            "platforms": {"linux": ["amd64"]},
            "tools": {
                "error-tool": {"repo": "owner/error-tool", "binary_name": "error-tool"},
            },
        },
    )

    # Create a BinSpec.matching_asset method that raises an exception
    def mock_matching_asset(self) -> NoReturn:  # noqa: ANN001, ARG001
        msg = "Simulated error in matching asset"
        raise RuntimeError(msg)

    # Use patch to inject our exception
    with (
        patch("dotbins.config.BinSpec.matching_asset", mock_matching_asset),
        patch(
            "dotbins.config.latest_release_info",
            return_value={"tag_name": "v1.0.0", "assets": []},
        ),
    ):
        config.update_tools(verbose=True)

    # Capture the output
    captured = capsys.readouterr()

    # Verify error message in the log output
    assert "Error processing error-tool for linux/amd64" in captured.out
    assert "Simulated error in matching asset" in captured.out

    # Direct inspection of the update summary object
    failed_entries = config._update_summary.failed
    assert len(failed_entries) > 0

    # Find the entry for our tool
    tool_entry = next((entry for entry in failed_entries if entry.tool == "error-tool"), None)
    assert tool_entry is not None

    # Verify the details of the failure
    assert tool_entry.platform == "linux"
    assert tool_entry.arch == "amd64"
    assert "Error preparing download" in tool_entry.reason
    assert "Simulated error in matching asset" in tool_entry.reason

    # Verify that no files were downloaded
    bin_dir = config.bin_dir("linux", "amd64")
    assert not bin_dir.exists() or not any(bin_dir.iterdir())

    # Verify version store doesn't have an entry for this tool
    tool_info = config.version_store.get_tool_info("error-tool", "linux", "amd64")
    assert tool_info is None


def test_binary_not_found_error_handling(
    tmp_path: Path,
    create_dummy_archive: Callable,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test error handling when binary extraction fails with FileNotFoundError.

    This tests the error path where:
    - The download succeeds
    - The extraction succeeds
    - But the binary can't be found in the extracted files
    - The error should be properly categorized as 'Binary not found'
    """
    # Setup config with incorrect binary path
    config = Config.from_dict(
        {
            "tools_dir": str(tmp_path),
            "platforms": {"linux": ["amd64"]},
            "tools": {
                "extraction-error-tool": {
                    "repo": "owner/extraction-error-tool",
                    "binary_name": "tool-binary",
                    "binary_path": "nonexistent/path/tool-binary",
                    "extract_binary": True,
                },
            },
        },
    )

    def mock_latest_release_info(repo: str, quiet: bool = False) -> dict:  # noqa: ARG001
        log(f"Getting release info for repo: {repo}", "info")
        return {
            "tag_name": "v1.0.0",
            "assets": [
                {
                    "name": "extraction-error-tool-1.0.0-linux_amd64.tar.gz",
                    "browser_download_url": "https://example.com/extraction-error-tool-1.0.0-linux_amd64.tar.gz",
                },
            ],
        }

    def mock_download_file(url: str, destination: str, verbose: bool) -> str:  # noqa: ARG001
        # Create a dummy archive but WITHOUT the expected binary path
        create_dummy_archive(Path(destination), binary_names="different-binary-name")
        return destination

    with (
        patch("dotbins.config.latest_release_info", side_effect=mock_latest_release_info),
        patch("dotbins.download.download_file", side_effect=mock_download_file),
    ):
        config.update_tools()

    # Capture the output
    captured = capsys.readouterr()

    # Verify error message in the log output
    assert "Error processing extraction-error-tool" in captured.out
    assert "not found" in captured.out.lower()

    # Direct inspection of the update summary object
    failed_entries = config._update_summary.failed
    assert len(failed_entries) > 0

    # Find the entry for our tool
    tool_entry = next(
        (entry for entry in failed_entries if entry.tool == "extraction-error-tool"),
        None,
    )
    assert tool_entry is not None

    # Verify the details of the failure - specifically check for "Binary not found" prefix
    assert tool_entry.platform == "linux"
    assert tool_entry.arch == "amd64"
    assert "Binary not found" in tool_entry.reason

    # Verify that no files were created in the destination directory
    bin_dir = config.bin_dir("linux", "amd64")
    assert not (bin_dir / "tool-binary").exists()


def test_auto_detect_binary_paths_error(
    tmp_path: Path,
    create_dummy_archive: Callable,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test error handling when auto-detection of binary paths fails.

    This tests the error path where:
    - The download succeeds
    - The extraction succeeds
    - The tool has no binary_path specified, so auto-detection is used
    - Auto-detection fails because no binary matches the expected name
    - The error should be properly categorized as 'Auto-detect binary paths error'
    """
    # Setup config without binary_path - will trigger auto-detection
    config = Config.from_dict(
        {
            "tools_dir": str(tmp_path),
            "platforms": {"linux": ["amd64"]},
            "tools": {
                "auto-detect-error-tool": {
                    "repo": "owner/auto-detect-error-tool",
                    "binary_name": "expected-binary",  # This name won't match anything in the archive
                    "extract_binary": True,
                    # No binary_path specified - will use auto-detection
                },
            },
        },
    )

    def mock_latest_release_info(repo: str, quiet: bool = False) -> dict:  # noqa: ARG001
        log(f"Getting release info for repo: {repo}", "info")
        return {
            "tag_name": "v1.0.0",
            "assets": [
                {
                    "name": "auto-detect-error-tool-1.0.0-linux_amd64.tar.gz",
                    "browser_download_url": "https://example.com/auto-detect-error-tool-1.0.0-linux_amd64.tar.gz",
                },
            ],
        }

    def mock_download_file(url: str, destination: str, verbose: bool) -> str:  # noqa: ARG001
        # Create a dummy archive with a binary that won't match the expected name
        create_dummy_archive(Path(destination), binary_names="different-binary-name")
        return destination

    with (
        patch("dotbins.config.latest_release_info", side_effect=mock_latest_release_info),
        patch("dotbins.download.download_file", side_effect=mock_download_file),
    ):
        config.update_tools()

    # Capture the output
    captured = capsys.readouterr()

    # Verify error message in the log output
    assert "Error processing auto-detect-error-tool" in captured.out
    assert "auto-detect" in captured.out.lower()

    # Direct inspection of the update summary object
    failed_entries = config._update_summary.failed
    assert len(failed_entries) > 0

    # Find the entry for our tool
    tool_entry = next(
        (entry for entry in failed_entries if entry.tool == "auto-detect-error-tool"),
        None,
    )
    assert tool_entry is not None

    # Verify the details of the failure - specifically check for "Auto-detect binary paths error" prefix
    assert tool_entry.platform == "linux"
    assert tool_entry.arch == "amd64"
    assert "Auto-detect binary paths error" in tool_entry.reason

    # Verify that no files were created in the destination directory
    bin_dir = config.bin_dir("linux", "amd64")
    assert not (bin_dir / "expected-binary").exists()


def test_download_file_request_exception(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test error handling when a requests.RequestException occurs during download.

    This tests the error path where:
    - A requests.RequestException occurs during the HTTP request
    - The error should be handled by download_file and propagated as a RuntimeError
    """
    # Setup basic config file
    config = Config.from_dict(
        {
            "tools_dir": str(tmp_path),
            "platforms": {"linux": ["amd64"]},
            "tools": {
                "download-error-tool": {
                    "repo": "owner/download-error-tool",
                    "binary_name": "download-error-tool",
                },
            },
        },
    )

    def mock_latest_release_info(repo: str, quiet: bool = False) -> dict:  # noqa: ARG001
        return {
            "tag_name": "v1.0.0",
            "assets": [
                {
                    "name": "download-error-tool-1.0.0-linux_amd64.tar.gz",
                    "browser_download_url": "https://example.com/download-error-tool-1.0.0-linux_amd64.tar.gz",
                },
            ],
        }

    def mock_requests_get(*args, **kwargs) -> NoReturn:  # noqa: ANN002, ANN003, ARG001
        # Simulate a network error during the request
        err_msg = "Connection refused"
        raise requests.RequestException(err_msg)

    with (
        patch("dotbins.config.latest_release_info", side_effect=mock_latest_release_info),
        patch("dotbins.utils.requests.get", side_effect=mock_requests_get),
    ):
        config.update_tools(verbose=False)  # Turn off verbose to reduce processing

    # Capture the output
    captured = capsys.readouterr()

    # Verify error message in the log output
    assert "Download failed: Connection refused" in captured.out

    # Direct inspection of the update summary object
    failed_entries = config._update_summary.failed
    assert len(failed_entries) > 0

    # Find the entry for our tool
    tool_entry = next(
        (entry for entry in failed_entries if entry.tool == "download-error-tool"),
        None,
    )
    assert tool_entry is not None

    # Verify the details of the failure
    assert tool_entry.platform == "linux"
    assert tool_entry.arch == "amd64"
    assert "Download failed" in tool_entry.reason

    # Verify that no files were downloaded
    bin_dir = config.bin_dir("linux", "amd64")
    assert not bin_dir.exists() or not any(bin_dir.iterdir())

    # Verify version store doesn't have an entry for this tool
    tool_info = config.version_store.get_tool_info("download-error-tool", "linux", "amd64")
    assert tool_info is None
