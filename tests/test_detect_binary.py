"""Tests for the auto_detect_paths_in_archive function."""

import os
import tarfile
import zipfile
from pathlib import Path
from typing import Callable
from unittest.mock import MagicMock, patch

import pytest

from dotbins.config import BinSpec, build_tool_config
from dotbins.detect_binary import auto_detect_paths_in_archive
from dotbins.download import AutoDetectBinaryPathsError, _extract_binary_from_archive


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


@pytest.fixture
def mock_archive_non_executables(tmp_path: Path) -> Path:
    """Create a mock archive with non-executable files."""
    extract_dir = tmp_path / "extract_non_exec"
    extract_dir.mkdir()

    # Create various non-executable files
    files = [
        "script.py",
        "doc.md",
        "config.yaml",
        "data.json",
        "image.png",
        "style.css",
        "code.ts",
        "binary.exe.txt",
    ]
    for file in files:
        (extract_dir / file).touch()

    # Create archive
    archive_path = tmp_path / "non_exec.zip"
    with zipfile.ZipFile(archive_path, "w") as zipf:
        for file in files:
            zipf.write(extract_dir / file, arcname=file)

    return archive_path


@pytest.fixture
def mock_archive_with_dirs(tmp_path: Path) -> Path:
    """Create a mock archive with directories having binary names."""
    extract_dir = tmp_path / "extract_dirs"
    extract_dir.mkdir()

    # Create directories with binary names
    (extract_dir / "fzf").mkdir()
    (extract_dir / "bin" / "delta").mkdir(parents=True)

    # Create actual binary
    binary = extract_dir / "actual-delta"
    binary.touch()
    os.chmod(binary, 0o755)  # Make executable  # noqa: S103

    archive_path = tmp_path / "with_dirs.zip"
    with zipfile.ZipFile(archive_path, "w") as zipf:
        zipf.write(extract_dir / "fzf", arcname="fzf")
        zipf.write(extract_dir / "bin" / "delta", arcname="bin/delta")
        zipf.write(binary, arcname="actual-delta")

    return archive_path


@pytest.fixture
def mock_archive_bin_matches(tmp_path: Path) -> Path:
    """Create a mock archive with multiple bin directory matches."""
    extract_dir = tmp_path / "extract_bin_matches"
    extract_dir.mkdir()

    # Create bin directories with various executables
    bin_paths = [
        "bin/tool",  # Generic bin match
        "bin/tool-extra",  # Named bin match
        "other-bin/tool",  # Non-standard bin
        "bin2/other-tool",  # Another bin dir
    ]

    for path in bin_paths:
        full_path = extract_dir / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.touch()
        os.chmod(full_path, 0o755)  # Make executable  # noqa: S103

    archive_path = tmp_path / "bin_matches.zip"
    with zipfile.ZipFile(archive_path, "w") as zipf:
        for path in bin_paths:
            zipf.write(extract_dir / path, arcname=path)

    return archive_path


@pytest.fixture
def mock_archive_substring_matches(tmp_path: Path) -> Path:
    """Create a mock archive with substring matches."""
    extract_dir = tmp_path / "extract_substring"
    extract_dir.mkdir()

    # Create files with substrings of the binary name
    files = [
        "mytool-v1",  # Substring match
        "other-mytool-bin",  # Another substring match
        "mytool.backup",  # Another variation
    ]

    for file in files:
        path = extract_dir / file
        path.touch()
        os.chmod(path, 0o755)  # Make executable  # noqa: S103

    archive_path = tmp_path / "substring_matches.zip"
    with zipfile.ZipFile(archive_path, "w") as zipf:
        for file in files:
            zipf.write(extract_dir / file, arcname=file)

    return archive_path


@pytest.fixture
def mock_archive_non_executable_match(tmp_path: Path) -> Path:
    """Create a mock archive with exact name matches that aren't executable."""
    extract_dir = tmp_path / "extract_non_exec_match"
    extract_dir.mkdir()

    # Create binary with exact name match but no executable permissions
    binary = extract_dir / "mytool"
    binary.touch()  # Explicitly not making executable

    # Create another binary with executable bit but different name
    other = extract_dir / "other-tool"
    other.touch()
    os.chmod(other, 0o755)  # Make executable  # noqa: S103

    archive_path = tmp_path / "non_exec_match.zip"
    with zipfile.ZipFile(archive_path, "w") as zipf:
        zipf.write(binary, arcname="mytool")
        zipf.write(other, arcname="other-tool")

    return archive_path


