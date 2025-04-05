"""Download and extraction functions for dotbins."""

from __future__ import annotations

import os
import shutil
import tempfile
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

from .detect_binary import auto_detect_extract_archive, auto_detect_paths_in_archive
from .utils import (
    calculate_sha256,
    download_file,
    execute_in_parallel,
    extract_archive,
    log,
    replace_home_in_path,
)

if TYPE_CHECKING:
    from .config import BinSpec, Config, ToolConfig
    from .summary import UpdateSummary
    from .versions import VersionStore


def _extract_binary_from_archive(
    archive_path: Path,
    destination_dir: Path,
    bin_spec: BinSpec,
    verbose: bool,
) -> None:
    """Extract binaries from an archive."""
    log(f"Extracting from {archive_path} for {bin_spec.platform}", "info", "📦")
    temp_dir = Path(tempfile.mkdtemp())

    try:
        extract_archive(archive_path, temp_dir)
        log(f"Archive extracted to {temp_dir}", "success", "📦")
        _log_extracted_files(temp_dir)
        paths_in_archive = _detect_paths_in_archive(temp_dir, bin_spec.tool_config)
        _process_binaries(temp_dir, destination_dir, paths_in_archive, bin_spec)

    except Exception as e:
        log(f"Error extracting archive: {e}", "error", print_exception=verbose)
        raise
    finally:
        shutil.rmtree(temp_dir)


class AutoDetectBinaryPathsError(Exception):
    """Error raised when auto-detecting binary paths fails."""


def _detect_paths_in_archive(temp_dir: Path, tool_config: ToolConfig) -> list[Path]:
    """Auto-detect binary paths if not specified in configuration."""
    if tool_config.path_in_archive:
        return tool_config.path_in_archive
    log("Binary path not specified, attempting auto-detection...", "info")
    binary_names = tool_config.binary_name
    paths_in_archive = auto_detect_paths_in_archive(temp_dir, binary_names)
    if not paths_in_archive:
        msg = f"Could not auto-detect binary paths for {', '.join(binary_names)}. Please specify path_in_archive in config."
        log(msg, "error")
        raise AutoDetectBinaryPathsError(msg)
    names = ", ".join(f"[b]{p}[/]" for p in paths_in_archive)
    log(f"Auto-detected binary paths: {names}", "success")
    return paths_in_archive


def _process_binaries(
    temp_dir: Path,
    destination_dir: Path,
    paths_in_archive: list[Path],
    bin_spec: BinSpec,
) -> None:
    """Process each binary by finding it and copying to destination."""
    for path_in_archive, binary_name in zip(paths_in_archive, bin_spec.tool_config.binary_name):
        source_path = _find_binary_in_extracted_files(
            temp_dir,
            str(path_in_archive),
            bin_spec.version,
            bin_spec.tool_arch,
            bin_spec.tool_platform,
        )
        _copy_binary_to_destination(source_path, destination_dir, binary_name)


def _log_extracted_files(temp_dir: Path) -> None:
    """Log the extracted files for debugging."""
    log("Extracted files:", "info", "ℹ️")  # noqa: RUF001
    for item in temp_dir.glob("**/*"):
        log(f"  - {item.relative_to(temp_dir)}", "info", "")


def _find_binary_in_extracted_files(
    temp_dir: Path,
    path_in_archive: str,
    version: str,
    tool_arch: str,
    tool_platform: str,
) -> Path:
    """Find a specific binary in the extracted files."""
    path_in_archive = _replace_variables_in_path(path_in_archive, version, tool_arch, tool_platform)

    if "*" in path_in_archive:
        matches = list(temp_dir.glob(path_in_archive))
        if not matches:
            msg = f"No files matching {path_in_archive} in archive"
            raise FileNotFoundError(msg)
        return matches[0]

    source_path = temp_dir / path_in_archive
    if not source_path.exists():
        msg = f"Binary ({path_in_archive}) not found at {source_path}"
        raise FileNotFoundError(msg)

    return source_path


def _copy_binary_to_destination(
    source_path: Path,
    destination_dir: Path,
    binary_name: str,
) -> None:
    """Copy the binary to its destination and set permissions."""
    destination_dir.mkdir(parents=True, exist_ok=True)
    dest_path = destination_dir / binary_name
    if os.name == "nt":
        # Maintain the original extension on Windows
        dest_path = dest_path.with_suffix(source_path.suffix)
    shutil.copy2(source_path, dest_path)
    if os.name == "nt":
        # Windows doesn't use the same executable bit concept, so just ensure write access
        dest_path.chmod(dest_path.stat().st_mode)
    else:
        dest_path.chmod(dest_path.stat().st_mode | 0o755)
    log(f"Copied binary to [b]{replace_home_in_path(dest_path, '~')}[/]", "success")


