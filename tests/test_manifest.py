"""Tests for the Manifest class."""

import json
import os
from datetime import datetime
from pathlib import Path

import pytest

from dotbins.config import Config
from dotbins.manifest import MANIFEST_VERSION, Manifest


@pytest.fixture
def temp_version_file(tmp_path: Path) -> Path:
    """Create a temporary version file with sample data."""
    manifest_file = tmp_path / "manifest.json"

    # Sample version data
    version_data = {
        "fzf/linux/amd64": {"tag": "0.29.0", "updated_at": "2023-01-01T12:00:00"},
        "bat/macos/arm64": {"tag": "0.18.3", "updated_at": "2023-01-02T14:30:00"},
        "version": 2,
    }

    # Write to file
    with open(manifest_file, "w") as f:
        json.dump(version_data, f)

    return manifest_file


def test_manifest_init(tmp_path: Path) -> None:
    """Test initializing a Manifest."""
    manifest = Manifest(tmp_path)
    assert manifest.manifest_file == tmp_path / "manifest.json"
    assert manifest.data == {"version": MANIFEST_VERSION}  # Empty if file doesn't exist


def test_manifest_load(
    tmp_path: Path,
    temp_version_file: Path,  # noqa: ARG001
) -> None:
    """Test loading version data from file."""
    manifest = Manifest(tmp_path)

    # Versions should be loaded from the file
    assert len(manifest.data) == 3
    assert "fzf/linux/amd64" in manifest.data
    assert "bat/macos/arm64" in manifest.data
    assert "version" in manifest.data

    # Verify data contents
    assert manifest.data["fzf/linux/amd64"]["tag"] == "0.29.0"
    assert manifest.data["bat/macos/arm64"]["updated_at"] == "2023-01-02T14:30:00"


def test_manifest_get_tool_info(
    tmp_path: Path,
    temp_version_file: Path,  # noqa: ARG001
) -> None:
    """Test getting tool info for a specific combination."""
    manifest = Manifest(tmp_path)

    # Test getting existing tool info
    info = manifest.get_tool_info("fzf", "linux", "amd64")
    assert info is not None
    assert info["tag"] == "0.29.0"

    # Test for non-existent tool
    assert manifest.get_tool_info("nonexistent", "linux", "amd64") is None


def test_manifest_update_tool_info(tmp_path: Path) -> None:
    """Test updating tool information."""
    manifest = Manifest(tmp_path)

    # Before update
    assert manifest.get_tool_info("ripgrep", "linux", "amd64") is None

    # Update tool info
    manifest.update_tool_info(
        tool="ripgrep",
        platform="linux",
        arch="amd64",
        tag="13.0.0",
        sha256="sha256",
        url="https://example.com/ripgrep-13.0.0-linux_amd64.tar.gz",
    )

    # After update
    info = manifest.get_tool_info("ripgrep", "linux", "amd64")
    assert info is not None
    assert info["tag"] == "13.0.0"

    # Verify the timestamp format is ISO format
    datetime.fromisoformat(info["updated_at"])  # Should not raise exception

    # Verify the file was created
    assert os.path.exists(tmp_path / "manifest.json")

    # Read the file and check contents
    with open(tmp_path / "manifest.json") as f:
        saved_data = json.load(f)

    assert "ripgrep/linux/amd64" in saved_data
    assert saved_data["ripgrep/linux/amd64"]["tag"] == "13.0.0"


def test_manifest_save_creates_parent_dirs(tmp_path: Path) -> None:
    """Test that save creates parent directories if needed."""
    nested_dir = tmp_path / "nested" / "path"
    manifest = Manifest(nested_dir)

    # Update to trigger save
    manifest.update_tool_info(
        tool="test",
        platform="linux",
        arch="amd64",
        tag="1.0.0",
        sha256="sha256",
        url="https://example.com/test-1.0.0-linux_amd64.tar.gz",
    )

    # Verify directories and file were created
    assert os.path.exists(nested_dir)
    assert os.path.exists(nested_dir / "manifest.json")


