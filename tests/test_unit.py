"""Unit tests for the dotbins module."""

from __future__ import annotations

import os
import tarfile
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Callable
from unittest.mock import patch

import pytest

import dotbins
from dotbins.config import BinSpec, Config, RawToolConfigDict, _find_config_file, build_tool_config
from dotbins.utils import replace_home_in_path
from dotbins.versions import VersionStore

if TYPE_CHECKING:
    from requests_mock import Mocker


def _is_executable_or_file(path: Path) -> bool:
    if os.name == "nt":
        # For Windows, skip the executable bit check, just check that the file exists
        return path.is_file()
    return path.stat().st_mode & 0o100 != 0  # Verify it's executable


def test_load_config(tmp_path: Path) -> None:
    """Test loading configuration from YAML."""
    # Create a sample config file - updated to new format
    config_content = """
    tools_dir: ~/tools
    platforms:
      linux:
        - amd64
        - arm64
      macos:
        - arm64
    tools:
        sample-tool:
            repo: sample/tool
            extract_archive: true
            binary_name: sample
            path_in_archive: bin/sample
            asset_patterns: sample-{version}-{platform}_{arch}.tar.gz
    """

    config_path = tmp_path / "dotbins.yaml"
    with open(config_path, "w") as f:
        f.write(config_content)

    # Load config and validate
    config = Config.from_file(str(config_path))

    # Verify config was loaded correctly
    assert config.tools_dir == Path(os.path.expanduser("~/tools"))
    assert "linux" in config.platforms
    assert "macos" in config.platforms
    assert "amd64" in config.platforms["linux"]
    assert "arm64" in config.platforms["linux"]
    assert "arm64" in config.platforms["macos"]
    assert "amd64" not in config.platforms["macos"]  # Important: no amd64 for macOS


def test_load_config_fallback() -> None:
    """Test config loading fallback when file not found."""
    # Mock open to raise FileNotFoundError
    with patch("builtins.open", side_effect=FileNotFoundError):
        config = Config.from_file("nonexistent.yaml")

    # Verify default config is returned
    assert config.tools_dir == Path(os.path.expanduser("~/.dotbins"))


def test_find_asset() -> None:
    """Test finding an asset matching a pattern."""
    tool_config = build_tool_config(
        tool_name="tool",
        raw_data={
            "repo": "test/repo",
            "binary_name": "tool",
            "path_in_archive": "tool",
            "asset_patterns": {  # type: ignore[typeddict-item]
                "linux": {
                    "amd64": "tool-{version}-linux_{arch}.tar.gz",
                    "arm64": "tool-{version}-linux_{arch}.tar.gz",
                },
            },
        },
        platforms={"linux": ["amd64", "arm64"]},
    )
    tool_config._release_info = {
        "tag_name": "v1.0.0",
        "assets": [
            {"name": "tool-1.0.0-linux_amd64.tar.gz"},
            {"name": "tool-1.0.0-linux_arm64.tar.gz"},
            {"name": "tool-1.0.0-darwin_amd64.tar.gz"},
        ],
    }
    assert tool_config._release_info is not None
    assets = tool_config._release_info["assets"]
    assert len(assets) == 3
    bin_spec = tool_config.bin_spec("amd64", "linux")
    assert bin_spec.asset_pattern() == "tool-1.0.0-linux_amd64.tar.gz"
    assert bin_spec.matching_asset() == assets[0]

    bin_spec = tool_config.bin_spec("arm64", "linux")
    assert bin_spec.asset_pattern() == "tool-1.0.0-linux_arm64.tar.gz"
    assert bin_spec.matching_asset() == assets[1]


def test_download_file(requests_mock: Mocker, tmp_path: Path) -> None:
    """Test downloading a file from URL."""
    # Setup mock response
    test_content = b"test file content"
    url = "https://example.com/test.tar.gz"
    requests_mock.get(url, content=test_content)

    # Call the function
    dest_path = str(tmp_path / "downloaded.tar.gz")
    result = dotbins.download.download_file(url, dest_path, github_token=None, verbose=True)

    # Verify the file was downloaded correctly
    assert result == dest_path
    with open(dest_path, "rb") as f:
        assert f.read() == test_content


