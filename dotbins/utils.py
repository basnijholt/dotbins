"""Utility functions for dotbins."""

from __future__ import annotations

import bz2
import functools
import gzip
import hashlib
import lzma
import os
import shutil
import sys
import tarfile
import textwrap
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Literal, TypeVar

import requests
from rich.console import Console

console = Console()

if TYPE_CHECKING:
    from .config import ToolConfig


def _maybe_github_token_header(github_token: str | None) -> dict[str, str]:  # pragma: no cover
    return {} if github_token is None else {"Authorization": f"token {github_token}"}


@functools.cache
def latest_release_info(repo: str, github_token: str | None) -> dict | None:
    """Fetch release information from GitHub for a single repository."""
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    log(f"Fetching latest release from {url}", "info", "🔍")
    headers = _maybe_github_token_header(github_token)
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        msg = f"Failed to fetch latest release for {repo}: {e}"
        raise RuntimeError(msg) from e


def download_file(url: str, destination: str, github_token: str | None, verbose: bool) -> str:
    """Download a file from a URL to a destination path."""
    log(f"Downloading from [b]{url}[/]", "info", "📥")
    # Already verbose when fetching release info
    headers = _maybe_github_token_header(github_token)
    try:
        response = requests.get(url, stream=True, timeout=30, headers=headers)
        response.raise_for_status()
        with open(destination, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return destination
    except requests.RequestException as e:
        log(f"Download failed: {e}", "error", print_exception=verbose)
        msg = f"Failed to download {url}: {e}"
        raise RuntimeError(msg) from e


def current_platform() -> tuple[str, str]:
    """Detect the current platform and architecture.

    Returns:
        Tuple containing (platform, architecture)
        platform: 'linux' or 'macos'
        architecture: 'amd64' or 'arm64'

    """
    # Detect platform
    platform = sys.platform
    platform = {
        "darwin": "macos",
    }.get(platform, platform)

    # Detect architecture
    machine = os.uname().machine.lower()
    arch = {
        "aarch64": "arm64",
        "x86_64": "amd64",
    }.get(machine, machine)

    return platform, arch


def replace_home_in_path(path: Path, home: str = "$HOME") -> str:
    """Replace ~ with $HOME in a path."""
    return str(path.absolute()).replace(os.path.expanduser("~"), home)


def _format_shell_instructions(
    tools_dir: Path,
    shell: Literal["bash", "zsh", "fish", "nushell"],
    tools: dict[str, ToolConfig],
) -> str:
    """Format shell instructions for a given shell."""
    tools_dir_str = replace_home_in_path(tools_dir)

    # Base script that sets up PATH
    if shell in {"bash", "zsh"}:
        base_script = textwrap.dedent(
            f"""\
            # dotbins - Add platform-specific binaries to PATH
            _os=$(uname -s | tr '[:upper:]' '[:lower:]')
            [[ "$_os" == "darwin" ]] && _os="macos"

            _arch=$(uname -m)
            [[ "$_arch" == "x86_64" ]] && _arch="amd64"
            [[ "$_arch" == "aarch64" || "$_arch" == "arm64" ]] && _arch="arm64"

            export PATH="{tools_dir_str}/$_os/$_arch/bin:$PATH"
            """,
        )
        before = ["if command -v {name} >/dev/null 2>&1; then"]
        after = ["fi"]
        base_script += _add_shell_code_to_script(tools, before, after)

        return base_script

    if shell == "fish":
        base_script = textwrap.dedent(
            f"""\
            # dotbins - Add platform-specific binaries to PATH
            set -l _os (uname -s | tr '[:upper:]' '[:lower:]')
            test "$_os" = "darwin"; and set _os "macos"

            set -l _arch (uname -m)
            test "$_arch" = "x86_64"; and set _arch "amd64"
            test "$_arch" = "aarch64" -o "$_arch" = "arm64"; and set _arch "arm64"

            fish_add_path {tools_dir_str}/$_os/$_arch/bin
            """,
        )

        before = [
            "# Configuration for {name}",
            "if command -v {name} >/dev/null 2>&1",
        ]
        after = ["end"]
        base_script += _add_shell_code_to_script(tools, before, after)
        return base_script

    if shell == "nushell":
        script_lines = [
            "# dotbins - Add platform-specific binaries to PATH",
            "let _os = (sys).host.name | str downcase",
            'let _os = if $_os == "darwin" { "macos" } else { $_os }',
            "",
            "let _arch = (sys).host.arch",
            'let _arch = if $_arch == "x86_64" { "amd64" } else if $_arch in ["aarch64", "arm64"] { "arm64" } else { $_arch }',
            "",
            f'$env.PATH = ($env.PATH | prepend $"{tools_dir}/$_os/$_arch/bin")',
        ]
        base_script = "\n".join(script_lines)
        before = ["if (which {name}) != null {{"]
        after = ["}"]
        base_script += _add_shell_code_to_script(tools, before, after)
        return base_script
    msg = f"Unsupported shell: {shell}"  # pragma: no cover
    raise ValueError(msg)  # pragma: no cover


def _add_shell_code_to_script(
    tools: dict[str, ToolConfig],
    before: list[str],
    after: list[str],
) -> str:
    if tools:
        lines = []
        for name, config in tools.items():
            if config.shell_code:
                config_lines = [
                    "# Configuration for {name}",
                    *(line.format(name=name) for line in before),
                    *[f"    {line}" for line in config.shell_code.strip().split("\n")],
                    *after,
                    "",
                ]
                lines.extend(config_lines)
        if lines:
            return "\n# Tool-specific configurations\n" + "\n".join(lines)
    return ""


def write_shell_scripts(
    tools_dir: Path,
    tools: dict[str, ToolConfig],
    print_shell_setup: bool = False,
) -> None:
    """Generate shell script files for different shells.

    Creates a 'shell' directory in the tools_dir and writes script files
    for bash, zsh, fish, and nushell that users can source in their shell
    configuration files.

    Args:
        tools_dir: The base directory where tools are installed
        print_shell_setup: Whether to print the shell setup instructions
        tools: Dictionary of tool configurations with shell_code to include

    """
    # Create shell directory
    shell_dir = tools_dir / "shell"
    shell_dir.mkdir(parents=True, exist_ok=True)

    # Generate scripts for each supported shell
    shell_files = {
        "bash": "bash.sh",
        "zsh": "zsh.sh",
        "fish": "fish.fish",
        "nushell": "nushell.nu",
    }

    for shell, filename in shell_files.items():
        script_content = _format_shell_instructions(tools_dir, shell, tools)  # type: ignore[arg-type]

        if shell in ["bash", "zsh"]:
            script_content = f"#!/usr/bin/env {shell}\n{script_content}"

        script_path = shell_dir / filename
        with open(script_path, "w") as f:
            f.write(script_content + "\n")

        script_path.chmod(script_path.stat().st_mode | 0o755)

    tools_dir1 = replace_home_in_path(tools_dir, "~")
    log(f"Generated shell scripts in {tools_dir1}/shell/", "success", "📝")
    if print_shell_setup:
        tools_dir2 = replace_home_in_path(tools_dir, "$HOME")
        log("Add this to your shell config:", "info")
        log(f"  Bash:    source {tools_dir2}/shell/bash.sh", "info", "👉")
        log(f"  Zsh:     source {tools_dir2}/shell/zsh.sh", "info", "👉")
        log(f"  Fish:    source {tools_dir2}/shell/fish.fish", "info", "👉")
        log(f"  Nushell: source {tools_dir2}/shell/nushell.nu", "info", "👉")


STYLE_EMOJI_MAP = {
    "success": "✅",
    "error": "❌",
    "warning": "⚠️",
    "info": "🔍",
    "default": "",
}

STYLE_FORMAT_MAP = {
    "success": "green",
    "error": "bold red",
    "warning": "yellow",
    "info": "cyan",
    "default": "",
}


def log(
    message: str,
    style: str = "default",
    emoji: str = "",
    *,
    print_exception: bool = False,
) -> None:
    """Print a formatted message to the console."""
    if not emoji:
        emoji = STYLE_EMOJI_MAP.get(style, "")

    prefix = f"{emoji} " if emoji else ""

    if style != "default":
        rich_format = STYLE_FORMAT_MAP.get(style, "")
        console.print(f"{prefix}[{rich_format}]{message}[/{rich_format}]")
    else:
        console.print(f"{prefix}{message}")
    if style == "error" and print_exception:
        console.print_exception()


def calculate_sha256(file_path: str | Path) -> str:
    """Calculate SHA256 hash of a file.

    Args:
        file_path: Path to the file

    Returns:
        Hexadecimal SHA256 hash string

    """
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        # Read the file in chunks to handle large files efficiently
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def extract_archive(archive_path: str | Path, dest_dir: str | Path) -> None:
    """Extract an archive to a destination directory.

    Supports zip, tar, tar.gz, tar.bz2, tar.xz, gz, bz2, and xz formats.
    """
    archive_path = Path(archive_path)
    dest_dir = Path(dest_dir)

    try:
        filename = archive_path.name.lower()

        # Handle zip files
        if filename.endswith(".zip"):
            with zipfile.ZipFile(archive_path) as zip_file:
                zip_file.extractall(path=dest_dir)
            return

        # Define mappings for tar-based archives
        tar_formats = {
            ".tar": "r",
            ".tar.gz": "r:gz",
            ".tgz": "r:gz",
            ".tar.bz2": "r:bz2",
            ".tbz2": "r:bz2",
            ".tar.xz": "r:xz",
            ".txz": "r:xz",
        }

        # Handle tar archives
        for ext, mode in tar_formats.items():
            if filename.endswith(ext):
                with tarfile.open(archive_path, mode=mode) as tar:
                    tar.extractall(path=dest_dir)
                return

        # Get file magic header for compression detection
        with open(archive_path, "rb") as f:
            header = f.read(6)

        # Helper function for single-file decompression
        def extract_compressed(open_func: Callable[[Path, str], Any]) -> None:
            output_path = dest_dir / archive_path.stem
            with (
                open_func(archive_path, "rb") as f_in,
                open(output_path, "wb") as f_out,
            ):
                shutil.copyfileobj(f_in, f_out)
            output_path.chmod(output_path.stat().st_mode | 0o755)

        # Try each compression format based on extension or file header
        if filename.endswith(".gz") or header.startswith(b"\x1f\x8b"):
            extract_compressed(gzip.open)
            return

        if filename.endswith(".bz2") or header.startswith(b"BZh"):
            extract_compressed(bz2.open)
            return

        if filename.endswith((".xz", ".lzma")) or header.startswith(b"\xfd\x37\x7a\x58\x5a\x00"):
            extract_compressed(lzma.open)
            return

        # Unsupported format
        msg = f"Unsupported archive format: {archive_path}"
        raise ValueError(msg)  # noqa: TRY301

    except Exception as e:
        log(f"Extraction failed: {e}", "error", print_exception=True)
        raise


def github_url_to_raw_url(repo_url: str) -> str:
    """Convert a GitHub repository URL to a raw URL."""
    # e.g.,
    # https://github.com/basnijholt/dotbins/blob/main/dotbins.yaml
    # becomes
    # https://raw.githubusercontent.com/basnijholt/dotbins/refs/heads/main/dotbins.yaml
    if "github.com" not in repo_url or "/blob/" not in repo_url:
        return repo_url
    return repo_url.replace(
        "github.com",
        "raw.githubusercontent.com",
    ).replace(
        "/blob/",
        "/refs/heads/",
    )


T = TypeVar("T")
R = TypeVar("R")


def execute_in_parallel(
    items: list[T],
    process_func: Callable[[T], R],
    max_workers: int = 16,
) -> list[R]:
    """Execute a function over a list of items in parallel.

    Args:
        items: List of items to process
        process_func: Function to apply to each item
        max_workers: Maximum number of parallel workers

    Returns:
        List of results from process_func applied to each item

    """
    with ThreadPoolExecutor(max_workers=min(max_workers, len(items) or 1)) as ex:
        futures = ex.map(process_func, items)
        return list(futures)


def humanize_time_ago(date_str: str) -> str:
    """Humanize a time ago string showing two largest time components."""
    # Note: Function doesn't properly handle future dates.
    date = datetime.fromisoformat(date_str)
    now = datetime.now()
    diff = now - date

    days = diff.days
    hours = diff.seconds // 3600
    minutes = (diff.seconds % 3600) // 60
    seconds = diff.seconds % 60

    if days > 0:
        return f"{days}d{hours}h" if hours > 0 else f"{days}d"
    if hours > 0:
        return f"{hours}h{minutes}m" if minutes > 0 else f"{hours}h"
    if minutes > 0:
        return f"{minutes}m{seconds}s" if seconds > 0 else f"{minutes}m"
    if seconds > 0:
        return f"{seconds}s"
    return "0s"
