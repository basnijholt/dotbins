"""Configuration for pytest fixtures used in dotbins tests."""

from __future__ import annotations

import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import Callable

import pytest


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