def test_manifest_load_invalid_json(tmp_path: Path) -> None:
    """Test loading from an invalid JSON file."""
    manifest_file = tmp_path / "manifest.json"

    # Write invalid JSON
    with open(manifest_file, "w") as f:
        f.write("{ this is not valid JSON")

    # Should handle gracefully and return empty dict
    manifest = Manifest(tmp_path)
    assert manifest.data == {"version": MANIFEST_VERSION}


def test_manifest_update_existing(
    tmp_path: Path,
    temp_version_file: Path,  # noqa: ARG001
) -> None:
    """Test updating an existing tool entry."""
    manifest = Manifest(tmp_path)

    # Initial state
    info = manifest.get_tool_info("fzf", "linux", "amd64")
    assert info is not None
    assert info["tag"] == "0.29.0"

    # Update to new version
    manifest.update_tool_info(
        tool="fzf",
        platform="linux",
        arch="amd64",
        tag="0.30.0",
        sha256="sha256",
        url="https://example.com/fzf-0.30.0-linux_amd64.tar.gz",
    )

    # Verify update
    updated_info = manifest.get_tool_info("fzf", "linux", "amd64")
    assert updated_info is not None
    assert updated_info["tag"] == "0.30.0"

    # Timestamp should be newer
    original_time = datetime.fromisoformat(info["updated_at"])
    updated_time = datetime.fromisoformat(updated_info["updated_at"])
    assert updated_time > original_time