def _replace_variables_in_path(path: str, version: str, arch: str, platform: str) -> str:
    """Replace variables in a path with their values."""
    if "{version}" in path and version:
        path = path.replace("{version}", version)

    if "{arch}" in path and arch:
        path = path.replace("{arch}", arch)

    if "{platform}" in path and platform:
        path = path.replace("{platform}", platform)

    return path


class _DownloadTask(NamedTuple):
    """Represents a single download task."""

    bin_spec: BinSpec
    asset_url: str
    asset_name: str
    destination_dir: Path
    temp_path: Path

    @property
    def tool_name(self) -> str:
        return self.tool_config.tool_name

    @property
    def tool_config(self) -> ToolConfig:
        return self.bin_spec.tool_config

    @property
    def version(self) -> str:
        return self.bin_spec.version

    @property
    def platform(self) -> str:
        return self.bin_spec.platform

    @property
    def arch(self) -> str:
        return self.bin_spec.arch


def _prepare_download_task(
    tool_name: str,
    platform: str,
    arch: str,
    config: Config,
    force: bool,
    verbose: bool,
) -> _DownloadTask | None:
    """Prepare a download task, checking if update is needed based on version."""
    try:
        tool_config = config.tools[tool_name]
        if tool_config._release_info is None:
            # Means we failed to fetch the release info
            return None
        bin_spec = tool_config.bin_spec(arch, platform)
        if bin_spec.skip_download(config, force):
            config._update_summary.add_skipped_tool(
                tool_name,
                platform,
                arch,
                version=bin_spec.version,
                reason="Already up-to-date",
            )
            return None
        asset = bin_spec.matching_asset()
        if asset is None:
            config._update_summary.add_failed_tool(
                tool_name,
                platform,
                arch,
                version=bin_spec.version,
                reason="No matching asset found",
            )
            return None
        tmp_dir = Path(tempfile.gettempdir())
        temp_path = tmp_dir / asset["browser_download_url"].split("/")[-1]
        return _DownloadTask(
            bin_spec=bin_spec,
            asset_url=asset["browser_download_url"],
            asset_name=asset["name"],
            destination_dir=config.bin_dir(platform, arch),
            temp_path=temp_path,
        )
    except Exception as e:
        log(
            f"Error processing {tool_name} for {platform}/{arch}: {e!s}",
            "error",
            print_exception=verbose,
        )
        config._update_summary.add_failed_tool(
            tool_name,
            platform,
            arch,
            version="Unknown",
            reason=f"Error preparing download: {e!s}",
        )
        return None


def prepare_download_tasks(
    config: Config,
    tools_to_sync: list[str] | None,
    platforms_to_sync: list[str] | None,
    architecture: str | None,
    force: bool,
    verbose: bool,
) -> list[_DownloadTask]:
    """Prepare download tasks for all tools and platforms."""
    download_tasks = []
    if tools_to_sync is None:
        tools_to_sync = list(config.tools)
    if platforms_to_sync is None:
        platforms_to_sync = list(config.platforms)

    for tool_name in tools_to_sync:
        for platform in platforms_to_sync:
            if platform not in config.platforms:
                config._update_summary.add_skipped_tool(
                    tool_name,
                    platform,
                    architecture if architecture else "Unknown",
                    version="Unknown",
                    reason="Platform not configured",
                )
                log(f"Skipping unknown platform: {platform}", "warning")
                continue

            archs_to_update = _determine_architectures(platform, architecture, config)
            if not archs_to_update:
                config._update_summary.add_skipped_tool(
                    tool_name,
                    platform,
                    architecture if architecture else "Unknown",
                    version="Unknown",
                    reason="No architectures configured",
                )
                log(f"Skipping unknown architecture: {architecture}", "warning")
                continue

            for arch in archs_to_update:
                task = _prepare_download_task(tool_name, platform, arch, config, force, verbose)
                if task:
                    download_tasks.append(task)

    return sorted(download_tasks, key=lambda t: (t.tool_name, t.platform, t.arch))


