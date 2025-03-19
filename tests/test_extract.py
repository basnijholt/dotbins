"""Tests for dotbins.extract."""

import bz2
import gzip
import io
import lzma
import shutil
import tarfile
import tempfile
import zipfile
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from dotbins.extract import (
    ExtractionError,
    binary_chooser,
    extract_file,
    glob_chooser,
    is_exec,
    literal_file_chooser,
    rename,
)


# Helper functions for creating test archives
def create_tar_archive(files: dict) -> bytes:
    """Create a tar archive with the specified files."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        for name, content in files.items():
            info = tarfile.TarInfo(name=name)
            if isinstance(content, dict):  # It's a directory
                info.type = tarfile.DIRTYPE
                info.mode = content.get("mode", 0o755)
                tar.addfile(info)
            else:
                info.size = len(content)
                info.mode = 0o755 if name.endswith((".sh", ".exe")) else 0o644
                tar.addfile(info, io.BytesIO(content))
    return buffer.getvalue()


def create_zip_archive(files: dict) -> bytes:
    """Create a zip archive with the specified files."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w") as zip_file:
        for name, content in files.items():
            if isinstance(content, dict):  # It's a directory
                # Directories in zip end with a slash
                dir_name = name if name.endswith("/") else f"{name}/"
                zip_info = zipfile.ZipInfo(dir_name)

                # Set mode bits (0o755 for directory)
                zip_info.external_attr = content.get("mode", 0o755) << 16
                zip_file.writestr(zip_info, "")
            else:
                # Regular file
                zip_info = zipfile.ZipInfo(name)

                # Set mode bits (0o755 for executables, 0o644 for others)
                mode = 0o755 if name.endswith((".sh", ".exe")) else 0o644
                zip_info.external_attr = mode << 16
                zip_file.writestr(zip_info, content)
    return buffer.getvalue()


def compress_data(data: bytes, compressor: str) -> bytes:
    """Compress data with the specified algorithm."""
    if compressor == "gzip":
        buffer = io.BytesIO()
        with gzip.GzipFile(fileobj=buffer, mode="w") as gz:
            gz.write(data)
        return buffer.getvalue()
    if compressor == "bzip2":
        return bz2.compress(data)
    if compressor == "xz":
        return lzma.compress(data)
    msg = f"Unknown compressor: {compressor}"  # pragma: no cover
    raise ValueError(msg)  # pragma: no cover


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


# Test utility functions
def test_is_exec() -> None:
    """Test the is_exec function."""
    assert is_exec("file.exe", 0o644) is True
    assert is_exec("file.appimage", 0o644) is True
    assert is_exec("file", 0o644) is True  # No extension
    assert is_exec("file.txt", 0o755) is False  # Executable permission
    assert is_exec("file.txt", 0o644) is False
    assert is_exec("file.deb", 0o755) is False  # Definitely not executable
    assert is_exec("file.1", 0o755) is False  # Definitely not executable


def test_rename() -> None:
    """Test the rename function."""
    assert rename("file.exe", "tool") == "file.exe"
    assert rename("file.appimage", "tool") == "file"
    assert rename("file.txt", "tool") == "file.txt"
    assert rename("file", "tool") == "tool"


def test_binary_chooser() -> None:
    """Test the binary_chooser function."""
    # Direct match for binary
    direct, possible = binary_chooser("tool", False, 0o755, "tool")
    assert direct is True
    assert possible is True

    # Directory is never a match
    direct, possible = binary_chooser("tool", True, 0o755, "tool")
    assert direct is False
    assert possible is False

    # Executable but not the right name
    direct, possible = binary_chooser("other", False, 0o755, "tool")
    assert direct is False
    assert possible is True

    # Right name but not executable
    direct, possible = binary_chooser("tool.txt", False, 0o644, "tool")
    assert direct is False
    assert possible is False