def test_manifest_print(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test printing version information."""
    manifest = Manifest(tmp_path)
    manifest._print_full()
    out, _ = capsys.readouterr()
    assert "No tool versions recorded yet." in out

    manifest.update_tool_info(
        tool="test",
        platform="linux",
        arch="amd64",
        tag="1.0.0",
        sha256="sha256",
        url="https://example.com/test-1.0.0-linux_amd64.tar.gz",
    )
    manifest._print_full()
    out, _ = capsys.readouterr()
    assert "test" in out
    assert "linux" in out
    assert "amd64" in out
    assert "1.0.0" in out

    # Test filtering by platform
    manifest.update_tool_info(
        tool="test2",
        platform="macos",
        arch="arm64",
        tag="2.0.0",
        sha256="sha256",
        url="https://example.com/test2-2.0.0-macos_arm64.tar.gz",
    )
    manifest._print_full(platform="linux")
    out, _ = capsys.readouterr()
    assert "test" in out
    assert "test2" not in out

    # Test filtering by architecture
    manifest._print_full(architecture="arm64")
    out, _ = capsys.readouterr()
    assert "test2" in out
    # "test" might appear in the table headers, so we can't assert it's not in the output
    # Instead check that we don't see "linux" which is unique to the test tool
    assert "linux" not in out


def test_manifest_print_compact(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test printing compact version information."""
    manifest = Manifest(tmp_path)
    manifest._print_compact()
    out, _ = capsys.readouterr()
    assert "No tool versions recorded yet." in out

    # Add multiple versions of the same tool
    manifest.update_tool_info(
        tool="testtool",
        platform="linux",
        arch="amd64",
        tag="1.0.0",
        sha256="sha256",
        url="https://example.com/testtool-1.0.0-linux_amd64.tar.gz",
    )
    manifest.update_tool_info(
        tool="testtool",
        platform="macos",
        arch="arm64",
        tag="1.0.0",
        sha256="sha256",
        url="https://example.com/testtool-1.0.0-macos_arm64.tar.gz",
    )
    manifest.update_tool_info(
        tool="othertool",
        platform="linux",
        arch="amd64",
        tag="2.0.0",
        sha256="sha256",
        url="https://example.com/othertool-2.0.0-linux_amd64.tar.gz",
    )

    manifest._print_compact()
    out, _ = capsys.readouterr()

    # Check compact format shows just one row per tool
    assert "testtool" in out
    assert "othertool" in out
    assert "linux/amd64, macos/arm64" in out or "macos/arm64, linux/amd64" in out

    # Test filtering in compact view
    manifest._print_compact(platform="linux")
    out, _ = capsys.readouterr()
    assert "testtool" in out
    assert "othertool" in out
    assert "macos/arm64" not in out


def test_print_with_missing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test printing version information with missing tools."""
    # Create a minimal Config mock
    config = Config.from_dict(
        {
            "tools_dir": str(tmp_path),
            "tools": {
                "test": {"repo": "test/repo"},
                "missing": {"repo": "missing/repo"},
            },
            "platforms": {
                "linux": ["amd64"],
                "macos": ["arm64"],
            },
        },
    )

    # Create Manifest with one installed tool
    manifest = Manifest(tmp_path)
    manifest.update_tool_info(
        tool="test",
        platform="linux",
        arch="amd64",
        tag="1.0.0",
        sha256="sha256",
        url="https://example.com/test-1.0.0-linux_amd64.tar.gz",
    )

    # Call the method with explicit linux platform
    manifest.print(config, platform="linux")

    # Check output
    out, _ = capsys.readouterr()

    assert "Missing Tools" in out

    installed, missing = out.split("Missing Tools")
    installed = installed.strip()
    missing = missing.strip()

    # Should show the installed tool
    assert "test" in installed
    assert "linux" in installed
    assert "amd64" in installed
    assert "1.0.0" in installed

    # Should also show missing tools
    assert "missing/repo" in missing
    assert "test/repo" not in missing
    assert "dotbins sync" in missing

    manifest.print(config, platform="windows")

    out, _ = capsys.readouterr()
    assert "No tools found for the specified filters" in out

    manifest.print(config, platform="windows", compact=True)

    out, _ = capsys.readouterr()
    assert "No tools found for the specified filters" in out

    # Reset the manifest
    manifest = Manifest(tmp_path)
    manifest.print(config, compact=True)
    out, _ = capsys.readouterr()
    assert "Run dotbins sync to install missing tools" in out


def test_legacy_version_store_is_upgraded(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test that the legacy version_store is upgraded to the new manifest format."""
    version_file = tmp_path / "versions.json"

    # Sample version data
    version_data = {
        "fzf/linux/amd64": {
            "version": "0.29.0",
            "updated_at": "2023-01-01T12:00:00",
            "sha256": "sha256",
        },
        "bat/macos/arm64": {
            "version": "0.18.3",
            "updated_at": "2023-01-02T14:30:00",
            "sha256": "sha256",
        },
    }

    # Write to file
    with open(version_file, "w") as f:
        json.dump(version_data, f)

    # Load the manifest
    manifest = Manifest(tmp_path)
    assert manifest.data == {
        "fzf/linux/amd64": {
            "tag": "0.29.0",
            "updated_at": "2023-01-01T12:00:00",
            "sha256": "sha256",
        },
        "bat/macos/arm64": {
            "tag": "0.18.3",
            "updated_at": "2023-01-02T14:30:00",
            "sha256": "sha256",
        },
        "version": 2,
    }
    assert manifest.manifest_file == tmp_path / "manifest.json"
    assert manifest.manifest_file.exists()
    assert not version_file.exists()
    out, _ = capsys.readouterr()
    assert "Converting manifest" in out


def test_tool_to_tag_mapping_warning(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test warning when tool_to_tag_mapping finds conflicting tags."""
    manifest = Manifest(tmp_path)

    # Add two entries for the same tool with different tags
    manifest.update_tool_info(
        tool="my-tool",
        platform="linux",
        arch="amd64",
        tag="v1.0.0",
        sha256="sha1",
        url="url1",
    )
    manifest.update_tool_info(
        tool="my-tool",
        platform="macos",
        arch="arm64",
        tag="v1.1.0",  # Different tag
        sha256="sha2",
        url="url2",
    )

    # Call the method that should trigger the warning
    mapping = manifest.tool_to_tag_mapping()

    # Capture the output
    out, _ = capsys.readouterr()

    # Assert the warning message is present
    assert "Tool my-tool has multiple tags" in out
    assert "v1.0.0" in out
    assert "v1.1.0" in out

    # The mapping should contain one of the tags (the first one encountered)
    assert mapping == {"my-tool": "v1.1.0"}