def _download_task(
    task: _DownloadTask,
    github_token: str | None,
    verbose: bool,
) -> bool:
    """Download a file for a DownloadTask."""
    try:
        log(
            f"Downloading [b]{task.asset_name}[/] for [b]{task.tool_name}[/] ([b]{task.platform}/{task.arch}[/])...",
            "info",
            "📥",
        )
        download_file(task.asset_url, str(task.temp_path), github_token, verbose)
        return True
    except Exception as e:
        log(f"Error downloading {task.asset_name}: {e!s}", "error", print_exception=verbose)
        return False


def download_files_in_parallel(
    download_tasks: list[_DownloadTask],
    github_token: str | None,
    verbose: bool,
) -> list[bool]:
    """Download files in parallel."""
    if not download_tasks:
        return []
    log(f"Downloading {len(download_tasks)} tools in parallel...", "info", "🔄")
    func = partial(_download_task, github_token=github_token, verbose=verbose)
    return execute_in_parallel(download_tasks, func, 16)


def _process_downloaded_task(
    task: _DownloadTask,
    success: bool,
    version_store: VersionStore,
    summary: UpdateSummary,
    verbose: bool,
) -> bool:
    """Process a downloaded file."""
    if not success:
        summary.add_failed_tool(
            task.tool_name,
            task.platform,
            task.arch,
            task.version,
            reason="Download failed",
        )
        return False

    try:
        # Calculate SHA256 hash before extraction
        sha256_hash = calculate_sha256(task.temp_path)
        log(f"SHA256: {sha256_hash}", "info", "🔐")

        task.destination_dir.mkdir(parents=True, exist_ok=True)
        extract_archive = task.tool_config.extract_archive
        if extract_archive is None:
            extract_archive = auto_detect_extract_archive(str(task.temp_path))
            log(
                f"Auto-detected [b]extract_archive[/] for [b]{task.tool_name}[/]: {extract_archive}",
                "info",
                "🔍",
            )

        if extract_archive:
            _extract_binary_from_archive(
                task.temp_path,
                task.destination_dir,
                task.bin_spec,
                verbose,
            )
        else:
            binary_names = task.tool_config.binary_name
            if len(binary_names) != 1:
                log(
                    f"Expected exactly one binary name for {task.tool_name}, got {len(binary_names)}",
                    "error",
                )
                summary.add_failed_tool(
                    task.tool_name,
                    task.platform,
                    task.arch,
                    task.version,
                    reason="Expected exactly one binary name",
                )
                return False
            binary_name = binary_names[0]
            _copy_binary_to_destination(task.temp_path, task.destination_dir, binary_name)
    except Exception as e:
        # Differentiate error types for better reporting
        error_prefix = "Error processing"
        if isinstance(e, AutoDetectBinaryPathsError):
            error_prefix = "Auto-detect binary paths error"
        elif isinstance(e, FileNotFoundError):
            error_prefix = "Binary not found"
        log(f"Error processing {task.tool_name}: {e!s}", "error", print_exception=verbose)
        summary.add_failed_tool(
            task.tool_name,
            task.platform,
            task.arch,
            task.version,
            reason=f"{error_prefix}: {e!s}",
        )
        return False
    else:
        summary.add_updated_tool(
            task.tool_name,
            task.platform,
            task.arch,
            task.version,
            old_version=version_store.get_tool_version(task.tool_name, task.platform, task.arch)
            or "—",
        )
        version_store.update_tool_info(
            task.tool_name,
            task.platform,
            task.arch,
            task.version,
            sha256=sha256_hash,
        )

        log(
            f"Successfully installed [b]{task.tool_name} v{task.version}[/] for [b]{task.platform}/{task.arch}[/]",
            "success",
        )
        return True
    finally:
        if task.temp_path.exists():
            task.temp_path.unlink()


def process_downloaded_files(
    download_tasks: list[_DownloadTask],
    download_successes: list[bool],
    version_store: VersionStore,
    summary: UpdateSummary,
    verbose: bool,
) -> None:
    """Process downloaded files."""
    if not download_successes:
        return
    log(f"Processing {len(download_successes)} downloaded tools...", "info", "🔄")
    for task, download_success in zip(download_tasks, download_successes):
        _process_downloaded_task(task, download_success, version_store, summary, verbose)


def _determine_architectures(
    platform: str,
    architecture: str | None,
    config: Config,
) -> list[str]:
    """Determine which architectures to update for a platform."""
    if architecture is not None:
        # Filter to only include the specified architecture if it's supported
        if architecture in config.platforms[platform]:
            return [architecture]
        log(
            f"Architecture {architecture} not configured for platform {platform}, skipping",
            "warning",
        )
        return []
    return config.platforms[platform]