def test_extract_from_archive_tar(tmp_path: Path, create_dummy_archive: Callable) -> None:
    """Test extracting binary from tar.gz archive."""
    # Create a test tarball using the fixture
    archive_path = tmp_path / "test.tar.gz"
    create_dummy_archive(dest_path=archive_path, binary_names="test-bin")

    # Setup tool config
    tool_config = build_tool_config(
        tool_name="test-tool",
        raw_data={
            "repo": "test/tool",
            "binary_name": "test-tool",
            "path_in_archive": "test-bin",
        },
    )

    # Create destination directory
    dest_dir = tmp_path / "bin"
    dest_dir.mkdir()

    # Extract the binary
    dotbins.download._extract_binary_from_archive(
        archive_path,
        dest_dir,
        BinSpec(tool_config=tool_config, version="1.0.0", arch="amd64", platform="linux"),
        verbose=True,
    )

    # Verify the binary was extracted and renamed correctly
    extracted_bin = dest_dir / "test-tool"
    assert extracted_bin.exists()
    assert _is_executable_or_file(extracted_bin)


def test_extract_from_archive_zip(tmp_path: Path, create_dummy_archive: Callable) -> None:
    """Test extracting binary from zip archive."""
    # Create a test zip file using the fixture
    archive_path = tmp_path / "test.zip"

    create_dummy_archive(
        dest_path=archive_path,
        binary_names="test-bin",
        archive_type="zip",
    )

    # Setup tool config
    tool_config = build_tool_config(
        tool_name="test-tool",
        raw_data={
            "repo": "test/tool",
            "binary_name": "test-tool",
            "path_in_archive": "test-bin",
        },
    )

    # Create destination directory
    dest_dir = tmp_path / "bin"
    dest_dir.mkdir()

    # Extract the binary
    dotbins.download._extract_binary_from_archive(
        archive_path,
        dest_dir,
        BinSpec(
            tool_config=tool_config,
            version="1.0.0",
            arch="amd64",
            platform="linux",
        ),
        verbose=True,
    )

    # Verify the binary was extracted and renamed correctly
    extracted_bin = dest_dir / "test-tool"
    assert extracted_bin.exists()
    assert _is_executable_or_file(extracted_bin)


def test_extract_from_archive_nested(tmp_path: Path, create_dummy_archive: Callable) -> None:
    """Test extracting binary from nested directory in archive."""
    # Create a test tarball with a nested directory
    archive_path = tmp_path / "test.tar.gz"

    create_dummy_archive(
        dest_path=archive_path,
        binary_names="test-bin",
        nested_dir="nested/dir",
    )

    # Setup tool config
    tool_config = build_tool_config(
        tool_name="test-tool",
        raw_data={
            "repo": "test/tool",
            "binary_name": "test-tool",
            "path_in_archive": "nested/dir/test-bin",
        },
    )

    # Create destination directory
    dest_dir = tmp_path / "bin"
    dest_dir.mkdir()

    # Extract the binary
    dotbins.download._extract_binary_from_archive(
        archive_path,
        dest_dir,
        BinSpec(
            tool_config=tool_config,
            version="1.0.0",
            arch="amd64",
            platform="linux",
        ),
        verbose=True,
    )

    # Verify the binary was extracted and renamed correctly
    extracted_bin = dest_dir / "test-tool"
    assert extracted_bin.exists()
    assert _is_executable_or_file(extracted_bin)


def test_make_binaries_executable(tmp_path: Path) -> None:
    """Test making binaries executable."""
    # Setup mock environment
    config = Config(
        tools_dir=tmp_path,
        platforms={"linux": ["amd64"]},  # Use new format
    )

    # Create test binary
    bin_dir = tmp_path / "linux" / "amd64" / "bin"
    bin_dir.mkdir(parents=True)
    bin_file = bin_dir / "test-bin"
    with open(bin_file, "w") as f:
        f.write("#!/bin/sh\necho test")

    # Reset permissions
    bin_file.chmod(0o644)

    config.make_binaries_executable()

    assert _is_executable_or_file(bin_file)


