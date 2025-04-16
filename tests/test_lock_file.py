"""Tests for the LockFile class."""

import json
import os
from datetime import datetime
from pathlib import Path

import pytest

from dotbins.config import Config
from dotbins.lock_file import LockFile


@pytest.fixture
def temp_lock_file(tmp_path: Path) -> Path:
    """Create a temporary lock file (versions.json) with sample data."""
    lock_file_path = tmp_path / "versions.json"

    # Sample tag data (using 'v' prefix)
    lock_data = {
        "fzf/linux/amd64": {
            "tag": "v0.29.0",
            "updated_at": "2023-01-01T12:00:00",
            "sha256": "sha_fzf",
        },
        "bat/macos/arm64": {
            "tag": "v0.18.3",
            "updated_at": "2023-01-02T14:30:00",
            "sha256": "sha_bat",
        },
        "version": 2,
    }

    # Write to file
    with open(lock_file_path, "w") as f:
        json.dump(lock_data, f)

    return lock_file_path


def test_lock_file_init(tmp_path: Path) -> None:
    """Test initializing a LockFile."""
    store = LockFile(tmp_path)
    assert store.version_file == tmp_path / "versions.json"
    assert store.data == {}  # Empty if file doesn't exist


def test_lock_file_load(
    tmp_path: Path,
    temp_lock_file: Path,  # noqa: ARG001
) -> None:
    """Test loading lock data from file."""
    store = LockFile(tmp_path)

    # Tags should be loaded from the file
    assert len(store.data) == 3
    assert "fzf/linux/amd64" in store.data
    assert "bat/macos/arm64" in store.data
    assert "version" in store.data

    # Verify data contents
    assert store.data["fzf/linux/amd64"]["tag"] == "v0.29.0"
    assert store.data["bat/macos/arm64"]["updated_at"] == "2023-01-02T14:30:00"


def test_lock_file_get_tool_info(
    tmp_path: Path,
    temp_lock_file: Path,  # noqa: ARG001
) -> None:
    """Test getting tool info for a specific combination."""
    store = LockFile(tmp_path)

    # Test getting existing tool info
    info = store.get_tool_info("fzf", "linux", "amd64")
    assert info is not None
    assert info["tag"] == "v0.29.0"

    # Test for non-existent tool
    assert store.get_tool_info("nonexistent", "linux", "amd64") is None


def test_lock_file_get_tool_tag(
    tmp_path: Path,
    temp_lock_file: Path,  # noqa: ARG001
) -> None:
    """Test getting the tag for a specific tool."""
    store = LockFile(tmp_path)
    assert store.get_tool_tag("fzf", "linux", "amd64") == "v0.29.0"
    assert store.get_tool_tag("nonexistent", "linux", "amd64") is None


def test_lock_file_update_tool_info(tmp_path: Path) -> None:
    """Test updating tool information."""
    store = LockFile(tmp_path)

    # Before update
    assert store.get_tool_info("ripgrep", "linux", "amd64") is None

    # Update tool info
    store.update_tool_info("ripgrep", "linux", "amd64", "v13.0.0", "sha_rg")

    # After update
    info = store.get_tool_info("ripgrep", "linux", "amd64")
    assert info is not None
    assert info["tag"] == "v13.0.0"
    assert info["sha256"] == "sha_rg"

    # Verify the timestamp format is ISO format
    datetime.fromisoformat(info["updated_at"])  # Should not raise exception

    # Verify the file was created
    assert os.path.exists(tmp_path / "versions.json")

    # Read the file and check contents
    with open(tmp_path / "versions.json") as f:
        saved_data = json.load(f)

    assert "ripgrep/linux/amd64" in saved_data
    assert saved_data["ripgrep/linux/amd64"]["tag"] == "v13.0.0"
    assert saved_data["ripgrep/linux/amd64"]["sha256"] == "sha_rg"


def test_lock_file_save_creates_parent_dirs(tmp_path: Path) -> None:
    """Test that save creates parent directories if needed."""
    nested_dir = tmp_path / "nested" / "path"
    store = LockFile(nested_dir)

    # Update to trigger save
    store.update_tool_info("test", "linux", "amd64", "v1.0.0", "sha256")

    # Verify directories and file were created
    assert os.path.exists(nested_dir)
    assert os.path.exists(nested_dir / "versions.json")


