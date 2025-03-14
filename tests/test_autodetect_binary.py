"""Tests for the auto_detect_binary_paths function."""

import os
import shutil
import tarfile
import tempfile
import zipfile
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from dotbins.config import ToolConfig
from dotbins.download import (
    _auto_detect_binary_paths,
    _extract_from_archive,
)


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for testing."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def mock_archive_simple(temp_dir: Path) -> Path:
    """Create a mock archive with a simple binary that exactly matches the name."""
    archive_path = temp_dir / "simple.tar.gz"
    extract_dir = temp_dir / "extract_simple"
    extract_dir.mkdir()

    # Create a binary file
    binary_path = extract_dir / "fzf"
    binary_path.touch()
    os.chmod(binary_path, 0o755)  # Make executable  # noqa: S103

    # Create archive
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(binary_path, arcname="fzf")

    return archive_path


@pytest.fixture
def mock_archive_nested(temp_dir: Path) -> Path:
    """Create a mock archive with a nested binary structure."""
    archive_path = temp_dir / "nested.zip"
    extract_dir = temp_dir / "extract_nested"
    extract_dir.mkdir()
    bin_dir = extract_dir / "bin"
    bin_dir.mkdir()

    # Create a binary file in bin directory
    binary_path = bin_dir / "delta"
    binary_path.touch()
    os.chmod(binary_path, 0o755)  # Make executable  # noqa: S103

    # Create another executable to test disambiguation
    other_path = extract_dir / "delta-backup"
    other_path.touch()
    os.chmod(other_path, 0o755)  # Make executable  # noqa: S103

    # Create archive
    with zipfile.ZipFile(archive_path, "w") as zipf:
        zipf.write(binary_path, arcname="bin/delta")
        zipf.write(other_path, arcname="delta-backup")

    return archive_path


@pytest.fixture
def mock_archive_multiple(temp_dir: Path) -> Path:
    """Create a mock archive with multiple binaries."""
    archive_path = temp_dir / "multiple.tar.gz"
    extract_dir = temp_dir / "extract_multiple"
    extract_dir.mkdir()

    # Create multiple binary files
    binary1_path = extract_dir / "uv"
    binary1_path.touch()
    os.chmod(binary1_path, 0o755)  # Make executable  # noqa: S103

    binary2_path = extract_dir / "uvx"
    binary2_path.touch()
    os.chmod(binary2_path, 0o755)  # Make executable  # noqa: S103

    # Create archive
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(binary1_path, arcname="uv")
        tar.add(binary2_path, arcname="uvx")

    return archive_path


@pytest.fixture
def mock_archive_no_match(temp_dir: Path) -> Path:
    """Create a mock archive with no matching binaries."""
    archive_path = temp_dir / "nomatch.tar.gz"
    extract_dir = temp_dir / "extract_nomatch"
    extract_dir.mkdir()

    # Create a non-matching binary file
    binary_path = extract_dir / "something-else"
    binary_path.touch()
    os.chmod(binary_path, 0o755)  # Make executable  # noqa: S103

    # Create archive
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(binary_path, arcname="something-else")

    return archive_path


def test_auto_detect_binary_paths_simple(
    temp_dir: Path,
    mock_archive_simple: Path,
) -> None:
    """Test auto-detection with a simple binary match."""
    # Set up test environment
    extract_dir = temp_dir / "test_extract_simple"
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
    temp_dir: Path,
    mock_archive_nested: Path,
) -> None:
    """Test auto-detection with a nested binary structure."""
    # Set up test environment
    extract_dir = temp_dir / "test_extract_nested"
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
    temp_dir: Path,
    mock_archive_multiple: Path,
) -> None:
    """Test auto-detection with multiple binaries."""
    # Set up test environment
    extract_dir = temp_dir / "test_extract_multiple"
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
    temp_dir: Path,
    mock_archive_no_match: Path,
) -> None:
    """Test auto-detection with no matching binaries."""
    # Set up test environment
    extract_dir = temp_dir / "test_extract_nomatch"
    extract_dir.mkdir()

    # Extract archive
    with tarfile.open(mock_archive_no_match, "r:gz") as tar:
        tar.extractall(path=extract_dir)

    # Test auto-detection
    binary_names = ["git-lfs"]
    detected_paths = _auto_detect_binary_paths(extract_dir, binary_names)

    assert len(detected_paths) == 0  # Should not find any matches


def test_extract_from_archive_with_auto_detection(
    temp_dir: Path,
    mock_archive_simple: Path,
) -> None:
    """Test the extract_from_archive function with auto-detection."""
    destination_dir = temp_dir / "bin"
    destination_dir.mkdir()

    # Mock config without binary_path
    tool_config = ToolConfig(
        tool_name="fzf",
        binary_name="fzf",
        # No binary_path!
        repo="junegunn/fzf",
        extract_binary=True,
    )

    # Mock console to capture output
    mock_console = MagicMock()

    with patch("dotbins.utils.console", mock_console):
        # Call the function
        _extract_from_archive(
            str(mock_archive_simple),
            destination_dir,
            tool_config,
            "linux",
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
    temp_dir: Path,
    mock_archive_no_match: Path,
) -> None:
    """Test the extract_from_archive function when auto-detection fails."""
    destination_dir = temp_dir / "bin"
    destination_dir.mkdir()

    # Mock config without binary_path
    tool_config = ToolConfig(
        tool_name="git-lfs",
        binary_name="git-lfs",
        # No binary_path!
        repo="git-lfs/git-lfs",
        extract_binary=True,
    )

    # Mock console to capture output
    mock_console = MagicMock()

    with (
        patch("dotbins.utils.console", mock_console),
        pytest.raises(ValueError, match="Could not auto-detect binary paths"),
    ):
        _extract_from_archive(
            str(mock_archive_no_match),
            destination_dir,
            tool_config,
            "linux",
        )
