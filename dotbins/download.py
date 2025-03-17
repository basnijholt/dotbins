"""Download and extraction functions for dotbins."""

from __future__ import annotations

import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

from .detect_binary import auto_detect_binary_paths
from .utils import calculate_sha256, download_file, extract_archive, log

if TYPE_CHECKING:
    from .config import BinSpec, Config, ToolConfig
    from .versions import VersionStore


def _extract_from_archive(
    archive_path: Path,
    destination_dir: Path,
    bin_spec: BinSpec,
) -> None:
    """Extract binaries from an archive."""
    log(f"Extracting from {archive_path} for {bin_spec.platform}", "info", "📦")
    temp_dir = Path(tempfile.mkdtemp())

    try:
        extract_archive(archive_path, temp_dir)
        log(f"Archive extracted to {temp_dir}", "success", "📦")
        _log_extracted_files(temp_dir)
        binary_paths = _detect_binary_paths(temp_dir, bin_spec.tool_config)
        _process_binaries(temp_dir, destination_dir, binary_paths, bin_spec)

    except Exception as e:
        log(f"Error extracting archive: {e}", "error", print_exception=True)
        raise
    finally:
        shutil.rmtree(temp_dir)


def _detect_binary_paths(temp_dir: Path, tool_config: ToolConfig) -> list[str]:
    """Auto-detect binary paths if not specified in configuration."""
    if tool_config.binary_path:
        return tool_config.binary_path
    log("Binary path not specified, attempting auto-detection...", "info", "🔍")
    binary_names = tool_config.binary_name
    binary_paths = auto_detect_binary_paths(temp_dir, binary_names)
    if not binary_paths:
        msg = f"Could not auto-detect binary paths for {', '.join(binary_names)}. Please specify binary_path in config."
        raise ValueError(msg)
    log(f"Auto-detected binary paths: {binary_paths}", "success")
    return binary_paths


def _process_binaries(
    temp_dir: Path,
    destination_dir: Path,
    binary_paths: list[str],
    bin_spec: BinSpec,
) -> None:
    """Process each binary by finding it and copying to destination."""
    for binary_path_pattern, binary_name in zip(binary_paths, bin_spec.tool_config.binary_name):
        source_path = _find_binary_in_extracted_files(
            temp_dir,
            binary_path_pattern,
            bin_spec.version,
            bin_spec.tool_arch,
            bin_spec.tool_platform,
        )
        _copy_binary_to_destination(source_path, destination_dir, binary_name)


def _log_extracted_files(temp_dir: Path) -> None:
    """Log the extracted files for debugging."""
    try:
        log("Extracted files:", "info", "ℹ️")  # noqa: RUF001
        for item in temp_dir.glob("**/*"):
            log(f"  - {item.relative_to(temp_dir)}", "info", "")
    except Exception:
        log("Could not list extracted files: {e}")


def _find_binary_in_extracted_files(
    temp_dir: Path,
    binary_path: str,
    version: str,
    tool_arch: str,
    tool_platform: str,
) -> Path:
    """Find a specific binary in the extracted files."""
    binary_path = _replace_variables_in_path(binary_path, version, tool_arch, tool_platform)

    if "*" in binary_path:
        matches = list(temp_dir.glob(binary_path))
        if not matches:
            msg = f"No files matching {binary_path} in archive"
            raise FileNotFoundError(msg)
        return matches[0]

    source_path = temp_dir / binary_path
    if not source_path.exists():
        msg = f"Binary ({binary_path}) not found at {source_path}"
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
    shutil.copy2(source_path, dest_path)
    dest_path.chmod(dest_path.stat().st_mode | 0o755)
    log(f"Copied binary to {dest_path}", "success")


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
) -> _DownloadTask | None:
    """Prepare a download task, checking if update is needed based on version."""
    try:
        tool_config = config.tools[tool_name]
        bin_spec = tool_config.bin_spec(arch, platform)
        if bin_spec.skip_download(config, force):
            return None
        asset = bin_spec.matching_asset()
        if asset is None:
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
            print_exception=True,
        )
        return None