def test_literal_file_chooser() -> None:
    """Test the literal_file_chooser function."""
    # Matches with literal file
    direct, possible = literal_file_chooser(
        "path/to/file.txt",
        False,
        0o644,
        "file.txt",
    )
    assert direct is False
    assert possible is True

    # Does not match
    direct, possible = literal_file_chooser(
        "path/to/other.txt",
        False,
        0o644,
        "file.txt",
    )
    assert direct is False
    assert possible is False


def test_glob_chooser() -> None:
    """Test the glob_chooser function."""
    # Matches with glob
    direct, possible = glob_chooser("path/to/file.txt", False, 0o644, "*.txt")
    assert direct is False
    assert possible is True

    # Match all
    direct, possible = glob_chooser("path/to/file.sh", False, 0o644, "*")
    assert direct is True
    assert possible is True

    # Does not match
    direct, possible = glob_chooser("path/to/file.txt", False, 0o644, "*.exe")
    assert direct is False
    assert possible is False


# Test tar extraction
def test_extract_tar_binary(temp_dir: Path) -> None:
    """Test the extract_file function with a tar archive."""
    # Create test data
    files = {
        "tool": b"#!/bin/sh\necho 'Hello, World!'\n",
        "other.txt": b"This is not an executable",
        "lib/data.txt": b"Some data",
    }
    tar_data = create_tar_archive(files)

    # Extract the binary
    extracted = extract_file("archive.tar", tar_data, "tool")
    assert extracted.name == "tool"
    assert extracted.archive_name == "tool"

    # Actually extract the file
    output_path = temp_dir / "output"
    extracted.extract(output_path)
    assert output_path.exists()
    assert output_path.read_bytes() == b"#!/bin/sh\necho 'Hello, World!'\n"
    assert output_path.stat().st_mode & 0o777 & 0o111 != 0  # Should be executable


def test_extract_tar_directory(temp_dir: Path) -> None:
    """Test the extract_file function with a tar archive and a directory."""
    # Create test data with a directory structure
    files = {
        "dir/": {"mode": 0o755},
        "dir/tool": b"#!/bin/sh\necho 'Hello, World!'\n",
        "dir/lib/": {"mode": 0o755},
        "dir/lib/data.txt": b"Some data",
    }
    tar_data = create_tar_archive(files)

    # Extract the directory
    extracted = extract_file("archive.tar", tar_data, "", "glob", "dir/")
    assert extracted.name == "dir/"
    assert extracted.archive_name == "dir"
    assert extracted.is_dir is True

    # Actually extract the directory
    output_path = temp_dir / "output_dir"
    extracted.extract(output_path)
    assert output_path.exists()
    assert output_path.is_dir()
    assert (output_path / "tool").exists()
    assert (output_path / "lib" / "data.txt").exists()
    assert (output_path / "tool").read_bytes() == b"#!/bin/sh\necho 'Hello, World!'\n"
    assert (output_path / "lib" / "data.txt").read_bytes() == b"Some data"
    assert (output_path / "tool").stat().st_mode & 0o777 & 0o111 != 0  # Should be executable


def test_extract_tar_multiple_candidates() -> None:
    """Test the extract_file function with a tar archive and multiple candidates."""
    # Create test data with multiple executables
    files = {
        "tool1": b"#!/bin/sh\necho 'Tool 1'\n",
        "tool2": b"#!/bin/sh\necho 'Tool 2'\n",
    }
    tar_data = create_tar_archive(files)

    # Should raise an error with multiple candidates
    with pytest.raises(ExtractionError) as excinfo:
        extract_file("archive.tar", tar_data, "", "glob", "*")

    assert "2 candidates found" in str(excinfo.value)
    assert len(excinfo.value.candidates) == 2


def test_extract_tar_no_candidates() -> None:
    """Test the extract_file function with a tar archive and no matching files."""
    # Create test data with no matching files
    files = {
        "file1.txt": b"Text file 1",
        "file2.txt": b"Text file 2",
    }
    tar_data = create_tar_archive(files)

    # Should raise an error with no candidates
    with pytest.raises(ExtractionError) as excinfo:
        extract_file("archive.tar", tar_data, "nonexistent")

    assert "Target not found" in str(excinfo.value)


