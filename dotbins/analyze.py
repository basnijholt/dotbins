"""Analysis tools for discovering and configuring new tools."""

from __future__ import annotations

import os
import os.path
import re
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from rich.console import Console

from .download import download_file, extract_archive
from .utils import get_latest_release

if TYPE_CHECKING:
    from pathlib import Path

# Initialize rich console
console = Console()


def generate_tool_configuration(
    repo: str,
    tool_name: str | None = None,
    release: dict | None = None,
) -> dict:
    """Analyze GitHub releases and generate tool configuration.

    Parameters
    ----------
    repo : str
        GitHub repository in the format 'owner/repo'
    tool_name : str, optional
        Name to use for the tool. If None, uses repo name
    release : dict, optional
        Pre-fetched release data. If None, it will be fetched from GitHub

    Returns
    -------
    dict
        Tool configuration dictionary

    """
    if not repo or "/" not in repo:
        msg = "Please provide a valid GitHub repository in the format 'owner/repo'"
        raise ValueError(msg)

    # Extract tool name from repo if not provided
    if not tool_name:
        tool_name = repo.split("/")[-1]

    # Get latest release info if not provided
    if release is None:
        release = get_latest_release(repo)

    # Find sample asset and determine binary path
    sample_asset = find_sample_asset(release["assets"])
    binary_path = None

    if sample_asset:
        binary_path = download_and_find_binary(sample_asset, tool_name)

    # Generate and return tool configuration
    return generate_tool_config(repo, tool_name, release, binary_path)


def analyze_tool(args: Any) -> None:
    """Analyze GitHub releases for a tool to help determine patterns."""
    repo = args.repo

    try:
        console.print(f"🔍 [blue]Analyzing releases for {repo}...[/blue]")
        release = get_latest_release(repo)

        console.print(
            f"\n🏷️ [green]Latest release: {release['tag_name']} ({release['name']})[/green]",
        )
        print_assets_info(release["assets"])

        # Extract tool name from repo or use provided name
        tool_name = args.name or repo.split("/")[-1]

        # Generate tool configuration
        tool_config = generate_tool_configuration(repo, tool_name, release)

        # Output YAML
        console.print("\n📋 [blue]Suggested configuration for YAML tools file:[/blue]")
        yaml_config = {tool_name: tool_config}
        print(yaml.dump(yaml_config, sort_keys=False, default_flow_style=False))

    except Exception as e:  # noqa: BLE001
        console.print("❌ [bold red]Error analyzing repo[/bold red]")
        console.print_exception()
        console.print(f"❌ [bold red]Error: {e!s}[/bold red]")
        import sys

        sys.exit(1)


def print_assets_info(assets: list[dict]) -> None:
    """Print detailed information about available assets."""
    console.print("\n📦 [blue]Available assets:[/blue]")
    for asset in assets:
        console.print(f"  - {asset['name']} ({asset['browser_download_url']})")

    # Platform categorization
    linux_assets = get_platform_assets(assets, "linux")
    console.print("\n🐧 [blue]Linux assets:[/blue]")
    for asset in linux_assets:
        console.print(f"  - {asset['name']}")

    macos_assets = get_platform_assets(assets, "macos")
    console.print("\n🍏 [blue]macOS assets:[/blue]")
    for asset in macos_assets:
        console.print(f"  - {asset['name']}")

    # Architecture categorization
    amd64_assets = get_arch_assets(assets, "amd64")
    console.print("\n💻 [blue]AMD64/x86_64 assets:[/blue]")
    for asset in amd64_assets:
        console.print(f"  - {asset['name']}")

    arm64_assets = get_arch_assets(assets, "arm64")
    console.print("\n📱 [blue]ARM64/aarch64 assets:[/blue]")
    for asset in arm64_assets:
        console.print(f"  - {asset['name']}")