def test_lock_file_load_invalid_json(tmp_path: Path) -> None:
    """Test loading from an invalid JSON file."""
    lock_file_path = tmp_path / "versions.json"

    # Write invalid JSON
    with open(lock_file_path, "w") as f:
        f.write("{ this is not valid JSON")

    # Should handle gracefully and return empty dict
    store = LockFile(tmp_path)
    assert store.data == {}


def test_lock_file_update_existing(
    tmp_path: Path,
    temp_lock_file: Path,  # noqa: ARG001
) -> None:
    """Test updating an existing tool entry."""
    store = LockFile(tmp_path)

    # Initial state
    info = store.get_tool_info("fzf", "linux", "amd64")
    assert info is not None
    assert info["tag"] == "v0.29.0"

    # Update to new version
    store.update_tool_info("fzf", "linux", "amd64", "v0.30.0", "sha_fzf_new")

    # Verify update
    updated_info = store.get_tool_info("fzf", "linux", "amd64")
    assert updated_info is not None
    assert updated_info["tag"] == "v0.30.0"
    assert updated_info["sha256"] == "sha_fzf_new"

    # Timestamp should be newer
    original_time = datetime.fromisoformat(info["updated_at"])
    updated_time = datetime.fromisoformat(updated_info["updated_at"])
    assert updated_time > original_time


def test_lock_file_print(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test printing lock file information (full view)."""
    store = LockFile(tmp_path)
    store._print_full()
    out, _ = capsys.readouterr()
    assert "No tool tags (versions) recorded yet." in out

    store.update_tool_info("test", "linux", "amd64", "v1.0.0", "sha_test")
    store._print_full()
    out, _ = capsys.readouterr()
    assert "test" in out
    assert "linux" in out
    assert "amd64" in out
    assert "v1.0.0" in out
    assert "sha_test"[:8] in out

    # Test filtering by platform
    store.update_tool_info("test2", "macos", "arm64", "v2.0.0", "sha_test2")
    store._print_full(platform="linux")
    out, _ = capsys.readouterr()
    assert "test" in out
    assert "test2" not in out

    # Test filtering by architecture
    store._print_full(architecture="arm64")
    out, _ = capsys.readouterr()
    assert "test2" in out
    assert "v2.0.0" in out
    # "test" might appear in the table headers, so we can't assert it's not in the output
    # Instead check that we don't see "linux" which is unique to the test tool
    assert "linux" not in out


def test_lock_file_print_compact(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test printing compact lock file information."""
    store = LockFile(tmp_path)
    store._print_compact()
    out, _ = capsys.readouterr()
    assert "No tool tags (versions) recorded yet." in out

    # Add multiple versions of the same tool
    store.update_tool_info("testtool", "linux", "amd64", "v1.0.0", "sha1")
    store.update_tool_info("testtool", "macos", "arm64", "v1.0.0", "sha2")
    store.update_tool_info("othertool", "linux", "amd64", "v2.0.0", "sha3")

    store._print_compact()
    out, _ = capsys.readouterr()

    # Check compact format shows just one row per tool
    assert "testtool" in out
    assert "othertool" in out
    assert "v1.0.0" in out
    assert "v2.0.0" in out
    assert "linux/amd64, macos/arm64" in out or "macos/arm64, linux/amd64" in out

    # Test filtering in compact view
    store._print_compact(platform="linux")
    out, _ = capsys.readouterr()
    assert "testtool" in out
    assert "othertool" in out
    assert "macos/arm64" not in out


def test_print_with_missing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test printing lock file information with missing tools."""
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

    # Create LockFile with one installed tool
    store = LockFile(tmp_path)
    store.update_tool_info("test", "linux", "amd64", "v1.0.0", "sha_test")

    # Call the method with explicit linux platform
    store.print(config, platform="linux")

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
    assert "v1.0.0" in installed
    assert "sha_test"[:8] in installed

    # Should also show missing tools
    assert "missing/repo" in missing
    assert "test/repo" not in missing
    assert "dotbins sync" in missing

    store.print(config, platform="windows")

    out, _ = capsys.readouterr()
    assert "No tools found for the specified filters" in out

    store.print(config, platform="windows", compact=True)

    out, _ = capsys.readouterr()
    assert "No tools found for the specified filters" in out

    # Reset the store
    store = LockFile(tmp_path)
    store.print(config, compact=True)
    out, _ = capsys.readouterr()
    assert "Run dotbins sync to install missing tools" in out
