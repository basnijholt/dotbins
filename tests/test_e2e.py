"""End-to-end tests for dotbins."""

import os
import tarfile
import tempfile
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest

from dotbins.cli import _update_tools
from dotbins.config import _config_from_dict
from dotbins.utils import log


@pytest.fixture
def temp_tools_dir() -> Generator[Path, None, None]:
    """Creates a temporary directory to serve as our `tools_dir`.

    Cleans up after the test.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def create_dummy_tarball(dest: Path, binary_name: str = "mybinary") -> None:
    """Creates a .tar.gz at `dest` containing a single executable file named `binary_name`."""
    with tempfile.TemporaryDirectory() as tmp_extract_dir:
        exe_path = Path(tmp_extract_dir) / binary_name
        exe_path.write_text("#!/usr/bin/env echo\n")
        exe_path.chmod(0o755)
        # Make a tar.gz containing that single file
        with tarfile.open(dest, "w:gz") as tar:
            tar.add(exe_path, arcname=binary_name)


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
def test_e2e_update_tools(temp_tools_dir: Path, raw_config: dict) -> None:
    """Shows an end-to-end test.

    This test:
    - Builds a Config from a dict
    - Mocks out `latest_release_info` to produce predictable asset names
    - Mocks out `download_file` so we skip real network usage
    - Calls `_update_tools` directly
    - Verifies that the binaries are extracted into the correct location.
    """
    config = _config_from_dict(raw_config)
    config.tools_dir = temp_tools_dir

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
            create_dummy_tarball(Path(destination), binary_name="mybinary")
        else:  # "othertool" in url
            create_dummy_tarball(Path(destination), binary_name="otherbin")
        return destination

    with (
        patch("dotbins.config.latest_release_info", side_effect=mock_latest_release_info),
        patch("dotbins.download.download_file", side_effect=mock_download_file),
    ):
        _update_tools(
            config=config,
            tools=[],  # empty => means "update all tools"
            platform=None,  # None => "all configured platforms"
            architecture=None,  # None => "all configured archs"
            current=False,
            force=False,
            shell_setup=False,
        )

    for tool_conf in config.tools.values():
        for platform, arch_list in config.platforms.items():
            for arch in arch_list:
                for binary_name in tool_conf.binary_name:
                    bin_file = config.bin_dir(platform, arch) / binary_name
                    assert bin_file.exists(), f"Expected {bin_file} to exist after update!"
                    assert os.access(bin_file, os.X_OK), f"Expected {bin_file} to be executable"


def test_e2e_update_tools_skip_up_to_date(temp_tools_dir: Path) -> None:
    """Demonstrates a scenario where we have a single tool that is already up-to-date.

    - We populate the VersionStore with the exact version returned by mocked GitHub releases.
    - The `_update_tools` call should skip downloading or extracting anything.
    """
    raw_config = {
        "tools_dir": str(temp_tools_dir),
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
    config.tools_dir = temp_tools_dir  # Ensures we respect the fixture path

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
        _update_tools(
            config=config,
            tools=[],  # update all tools
            platform=None,  # all configured platforms
            architecture=None,  # all configured archs
            current=False,
            force=False,
            shell_setup=False,
        )

    # If everything is skipped, no new binary is downloaded,
    # and the existing version_store is unchanged.
    stored_info = config.version_store.get_tool_info("mytool", "linux", "amd64")
    assert stored_info is not None
    assert stored_info["version"] == "1.2.3"


def test_e2e_update_tools_partial_skip_and_update(temp_tools_dir: Path) -> None:
    """Partial skip & update.

    Demonstrates:
    - 'mytool' is already up-to-date => skip
    - 'othertool' is on an older version => must update.
    """
    raw_config = {
        "tools_dir": str(temp_tools_dir),
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
    config.tools_dir = temp_tools_dir

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
        create_dummy_tarball(Path(destination), binary_name="otherbin")
        return destination

    with (
        patch("dotbins.config.latest_release_info", side_effect=mock_latest_release_info),
        patch("dotbins.download.download_file", side_effect=mock_download_file),
    ):
        _update_tools(
            config=config,
            tools=[],  # update all tools
            platform=None,  # all platforms
            architecture=None,  # all archs
            current=False,
            force=False,
            shell_setup=False,
        )

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


def test_e2e_update_tools_force_re_download(temp_tools_dir: Path) -> None:
    """Force a re-download.

    Scenario:
    - 'mytool' is already up to date at version 1.2.3
    - We specify `force=True` => it MUST redownload
    """
    raw_config = {
        "tools_dir": str(temp_tools_dir),
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
        create_dummy_tarball(Path(destination), binary_name="mybinary")
        return destination

    with (
        patch("dotbins.config.latest_release_info", side_effect=mock_latest_release_info),
        patch("dotbins.download.download_file", side_effect=mock_download_file),
    ):
        # Force a re-download, even though we're "up to date"
        _update_tools(
            config=config,
            tools=["mytool"],
            platform="linux",
            architecture="amd64",
            current=False,
            force=True,  # Key point: forcing
            shell_setup=False,
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


def test_e2e_update_tools_specific_platform(temp_tools_dir: Path) -> None:
    """Update a specific platform.

    Scenario: We have a config with 'linux' & 'macos', but only request updates for 'macos'
    => Only macOS assets are fetched and placed in the correct bin dir.
    """
    raw_config = {
        "tools_dir": str(temp_tools_dir),
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
        create_dummy_tarball(Path(destination), binary_name="mybinary")
        return destination

    with (
        patch("dotbins.config.latest_release_info", side_effect=mock_latest_release_info),
        patch("dotbins.download.download_file", side_effect=mock_download_file),
    ):
        # Only update macOS => We expect only the darwin_arm64 asset
        _update_tools(
            config=config,
            tools=[],  # update all tools
            platform="macos",  # crucial
            architecture=None,  # means all archs for macos => only arm64 in this config
            current=False,
            force=False,
            shell_setup=False,
        )

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