def get_platform_assets(assets: list[dict], platform: str) -> list[dict]:
    """Filter assets by platform."""
    platform_keywords = {"linux": ["linux"], "macos": ["darwin", "macos"]}

    keywords = platform_keywords.get(platform, [])
    if not keywords:
        return []

    return [a for a in assets if any(kw in a["name"].lower() for kw in keywords)]


def get_arch_assets(assets: list[dict], arch: str) -> list[dict]:
    """Filter assets by architecture."""
    arch_keywords = {"amd64": ["amd64", "x86_64"], "arm64": ["arm64", "aarch64"]}

    keywords = arch_keywords.get(arch, [])
    if not keywords:
        return []

    return [a for a in assets if any(kw in a["name"].lower() for kw in keywords)]


def find_sample_asset(assets: list[dict]) -> dict | None:
    """Find a suitable sample asset for analysis."""
    # Priority: Linux x86_64 compressed files, then macOS x86_64 compressed files
    compressed_extensions = (".tar.gz", ".tgz", ".zip")

    # Try Linux x86_64 first
    linux_assets = get_platform_assets(assets, "linux")
    for asset in linux_assets:
        if "x86_64" in asset["name"] and any(
            asset["name"].endswith(ext) for ext in compressed_extensions
        ):
            return asset

    # Then try macOS
    macos_assets = get_platform_assets(assets, "macos")
    for asset in macos_assets:
        if "x86_64" in asset["name"] and any(
            asset["name"].endswith(ext) for ext in compressed_extensions
        ):
            return asset

    return None


def download_and_find_binary(asset: dict, tool_name: str) -> str | list[str] | None:
    """Download sample asset and find binary path."""
    console.print(
        f"\n📥 [blue]Downloading sample archive: {asset['name']} to inspect contents...[/blue]",
    )

    temp_path = None
    temp_dir = None

    try:
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=os.path.splitext(asset["name"])[1],
        ) as temp_file:
            temp_path = temp_file.name

        download_file(asset["browser_download_url"], temp_path)
        temp_dir = tempfile.mkdtemp()

        # Extract the archive
        extract_archive(temp_path, temp_dir)

        # Find executables
        executables = find_executables(temp_dir)

        console.print("\n🔍 [blue]Executable files found in the archive:[/blue]")
        for exe in executables:
            console.print(f"  - {exe}")

        # Determine binary path
        binary_path = determine_binary_path(executables, tool_name)

        if binary_path:
            console.print(f"\n✅ [green]Detected binary path: {binary_path}[/green]")

        return binary_path

    finally:
        # Clean up
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


def find_executables(directory: str | Path) -> list[str]:
    """Find executable files in a directory structure."""
    executables = []
    for root, _, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            if os.access(file_path, os.X_OK):
                rel_path = os.path.relpath(file_path, directory)
                executables.append(rel_path)
    return executables


def determine_binary_path(
    executables: list[str],
    tool_name: str,
) -> str | list[str] | None:
    """Determine the most likely binary paths based on executables."""
    if not executables:
        return None

    # Find all executables that match the tool name pattern
    matches = []
    for exe in executables:
        base_name = os.path.basename(exe)
        if tool_name.lower() in base_name.lower():
            matches.append(exe)

    # If we found multiple matches that seem related, return a list
    if len(matches) > 1:
        return matches

    # Otherwise, follow the old logic for single binary
    # Try to find an exact name match first
    for exe in executables:
        base_name = os.path.basename(exe)
        if base_name.lower() == tool_name.lower():
            return exe

    # Then try to find executables in bin/
    for exe in executables:
        if "bin/" in exe:
            return exe

    # Finally, just take the first executable
    return executables[0]