@pytest.fixture
def mock_archive_bin_dir_fallback(tmp_path: Path) -> Path:
    """Create a mock archive with bin directory matches but no name matches."""
    extract_dir = tmp_path / "extract_bin_fallback"
    extract_dir.mkdir()

    # Create executables in bin directories
    bin_paths = [
        "bin/completely-different",  # Will be found first due to bin/
        "bin2/unrelated",  # Another bin match
        "other/not-mytool",  # Non-bin match with name
    ]

    for path in bin_paths:
        full_path = extract_dir / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.touch()
        os.chmod(full_path, 0o755)  # Make executable  # noqa: S103

    archive_path = tmp_path / "bin_fallback.zip"
    with zipfile.ZipFile(archive_path, "w") as zipf:
        for path in bin_paths:
            zipf.write(extract_dir / path, arcname=path)

    return archive_path


def test_auto_detect_paths_in_archive_simple(
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
    detected_paths = auto_detect_paths_in_archive(extract_dir, binary_names)

    assert len(detected_paths) == 1
    assert detected_paths[0] == Path("fzf")


def test_auto_detect_paths_in_archive_nested(
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
    detected_paths = auto_detect_paths_in_archive(extract_dir, binary_names)

    assert len(detected_paths) == 1
    assert detected_paths[0] == Path("bin/delta")  # Should prefer the one in bin/


def test_auto_detect_paths_in_archive_multiple(
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
    detected_paths = auto_detect_paths_in_archive(extract_dir, binary_names)

    assert len(detected_paths) == 2
    assert detected_paths[0] == Path("uv")
    assert detected_paths[1] == Path("uvx")


def test_auto_detect_paths_in_archive_no_match(
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
    detected_paths = auto_detect_paths_in_archive(extract_dir, binary_names)

    assert len(detected_paths) == 0  # Should not find any matches


def test_extract_from_archive_with_auto_detection(
    tmp_path: Path,
    mock_archive_simple: Path,
    capsys: pytest.CaptureFixture,
) -> None:
    """Test the extract_from_archive function with auto-detection."""
    destination_dir = tmp_path / "bin"
    destination_dir.mkdir()

    # Mock config without path_in_archive
    tool_config = build_tool_config(
        tool_name="fzf",
        raw_data={
            "binary_name": "fzf",
            "repo": "junegunn/fzf",
            "extract_archive": True,
        },
    )

    # Call the function
    _extract_binary_from_archive(
        mock_archive_simple,
        destination_dir,
        BinSpec(
            tool_config=tool_config,
            version="1.0.0",
            arch="amd64",
            platform="linux",
        ),
        verbose=True,
    )

    # Check that the binary was copied correctly
    assert (destination_dir / "fzf").exists()
    assert os.access(destination_dir / "fzf", os.X_OK)

    # Check that auto-detection message was logged
    captured = capsys.readouterr()
    out = captured.out
    assert "Binary path not specified, attempting auto-detection..." in out
    assert "Auto-detected binary paths: fzf" in out, out


def test_extract_from_archive_auto_detection_failure(
    tmp_path: Path,
    mock_archive_no_match: Path,
) -> None:
    """Test the extract_from_archive function when auto-detection fails."""
    destination_dir = tmp_path / "bin"
    destination_dir.mkdir()

    # Mock config without path_in_archive
    tool_config = build_tool_config(
        tool_name="git-lfs",
        raw_data={
            "binary_name": "git-lfs",
            "repo": "git-lfs/git-lfs",
            "extract_archive": True,
        },
    )

    # Mock console to capture output
    mock_console = MagicMock()

    with (
        patch("dotbins.utils.console", mock_console),
        pytest.raises(AutoDetectBinaryPathsError, match="Could not auto-detect binary paths"),
    ):
        _extract_binary_from_archive(
            mock_archive_no_match,
            destination_dir,
            BinSpec(
                tool_config=tool_config,
                version="1.0.0",
                arch="amd64",
                platform="linux",
            ),
            verbose=True,
        )


def test_non_executable_files_ignored(
    tmp_path: Path,
    mock_archive_non_executables: Path,
) -> None:
    """Test that non-executable files are ignored."""
    extract_dir = tmp_path / "test_non_exec"
    extract_dir.mkdir()

    with zipfile.ZipFile(mock_archive_non_executables, "r") as zipf:
        zipf.extractall(path=extract_dir)

    # Try to detect various non-executable files
    for name in ["script", "doc", "binary"]:
        detected_paths = auto_detect_paths_in_archive(extract_dir, [name])
        assert len(detected_paths) == 0, f"Should not detect {name} as binary"


def test_directories_ignored(
    tmp_path: Path,
    mock_archive_with_dirs: Path,
) -> None:
    """Test that directories with binary names don't affect binary detection."""
    extract_dir = tmp_path / "test_dirs"
    extract_dir.mkdir()

    with zipfile.ZipFile(mock_archive_with_dirs, "r") as zipf:
        zipf.extractall(path=extract_dir)

    # The directories named 'fzf' or 'delta' won't even be considered
    # because os.walk only passes files to our detection logic
    detected_paths = auto_detect_paths_in_archive(extract_dir, ["delta"])
    assert detected_paths == [Path("actual-delta")]

    # Verify the directories exist but weren't considered
    assert (extract_dir / "fzf").is_dir()
    assert (extract_dir / "bin" / "delta").is_dir()


def test_substring_matches_fallback(
    tmp_path: Path,
    mock_archive_substring_matches: Path,
) -> None:
    """Test that substring matches are used as fallback."""
    extract_dir = tmp_path / "test_substring"
    extract_dir.mkdir()

    with zipfile.ZipFile(mock_archive_substring_matches, "r") as zipf:
        zipf.extractall(path=extract_dir)

    # Should find substring match
    detected_paths = auto_detect_paths_in_archive(extract_dir, ["mytool"])
    assert len(detected_paths) == 1
    assert detected_paths[0] in [Path("mytool-v1"), Path("other-mytool-bin"), Path("mytool.backup")]


def test_non_executable_exact_match(
    tmp_path: Path,
    mock_archive_non_executable_match: Path,
) -> None:
    """Test handling of exact name matches that aren't executable."""
    extract_dir = tmp_path / "test_non_exec_match"
    extract_dir.mkdir()

    with zipfile.ZipFile(mock_archive_non_executable_match, "r") as zipf:
        zipf.extractall(path=extract_dir)

    detected_paths = auto_detect_paths_in_archive(extract_dir, ["mytool"])
    assert detected_paths == [Path("mytool")]


def test_bin_directory_fallback(
    tmp_path: Path,
    mock_archive_bin_dir_fallback: Path,
) -> None:
    """Test bin directory matching logic with and without name matches."""
    extract_dir = tmp_path / "test_bin_fallback"
    extract_dir.mkdir()

    with zipfile.ZipFile(mock_archive_bin_dir_fallback, "r") as zipf:
        zipf.extractall(path=extract_dir)

    # When no name matches in bin/, should take first bin/ match
    detected_paths = auto_detect_paths_in_archive(extract_dir, ["mytool"])

    # On Windows, the specific binary choice can be different since
    # executable bits don't exist in the same way
    if os.name == "nt":
        assert len(detected_paths) == 1
        # We care that it found something, but the exact match may vary
        assert detected_paths[0] in [Path("bin/completely-different"), Path("other/not-mytool")]
    else:
        assert detected_paths == [Path("bin/completely-different")]

    # Verify that other executables exist but weren't chosen
    assert (extract_dir / "bin2" / "unrelated").exists()
    assert (extract_dir / "other" / "not-mytool").exists()


def test_bin_directory_preference(
    tmp_path: Path,
    mock_archive_bin_matches: Path,
) -> None:
    """Test bin directory matching logic with name matches."""
    extract_dir = tmp_path / "test_bin_matches"
    extract_dir.mkdir()

    with zipfile.ZipFile(mock_archive_bin_matches, "r") as zipf:
        zipf.extractall(path=extract_dir)

    detected_paths = auto_detect_paths_in_archive(extract_dir, ["tool"])
    assert detected_paths == [Path("bin/tool")]

    detected_paths = auto_detect_paths_in_archive(extract_dir, ["other-tool"])
    assert detected_paths == [Path("bin2/other-tool")]

    detected_paths = auto_detect_paths_in_archive(extract_dir, ["extra"])
    assert detected_paths == [Path("bin/tool-extra")]

    # Verify all test files exist
    assert (extract_dir / "bin" / "tool").exists()
    assert (extract_dir / "bin" / "tool-extra").exists()
    assert (extract_dir / "other-bin" / "tool").exists()