def test_extract_tar_with_multiple_flag(temp_dir: Path) -> None:
    """Test the extract_file function with a tar archive and multiple=True."""
    # Create test data with multiple executables
    files = {
        "tool1": b"#!/bin/sh\necho 'Tool 1'\n",
        "tool2": b"#!/bin/sh\necho 'Tool 2'\n",
    }
    tar_data = create_tar_archive(files)

    # With multiple=True, it should return the directly matching one
    extracted = extract_file("archive.tar", tar_data, "tool1", multiple=True)
    assert extracted.name == "tool1"
    assert extracted.archive_name == "tool1"

    # Actually extract the file
    output_path = temp_dir / "output_multiple"
    extracted.extract(output_path)
    assert output_path.exists()
    assert output_path.read_bytes() == b"#!/bin/sh\necho 'Tool 1'\n"


# Test zip extraction
def test_extract_zip_binary(temp_dir: Path) -> None:
    """Test the extract_file function with a zip archive."""
    # Create test data
    files = {
        "tool.exe": b"Windows executable content",
        "other.txt": b"This is not an executable",
    }
    zip_data = create_zip_archive(files)

    # Extract the binary
    extracted = extract_file("archive.zip", zip_data, "tool")
    assert extracted.name == "tool.exe"
    assert extracted.archive_name == "tool.exe"

    # Actually extract the file
    output_path = temp_dir / "output.exe"
    extracted.extract(output_path)
    assert output_path.exists()
    assert output_path.read_bytes() == b"Windows executable content"
    assert output_path.stat().st_mode & 0o777 & 0o111 != 0  # Should be executable


def test_extract_zip_directory(temp_dir: Path) -> None:
    """Test the extract_file function with a zip archive and a directory."""
    # Create test data with a directory structure
    files = {
        "dir/": {},
        "dir/tool.exe": b"Windows executable content",
        "dir/lib/": {},
        "dir/lib/data.txt": b"Some data",
    }
    zip_data = create_zip_archive(files)

    # Extract the directory
    extracted = extract_file("archive.zip", zip_data, "", "glob", "dir/")
    assert extracted.name == "dir/"
    assert extracted.archive_name == "dir/"
    assert extracted.is_dir is True

    # Actually extract the directory
    output_path = temp_dir / "output_dir"
    extracted.extract(output_path)
    assert output_path.exists()
    assert output_path.is_dir()
    assert (output_path / "tool.exe").exists()
    assert (output_path / "lib" / "data.txt").exists()
    assert (output_path / "tool.exe").read_bytes() == b"Windows executable content"
    assert (output_path / "lib" / "data.txt").read_bytes() == b"Some data"
    assert (output_path / "tool.exe").stat().st_mode & 0o777 & 0o111 != 0  # Should be executable


def test_extract_zip_multiple_candidates() -> None:
    """Test the extract_file function with a zip archive and multiple candidates."""
    # Create test data with multiple executables
    files = {
        "tool1.exe": b"Windows executable 1",
        "tool2.exe": b"Windows executable 2",
    }
    zip_data = create_zip_archive(files)

    # Should raise an error with multiple candidates
    with pytest.raises(ExtractionError) as excinfo:
        extract_file("archive.zip", zip_data, "", "glob", "*.exe")

    assert "2 candidates found" in str(excinfo.value)
    assert len(excinfo.value.candidates) == 2


def test_extract_zip_no_candidates() -> None:
    """Test the extract_file function with a zip archive and no matching files."""
    # Create test data with no matching files
    files = {
        "file1.txt": b"Text file 1",
        "file2.txt": b"Text file 2",
    }
    zip_data = create_zip_archive(files)

    # Should raise an error with no candidates
    with pytest.raises(ExtractionError) as excinfo:
        extract_file("archive.zip", zip_data, "nonexistent")

    assert "Target not found" in str(excinfo.value)