def test_download_tool_already_exists(requests_mock: Mocker, tmp_path: Path) -> None:
    """Test prepare_download_task when binary already exists."""
    # Setup environment with complete tool config
    test_tool_config = build_tool_config(
        tool_name="test-tool",
        raw_data={
            "repo": "test/tool",
            "extract_archive": True,
            "binary_name": "test-tool",
            "path_in_archive": "test-tool",
            "asset_patterns": "test-tool-{version}-{platform}_{arch}.tar.gz",
        },
    )

    version_store = VersionStore(tmp_path)
    version_store.update_tool_info(
        "test-tool",
        "linux",
        "amd64",
        "1.0.0",
        "sha256",
    )

    config = Config(
        tools_dir=tmp_path,
        tools={"test-tool": test_tool_config},
    )

    # Create the binary directory and file
    bin_dir = tmp_path / "linux" / "amd64" / "bin"
    bin_dir.mkdir(parents=True)
    bin_file = bin_dir / "test-tool"
    with open(bin_file, "w") as f:
        f.write("#!/bin/sh\necho test")

    response_data = {
        "tag_name": "v1.0.0",
        "assets": [
            {"tag_name": "v1.0.0", "assets": []},
        ],
    }
    requests_mock.get(
        "https://api.github.com/repos/test/tool/releases/latest",
        json=response_data,
    )

    # With prepare_download_task, it should return None if file exists
    result = dotbins.download._prepare_download_task(
        "test-tool",
        "linux",
        "amd64",
        config,
        force=False,
        verbose=True,
    )

    # Should return None (skip download) since file exists
    assert result is None


def test_download_tool_asset_not_found(
    tmp_path: Path,
    requests_mock: Mocker,
) -> None:
    """Test prepare_download_task when asset is not found."""
    # Mock GitHub API response with no matching Linux assets
    response_data = {
        "tag_name": "v1.0.0",
        "assets": [
            {
                "name": "tool-1.0.0-windows_amd64.zip",
                "browser_download_url": "https://example.com/tool-1.0.0-windows_amd64.zip",
            },
        ],  # No Linux asset
    }
    requests_mock.get(
        "https://api.github.com/repos/test/tool/releases/latest",
        json=response_data,
    )
    test_tool_config = build_tool_config(
        tool_name="test-tool",
        raw_data={
            "repo": "test/tool",
            "binary_name": "test-tool",
            "asset_patterns": "tool-{version}-linux_{arch}.tar.gz",
        },
    )
    # Setup environment
    config = Config(
        tools_dir=tmp_path,
        tools={"test-tool": test_tool_config},
    )
    config.tools["test-tool"]._release_info = {"tag_name": "v1.0.0", "assets": []}
    # Call the function
    result = dotbins.download._prepare_download_task(
        "test-tool",
        "linux",
        "amd64",
        config,
        force=False,
        verbose=True,
    )

    # Should return None since asset wasn't found
    assert result is None


def test_extract_from_archive_unknown_type(tmp_path: Path) -> None:
    """Test extract_from_archive with unknown archive type."""
    # Create a dummy file with unknown extension
    archive_path = tmp_path / "test.xyz"
    with open(archive_path, "w") as f:
        f.write("dummy content")

    # Setup tool config
    test_tool_config = build_tool_config(
        tool_name="test-tool",
        raw_data={
            "repo": "test/tool",
            "binary_name": "test-tool",
            "path_in_archive": "test-bin",
        },
    )

    # Create destination directory
    dest_dir = tmp_path / "bin"
    dest_dir.mkdir()

    # Call the function and check for exception
    with pytest.raises(ValueError, match="Unsupported archive format"):
        dotbins.download._extract_binary_from_archive(
            archive_path,
            dest_dir,
            BinSpec(
                tool_config=test_tool_config,
                version="1.0.0",
                arch="amd64",
                platform="linux",
            ),
            verbose=True,
        )