def generate_tool_config(
    repo: str,
    tool_name: str,
    release: dict,
    binary_path: str | list[str] | None,
) -> dict:
    """Generate tool configuration based on release information."""
    assets = release["assets"]
    linux_assets = get_platform_assets(assets, "linux")
    macos_assets = get_platform_assets(assets, "macos")

    # Determine if we need architecture conversion
    arch_conversion = any("x86_64" in a["name"] for a in assets) or any(
        "aarch64" in a["name"] for a in assets
    )

    # Create tool configuration
    tool_config = {
        "repo": repo,
        "extract_binary": True,
        "binary_name": tool_name,
    }

    # Add binary path if found
    if binary_path:
        version = release["tag_name"].lstrip("v")

        # Handle both string and list paths
        if isinstance(binary_path, list):
            # For lists, replace version in each path
            binary_paths = []
            for path in binary_path:
                if version in path:
                    path = path.replace(version, "{version}")  # noqa: PLW2901
                binary_paths.append(path)
            tool_config["binary_path"] = binary_paths

            # Also make binary_name a list if it's not already
            if not isinstance(tool_config["binary_name"], list):
                # Create a list of binary names based on the basename of each path
                binary_names = [os.path.basename(path) for path in binary_path]
                tool_config["binary_name"] = binary_names
        else:
            # For single string path
            if version in binary_path:
                binary_path = binary_path.replace(version, "{version}")
            tool_config["binary_path"] = binary_path

    # Add arch_map if needed
    if arch_conversion:
        tool_config["arch_map"] = {"amd64": "x86_64", "arm64": "aarch64"}

    # Generate asset patterns
    platform_specific = bool(linux_assets and macos_assets)
    if platform_specific:
        asset_patterns = generate_platform_specific_patterns(release)
        tool_config["asset_patterns"] = asset_patterns
    else:
        # Single pattern for all platforms
        pattern = generate_single_pattern(release)
        if pattern != "?":
            # Use asset_patterns as a string instead of asset_pattern
            tool_config["asset_patterns"] = pattern

    return tool_config


def generate_platform_specific_patterns(release: dict) -> dict:
    """Generate platform-specific asset patterns."""
    assets = release["assets"]
    linux_assets = get_platform_assets(assets, "linux")
    macos_assets = get_platform_assets(assets, "macos")
    amd64_assets = get_arch_assets(assets, "amd64")

    patterns = {"linux": "?", "macos": "?"}
    version = release["tag_name"].lstrip("v")

    # Find pattern for Linux
    if linux_assets and amd64_assets:
        for asset in linux_assets:
            if "x86_64" in asset["name"] or "amd64" in asset["name"]:
                pattern = asset["name"]
                # Replace architecture and version placeholders
                if "x86_64" in pattern:
                    pattern = pattern.replace("x86_64", "{arch}")
                elif "amd64" in pattern:
                    pattern = pattern.replace("amd64", "{arch}")

                if version in pattern:
                    pattern = pattern.replace(version, "{version}")
                patterns["linux"] = pattern
                break

    # Find pattern for macOS
    if macos_assets and amd64_assets:
        for asset in macos_assets:
            if "x86_64" in asset["name"] or "amd64" in asset["name"]:
                pattern = asset["name"]
                # Replace architecture and version placeholders
                if "x86_64" in pattern:
                    pattern = pattern.replace("x86_64", "{arch}")
                elif "amd64" in pattern:
                    pattern = pattern.replace("amd64", "{arch}")

                if version in pattern:
                    pattern = pattern.replace(version, "{version}")
                patterns["macos"] = pattern
                break

    return patterns


def generate_single_pattern(release: dict) -> str:
    """Generate a single asset pattern for all platforms."""
    if not release["assets"]:
        return "?"

    asset_name = release["assets"][0]["name"]
    pattern = asset_name
    version = release["tag_name"].lstrip("v")

    # Replace version if present
    if version in pattern:
        pattern = pattern.replace(version, "{version}")

    # Replace platform if present
    if "darwin" in pattern.lower():
        pattern = re.sub(r"(?i)darwin", "{platform}", pattern)
    elif "linux" in pattern.lower():
        pattern = re.sub(r"(?i)linux", "{platform}", pattern)

    # Replace architecture if present
    if "x86_64" in pattern:
        pattern = pattern.replace("x86_64", "{arch}")
    elif "amd64" in pattern:
        pattern = pattern.replace("amd64", "{arch}")

    return pattern
