"""Tests for the VersionStore class."""

import json
import os
from datetime import datetime
from pathlib import Path

import pytest

from dotbins.config import Config
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


def test_version_store_print(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test printing version information."""
    store = VersionStore(tmp_path)
    store._print_full()
    out, _ = capsys.readouterr()
    assert "No tool versions recorded yet." in out

    store.update_tool_info("test", "linux", "amd64", "1.0.0")
    store._print_full()
    out, _ = capsys.readouterr()
    assert "test" in out
    assert "linux" in out
    assert "amd64" in out
    assert "1.0.0" in out

    # Test filtering by platform
    store.update_tool_info("test2", "macos", "arm64", "2.0.0")
    store._print_full(platform="linux")
    out, _ = capsys.readouterr()
    assert "test" in out
    assert "test2" not in out

    # Test filtering by architecture
    store._print_full(architecture="arm64")
    out, _ = capsys.readouterr()
    assert "test2" in out
    # "test" might appear in the table headers, so we can't assert it's not in the output
    # Instead check that we don't see "linux" which is unique to the test tool
    assert "linux" not in out


def test_version_store_print_compact(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test printing compact version information."""
    store = VersionStore(tmp_path)
    store._print_compact()
    out, _ = capsys.readouterr()
    assert "No tool versions recorded yet." in out

    # Add multiple versions of the same tool
    store.update_tool_info("testtool", "linux", "amd64", "1.0.0")
    store.update_tool_info("testtool", "macos", "arm64", "1.0.0")
    store.update_tool_info("othertool", "linux", "amd64", "2.0.0")

    store._print_compact()
    out, _ = capsys.readouterr()

    # Check compact format shows just one row per tool
    assert "testtool" in out
    assert "othertool" in out
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

    # Create VersionStore with one installed tool
    store = VersionStore(tmp_path)
    store.update_tool_info("test", "linux", "amd64", "1.0.0")

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
    assert "1.0.0" in installed

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
    store = VersionStore(tmp_path)
    store.print(config, compact=True)
    out, _ = capsys.readouterr()
    assert "Run dotbins sync to install missing tools" in out
