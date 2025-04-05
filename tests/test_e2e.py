"""End-to-end tests for dotbins."""

from __future__ import annotations

import os
import tarfile
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, NoReturn
from unittest.mock import patch

import pytest
import requests

from dotbins.cli import _get_tool
from dotbins.config import Config, RawConfigDict, RawToolConfigDict
from dotbins.utils import current_platform, log

if TYPE_CHECKING:
    from requests_mock import Mocker


def _create_mock_release_info(
    tool_name: str,
    version: str,
    platforms: dict[str, list[str]],
    extension: str = ".tar.gz",
) -> dict[str, Any]:
    assets = [
        {
            "name": f"{tool_name}-{version}-{platform}_{arch}{extension}",
            "browser_download_url": f"https://example.com/{tool_name}-{version}-{platform}_{arch}{extension}",
        }
        for platform in platforms
        for arch in platforms[platform]
    ]
    return {"tag_name": f"v{version}", "assets": assets}


def _set_mock_release_info(
    config: Config,
    version: str = "1.2.3",
    extension: str = ".tar.gz",
) -> None:
    """Set the mock release info for the given config."""
    for tool_name, tool_config in config.tools.items():
        tool_config._release_info = _create_mock_release_info(
            tool_name,
            version,
            config.platforms,
            extension,
        )


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
        "tools": tool_configs,  # type: ignore[typeddict-item]
    }

    config = Config.from_dict(raw_config)
    _set_mock_release_info(config)

    def mock_download_file(
        url: str,
        destination: str,
        github_token: str | None,  # noqa: ARG001
        verbose: bool,  # noqa: ARG001
    ) -> str:
        # Extract tool name from URL
        parts = url.split("/")[-1].split("-")
        tool_name = parts[0]

        # Create a dummy archive with the right name
        create_dummy_archive(Path(destination), tool_name)
        return destination

    with patch("dotbins.download.download_file", side_effect=mock_download_file):
        log("Running sync_tools")
        # Run the update
        config.sync_tools(
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
            "extract_archive": True,
            "binary_name": "mytool",
            "path_in_archive": "mytool",
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
            "extract_archive": True,
            "binary_name": "tool1",
            "path_in_archive": "tool1",
            "asset_patterns": "tool1-{version}-{platform}_{arch}.tar.gz",
        },
        "tool2": {
            "repo": "fakeuser/tool2",
            "extract_archive": True,
            "binary_name": "tool2",
            "path_in_archive": "tool2",
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
                    "extract_archive": True,
                    "binary_name": "mybinary",
                    "path_in_archive": "mybinary",
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
                    "extract_archive": True,
                    "binary_name": "mybinary",
                    "path_in_archive": "mybinary",
                    "asset_patterns": {
                        "linux": {
                            "amd64": "mytool-{version}-linux_{arch}.tar.gz",
                            "arm64": "mytool-{version}-linux_{arch}.tar.gz",
                        },
                    },
                },
                "othertool": {
                    "repo": "fakeuser/othertool",
                    "extract_archive": True,
                    "binary_name": "otherbin",
                    "path_in_archive": "otherbin",
                    "asset_patterns": "othertool-{version}-{platform}_{arch}.tar.gz",
                },
            },
        },
    ],
)
def test_e2e_sync_tools(
    tmp_path: Path,
    raw_config: RawConfigDict,
    create_dummy_archive: Callable,
) -> None:
    """Test the end-to-end tool sync workflow with different configurations."""
    config = Config.from_dict(raw_config)
    config.tools_dir = tmp_path
    _set_mock_release_info(config, version="1.2.3")

    def mock_download_file(
        url: str,
        destination: str,
        github_token: str | None,  # noqa: ARG001
        verbose: bool,  # noqa: ARG001
    ) -> str:
        log(f"MOCKED download_file from {url} -> {destination}", "info")
        if "mytool" in url:
            create_dummy_archive(Path(destination), binary_names="mybinary")
        else:  # "othertool" in url
            create_dummy_archive(Path(destination), binary_names="otherbin")
        return destination

    with patch("dotbins.download.download_file", side_effect=mock_download_file):
        config.sync_tools()

    verify_binaries_installed(config)