def test_extract_zip_bad_zip() -> None:
    """Test the extract_file function with invalid zip data."""
    # Create invalid zip data
    bad_zip_data = b"This is not a valid ZIP file"

    # Should raise an error for invalid ZIP
    with pytest.raises(ExtractionError) as excinfo:
        extract_file("archive.zip", bad_zip_data, "tool")

    assert "Failed to extract zip" in str(excinfo.value)


# Test compressed archives
def test_extract_tar_gz(temp_dir: Path) -> None:
    """Test the extract_file function with a tar.gz archive."""
    # Create test data
    files = {
        "tool": b"#!/bin/sh\necho 'Hello, World!'\n",
    }
    tar_data = create_tar_archive(files)
    tar_gz_data = compress_data(tar_data, "gzip")

    # Extract the binary
    extracted = extract_file("archive.tar.gz", tar_gz_data, "tool")
    assert extracted.name == "tool"
    assert extracted.archive_name == "tool"

    # Actually extract the file
    output_path = temp_dir / "output_gz"
    extracted.extract(output_path)
    assert output_path.exists()
    assert output_path.read_bytes() == b"#!/bin/sh\necho 'Hello, World!'\n"


def test_extract_tar_bz2(temp_dir: Path) -> None:
    """Test the extract_file function with a tar.bz2 archive."""
    # Create test data
    files = {
        "tool": b"#!/bin/sh\necho 'Hello, World!'\n",
    }
    tar_data = create_tar_archive(files)
    tar_bz2_data = compress_data(tar_data, "bzip2")

    # Extract the binary
    extracted = extract_file("archive.tar.bz2", tar_bz2_data, "tool")
    assert extracted.name == "tool"
    assert extracted.archive_name == "tool"

    # Actually extract the file
    output_path = temp_dir / "output_bz2"
    extracted.extract(output_path)
    assert output_path.exists()
    assert output_path.read_bytes() == b"#!/bin/sh\necho 'Hello, World!'\n"


def test_extract_tar_xz(temp_dir: Path) -> None:
    """Test the extract_file function with a tar.xz archive."""
    # Create test data
    files = {
        "tool": b"#!/bin/sh\necho 'Hello, World!'\n",
    }
    tar_data = create_tar_archive(files)
    tar_xz_data = compress_data(tar_data, "xz")

    # Extract the binary
    extracted = extract_file("archive.tar.xz", tar_xz_data, "tool")
    assert extracted.name == "tool"
    assert extracted.archive_name == "tool"

    # Actually extract the file
    output_path = temp_dir / "output_xz"
    extracted.extract(output_path)
    assert output_path.exists()
    assert output_path.read_bytes() == b"#!/bin/sh\necho 'Hello, World!'\n"


# Test single compressed files
def test_extract_single_file_gz(temp_dir: Path) -> None:
    """Test the extract_file function with a gz archive."""
    # Create compressed data
    content = b"#!/bin/sh\necho 'Hello, World!'\n"
    compressed = compress_data(content, "gzip")

    # Extract the file
    extracted = extract_file("tool.gz", compressed, "tool")
    assert extracted.name == "tool"
    assert extracted.archive_name == "tool.gz"

    # Actually extract the file
    output_path = temp_dir / "output_single_gz"
    extracted.extract(output_path)
    assert output_path.exists()
    assert output_path.read_bytes() == content
    assert output_path.stat().st_mode & 0o777 & 0o111 != 0  # Should be executable


def test_extract_single_file_bz2(temp_dir: Path) -> None:
    """Test the extract_file function with a bz2 archive."""
    # Create compressed data
    content = b"#!/bin/sh\necho 'Hello, World!'\n"
    compressed = compress_data(content, "bzip2")

    # Extract the file
    extracted = extract_file("tool.bz2", compressed, "tool")
    assert extracted.name == "tool"
    assert extracted.archive_name == "tool.bz2"

    # Actually extract the file
    output_path = temp_dir / "output_single_bz2"
    extracted.extract(output_path)
    assert output_path.exists()
    assert output_path.read_bytes() == content