def test_extract_from_archive_missing_binary(tmp_path: Path) -> None:
    """Test extract_from_archive when binary is not in archive."""
    # Create a test tarball without the binary

    archive_path = tmp_path / "test.tar.gz"
    with tarfile.open(archive_path, "w:gz") as tar:
        # Create a dummy file instead of the binary
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"dummy content")
            tmp_path2 = tmp.name
        tar.add(tmp_path2, arcname="dummy-file")
        os.unlink(tmp_path2)

    # Setup tool config
    test_tool_config = build_tool_config(
        tool_name="test-tool",
        raw_data={
            "repo": "test/tool",
            "binary_name": "test-tool",
            "path_in_archive": "test-bin",  # This path doesn't exist in archive
        },
    )

    # Create destination directory
    dest_dir = tmp_path / "bin"
    dest_dir.mkdir()

    # Call the function and check for exception
    with pytest.raises(FileNotFoundError):
        dotbins.download._extract_binary_from_archive(
            archive_path,
            dest_dir,
            BinSpec(
                tool_config=test_tool_config,
                version="1.0.0",
                arch="amd64",
                platform="linux",
            ),
            verbose=True,
        )


def test_extract_from_archive_multiple_binaries(
    tmp_path: Path,
    create_dummy_archive: Callable,
) -> None:
    """Test extracting multiple binaries from an archive."""
    # Create a test tarball with multiple binaries
    archive_path = tmp_path / "test.tar.gz"
    create_dummy_archive(
        dest_path=archive_path,
        binary_names=["primary-bin", "secondary-bin"],  # List of binary names
        nested_dir="test-1.0.0",
    )

    # Setup tool config with multiple binaries
    test_tool_config = build_tool_config(
        tool_name="test-tool",
        raw_data={
            "repo": "test/tool",
            "binary_name": ["primary-tool", "secondary-tool"],
            "path_in_archive": ["test-1.0.0/primary-bin", "test-1.0.0/secondary-bin"],
        },
    )

    # Create destination directory
    dest_dir = tmp_path / "bin"
    dest_dir.mkdir()

    # Call the function
    dotbins.download._extract_binary_from_archive(
        archive_path,
        dest_dir,
        BinSpec(
            tool_config=test_tool_config,
            version="1.0.0",
            arch="amd64",
            platform="linux",
        ),
        verbose=True,
    )

    # Verify both binaries were extracted and renamed correctly
    for bin_name in ["primary-tool", "secondary-tool"]:
        extracted_bin = dest_dir / bin_name
        assert extracted_bin.exists(), f"Binary {bin_name} not found"
        assert _is_executable_or_file(extracted_bin)

    # Verify the contents of both extracted files
    for bin_name in ["primary-tool", "secondary-tool"]:
        with open(dest_dir / bin_name, "rb") as f:
            content = f.read()
        assert content.strip()


def test_build_tool_config_skips_unknown_platforms() -> None:
    """Test that build_tool_config correctly skips unknown platforms in asset_patterns."""
    # Define a tool config with both valid and unknown platforms in asset_patterns
    raw_data: RawToolConfigDict = {
        "repo": "test/repo",
        "binary_name": "tool",
        "path_in_archive": "tool",
        "asset_patterns": {  # type: ignore[typeddict-item]
            "linux": {  # Valid platform
                "amd64": "tool-{version}-linux_{arch}.tar.gz",
                "arm64": "tool-{version}-linux_{arch}.tar.gz",
            },
            "windows": {  # Unknown platform (not in default Config.platforms)
                "amd64": "tool-{version}-windows_{arch}.zip",
            },
            "macos": {  # Valid platform
                "amd64": "tool-{version}-darwin_{arch}.tar.gz",
            },
        },
    }

    platforms = {
        "linux": ["amd64", "arm64"],
        "macos": ["arm64"],
    }
    # Build the tool config
    tool_config = build_tool_config(tool_name="tool", raw_data=raw_data, platforms=platforms)  # type: ignore[arg-type]
    assert tool_config.asset_patterns == {
        "linux": {
            "amd64": "tool-{version}-linux_{arch}.tar.gz",
            "arm64": "tool-{version}-linux_{arch}.tar.gz",
        },
        "macos": {"arm64": None},
    }


