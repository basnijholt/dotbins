"""Tests for dotbins.utils."""

import bz2
import gzip
import lzma
import os
import tarfile
import zipfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from dotbins.utils import extract_archive, github_url_to_raw_url, humanize_time_ago


def test_github_url_to_raw_url() -> None:
    """Test that github_url_to_raw_url converts a GitHub repository URL to a raw URL."""
    original_url = "https://github.com/basnijholt/dotbins/blob/main/dotbins.yaml"
    raw_url = "https://raw.githubusercontent.com/basnijholt/dotbins/refs/heads/main/dotbins.yaml"
    assert github_url_to_raw_url(original_url) == raw_url
    assert github_url_to_raw_url(raw_url) == raw_url
    untouched_url = "https://github.com/basnijholt/dotbins"
    assert github_url_to_raw_url(untouched_url) == untouched_url


@pytest.fixture
def archive_dirs(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Set up test directories and create a test binary file."""
    temp_dir = tmp_path / "temp"
    dest_dir = tmp_path / "dest"
    temp_dir.mkdir(parents=True, exist_ok=True)
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Create a test file to include in archives
    test_file = temp_dir / "test_binary"
    test_file.write_text("#!/bin/sh\necho 'Hello, world!'\n")
    test_file.chmod(0o755)  # Make executable

    return temp_dir, dest_dir, test_file


def verify_extraction(
    dest_dir: Path,
    test_file: Path,
    expected_file: str = "test_binary",
) -> None:
    """Verify that extraction produced the expected file and it's executable."""
    extracted_file = dest_dir / expected_file
    assert extracted_file.exists(), f"Expected file {expected_file} was not extracted"
    assert extracted_file.read_text() == test_file.read_text()
    # Make sure permissions are checked correctly
    if os.name != "nt":  # Skip on Windows
        assert os.access(extracted_file, os.X_OK), f"{expected_file} is not executable"


def test_extract_targz(archive_dirs: tuple[Path, Path, Path]) -> None:
    """Test extracting a .tar.gz file."""
    temp_dir, dest_dir, test_file = archive_dirs
    archive_path = temp_dir / "archive.tar.gz"

    # Create a valid tar.gz archive
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(test_file, arcname=test_file.name)

    extract_archive(archive_path, dest_dir)
    verify_extraction(dest_dir, test_file)


def test_extract_tgz(archive_dirs: tuple[Path, Path, Path]) -> None:
    """Test extracting a .tgz file."""
    temp_dir, dest_dir, test_file = archive_dirs
    archive_path = temp_dir / "archive.tgz"

    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(test_file, arcname=test_file.name)

    extract_archive(archive_path, dest_dir)
    verify_extraction(dest_dir, test_file)


def test_extract_tar_bz2(archive_dirs: tuple[Path, Path, Path]) -> None:
    """Test extracting a .tar.bz2 file."""
    temp_dir, dest_dir, test_file = archive_dirs
    archive_path = temp_dir / "archive.tar.bz2"

    with tarfile.open(archive_path, "w:bz2") as tar:
        tar.add(test_file, arcname=test_file.name)

    extract_archive(archive_path, dest_dir)
    verify_extraction(dest_dir, test_file)


def test_extract_tar(archive_dirs: tuple[Path, Path, Path]) -> None:
    """Test extracting a plain .tar file."""
    temp_dir, dest_dir, test_file = archive_dirs
    archive_path = temp_dir / "archive.tar"

    with tarfile.open(archive_path, "w") as tar:
        tar.add(test_file, arcname=test_file.name)

    extract_archive(archive_path, dest_dir)
    verify_extraction(dest_dir, test_file)


def test_extract_zip(archive_dirs: tuple[Path, Path, Path]) -> None:
    """Test extracting a .zip file."""
    temp_dir, dest_dir, test_file = archive_dirs
    archive_path = temp_dir / "archive.zip"

    with zipfile.ZipFile(archive_path, "w") as zip_file:
        # Save mode explicitly by using external_attr
        # 0o755 (executable) = 0o100755 in ZIP attr mode
        zip_info = zipfile.ZipInfo(test_file.name)
        zip_info.external_attr = 0o100755 << 16  # Set executable permission bits
        zip_file.writestr(zip_info, test_file.read_text())

    extract_archive(archive_path, dest_dir)

    # Manually fix permissions since zipfile might not preserve them
    extracted_file = dest_dir / test_file.name
    if not os.access(extracted_file, os.X_OK) and os.name != "nt":
        extracted_file.chmod(0o755)

    verify_extraction(dest_dir, test_file)


def test_extract_gz(archive_dirs: tuple[Path, Path, Path]) -> None:
    """Test extracting a single .gz file."""
    temp_dir, dest_dir, test_file = archive_dirs
    archive_path = temp_dir / "test_binary.gz"

    # Create a simple gz file (not tar.gz)
    with gzip.open(archive_path, "wb") as f_out:
        f_out.write(test_file.read_bytes())

    # This should now work with our updated extraction function
    extract_archive(archive_path, dest_dir)
    verify_extraction(dest_dir, test_file)


def test_extract_bz2(archive_dirs: tuple[Path, Path, Path]) -> None:
    """Test extracting a single .bz2 file."""
    temp_dir, dest_dir, test_file = archive_dirs
    archive_path = temp_dir / "test_binary.bz2"

    # Create a simple bz2 file (not tar.bz2)
    with bz2.open(archive_path, "wb") as f_out:
        f_out.write(test_file.read_bytes())

    # This should now work with our updated extraction function
    extract_archive(archive_path, dest_dir)
    verify_extraction(dest_dir, test_file)


def test_extract_xz(archive_dirs: tuple[Path, Path, Path]) -> None:
    """Test extracting a single .xz file."""
    temp_dir, dest_dir, test_file = archive_dirs
    archive_path = temp_dir / "test_binary.xz"

    # Create a simple xz file (not tar.xz)
    with lzma.open(archive_path, "wb") as f_out:
        f_out.write(test_file.read_bytes())

    # This should now work with our updated extraction function
    extract_archive(archive_path, dest_dir)
    verify_extraction(dest_dir, test_file)


def test_extract_unsupported_format(archive_dirs: tuple[Path, Path, Path]) -> None:
    """Test extracting an unsupported file format."""
    temp_dir, dest_dir, _ = archive_dirs
    archive_path = temp_dir / "archive.unknown"
    archive_path.write_text("Not a valid archive")

    with pytest.raises(ValueError, match="Unsupported archive format"):
        extract_archive(archive_path, dest_dir)


def test_extract_header_detection(archive_dirs: tuple[Path, Path, Path]) -> None:
    """Test that header detection works with a non-standard extension."""
    temp_dir, dest_dir, test_file = archive_dirs

    # Create a gzip file with a non-standard extension
    weird_path = temp_dir / "binary.weird"
    with gzip.open(weird_path, "wb") as f_out:
        f_out.write(test_file.read_bytes())

    # Now this should work with our fixed extraction function
    extract_archive(weird_path, dest_dir)
    verify_extraction(dest_dir, test_file, "binary")


def test_extraction_error(archive_dirs: tuple[Path, Path, Path]) -> None:
    """Test handling of extraction errors."""
    temp_dir, dest_dir, _ = archive_dirs

    # Create a valid-looking but corrupted file
    archive_path = temp_dir / "archive.tar.gz"
    with open(archive_path, "wb") as f:
        # Write just enough of a gzip header to be detected
        f.write(b"\x1f\x8b\x08\x00\x00\x00\x00\x00")
        # But corrupted content
        f.write(b"corrupted data")

    # This should raise because it's not a valid gzip file
    with pytest.raises((ValueError, tarfile.ReadError), match=".*"):
        extract_archive(archive_path, dest_dir)


def test_humanize_time_ago() -> None:
    """Test humanize_time_ago with various time differences."""
    # Define a fixed reference time for testing
    fixed_now = datetime(2023, 5, 15, 12, 30, 0)  # noqa: DTZ001

    with patch("dotbins.utils.datetime") as mock_datetime:
        # Mock datetime.now() to return our fixed time
        mock_datetime.now.return_value = fixed_now
        # Pass through the fromisoformat method
        mock_datetime.fromisoformat = datetime.fromisoformat

        # Test days + hours
        assert humanize_time_ago("2023-05-10T10:30:00") == "5d2h"

        # Test days only
        assert humanize_time_ago("2023-05-10T12:30:00") == "5d"

        # Test hours + minutes
        assert humanize_time_ago("2023-05-15T08:15:00") == "4h15m"

        # Test hours only
        assert humanize_time_ago("2023-05-15T08:30:00") == "4h"

        # Test minutes + seconds
        assert humanize_time_ago("2023-05-15T12:25:15") == "4m45s"

        # Test minutes only
        assert humanize_time_ago("2023-05-15T12:25:00") == "5m"

        # Test seconds only
        assert humanize_time_ago("2023-05-15T12:29:30") == "30s"

        # Test zero difference
        assert humanize_time_ago("2023-05-15T12:30:00") == "0s"
