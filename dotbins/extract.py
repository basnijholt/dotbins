"""Extract files from archives."""

from __future__ import annotations

import bz2
import contextlib
import fnmatch
import gzip
import io
import lzma
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal


@dataclass
class ArchiveFileInfo:
    """Information about a file in an archive."""

    name: str
    is_dir: bool
    mode: int
    data: bytes | None = None
    linkname: str = ""
    is_symlink: bool = False
    is_hardlink: bool = False


@dataclass
class ExtractedFile:
    """Represents a file extracted from an archive."""

    name: str  # name to extract to
    archive_name: str  # name in archive
    mode: int  # file mode
    extract: Callable[[Path], None]  # function to extract file to a path
    is_dir: bool = False

    def __str__(self) -> str:
        """Return the extracted file name."""
        return self.archive_name


class ExtractionError(Exception):
    """Error during extraction process."""

    def __init__(
        self,
        message: str,
        candidates: list[ExtractedFile] | None = None,
    ) -> None:
        """Initialize the ExtractionError."""
        self.message = message
        self.candidates = candidates or []
        super().__init__(message)


def _is_definitely_not_exec(filename: str) -> bool:
    """Check if a file is definitely not executable."""
    return filename.endswith((".deb", ".1", ".txt"))


def is_exec(filename: str, mode: int) -> bool:
    """Determine if a file is executable based on name and permissions."""
    # First check mode bits
    if mode & 0o111 != 0 and not _is_definitely_not_exec(filename):
        return True

    # Then check filename
    if _is_definitely_not_exec(filename):
        return False

    return filename.endswith((".exe", ".appimage")) or "." not in Path(filename).name


def rename(filename: str, nameguess: str) -> str:
    """Rename files to appropriate executable names."""
    if _is_definitely_not_exec(filename):
        return filename

    if filename.endswith(".appimage"):
        return filename[:-9]  # remove .appimage extension
    if filename.endswith(".exe"):
        return filename
    return nameguess