def test_extract_from_archive_with_arch_platform_version_in_path(
    tmp_path: Path,
    create_dummy_archive: Callable,
) -> None:
    """Test extracting binary from archive with arch, platform and version in path."""
    # reaches _replace_variables_in_path
    # Create a test tarball with a nested directory
    archive_path = tmp_path / "test.tar.gz"

    create_dummy_archive(
        dest_path=archive_path,
        binary_names="test-bin",
        nested_dir="nested-1.0.0-linux-amd64",
    )

    # Setup tool config
    tool_config = build_tool_config(
        tool_name="test-tool",
        raw_data={
            "repo": "test/tool",
            "binary_name": "test-tool",
            "path_in_archive": "nested-{version}-{platform}-{arch}/test-bin",
        },
    )

    # Create destination directory
    dest_dir = tmp_path / "bin"
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Extract the binary
    dotbins.download._extract_binary_from_archive(
        archive_path,
        dest_dir,
        BinSpec(
            tool_config=tool_config,
            version="1.0.0",
            arch="amd64",
            platform="linux",
        ),
        verbose=True,
    )

    # Verify the binary was extracted and renamed correctly
    extracted_bin = dest_dir / "test-tool"
    assert extracted_bin.exists()
    assert _is_executable_or_file(extracted_bin)


def test_find_config_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test finding configuration file covers all code paths."""
    # Case 1: Explicit path that exists
    config_path = tmp_path / "explicit_config.yaml"
    config_path.write_text("test content")
    result = _find_config_file(config_path)
    assert result == config_path
    out = capsys.readouterr().out.replace("\n", "")
    nice_path = replace_home_in_path(config_path, "~")
    assert f"Loading configuration from: {nice_path}" in out, out

    # Case 2: Explicit path that doesn't exist
    non_existent_path = tmp_path / "non_existent.yaml"
    result = _find_config_file(non_existent_path)
    assert result is None
    out = capsys.readouterr().out.replace("\n", "")
    assert f"Config path provided but not found: {non_existent_path}" in out

    # Case 3: No explicit path, check default locations
    with (
        patch("pathlib.Path.cwd", return_value=tmp_path / "cwd"),
        patch("pathlib.Path.home", return_value=tmp_path / "home"),
    ):
        # Define all candidate paths to test in order
        candidates = [
            (tmp_path / "cwd" / "dotbins.yaml", "cwd config"),
            (tmp_path / "home" / ".config" / "dotbins" / "config.yaml", "config dir config"),
            (tmp_path / "home" / ".config" / "dotbins.yaml", "dot config"),
            (tmp_path / "home" / ".dotbins.yaml", "home dotbins"),
            (tmp_path / "home" / ".dotbins" / "dotbins.yaml", "dotbins dir config"),
        ]

        # Test each candidate path in order
        for config_file, content in candidates:
            # Create necessary parent directories
            config_file.parent.mkdir(parents=True, exist_ok=True)
            config_file.write_text(content)

            # Test the function finds this config file
            result = _find_config_file(None)
            assert result == config_file
            out = capsys.readouterr().out.replace("\n", "")

            # Handle path format differences between OS
            nice_path = replace_home_in_path(config_file, "~")
            assert f"Loading configuration from: {nice_path}" in out, out

            # Remove this config file before testing the next one
            config_file.unlink()

        # Case 4: No config file exists anywhere
        result = _find_config_file(None)
        assert result is None
        out = capsys.readouterr().out.replace("\n", "")
        assert "No configuration file found, using default settings" in out