def test_e2e_sync_tools_skip_up_to_date(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test that tools are skipped if they are already up to date."""
    raw_config: RawConfigDict = {
        "tools_dir": str(tmp_path),
        "platforms": {"linux": ["amd64"]},
        "tools": {
            "mytool": {
                "repo": "fakeuser/mytool",
                "extract_archive": True,
                "binary_name": "mybinary",
                "path_in_archive": "mybinary",
                "asset_patterns": "mytool-{version}-linux_{arch}.tar.gz",
            },
        },
    }

    config = Config.from_dict(raw_config)
    config.tools_dir = tmp_path  # Ensures we respect the fixture path
    _set_mock_release_info(config, version="1.2.3")

    # Pre-populate version_store with version='1.2.3' so it should SKIP
    config.version_store.update_tool_info(
        tool="mytool",
        platform="linux",
        arch="amd64",
        version="1.2.3",
        sha256="sha256",
    )
    bin_dir = config.bin_dir("linux", "amd64")
    bin_dir.mkdir(parents=True, exist_ok=True)
    (bin_dir / "mybinary").touch()  # Ensure binary exists

    def mock_download_file(*args: Any, **kwargs: Any) -> str:  # pragma: no cover
        msg = "This should never be called"
        raise NotImplementedError(msg)

    with patch("dotbins.download.download_file", side_effect=mock_download_file):
        config.sync_tools()

    # If everything is skipped, no new binary is downloaded,
    # and the existing version_store is unchanged.
    stored_info = config.version_store.get_tool_info("mytool", "linux", "amd64")
    assert stored_info is not None
    assert stored_info["version"] == "1.2.3"

    # Check that no download was attempted
    out = capsys.readouterr().out
    assert "--force to re-download" in out


def test_e2e_sync_tools_partial_skip_and_update(
    tmp_path: Path,
    create_dummy_archive: Callable,
) -> None:
    """Test that some tools are skipped and others are updated."""
    raw_config: RawConfigDict = {
        "tools_dir": str(tmp_path),
        "platforms": {"linux": ["amd64"]},
        "tools": {
            "mytool": {
                "repo": "fakeuser/mytool",
                "extract_archive": True,
                "binary_name": "mybinary",
                "path_in_archive": "mybinary",
                "asset_patterns": "mytool-{version}-linux_{arch}.tar.gz",
            },
            "othertool": {
                "repo": "fakeuser/othertool",
                "extract_archive": True,
                "binary_name": "otherbin",
                "path_in_archive": "otherbin",
                "asset_patterns": "othertool-{version}-linux_{arch}.tar.gz",
            },
        },
    }

    config = Config.from_dict(raw_config)
    _set_mock_release_info(config, version="2.0.0")

    # Mark 'mytool' as already up-to-date
    config.version_store.update_tool_info(
        tool="mytool",
        platform="linux",
        arch="amd64",
        version="2.0.0",
        sha256="sha256",
    )

    # Mark 'othertool' as older so it gets updated
    config.version_store.update_tool_info(
        tool="othertool",
        platform="linux",
        arch="amd64",
        version="1.0.0",
        sha256="sha256",
    )

    def mock_download_file(
        url: str,
        destination: str,
        github_token: str | None,  # noqa: ARG001
        verbose: bool,  # noqa: ARG001
    ) -> str:
        # Only called for 'othertool' if skip for 'mytool' works
        if "mytool" in url:
            msg = "Should not download mytool if up-to-date!"
            raise RuntimeError(msg)
        create_dummy_archive(Path(destination), binary_names="otherbin")
        return destination

    with patch("dotbins.download.download_file", side_effect=mock_download_file):
        config.sync_tools()

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


def test_e2e_sync_tools_force_re_download(tmp_path: Path, create_dummy_archive: Callable) -> None:
    """Test that the --force flag forces re-download of up-to-date tools."""
    raw_config: RawConfigDict = {
        "tools_dir": str(tmp_path),
        "platforms": {"linux": ["amd64"]},
        "tools": {
            "mytool": {
                "repo": "fakeuser/mytool",
                "extract_archive": True,
                "binary_name": "mybinary",
                "path_in_archive": "mybinary",
                "asset_patterns": "mytool-{version}-linux_{arch}.tar.gz",
            },
        },
    }
    config = Config.from_dict(raw_config)
    _set_mock_release_info(config, version="1.2.3")
    # Mark 'mytool' as installed at 1.2.3
    config.version_store.update_tool_info("mytool", "linux", "amd64", "1.2.3", "sha256")
    tool_info = config.version_store.get_tool_info("mytool", "linux", "amd64")
    assert tool_info is not None
    original_updated_at = tool_info["updated_at"]

    downloaded_urls = []

    def mock_download_file(
        url: str,
        destination: str,
        github_token: str | None,  # noqa: ARG001
        verbose: bool,  # noqa: ARG001
    ) -> str:
        downloaded_urls.append(url)
        create_dummy_archive(Path(destination), binary_names="mybinary")
        return destination

    with patch("dotbins.download.download_file", side_effect=mock_download_file):
        # Force a re-download, even though we're "up to date"
        config.sync_tools(
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


def test_e2e_sync_tools_specific_platform(tmp_path: Path, create_dummy_archive: Callable) -> None:
    """Test syncing tools for a specific platform only."""
    raw_config: RawConfigDict = {
        "tools_dir": str(tmp_path),
        "platforms": {
            "linux": ["amd64", "arm64"],
            "macos": ["arm64"],
        },
        "tools": {
            "mytool": {
                "repo": "fakeuser/mytool",
                "extract_archive": True,
                "binary_name": "mybinary",
                "path_in_archive": "mybinary",
                "asset_patterns": {  # type: ignore[typeddict-item]
                    "linux": {
                        "amd64": "mytool-{version}-linux_amd64.tar.gz",
                        "arm64": "mytool-{version}-linux_arm64.tar.gz",
                    },
                    "macos": {
                        "arm64": "mytool-{version}-{platform}_arm64.tar.gz",
                    },
                },
            },
        },
    }
    config = Config.from_dict(raw_config)
    _set_mock_release_info(config, version="1.0.0")

    downloaded_files = []

    def mock_download_file(
        url: str,
        destination: str,
        github_token: str | None,  # noqa: ARG001
        verbose: bool,  # noqa: ARG001
    ) -> str:
        downloaded_files.append(url)
        # Each call uses the same tar generation but with different binary content
        create_dummy_archive(Path(destination), binary_names="mybinary")
        return destination

    with patch("dotbins.download.download_file", side_effect=mock_download_file):
        # Only update macOS => We expect only the macos_arm64 asset
        config.sync_tools(platform="macos")

    # Should only have downloaded the macos_arm64 file
    assert len(downloaded_files) == 1
    assert "mytool-1.0.0-macos_arm64.tar.gz" in downloaded_files[0]

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

    def mock_fetch_release_info(
        repo: str,  # noqa: ARG001
        version: str | None = None,  # noqa: ARG001
        github_token: str | None = None,  # noqa: ARG001
    ) -> dict:
        return {
            "tag_name": "v1.0.0",
            "assets": [
                {
                    "name": f"mytool-1.0.0-{platform}_{arch}.tar.gz",
                    "browser_download_url": f"https://example.com/mytool-1.0.0-{platform}_{arch}.tar.gz",
                },
            ],
        }

    def mock_download_file(
        url: str,  # noqa: ARG001
        destination: str,
        github_token: str | None,  # noqa: ARG001
        verbose: bool,  # noqa: ARG001
    ) -> str:
        create_dummy_archive(Path(destination), binary_names="mytool")
        return destination

    with (
        patch("dotbins.download.download_file", side_effect=mock_download_file),
        patch("dotbins.config.fetch_release_info", side_effect=mock_fetch_release_info),
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

    def mock_fetch_release_info(
        repo: str,
        version: str | None = None,  # noqa: ARG001
        github_token: str | None = None,  # noqa: ARG001
    ) -> dict:
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

    def mock_download_file(
        url: str,
        destination: str,
        github_token: str | None,  # noqa: ARG001
        verbose: bool,  # noqa: ARG001
    ) -> str:
        log(f"Downloading from {url} to {destination}", "info")
        tool_name = url.split("/")[-1].split("-")[0]
        log(f"Creating archive for {tool_name}", "info")
        create_dummy_archive(Path(destination), binary_names=tool_name)
        return destination

    with (
        patch("dotbins.utils.requests.get", side_effect=mock_requests_get),
        patch("dotbins.download.download_file", side_effect=mock_download_file),
        patch("dotbins.config.fetch_release_info", side_effect=mock_fetch_release_info),
    ):
        _get_tool(source="https://example.com/config.yaml", dest_dir=dest_dir)

    # Verify that both tools from the config were installed
    assert (dest_dir / "tool1").exists()
    assert (dest_dir / "tool2").exists()


def test_get_tool_command_with_local_config(
    tmp_path: Path,
    create_dummy_archive: Callable,
) -> None:
    """Test the 'get' command with a local config file.

    This tests the functionality to install the tools defined in a local YAML configuration file.
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
    cfg_path = tmp_path / "dotbins.yaml"
    cfg_path.write_text(yaml_content)

    def mock_fetch_release_info(
        repo: str,
        version: str | None = None,  # noqa: ARG001
        github_token: str | None = None,  # noqa: ARG001
    ) -> dict:
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

    def mock_download_file(
        url: str,
        destination: str,
        github_token: str | None,  # noqa: ARG001
        verbose: bool,  # noqa: ARG001
    ) -> str:
        log(f"Downloading from {url} to {destination}", "info")
        tool_name = url.split("/")[-1].split("-")[0]
        log(f"Creating archive for {tool_name}", "info")
        create_dummy_archive(Path(destination), binary_names=tool_name)
        return destination

    with (
        patch("dotbins.download.download_file", side_effect=mock_download_file),
        patch("dotbins.config.fetch_release_info", side_effect=mock_fetch_release_info),
    ):
        _get_tool(source=str(cfg_path), dest_dir=dest_dir)

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
    _set_mock_release_info(config, version="1.0.0")
    assert config.tools_dir == dest_dir
    assert config.platforms == {platform: [arch]}

    def mock_download_file(
        url: str,
        destination: str,
        github_token: str | None,  # noqa: ARG001
        verbose: bool,  # noqa: ARG001
    ) -> str:
        log(f"Downloading from {url} to {destination}", "info")
        tool_name = url.split("/")[-1].split("-")[0]
        log(f"Creating archive for {tool_name}", "info")
        create_dummy_archive(Path(destination), binary_names=tool_name)
        return destination

    with patch("dotbins.download.download_file", side_effect=mock_download_file):
        config.sync_tools(copy_config_file=True)

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
    _set_mock_release_info(config, version="1.0.0")

    config.sync_tools(platform="windows")
    captured = capsys.readouterr()
    assert "Skipping unknown platform: windows" in captured.out

    config.sync_tools(architecture="nonexistent")
    captured = capsys.readouterr()
    assert "Skipping unknown architecture: nonexistent" in captured.out


def test_non_extract_with_multiple_binary_names(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test error handling when a non-extractable binary has multiple binary names specified.

    This tests the error path where:
    - extract_archive is set to False (use download directly)
    - More than one binary name is specified
    - The update should fail with a specific error in the summary
    """
    # Setup config with a tool that has extract_archive=False but multiple binary names
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
                    extract_archive: false
                    binary_name:
                      - tool-bin1
                      - tool-bin2
            """,
        ),
    )
    config = Config.from_file(config_path)
    _set_mock_release_info(config, version="1.0.0")

    def mock_download_file(
        url: str,  # noqa: ARG001
        destination: str,
        github_token: str | None,  # noqa: ARG001
        verbose: bool,  # noqa: ARG001
    ) -> str:
        # Create a dummy file - this would normally be a binary file
        Path(destination).write_text("dummy binary content")
        return destination

    with patch("dotbins.download.download_file", side_effect=mock_download_file):
        # Run the update which should fail for the multi-bin tool
        config.sync_tools()

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
    - extract_archive is set to False (direct copy of downloaded file)
    - Exactly one binary name is specified
    - The binary should be copied directly to the destination
    """
    # Setup config with a tool that has extract_archive=False and a single binary name
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
                    extract_archive: false
                    binary_name: tool-binary
            """,
        ),
    )
    config = Config.from_file(config_path)
    extension = ".exe" if os.name == "nt" else ".tar.gz"
    _set_mock_release_info(config, version="1.0.0", extension=extension)

    def mock_download_file(
        url: str,  # noqa: ARG001
        destination: str,
        github_token: str | None,  # noqa: ARG001
        verbose: bool,  # noqa: ARG001
    ) -> str:
        # Create a dummy binary file with executable content
        Path(destination).write_text("#!/bin/sh\necho 'Hello from tool-binary'")
        return destination

    with patch("dotbins.download.download_file", side_effect=mock_download_file):
        # Run the update which should succeed for the single binary tool
        config.sync_tools()

    # Capture the output
    captured = capsys.readouterr()

    # Verify successful messages in the output
    assert "Successfully installed single-bin-tool" in captured.out

    # Verify that the binary file was created with the correct name
    bin_dir = config.bin_dir("linux", "amd64")
    name = "tool-binary.exe" if os.name == "nt" else "tool-binary"
    binary_path = bin_dir / name
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
    config.tools["error-tool"]._release_info = {"tag_name": "v1.0.0", "assets": []}

    # Create a BinSpec.matching_asset method that raises an exception
    def mock_matching_asset(self) -> NoReturn:  # noqa: ANN001, ARG001
        msg = "Simulated error in matching asset"
        raise RuntimeError(msg)

    # Use patch to inject our exception
    with patch("dotbins.config.BinSpec.matching_asset", mock_matching_asset):
        config.sync_tools(verbose=True)

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
                    "path_in_archive": "nonexistent/path/tool-binary",
                    "extract_archive": True,
                },
            },
        },
    )
    _set_mock_release_info(config, version="1.0.0")

    def mock_download_file(
        url: str,  # noqa: ARG001
        destination: str,
        github_token: str | None,  # noqa: ARG001
        verbose: bool,  # noqa: ARG001
    ) -> str:
        # Create a dummy archive but WITHOUT the expected binary path
        create_dummy_archive(Path(destination), binary_names="different-binary-name")
        return destination

    with patch("dotbins.download.download_file", side_effect=mock_download_file):
        config.sync_tools()

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