def _write_file(data: bytes, path: Path, mode: int) -> None:
    """Write data to a file with specified permissions."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    path.chmod(mode)


# Chooser functions
def binary_chooser(name: str, is_dir: bool, mode: int, tool: str) -> tuple[bool, bool]:
    """Choose executable files."""
    if is_dir:
        return False, False

    basename = Path(name).name
    is_match = basename in (tool, f"{tool}.exe", f"{tool}.appimage")
    is_possible = not is_dir and is_exec(name, mode)
    return is_match and is_possible, is_possible


def literal_file_chooser(
    name: str,
    is_dir: bool,  # noqa: ARG001
    mode: int,  # noqa: ARG001
    filename: str,
) -> tuple[bool, bool]:
    """Choose files with exact name match."""
    basename = Path(name).name
    return False, basename == Path(filename).name and name.endswith(filename)


def glob_chooser(
    name: str,
    is_dir: bool,  # noqa: ARG001
    mode: int,  # noqa: ARG001
    pattern: str,
) -> tuple[bool, bool]:
    """Choose files matching a glob pattern."""
    if pattern in ("*", "/"):
        return True, True

    name = name.removesuffix("/")
    pattern = pattern.removesuffix("/")  # Handle pattern without trailing slash

    basename = Path(name).name
    is_match = fnmatch.fnmatch(basename, pattern) or fnmatch.fnmatch(name, pattern)
    return False, is_match


def _decompress_data(data: bytes, decompressor: str | None = None) -> bytes:
    """Decompress data with the specified algorithm."""
    if not decompressor:
        return data

    try:
        if decompressor == "gzip":
            buffer = io.BytesIO(data)
            with gzip.GzipFile(fileobj=buffer) as gz:
                return gz.read()
        elif decompressor == "bzip2":
            return bz2.decompress(data)
        elif decompressor == "xz":
            return lzma.decompress(data)
        return data
    except Exception as e:
        msg = f"Failed to decompress with {decompressor}: {e}"
        raise ExtractionError(msg) from e


def _extract_regular_file(
    to_path: Path,
    file_data: bytes,
    mode: int,
    name: str,
) -> None:
    """Extract a regular file to the specified path."""
    mode_to_use = mode | 0o111 if is_exec(name, mode) else mode
    _write_file(file_data, to_path, mode_to_use)


def _extract_tar_directory(
    to_path: Path,
    prefix_len: int,
    dir_name: str,
    data: bytes,
) -> None:
    """Extract a directory from a tar archive."""
    to_path.mkdir(parents=True, exist_ok=True)

    with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as extract_tar:
        for sub_member in extract_tar.getmembers():
            if not sub_member.name.startswith(dir_name):
                continue

            rel_path = sub_member.name[prefix_len:]
            rel_path = rel_path.removeprefix("/")
            target_path = to_path / rel_path

            if sub_member.isdir():
                target_path.mkdir(parents=True, exist_ok=True)
            elif sub_member.issym() or sub_member.islnk():
                # Handle symlinks and hardlinks
                if target_path.exists():
                    target_path.unlink()
                target_path.parent.mkdir(parents=True, exist_ok=True)

                if sub_member.issym():
                    target_path.symlink_to(sub_member.linkname)
                else:
                    with contextlib.suppress(Exception):
                        target_path.link_to(sub_member.linkname)
            else:
                # Regular file
                file_data = extract_tar.extractfile(sub_member)
                if file_data:
                    sub_data = file_data.read()
                    sub_mode = sub_member.mode
                    mode_to_use = (
                        sub_mode | 0o111 if is_exec(str(target_path), sub_mode) else sub_mode
                    )
                    _write_file(sub_data, target_path, mode_to_use)


def _extract_zip_directory(
    to_path: Path,
    prefix_len: int,
    dir_name: str,
    data: bytes,
) -> None:
    """Extract a directory from a zip archive."""
    to_path.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(io.BytesIO(data)) as extract_zip:
        for sub_info in extract_zip.infolist():
            if not sub_info.filename.startswith(dir_name):
                continue

            rel_path = sub_info.filename[prefix_len:]
            target_path = to_path / rel_path

            if sub_info.filename.endswith("/"):
                target_path.mkdir(parents=True, exist_ok=True)
            else:
                sub_data = extract_zip.read(sub_info.filename)
                sub_mode = 0o644
                if sub_info.external_attr > 0:
                    sub_mode = (sub_info.external_attr >> 16) & 0o777
                mode_to_use = sub_mode | 0o111 if is_exec(str(target_path), sub_mode) else sub_mode
                _write_file(sub_data, target_path, mode_to_use)


def _create_tar_extract_func(
    file_info: ArchiveFileInfo,
    dirs: list[str],
    all_file_data: dict[str, bytes],
    archive_data: bytes,
) -> Callable[[Path], None]:
    """Create an extraction function for a tar archive file."""
    if not file_info.is_dir:
        # Regular file extraction
        file_data = all_file_data.get(file_info.name, b"")
        return lambda to_path: _extract_regular_file(
            to_path,
            file_data,
            file_info.mode,
            file_info.name,
        )
    # Directory extraction
    dirs.append(file_info.name)
    prefix_len = len(file_info.name)
    return lambda to_path: _extract_tar_directory(
        to_path,
        prefix_len,
        file_info.name,
        archive_data,
    )


def _create_zip_extract_func(
    file_info: ArchiveFileInfo,
    dirs: list[str],
    all_file_data: dict[str, bytes],
    archive_data: bytes,
) -> Callable[[Path], None]:
    """Create an extraction function for a zip archive file."""
    if not file_info.is_dir:
        # Regular file extraction
        file_data = all_file_data.get(file_info.name, b"")
        return lambda to_path: _extract_regular_file(
            to_path,
            file_data,
            file_info.mode,
            file_info.name,
        )
    # Directory extraction
    dirs.append(file_info.name)
    prefix_len = len(file_info.name)
    return lambda to_path: _extract_zip_directory(
        to_path,
        prefix_len,
        file_info.name,
        archive_data,
    )


def _process_archive_candidates(
    file_infos: list[ArchiveFileInfo],
    chooser_fn: Callable,
    chooser_args: dict[str, Any],
    extract_func_creator: Callable,
    all_file_data: dict[str, bytes],
    archive_data: bytes,
    multiple: bool = False,
) -> ExtractedFile:
    """Generic function to process archive candidates and apply chooser logic.

    Args:
        file_infos: List of archive file information
        chooser_fn: Function to determine if a file should be extracted
        chooser_args: Arguments for the chooser function
        extract_func_creator: Function to create extraction functions
        all_file_data: Dictionary of file data indexed by name
        archive_data: Raw archive data
        multiple: If True, allow multiple candidates

    Returns:
        The extracted file object

    Raises:
        ExtractionError: If no candidates or too many candidates found

    """
    candidates: list[ExtractedFile] = []
    direct_candidates: list[ExtractedFile] = []
    dirs: list[str] = []

    for file_info in file_infos:
        # Skip files in already selected directories
        if any(file_info.name.startswith(d) for d in dirs):
            continue

        # Apply the chooser function
        direct, possible = chooser_fn(
            file_info.name,
            file_info.is_dir,
            file_info.mode,
            **chooser_args,
        )

        if direct or possible:
            # Preserve trailing slash for directory names
            name = file_info.name
            if file_info.is_dir and not name.endswith("/"):
                name += "/"

            name = rename(name, name)

            # Get extraction function
            extract_func = extract_func_creator(
                file_info,
                dirs,
                all_file_data,
                archive_data,
            )

            ef = ExtractedFile(
                name=name,
                archive_name=file_info.name,
                mode=file_info.mode,
                extract=extract_func,
                is_dir=file_info.is_dir,
            )

            if direct:
                direct_candidates.append(ef)
            candidates.append(ef)

    # Handle candidate selection
    if direct_candidates and multiple:
        return direct_candidates[0]

    if len(candidates) == 1:
        return candidates[0]

    if len(candidates) == 0:
        msg = "Target not found in archive"
        raise ExtractionError(msg)

    # When pattern is "*", we have multiple candidates but want to treat them specially
    if chooser_args.get("pattern") == "*" and candidates and not multiple:
        msg = f"{len(candidates)} candidates found"
        raise ExtractionError(msg, candidates)

    # For all other cases with multiple candidates
    if len(candidates) > 1 and not multiple:
        msg = f"{len(candidates)} candidates found"
        raise ExtractionError(msg, candidates)

    # If we get here with multiple=True, just return the first candidate
    return candidates[0]


def _extract_tar(
    data: bytes,
    chooser_fn: Callable[[str, bool, int, Any], tuple[bool, bool]],
    chooser_args: dict[str, Any],
    multiple: bool = False,
) -> ExtractedFile:
    """Extract files from a tar archive."""
    file_infos = []
    all_file_data = {}  # Store file data by name

    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as tar:
            # First pass: collect all file info
            for member in tar.getmembers():
                file_info = ArchiveFileInfo(
                    name=member.name,
                    is_dir=member.isdir(),
                    mode=member.mode,
                    linkname=member.linkname if hasattr(member, "linkname") else "",
                    is_symlink=member.issym() if hasattr(member, "issym") else False,
                    is_hardlink=member.islnk() if hasattr(member, "islnk") else False,
                )

                # Read file data if not a directory or link
                if not file_info.is_dir and not file_info.is_symlink and not file_info.is_hardlink:
                    file_data = tar.extractfile(member)
                    if file_data:
                        all_file_data[member.name] = file_data.read()

                file_infos.append(file_info)

        return _process_archive_candidates(
            file_infos,
            chooser_fn,
            chooser_args,
            _create_tar_extract_func,
            all_file_data,
            data,
            multiple,
        )

    except tarfile.TarError as e:
        msg = f"Failed to extract tar: {e}"
        raise ExtractionError(msg)  # noqa: B904


def _extract_zip(
    data: bytes,
    chooser_fn: Callable[[str, bool, int, Any], tuple[bool, bool]],
    chooser_args: dict[str, Any],
    multiple: bool = False,
) -> ExtractedFile:
    """Extract files from a zip archive."""
    file_infos = []
    all_file_data = {}  # Store file data by name

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zip_file:
            # First pass: collect all file info
            for info in zip_file.infolist():
                is_dir = info.filename.endswith("/")
                file_mode = 0o644
                if info.external_attr > 0:
                    file_mode = (info.external_attr >> 16) & 0o777

                file_info = ArchiveFileInfo(
                    name=info.filename,
                    is_dir=is_dir,
                    mode=file_mode,
                )

                # Read file data if not a directory
                if not is_dir:
                    all_file_data[info.filename] = zip_file.read(info.filename)

                file_infos.append(file_info)

        return _process_archive_candidates(
            file_infos,
            chooser_fn,
            chooser_args,
            _create_zip_extract_func,
            all_file_data,
            data,
            multiple,
        )

    except zipfile.BadZipFile as e:
        msg = f"Failed to extract zip: {e}"
        raise ExtractionError(msg)  # noqa: B904


def _extract_single_file(
    to_path: Path,
    data: bytes,
    decompressor: str | None,
    mode: int,
) -> None:
    """Extract a single compressed file to a path."""
    decompressed = _decompress_data(data, decompressor)
    _write_file(decompressed, to_path, mode)


def extract_single_file(
    data: bytes,
    filename: str,
    rename_to: str,
    decompressor: str | None = None,
) -> ExtractedFile:
    """Create an ExtractedFile for a single compressed file."""
    name = rename(filename, rename_to)
    mode = 0o666 | (0o111 if is_exec(name, 0o666) else 0)

    return ExtractedFile(
        name=name,
        archive_name=filename,
        mode=mode,
        extract=lambda to_path: _extract_single_file(to_path, data, decompressor, mode),
        is_dir=False,
    )


def extract_file(  # noqa: PLR0911, PLR0912
    filename: str,
    data: bytes,
    tool: str = "",
    chooser_type: Literal["binary", "literal", "glob"] = "binary",
    chooser_arg: str | None = None,
    multiple: bool = False,
) -> ExtractedFile:
    """Extract files from an archive based on filename extension.

    Args:
        filename: The archive filename
        data: The archive data
        tool: The tool name (defaults to filename)
        chooser_type: The type of chooser to use
        chooser_arg: Argument for the chooser (defaults to tool)
        multiple: Whether to allow multiple candidates

    Returns:
        The extracted file object

    Raises:
        ExtractionError: If extraction fails or multiple candidates are found
        ValueError: If an invalid chooser type is provided

    """
    if not tool:
        tool = filename

    if not chooser_arg:
        chooser_arg = tool

    # Select the chooser function
    chooser_fn: Callable[[str, bool, int, Any], tuple[bool, bool]]
    chooser_args: dict[str, Any]

    if chooser_type == "binary":
        chooser_fn = binary_chooser
        chooser_args = {"tool": chooser_arg}
    elif chooser_type == "literal":
        chooser_fn = literal_file_chooser
        chooser_args = {"filename": chooser_arg}
    elif chooser_type == "glob":
        chooser_fn = glob_chooser
        chooser_args = {"pattern": chooser_arg}
    else:
        msg = f"Unknown chooser type: {chooser_type}"
        raise ValueError(msg)

    try:
        # Determine the file type and extract accordingly
        if filename.endswith((".tar.gz", ".tgz")):
            decompressed = _decompress_data(data, "gzip")
            return _extract_tar(decompressed, chooser_fn, chooser_args, multiple)
        if filename.endswith((".tar.bz2", ".tbz")):
            decompressed = _decompress_data(data, "bzip2")
            return _extract_tar(decompressed, chooser_fn, chooser_args, multiple)
        if filename.endswith((".tar.xz", ".txz")):
            decompressed = _decompress_data(data, "xz")
            return _extract_tar(decompressed, chooser_fn, chooser_args, multiple)
        if filename.endswith(".tar"):
            return _extract_tar(data, chooser_fn, chooser_args, multiple)
        if filename.endswith(".zip"):
            return _extract_zip(data, chooser_fn, chooser_args, multiple)
        if filename.endswith(".gz"):
            return extract_single_file(data, filename, tool, "gzip")
        if filename.endswith(".bz2"):
            return extract_single_file(data, filename, tool, "bzip2")
        if filename.endswith(".xz"):
            return extract_single_file(data, filename, tool, "xz")

        return extract_single_file(data, filename, tool)
    except Exception as e:
        # Catch any other exceptions that weren't already converted to ExtractionError
        if not isinstance(e, ExtractionError):
            msg = f"Failed to extract {filename}: {e}"
            raise ExtractionError(msg) from e
        raise