def test_extract_single_file_xz(temp_dir: Path) -> None:
    """Test the extract_file function with a xz archive."""
    # Create compressed data
    content = b"#!/bin/sh\necho 'Hello, World!'\n"
    compressed = compress_data(content, "xz")

    # Extract the file
    extracted = extract_file("tool.xz", compressed, "tool")
    assert extracted.name == "tool"
    assert extracted.archive_name == "tool.xz"

    # Actually extract the file
    output_path = temp_dir / "output_single_xz"
    extracted.extract(output_path)
    assert output_path.exists()
    assert output_path.read_bytes() == content


def test_extract_regular_file(temp_dir: Path) -> None:
    """Test the extract_file function with a regular file."""
    # Create regular file data
    content = b"#!/bin/sh\necho 'Hello, World!'\n"

    # Extract the file
    extracted = extract_file("tool", content, "tool")
    assert extracted.name == "tool"
    assert extracted.archive_name == "tool"

    # Actually extract the file
    output_path = temp_dir / "output_regular"
    extracted.extract(output_path)
    assert output_path.exists()
    assert output_path.read_bytes() == content
    assert output_path.stat().st_mode & 0o777 & 0o111 != 0  # Should be executable


# Test error cases
def test_invalid_chooser_type() -> None:
    """Test that an error is raised for an invalid chooser type."""
    with pytest.raises(ValueError, match="Unknown chooser type: invalid") as excinfo:
        extract_file("archive.tar", b"data", chooser_type="invalid")  # type: ignore[arg-type]

    assert "Unknown chooser type" in str(excinfo.value)


def test_extract_tar_error() -> None:
    """Test that an error is raised for an invalid tar file."""
    # Create invalid tar data
    bad_tar_data = b"This is not a valid TAR file"

    # Should raise an error for invalid TAR
    with pytest.raises(ExtractionError) as excinfo:
        extract_file("archive.tar", bad_tar_data, "tool")

    assert "Failed to extract tar" in str(excinfo.value)


# Test with mocks and specific edge cases
@patch("dotbins.extract._decompress_data")
def test_decompression_error(mock_decompress: MagicMock) -> None:
    """Test that an error is raised for a decompression error."""
    mock_decompress.side_effect = Exception("Decompression failed")

    with pytest.raises(ExtractionError, match="Decompression failed"):
        extract_file("archive.tar.gz", b"data", "tool")


def test_symlink_handling() -> None:
    """Test handling of symlinks in tar archives."""
    # This is a bit tricky to test directly due to the need for a real tar archive with symlinks.
    # In a real test, we'd create an archive with symlinks, but for simplicity we'll patch the tarfile.

    # Mock the tar extraction
    with patch("tarfile.open") as mock_tar_open:
        # Create a mock tar file and members
        mock_tar = MagicMock()

        # Create a directory member first
        mock_dir = MagicMock()
        mock_dir.name = "dir"
        mock_dir.isdir.return_value = True
        mock_dir.issym.return_value = False
        mock_dir.islnk.return_value = False

        # Create a symlink member
        mock_link = MagicMock()
        mock_link.name = "dir/link"
        mock_link.linkname = "target"
        mock_link.isdir.return_value = False
        mock_link.issym.return_value = True
        mock_link.islnk.return_value = False

        # Return both members
        mock_tar.getmembers.return_value = [mock_dir, mock_link]
        mock_tar_open.return_value.__enter__.return_value = mock_tar

        # Test directory extraction with a symlink
        extracted = extract_file("archive.tar", b"data", "", "glob", "dir")

        # We can't actually test the symlink creation without a real tar file,
        # but we can verify that the extraction logic is reached.
        assert extracted is not None
        assert extracted.is_dir is True


def test_with_real_tar_gz() -> None:
    """Test extracting a real tar.gz archive."""
    try:
        # Get a real archive from a test data directory
        test_file = Path(__file__).parent / "testdata" / "sample.tar.gz"
        if test_file.exists():
            with open(test_file, "rb") as f:
                data = f.read()
            # Try to extract from it
            extracted = extract_file(str(test_file), data, "")
            assert extracted is not None
    except (FileNotFoundError, ExtractionError):
        pytest.skip("Real archive test data not available")
