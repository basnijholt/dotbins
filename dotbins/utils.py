"""Utility functions for dotbins."""

from __future__ import annotations

import logging
import os
import sys

import requests
from rich.console import Console

# Initialize rich console
console = Console()
logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:  # noqa: FBT001, FBT002
    """Configure logging level based on verbosity."""
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def get_latest_release(repo: str) -> dict:
    """Get the latest release information from GitHub."""
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    console.print(f"🔍 [blue]Fetching latest release from {url}[/blue]")

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        console.print("Failed to fetch latest release.")
        console.print_exception()
        msg = f"Failed to fetch latest release for {repo}: {e}"
        raise RuntimeError(msg) from e


def current_platform() -> tuple[str, str]:
    """Detect the current platform and architecture.

    Returns:
        Tuple containing (platform, architecture)
        platform: 'linux' or 'macos'
        architecture: 'amd64' or 'arm64'

    """
    # Detect platform
    platform = "linux"
    if sys.platform == "darwin":
        platform = "macos"

    # Detect architecture
    arch = "amd64"
    machine = os.uname().machine.lower()
    if machine in ["arm64", "aarch64"]:
        arch = "arm64"

    return platform, arch


def get_platform_map(platform: str, platform_map: str) -> str:
    """Map dotbins platform names to tool-specific platform names.

    Args:
        platform: Platform name used by dotbins (e.g., 'macos')
        platform_map: Mapping string in format 'src:dst,src:dst' (e.g., 'macos:darwin')

    Returns:
        Mapped platform name

    """
    if not platform_map:
        return platform

    for mapping in platform_map.split(","):
        parts = mapping.strip().split(":")
        if len(parts) == 2 and parts[0] == platform:  # noqa: PLR2004
            return parts[1]

    return platform


def print_shell_setup() -> None:
    """Print shell setup instructions."""
    print("\n# Add this to your shell configuration file (e.g., .bashrc, .zshrc):")
    print(
        """
# dotbins - Add platform-specific binaries to PATH
_os=$(uname -s | tr '[:upper:]' '[:lower:]')
[[ "$_os" == "darwin" ]] && _os="macos"

_arch=$(uname -m)
[[ "$_arch" == "x86_64" ]] && _arch="amd64"
[[ "$_arch" == "aarch64" || "$_arch" == "arm64" ]] && _arch="arm64"

export PATH="$HOME/.dotfiles/tools/$_os/$_arch/bin:$PATH"
""",
    )
