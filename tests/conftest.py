"""Configuration for pytest fixtures used in dotbins tests."""

from __future__ import annotations

import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING, Callable

import pytest

if TYPE_CHECKING:
    from requests_mock import Mocker


@pytest.fixture
def create_dummy_archive() -> Callable:
    r"""Create an archive file with binary files for testing.

    Returns a function that creates archive files with specified binaries.

    Usage:
        archive_path = create_dummy_archive(
            dest_path=tmp_path / "test.tar.gz",
            binary_names=["mybinary", "otherbinary"],
            archive_type="tar.gz",
            binary_content="#!/bin/sh\necho test"
        )
    """

    def _create_archive(
        dest_path: Path,
        binary_names: str | list[str],
        archive_type: str = "tar.gz",
        binary_content: str = "#!/usr/bin/env echo\n",
        nested_dir: str | None = None,
    ) -> Path:
        if isinstance(binary_names, str):
            binary_names = [binary_names]

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            # Create nested directory if requested
            if nested_dir:
                bin_dir = tmp_path / nested_dir
                bin_dir.mkdir(exist_ok=True, parents=True)
            else:
                bin_dir = tmp_path

            created_files = []
            for binary in binary_names:
                # Create the binary file
                bin_file = bin_dir / binary
                bin_file.write_text(binary_content)
                bin_file.chmod(0o755)
                created_files.append(bin_file)

            # Create the archive
            if archive_type == "tar.gz":
                with tarfile.open(dest_path, "w:gz") as tar:
                    for file_path in created_files:
                        archive_path = file_path.relative_to(tmp_path)
                        tar.add(file_path, arcname=str(archive_path))
            elif archive_type == "zip":
                with zipfile.ZipFile(dest_path, "w") as zipf:
                    for file_path in created_files:
                        archive_path = file_path.relative_to(tmp_path)
                        zipf.write(file_path, arcname=str(archive_path))
            else:  # pragma: no cover
                msg = f"Unsupported archive type: {archive_type}"
                raise ValueError(msg)

            return dest_path

    return _create_archive


@pytest.fixture
def mock_github_api(
    requests_mock: Mocker,
    tmp_path: Path,
    create_dummy_archive: Callable,
) -> Mocker:
    """Mock GitHub API responses."""
    # Mock the latest release endpoint
    release_data = {
        "tag_name": "v1.0.0",
        "name": "Release 1.0.0",
        "assets": [
            {
                "name": "test-tool-1.0.0-linux_amd64.tar.gz",
                "browser_download_url": "https://example.com/test-tool-1.0.0-linux_amd64.tar.gz",
            },
            {
                "name": "test-tool-1.0.0-linux_arm64.tar.gz",
                "browser_download_url": "https://example.com/test-tool-1.0.0-linux_arm64.tar.gz",
            },
            {
                "name": "test-tool-1.0.0-darwin_amd64.tar.gz",
                "browser_download_url": "https://example.com/test-tool-1.0.0-darwin_amd64.tar.gz",
            },
            {
                "name": "test-tool-1.0.0-darwin_arm64.tar.gz",
                "browser_download_url": "https://example.com/test-tool-1.0.0-darwin_arm64.tar.gz",
            },
        ],
    }

    requests_mock.get(
        "https://api.github.com/repos/test/tool/releases/latest",
        json=release_data,
    )

    # Create a temporary file for our test binary
    test_binary = tmp_path / "test_binary.tar.gz"
    create_dummy_archive(dest_path=test_binary, binary_names="test-tool")

    # Read the tarball content
    with open(test_binary, "rb") as f:
        tarball_content = f.read()

    # Mock binary download endpoints
    for asset in release_data["assets"]:
        assert isinstance(asset, dict)
        requests_mock.get(asset["browser_download_url"], content=tarball_content)

    return requests_mock