def prepare_download_tasks(
    config: Config,
    tools_to_update: list[str] | None = None,
    platforms_to_update: list[str] | None = None,
    architecture: str | None = None,
    force: bool = False,
) -> tuple[list[_DownloadTask], int]:
    """Prepare download tasks for all tools and platforms."""
    download_tasks = []
    total_count = 0
    if tools_to_update is None:
        tools_to_update = list(config.tools)
    if platforms_to_update is None:
        platforms_to_update = list(config.platforms)

    for tool_name in tools_to_update:
        for platform in platforms_to_update:
            if platform not in config.platforms:
                log(f"Skipping unknown platform: {platform}", "warning")
                continue

            archs_to_update = _determine_architectures(platform, architecture, config)
            if not archs_to_update:
                continue

            for arch in archs_to_update:
                total_count += 1
                task = _prepare_download_task(tool_name, platform, arch, config, force)
                if task:
                    download_tasks.append(task)

    return sorted(download_tasks, key=lambda t: t.asset_url), total_count


def _download_task(task: _DownloadTask) -> tuple[_DownloadTask, bool]:
    """Download a file for a DownloadTask."""
    try:
        log(
            f"Downloading {task.asset_name} for {task.tool_name} ({task.platform}/{task.arch})...",
            "info",
            "📥",
        )
        download_file(task.asset_url, str(task.temp_path))
        return task, True
    except Exception as e:
        log(f"Error downloading {task.asset_name}: {e!s}", "error", print_exception=True)
        return task, False


def download_files_in_parallel(
    download_tasks: list[_DownloadTask],
) -> list[tuple[_DownloadTask, bool]]:
    """Download files in parallel using ThreadPoolExecutor."""
    log(f"\nDownloading {len(download_tasks)} tools in parallel...", "info", "🔄")
    downloaded_tasks = []
    with ThreadPoolExecutor(max_workers=min(8, len(download_tasks) or 1)) as ex:
        future_to_task = {ex.submit(_download_task, task): task for task in download_tasks}
        for future in as_completed(future_to_task):
            task, success = future.result()
            downloaded_tasks.append((task, success))
    return downloaded_tasks


def _process_downloaded_task(
    task: _DownloadTask,
    success: bool,
    version_store: VersionStore,
) -> bool:
    """Process a downloaded file."""
    if not success:
        return False
    try:
        # Calculate SHA256 hash before extraction
        sha256_hash = calculate_sha256(task.temp_path)
        log(f"SHA256: {sha256_hash}", "info", "🔐")

        task.destination_dir.mkdir(parents=True, exist_ok=True)
        if task.tool_config.extract_binary:
            _extract_from_archive(task.temp_path, task.destination_dir, task.bin_spec)
        else:
            binary_names = task.tool_config.binary_name
            if len(binary_names) != 1:
                log(
                    f"Expected exactly one binary name for {task.tool_name}, got {len(binary_names)}",
                    "error",
                )
                return False
            binary_name = binary_names[0]

            shutil.copy2(task.temp_path, task.destination_dir / binary_name)
            dest_file = task.destination_dir / binary_name
            dest_file.chmod(dest_file.stat().st_mode | 0o755)

        version_store.update_tool_info(
            task.tool_name,
            task.platform,
            task.arch,
            task.version,
            sha256=sha256_hash,
        )

        log(
            f"Successfully processed {task.tool_name} v{task.version} for {task.platform}/{task.arch}",
            "success",
        )
        return True
    except Exception as e:
        log(f"Error processing {task.tool_name}: {e!s}", "error", print_exception=True)
        return False
    finally:
        if task.temp_path.exists():
            task.temp_path.unlink()


def process_downloaded_files(
    downloaded_tasks: list[tuple[_DownloadTask, bool]],
    version_store: VersionStore,
) -> int:
    """Process downloaded files and return success count."""
    log(f"\nProcessing {len(downloaded_tasks)} downloaded tools...", "info", "🔄")
    success_count = 0
    for task, download_success in downloaded_tasks:
        if _process_downloaded_task(task, download_success, version_store):
            success_count += 1
    return success_count


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
