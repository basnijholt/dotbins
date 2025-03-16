"""Tests for the auto_detect_binary_paths function."""

import os
import tarfile
import zipfile
from pathlib import Path
from typing import Callable
from unittest.mock import MagicMock, patch

import pytest

from dotbins.config import BinSpec, build_tool_config
from dotbins.download import _auto_detect_binary_paths, _extract_from_archive


@pytest.fixture
def mock_archive_simple(tmp_path: Path, create_dummy_archive: Callable) -> Path:
    """Create a mock archive with a simple binary that exactly matches the name."""
    archive_path = tmp_path / "simple.tar.gz"
    create_dummy_archive(dest_path=archive_path, binary_names="fzf")
    return archive_path


@pytest.fixture
def mock_archive_nested(tmp_path: Path) -> Path:
    """Create a mock archive with a nested binary structure."""
    # First create an extraction directory to organize our files
    extract_dir = tmp_path / "extract_nested"
    extract_dir.mkdir()

    # Create a nested structure manually
    bin_dir = extract_dir / "bin"
    bin_dir.mkdir()

    # Create binary files
    binary_path = bin_dir / "delta"
    binary_path.touch()
    os.chmod(binary_path, 0o755)  # Make executable  # noqa: S103

    other_path = extract_dir / "delta-backup"
    other_path.touch()
    os.chmod(other_path, 0o755)  # Make executable  # noqa: S103

    # Create archive (we'll use zipfile directly since we need specific structure)
    archive_path = tmp_path / "nested.zip"
    with zipfile.ZipFile(archive_path, "w") as zipf:
        zipf.write(binary_path, arcname="bin/delta")
        zipf.write(other_path, arcname="delta-backup")

    return archive_path


@pytest.fixture
def mock_archive_multiple(tmp_path: Path, create_dummy_archive: Callable) -> Path:
    """Create a mock archive with multiple binaries."""
    archive_path = tmp_path / "multiple.tar.gz"
    create_dummy_archive(dest_path=archive_path, binary_names=["uv", "uvx"])
    return archive_path


@pytest.fixture
def mock_archive_no_match(tmp_path: Path, create_dummy_archive: Callable) -> Path:
    """Create a mock archive with no matching binaries."""
    archive_path = tmp_path / "nomatch.tar.gz"
    create_dummy_archive(dest_path=archive_path, binary_names="something-else")
    return archive_path


def test_auto_detect_binary_paths_simple(
    tmp_path: Path,
    mock_archive_simple: Path,
) -> None:
    """Test auto-detection with a simple binary match."""
    # Set up test environment
    extract_dir = tmp_path / "test_extract_simple"
    extract_dir.mkdir()

    # Extract archive
    with tarfile.open(mock_archive_simple, "r:gz") as tar:
        tar.extractall(path=extract_dir)

    # Test auto-detection
    binary_names = ["fzf"]
    detected_paths = _auto_detect_binary_paths(extract_dir, binary_names)

    assert len(detected_paths) == 1
    assert detected_paths[0] == "fzf"


def test_auto_detect_binary_paths_nested(
    tmp_path: Path,
    mock_archive_nested: Path,
) -> None:
    """Test auto-detection with a nested binary structure."""
    # Set up test environment
    extract_dir = tmp_path / "test_extract_nested"
    extract_dir.mkdir()

    # Extract archive
    with zipfile.ZipFile(mock_archive_nested, "r") as zipf:
        zipf.extractall(path=extract_dir)

    # Test auto-detection
    binary_names = ["delta"]
    detected_paths = _auto_detect_binary_paths(extract_dir, binary_names)

    assert len(detected_paths) == 1
    assert detected_paths[0] == "bin/delta"  # Should prefer the one in bin/


def test_auto_detect_binary_paths_multiple(
    tmp_path: Path,
    mock_archive_multiple: Path,
) -> None:
    """Test auto-detection with multiple binaries."""
    # Set up test environment
    extract_dir = tmp_path / "test_extract_multiple"
    extract_dir.mkdir()

    # Extract archive
    with tarfile.open(mock_archive_multiple, "r:gz") as tar:
        tar.extractall(path=extract_dir)

    # Test auto-detection
    binary_names = ["uv", "uvx"]
    detected_paths = _auto_detect_binary_paths(extract_dir, binary_names)

    assert len(detected_paths) == 2
    assert detected_paths[0] == "uv"
    assert detected_paths[1] == "uvx"


def test_auto_detect_binary_paths_no_match(
    tmp_path: Path,
    mock_archive_no_match: Path,
) -> None:
    """Test auto-detection with no matching binaries."""
    # Set up test environment
    extract_dir = tmp_path / "test_extract_nomatch"
    extract_dir.mkdir()

    # Extract archive
    with tarfile.open(mock_archive_no_match, "r:gz") as tar:
        tar.extractall(path=extract_dir)

    # Test auto-detection
    binary_names = ["git-lfs"]
    detected_paths = _auto_detect_binary_paths(extract_dir, binary_names)

    assert len(detected_paths) == 0  # Should not find any matches


def test_extract_from_archive_with_auto_detection(
    tmp_path: Path,
    mock_archive_simple: Path,
) -> None:
    """Test the extract_from_archive function with auto-detection."""
    destination_dir = tmp_path / "bin"
    destination_dir.mkdir()

    # Mock config without binary_path
    tool_config = build_tool_config(
        tool_name="fzf",
        raw_data={
            "binary_name": "fzf",
            "repo": "junegunn/fzf",
            "extract_binary": True,
        },
    )

    # Mock console to capture output
    mock_console = MagicMock()

    with patch("dotbins.utils.console", mock_console):
        # Call the function
        _extract_from_archive(
            mock_archive_simple,
            destination_dir,
            BinSpec(
                tool_config=tool_config,
                version="1.0.0",
                arch="amd64",
                platform="linux",
            ),
        )

    # Check that the binary was copied correctly
    assert (destination_dir / "fzf").exists()
    assert os.access(destination_dir / "fzf", os.X_OK)

    # Check that auto-detection message was logged
    mock_console.print.assert_any_call(
        "🔍 [cyan]Binary path not specified, attempting auto-detection...[/cyan]",
    )
    mock_console.print.assert_any_call(
        "✅ [green]Auto-detected binary paths: ['fzf'][/green]",
    )


def test_extract_from_archive_auto_detection_failure(
    tmp_path: Path,
    mock_archive_no_match: Path,
) -> None:
    """Test the extract_from_archive function when auto-detection fails."""
    destination_dir = tmp_path / "bin"
    destination_dir.mkdir()

    # Mock config without binary_path
    tool_config = build_tool_config(
        tool_name="git-lfs",
        raw_data={
            "binary_name": "git-lfs",
            "repo": "git-lfs/git-lfs",
            "extract_binary": True,
        },
    )

    # Mock console to capture output
    mock_console = MagicMock()

    with (
        patch("dotbins.utils.console", mock_console),
        pytest.raises(ValueError, match="Could not auto-detect binary paths"),
    ):
        _extract_from_archive(
            mock_archive_no_match,
            destination_dir,
            BinSpec(
                tool_config=tool_config,
                version="1.0.0",
                arch="amd64",
                platform="linux",
            ),
        )
