"""Tests for the VersionStore class."""

import json
import os
from datetime import datetime
from pathlib import Path

import pytest

from dotbins.versions import VersionStore


@pytest.fixture
def temp_version_file(tmp_path: Path) -> Path:
    """Create a temporary version file with sample data."""
    version_file = tmp_path / "versions.json"

    # Sample version data
    version_data = {
        "fzf/linux/amd64": {"version": "0.29.0", "updated_at": "2023-01-01T12:00:00"},
        "bat/macos/arm64": {"version": "0.18.3", "updated_at": "2023-01-02T14:30:00"},
    }

    # Write to file
    with open(version_file, "w") as f:
        json.dump(version_data, f)

    return version_file


def test_version_store_init(tmp_path: Path) -> None:
    """Test initializing a VersionStore."""
    store = VersionStore(tmp_path)
    assert store.version_file == tmp_path / "versions.json"
    assert store.versions == {}  # Empty if file doesn't exist


def test_version_store_load(
    tmp_path: Path,
    temp_version_file: Path,  # noqa: ARG001
) -> None:
    """Test loading version data from file."""
    store = VersionStore(tmp_path)

    # Versions should be loaded from the file
    assert len(store.versions) == 2
    assert "fzf/linux/amd64" in store.versions
    assert "bat/macos/arm64" in store.versions

    # Verify data contents
    assert store.versions["fzf/linux/amd64"]["version"] == "0.29.0"
    assert store.versions["bat/macos/arm64"]["updated_at"] == "2023-01-02T14:30:00"


def test_version_store_get_tool_info(
    tmp_path: Path,
    temp_version_file: Path,  # noqa: ARG001
) -> None:
    """Test getting tool info for a specific combination."""
    store = VersionStore(tmp_path)

    # Test getting existing tool info
    info = store.get_tool_info("fzf", "linux", "amd64")
    assert info is not None
    assert info["version"] == "0.29.0"

    # Test for non-existent tool
    assert store.get_tool_info("nonexistent", "linux", "amd64") is None


def test_version_store_update_tool_info(tmp_path: Path) -> None:
    """Test updating tool information."""
    store = VersionStore(tmp_path)

    # Before update
    assert store.get_tool_info("ripgrep", "linux", "amd64") is None

    # Update tool info
    store.update_tool_info("ripgrep", "linux", "amd64", "13.0.0")

    # After update
    info = store.get_tool_info("ripgrep", "linux", "amd64")
    assert info is not None
    assert info["version"] == "13.0.0"

    # Verify the timestamp format is ISO format
    datetime.fromisoformat(info["updated_at"])  # Should not raise exception

    # Verify the file was created
    assert os.path.exists(tmp_path / "versions.json")

    # Read the file and check contents
    with open(tmp_path / "versions.json") as f:
        saved_data = json.load(f)

    assert "ripgrep/linux/amd64" in saved_data
    assert saved_data["ripgrep/linux/amd64"]["version"] == "13.0.0"


def test_version_store_list_all(
    tmp_path: Path,
    temp_version_file: Path,  # noqa: ARG001
) -> None:
    """Test listing all version information."""
    store = VersionStore(tmp_path)

    # List all versions
    versions = store.list_all()

    assert len(versions) == 2
    assert "fzf/linux/amd64" in versions
    assert "bat/macos/arm64" in versions


def test_version_store_save_creates_parent_dirs(tmp_path: Path) -> None:
    """Test that save creates parent directories if needed."""
    nested_dir = tmp_path / "nested" / "path"
    store = VersionStore(nested_dir)

    # Update to trigger save
    store.update_tool_info("test", "linux", "amd64", "1.0.0")

    # Verify directories and file were created
    assert os.path.exists(nested_dir)
    assert os.path.exists(nested_dir / "versions.json")


def test_version_store_load_invalid_json(tmp_path: Path) -> None:
    """Test loading from an invalid JSON file."""
    version_file = tmp_path / "versions.json"

    # Write invalid JSON
    with open(version_file, "w") as f:
        f.write("{ this is not valid JSON")

    # Should handle gracefully and return empty dict
    store = VersionStore(tmp_path)
    assert store.versions == {}


def test_version_store_update_existing(
    tmp_path: Path,
    temp_version_file: Path,  # noqa: ARG001
) -> None:
    """Test updating an existing tool entry."""
    store = VersionStore(tmp_path)

    # Initial state
    info = store.get_tool_info("fzf", "linux", "amd64")
    assert info is not None
    assert info["version"] == "0.29.0"

    # Update to new version
    store.update_tool_info("fzf", "linux", "amd64", "0.30.0")

    # Verify update
    updated_info = store.get_tool_info("fzf", "linux", "amd64")
    assert updated_info is not None
    assert updated_info["version"] == "0.30.0"

    # Timestamp should be newer
    original_time = datetime.fromisoformat(info["updated_at"])
    updated_time = datetime.fromisoformat(updated_info["updated_at"])
    assert updated_time > original_time