def test_auto_detect_paths_in_archive_error(
    tmp_path: Path,
    create_dummy_archive: Callable,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test error handling when auto-detection of binary paths fails.

    This tests the error path where:
    - The download succeeds
    - The extraction succeeds
    - The tool has no path_in_archive specified, so auto-detection is used
    - Auto-detection fails because no binary matches the expected name
    - The error should be properly categorized as 'Auto-detect binary paths error'
    """
    # Setup config without path_in_archive - will trigger auto-detection
    config = Config.from_dict(
        {
            "tools_dir": str(tmp_path),
            "platforms": {"linux": ["amd64"]},
            "tools": {
                "auto-detect-error-tool": {
                    "repo": "owner/auto-detect-error-tool",
                    "binary_name": "expected-binary",  # This name won't match anything in the archive
                    "extract_archive": True,
                    # No path_in_archive specified - will use auto-detection
                },
            },
        },
    )
    _set_mock_release_info(config, version="1.0.0")

    def mock_download_file(
        url: str,  # noqa: ARG001
        destination: str,
        github_token: str | None,  # noqa: ARG001
        verbose: bool,  # noqa: ARG001
    ) -> str:
        # Create a dummy archive with a binary that won't match the expected name
        create_dummy_archive(Path(destination), binary_names="different-binary-name")
        return destination

    with patch("dotbins.download.download_file", side_effect=mock_download_file):
        config.sync_tools()

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
    _set_mock_release_info(config, version="1.0.0")

    def mock_requests_get(*args, **kwargs) -> NoReturn:  # noqa: ANN002, ANN003, ARG001
        # Simulate a network error during the request
        err_msg = "Connection refused"
        raise requests.RequestException(err_msg)

    with (
        patch("dotbins.utils.requests.get", side_effect=mock_requests_get),
    ):
        config.sync_tools(verbose=False)  # Turn off verbose to reduce processing

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


def test_no_matching_asset(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test error handling when no matching asset is found."""
    config = Config.from_dict(
        {
            "tools_dir": str(tmp_path),
            "platforms": {"linux": ["amd64"]},
            "tools": {
                "mytool": {
                    "repo": "fakeuser/mytool",
                    "asset_patterns": "mytool-{version}-linux_{arch}.tar.gz",
                },
            },
        },
    )
    config.tools["mytool"]._release_info = {"tag_name": "v1.0.0", "assets": []}

    config.sync_tools()

    # Capture the output
    captured = capsys.readouterr()

    # Verify error message in the log output
    assert "No matching asset found" in captured.out


def test_no_tools(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test syncing with no tools."""
    config = Config(tools_dir=tmp_path)
    config.sync_tools()

    captured = capsys.readouterr()
    assert "No tools configured" in captured.out


def test_auto_detect_asset_multiple_perfect_matches(
    tmp_path: Path,
    create_dummy_archive: Callable,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test handling of multiple perfect matches."""
    raw_config: RawConfigDict = {
        "tools_dir": str(tmp_path),
        "platforms": {"linux": ["amd64"]},
        "tools": {"mytool": {"repo": "fakeuser/mytool"}},
    }
    config = Config.from_dict(raw_config)

    config.tools["mytool"]._release_info = {
        "tag_name": "v1.2.3",
        "assets": [
            {
                "name": "mytool-1.2.3-linux_amd64.tar.gz",
                "browser_download_url": "https://example.com/mytool-1.2.3-linux_amd64.tar.gz",
            },
            {
                "name": "mytool-1.2.3-linux_x86_64.tar.gz",
                "browser_download_url": "https://example.com/mytool-1.2.3-linux_x86_64.tar.gz",
            },
        ],
    }

    def mock_download_file(
        url: str,  # noqa: ARG001
        destination: str,
        github_token: str | None,  # noqa: ARG001
        verbose: bool,  # noqa: ARG001
    ) -> str:
        # Create a dummy archive with a binary that won't match the expected name
        create_dummy_archive(Path(destination), binary_names="mytool")
        return destination

    with patch("dotbins.download.download_file", side_effect=mock_download_file):
        config.sync_tools()

    out = capsys.readouterr().out
    assert "Found multiple candidates" in out
    assert "selecting first" in out

    # Verify that the correct binary was downloaded
    bin_dir = config.bin_dir("linux", "amd64")
    assert bin_dir.exists()
    assert (bin_dir / "mytool").exists()


def test_auto_detect_asset_no_matches(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test handling of no matching assets."""
    raw_config: RawConfigDict = {
        "tools_dir": str(tmp_path),
        "platforms": {"linux": ["arm64"]},
        "tools": {"mytool": {"repo": "fakeuser/mytool"}},
    }
    config = Config.from_dict(raw_config)

    config.tools["mytool"]._release_info = _create_mock_release_info(
        "mytool",
        "1.2.3",
        {"linux": ["amd64", "i386"]},  # Different arch
    )

    config.sync_tools()

    out = capsys.readouterr().out
    assert "Found multiple candidates" in out, out
    assert "manually select one" in out


def test_sync_tools_with_empty_archive(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test syncing tools with an empty archive."""
    raw_config: RawConfigDict = {
        "tools_dir": str(tmp_path),
        "platforms": {"linux": ["amd64"]},
        "tools": {
            "mytool": {"repo": "fakeuser/mytool", "path_in_archive": "*", "extract_archive": True},
        },
    }
    config = Config.from_dict(raw_config)
    _set_mock_release_info(config, version="1.2.3")

    def mock_download_file(
        url: str,  # noqa: ARG001
        destination: str,
        github_token: str | None,  # noqa: ARG001
        verbose: bool,  # noqa: ARG001
    ) -> str:
        # Create an empty archive
        Path(destination).touch()
        with tarfile.open(destination, "w:gz") as tar:
            tar.add(destination, arcname="empty.tar.gz")
        return destination

    with patch("dotbins.download.download_file", side_effect=mock_download_file):
        config.sync_tools()

    out = capsys.readouterr().out
    assert "Error extracting archive: No files matching *" in out
    assert "Error processing mytool: No files matching *" in out


def test_failed_to_fetch_release_info(
    tmp_path: Path,
    requests_mock: Mocker,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test handling of failed to fetch release info."""
    raw_config: RawConfigDict = {
        "tools_dir": str(tmp_path),
        "platforms": {"linux": ["amd64"]},
        "tools": {"mytool": {"repo": "fakeuser/mytool"}},
    }
    config = Config.from_dict(raw_config)
    requests_mock.get(
        "https://api.github.com/repos/fakeuser/mytool/releases/latest",
        status_code=403,
        # Same as on real GitHub API
        reason="rate limit exceeded for url: https://api.github.com/repos/fakeuser/mytool/releases/latest",
    )
    config.sync_tools()

    out = capsys.readouterr().out
    assert "Failed to fetch latest release for" in out
    assert "limit exceeded" in out


def test_failed_to_download_file(
    tmp_path: Path,
    requests_mock: Mocker,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test handling of failed to download file."""
    raw_config: RawConfigDict = {
        "tools_dir": str(tmp_path),
        "platforms": {"linux": ["amd64"]},
        "tools": {"mytool": {"repo": "fakeuser/mytool"}},
    }
    config = Config.from_dict(raw_config)
    url = "https://example.com/mytool-1.2.3-linux_amd64.tar.gz"
    requests_mock.get(
        "https://api.github.com/repos/fakeuser/mytool/releases/latest",
        json={
            "tag_name": "v1.2.3",
            "assets": [
                {
                    "name": "mytool-1.2.3-linux_amd64.tar.gz",
                    "browser_download_url": url,
                },
            ],
        },
    )
    requests_mock.get(
        url=url,
        status_code=403,
        reason="rate limit exceeded for url: https://api.github.com/repos/fakeuser/mytool/releases/latest",
    )
    config.sync_tools()

    out = capsys.readouterr().out
    assert "Failed to download" in out
    assert "limit exceeded" in out


def test_cli_unknown_tool(tmp_path: Path) -> None:
    """Test syncing an unknown tool."""
    raw_config: RawConfigDict = {
        "tools_dir": str(tmp_path),
        "platforms": {"linux": ["amd64"]},
        "tools": {"test-tool": {"repo": "test/tool"}},
    }
    config = Config.from_dict(raw_config)
    with pytest.raises(SystemExit):
        config.sync_tools(
            tools=["unknown-tool"],
            platform=None,
            architecture=None,
            current=False,
            force=False,
            generate_readme=True,
            copy_config_file=True,
            generate_shell_scripts=True,
            github_token=None,
            verbose=True,
        )


def test_sync_tool_match_path_in_archive_with_glob(
    tmp_path: Path,
    create_dummy_archive: Callable,
) -> None:
    """Test syncing a specific tool."""
    # Set up mock environment
    config = Config.from_dict(
        {
            "tools_dir": str(tmp_path),
            "platforms": {"linux": ["amd64"]},
            "tools": {
                "test-tool": {
                    "repo": "test/tool",
                    "extract_archive": True,
                    "binary_name": "test-tool",
                    "path_in_archive": "*",
                    "asset_patterns": "test-tool-{version}-{platform}_{arch}.tar.gz",
                    "platform_map": {"macos": "darwin"},
                },
            },
        },
    )
    tool_config = config.tools["test-tool"]
    tool_config._release_info = {
        "tag_name": "v1.0.0",
        "assets": [
            {
                "name": "test-tool-1.0.0-linux_amd64.tar.gz",
                "browser_download_url": "https://example.com/test-tool-1.0.0-linux_amd64.tar.gz",
            },
        ],
    }

    # Create config with our test tool - use new format
    config = Config(
        tools_dir=tmp_path / "tools",
        platforms={"linux": ["amd64"]},  # Just linux/amd64 for this test
        tools={"test-tool": tool_config},
    )

    # Mock the download_file function to use our fixture
    def mock_download_file(
        url: str,  # noqa: ARG001
        destination: str,
        github_token: str | None,  # noqa: ARG001
        verbose: bool,  # noqa: ARG001
    ) -> str:
        create_dummy_archive(dest_path=Path(destination), binary_names="test-tool")
        return destination

    # Directly call sync_tools
    with patch("dotbins.download.download_file", mock_download_file):
        config.sync_tools(
            tools=["test-tool"],
            platform="linux",
            architecture="amd64",
            current=False,
            force=False,
            generate_readme=True,
            copy_config_file=True,
            generate_shell_scripts=True,
            github_token=None,
            verbose=True,
        )

    # Check if binary was installed
    assert (tmp_path / "tools" / "linux" / "amd64" / "bin" / "test-tool").exists()


def test_tool_shell_code_in_shell_scripts(
    tmp_path: Path,
    create_dummy_archive: Callable,
) -> None:
    """Test that tool shell_code is included in the generated shell scripts.

    It verifies that:
    1. shell_code is properly included for tools that have it
    2. tools without shell_code don't have code blocks generated
    3. syntax is appropriate for different shells (bash, zsh, fish, nushell)
    4. sync_tools correctly triggers shell script generation
    """
    tools_dir = tmp_path / "tools"

    # Create a config with tools that have shell_code and some that don't
    tool_configs: dict[str, RawToolConfigDict] = {
        "fzf": {
            "repo": "junegunn/fzf",
            "shell_code": "source <(fzf --zsh)",
        },
        "bat": {
            "repo": "sharkdp/bat",  # No shell_code
        },
        "zoxide": {
            "repo": "ajeetdsouza/zoxide",
            "shell_code": 'eval "$(zoxide init zsh)"',
        },
        "eza": {
            "repo": "eza-community/eza",
            "shell_code": "alias l='eza -lah --git'",
        },
        "starship": {
            "repo": "starship/starship",
            "shell_code": {
                "zsh": 'eval "$(starship init zsh)"',
                "bash": 'eval "$(starship init bash)"',
                "fish": "starship init fish | source",
                "nushell": (
                    'mkdir ($nu.data-dir | path join "vendor/autoload")'
                    '\nstarship init nu | save -f ($nu.data-dir | path join "vendor/autoload/starship.nu")'
                ),
            },
        },
    }

    config = Config.from_dict(
        {
            "tools_dir": str(tools_dir),
            "platforms": {"linux": ["amd64"]},
            "tools": tool_configs,  # type: ignore[typeddict-item]
        },
    )
    _set_mock_release_info(config, version="1.2.3")

    # Mock the download_file function
    def mock_download_file(
        url: str,
        destination: str,
        github_token: str | None,  # noqa: ARG001
        verbose: bool,  # noqa: ARG001
    ) -> str:
        binary_name = url.split("/")[-1].split("-")[0]
        create_dummy_archive(Path(destination), binary_name)
        return destination

    # Run sync_tools to generate the shell scripts
    with patch("dotbins.download.download_file", side_effect=mock_download_file):
        config.sync_tools()

    # Check that shell scripts were generated for all supported shells
    shell_files = {
        "bash": "bash.sh",
        "zsh": "zsh.sh",
        "fish": "fish.fish",
        "nushell": "nushell.nu",
        "powershell": "powershell.ps1",
    }

    for shell, filename in shell_files.items():
        shell_script_path = tools_dir / "shell" / filename
        assert shell_script_path.exists(), f"Shell script for {shell} not created"

        # Read the shell script content
        content = shell_script_path.read_text()

        # Verify shell_code is included with correct syntax for each shell
        if shell in ("bash", "zsh"):
            # Check tools with shell_code
            for tool in ["fzf", "zoxide", "eza", "starship"]:
                assert f"if command -v {tool} >/dev/null 2>&1; then" in content

            # Verify specific shell code for each tool
            assert "source <(fzf --zsh)" in content
            assert 'eval "$(zoxide init zsh)"' in content
            assert "alias l='eza -lah --git'" in content

            # Check shell-specific starship code
            if shell == "bash":
                assert 'eval "$(starship init bash)"' in content
            elif shell == "zsh":
                assert 'eval "$(starship init zsh)"' in content

            # Check tool without shell_code has no block
            assert "if command -v bat >/dev/null 2>&1; then" not in content

        elif shell == "fish":
            # Check tools with shell_code (fish syntax)
            for tool in ["fzf", "zoxide", "eza", "starship"]:
                assert f"if command -v {tool} >/dev/null 2>&1" in content

            # Verify specific shell code
            assert "source <(fzf --zsh)" in content
            assert 'eval "$(zoxide init zsh)"' in content
            assert "alias l='eza -lah --git'" in content
            assert "starship init fish | source" in content  # Fish-specific starship code

            # Check tool without shell_code has no block
            assert "if command -v bat >/dev/null 2>&1" not in content

        elif shell == "nushell":
            # Check tools with shell_code (nushell syntax)
            for tool in ["fzf", "zoxide", "eza", "starship"]:
                assert f"if (which {tool}) != null {{" in content

            # Verify specific shell code
            assert "source <(fzf --zsh)" in content
            assert 'eval "$(zoxide init zsh)"' in content
            assert "alias l='eza -lah --git'" in content

            # Nushell-specific starship code
            assert 'mkdir ($nu.data-dir | path join "vendor/autoload")' in content
            assert (
                'starship init nu | save -f ($nu.data-dir | path join "vendor/autoload/starship.nu")'
                in content
            )

            # Check tool without shell_code has no block
            assert "if (which bat) != null {" not in content


def test_eza_arch_detection(
    tmp_path: Path,
    create_dummy_archive: Callable,
) -> None:
    """Test that eza is detected correctly for different architectures."""
    # Covers the "If p_val is a single string, apply to all arch" case
    config = Config.from_dict(
        {
            "tools_dir": str(tmp_path),
            "platforms": {"linux": ["amd64", "arm64"]},
            "tools": {
                "eza": {
                    "repo": "eza-community/eza",
                    "arch_map": {"amd64": "x86_64", "arm64": "aarch64"},
                    "asset_patterns": {
                        "linux": "eza_{arch}-unknown-linux-gnu.tar.gz",
                        "macos": None,
                    },  # type: ignore[typeddict-item]
                },
            },
        },
    )

    config.tools["eza"]._release_info = {
        "tag_name": "0.12.1",
        "assets": [
            {
                "name": "eza_x86_64-unknown-linux-gnu.tar.gz",
                "browser_download_url": "https://example.com/eza_x86_64-unknown-linux-gnu.tar.gz",
            },
            {
                "name": "eza_aarch64-unknown-linux-gnu.tar.gz",
                "browser_download_url": "https://example.com/eza_aarch64-unknown-linux-gnu.tar.gz",
            },
        ],
    }

    def mock_download_file(
        url: str,  # noqa: ARG001
        destination: str,
        github_token: str | None,  # noqa: ARG001
        verbose: bool,  # noqa: ARG001
    ) -> str:
        create_dummy_archive(Path(destination), "eza")
        return destination

    with patch("dotbins.download.download_file", side_effect=mock_download_file):
        config.sync_tools()


@pytest.mark.parametrize("tag", ["latest", "v1.0.0", ""])
def test_tool_with_custom_tag(
    tmp_path: Path,
    requests_mock: Mocker,
    create_dummy_archive: Callable,
    capsys: pytest.CaptureFixture[str],
    tag: str,
) -> None:
    """Test that a tool with a custom tag is synced correctly."""
    config_path = tmp_path / "dotbins.yaml"
    config_path.write_text(
        textwrap.dedent(
            f"""\
            tools_dir: {tmp_path!s}
            platforms:
                linux: ["amd64"]
            tools:
                tool:
                    repo: owner/tool
                    tag: {tag}
            """,
        ),
    )
    config = Config.from_file(config_path)
    json = {
        "tag_name": "v1.0.0",
        "assets": [
            {
                "name": "tool-v1.0.0-linux-amd64.tar.gz",
                "browser_download_url": "https://example.com/tool-v1.0.0-linux-amd64.tar.gz",
            },
        ],
    }
    requests_mock.get("https://api.github.com/repos/owner/tool/releases/tags/v1.0.0", json=json)
    requests_mock.get("https://api.github.com/repos/owner/tool/releases/latest", json=json)

    def mock_download_file(
        url: str,  # noqa: ARG001
        destination: str,
        github_token: str | None,  # noqa: ARG001
        verbose: bool,  # noqa: ARG001
    ) -> str:
        # Create a dummy binary file with executable content
        create_dummy_archive(Path(destination), binary_names="tool")
        return destination

    with patch("dotbins.download.download_file", side_effect=mock_download_file):
        # Run the update which should succeed for the single binary tool
        config.sync_tools()

    # Capture the output
    out = capsys.readouterr().out

    # Verify successful messages in the output
    assert "Successfully installed tool" in out

    # Verify that the binary file was created with the correct name
    bin_dir = config.bin_dir("linux", "amd64")
    binary_path = bin_dir / "tool"
    assert binary_path.exists(), out
    # Verify the version store was updated
    tool_info = config.version_store.get_tool_info("tool", "linux", "amd64")
    assert tool_info is not None
    assert tool_info["version"] == "1.0.0"
