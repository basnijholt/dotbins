"""Analysis tools for discovering and configuring new tools."""

from __future__ import annotations

import os
import os.path
import re
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from .config import RawToolConfigDict, ToolConfig, build_tool_config
from .download import download_file, extract_archive
from .utils import latest_release_info, log

if TYPE_CHECKING:
    from pathlib import Path


def generate_tool_configuration(
    repo: str,
    tool_name: str | None = None,
    release: dict | None = None,
) -> ToolConfig:
    """Analyze GitHub releases and generate tool configuration.

    Args:
        repo: GitHub repository in the format 'owner/repo'
        tool_name: Name to use for the tool. If None, uses repo name
        release: Pre-fetched release data. If None, it will be fetched from GitHub

    Returns:
        Tool configuration object

    """
    if not repo or "/" not in repo:
        msg = "Please provide a valid GitHub repository in the format 'owner/repo'"
        raise ValueError(msg)

    # Extract tool name from repo if not provided
    if not tool_name:
        tool_name = repo.split("/")[-1]

    # Get latest release info if not provided
    if release is None:
        release = latest_release_info(repo)

    # Find sample asset and determine binary path
    sample_asset = _find_sample_asset(release["assets"])
    binary_path = None

    if sample_asset:
        binary_path = _download_and_find_binary(sample_asset, tool_name)

    # Generate and return tool configuration
    return generate_tool_config(repo, tool_name, release, binary_path)


def analyze_tool(repo: str, name: str | None = None) -> None:
    """Analyze GitHub releases for a tool to help determine patterns."""
    try:
        log(f"Analyzing releases for {repo}...", "info", "🔍")
        release = latest_release_info(repo)

        log(
            f"Latest release: {release['tag_name']} ({release['name']})",
            "success",
            "🏷️",
        )
        _print_assets_info(release["assets"])

        # Extract tool name from repo or use provided name
        tool_name = name or repo.split("/")[-1]

        # Generate tool configuration
        tool_config = generate_tool_configuration(repo, tool_name, release)

        # Output YAML
        log("Suggested configuration for YAML tools file:", "info", "📋")
        # Convert ToolConfig to dict for YAML serialization
        tool_config_dict = {
            k: v for k, v in tool_config.__dict__.items() if v is not None and k != "tool_name"
        }
        yaml_config = {tool_name: tool_config_dict}
        print(yaml.dump(yaml_config, sort_keys=False, default_flow_style=False))
        log("Please review and adjust the configuration as needed!", "warning", "# ⚠️")
    except Exception:
        log("Error analyzing repo", "error", print_exception=True)
        import sys

        sys.exit(1)


def _print_assets_info(assets: list[dict]) -> None:
    """Print detailed information about available assets."""
    log("Available assets:", "info", "📦")
    for asset in assets:
        log(f"  - {asset['name']} ({asset['browser_download_url']})")

    # Platform categorization
    _print_platform_assets(assets, "linux", "🐧")
    _print_platform_assets(assets, "macos", "🍏")

    # Architecture categorization
    _print_arch_assets(assets, "amd64", "💻")
    _print_arch_assets(assets, "arm64", "📱")


def _print_platform_assets(assets: list[dict], platform: str, icon: str) -> None:
    """Print assets for a specific platform."""
    platform_assets = get_platform_assets(assets, platform)
    log(f"{platform.capitalize()} assets:", "info", icon)
    for asset in platform_assets:
        log(f"  - {asset['name']}")


def _print_arch_assets(assets: list[dict], arch: str, icon: str) -> None:
    """Print assets for a specific architecture."""
    arch_assets = get_arch_assets(assets, arch)
    arch_display = "AMD64/x86_64" if arch == "amd64" else "ARM64/aarch64"
    log(f"{arch_display} assets:", "info", icon)
    for asset in arch_assets:
        log(f"  - {asset['name']}")


def _get_filtered_assets(
    assets: list[dict],
    filter_type: str,
    value: str,
) -> list[dict]:
    """Filter assets by platform or architecture."""
    filters = {
        "platform": {"linux": ["linux"], "macos": ["darwin", "macos"]},
        "arch": {"amd64": ["amd64", "x86_64"], "arm64": ["arm64", "aarch64"]},
    }

    keywords = filters.get(filter_type, {}).get(value, [])
    if not keywords:
        return []

    return [a for a in assets if any(kw in a["name"].lower() for kw in keywords)]


def get_platform_assets(assets: list[dict], platform: str) -> list[dict]:
    """Filter assets by platform."""
    return _get_filtered_assets(assets, "platform", platform)


def get_arch_assets(assets: list[dict], arch: str) -> list[dict]:
    """Filter assets by architecture."""
    return _get_filtered_assets(assets, "arch", arch)


def _find_sample_asset(assets: list[dict]) -> dict | None:
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


def _download_and_find_binary(asset: dict, tool_name: str) -> str | list[str] | None:
    """Download sample asset and find binary path."""
    log(
        f"Downloading sample archive: {asset['name']} to inspect contents...",
        "info",
        "📥",
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

        extract_archive(temp_path, temp_dir)
        executables = find_executables(temp_dir)

        log("Executable files found in the archive:", "info", "🔍")
        for exe in executables:
            log(f"  - {exe}")

        binary_path = determine_binary_path(executables, tool_name)

        if binary_path:
            log(f"Detected binary path: {binary_path}", "success")

        return binary_path

    finally:
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

    # Step 1: Look for exact name matches
    exact_matches = [
        exe for exe in executables if os.path.basename(exe).lower() == tool_name.lower()
    ]
    if exact_matches:
        return exact_matches[0] if len(exact_matches) == 1 else exact_matches

    # Step 2: Look for partial name matches
    partial_matches = [
        exe for exe in executables if tool_name.lower() in os.path.basename(exe).lower()
    ]
    if partial_matches:
        return partial_matches[0] if len(partial_matches) == 1 else partial_matches

    # Step 3: Look for binaries in bin/ directory
    bin_matches = [exe for exe in executables if "bin/" in exe]
    if bin_matches:
        return bin_matches[0]

    # Step 4: Fall back to the first executable
    return executables[0]


def generate_tool_config(
    repo: str,
    tool_name: str,
    release: dict,
    binary_path: str | list[str] | None,
) -> ToolConfig:
    """Generate tool configuration based on release information."""
    assets = release["assets"]
    linux_assets = get_platform_assets(assets, "linux")
    macos_assets = get_platform_assets(assets, "macos")

    # Process binary_path to make it more generic/flexible
    processed_binary_path: str | list[str] | None = None
    if binary_path:
        if isinstance(binary_path, list):
            processed_binary_path = [_generalize_binary_path(path) for path in binary_path]
        else:
            processed_binary_path = _generalize_binary_path(binary_path)

    arch_map = {"amd64": "x86_64", "arm64": "aarch64"} if _needs_arch_conversion(assets) else {}

    asset_patterns = _get_asset_patterns(release, linux_assets, macos_assets)
    raw_data: RawToolConfigDict = {
        "repo": repo,
        "binary_name": tool_name,
        "extract_binary": True,
        "asset_patterns": asset_patterns,  # type: ignore[typeddict-item]
        "arch_map": arch_map,
    }
    if processed_binary_path is not None:
        raw_data["binary_path"] = processed_binary_path
    return build_tool_config(
        tool_name=tool_name,
        raw_data=raw_data,
    )


def _get_asset_patterns(
    release: dict,
    linux_assets: list[dict],
    macos_assets: list[dict],
) -> str | dict[str, str | None]:
    """Get asset patterns based on release info."""
    platform_specific = bool(linux_assets and macos_assets)
    if platform_specific:
        return generate_platform_specific_patterns(release)
    return generate_single_pattern(release)


def _generalize_binary_path(path: str) -> str:
    """Create a generalized binary path with wildcards for maximum flexibility.

    Takes a concrete binary path like "uv-x86_64-unknown-linux-gnu/uv" and
    converts it to a wildcard pattern like "*/uv"
    """
    # Get the basename (actual binary name)
    basename = os.path.basename(path)

    # If there's a single directory level, use a simple wildcard pattern
    if "/" in path and path.count("/") == 1:
        return f"*/{basename}"

    # If there are multiple directory levels, preserve the last directory
    # This helps with cases where the binary might be in 'bin/' or similar
    if "/" in path and path.count("/") > 1:
        last_dir = os.path.dirname(path).split("/")[-1]
        return f"*/{last_dir}/{basename}"

    # If there's no directory structure, just return the basename
    return basename


def _needs_arch_conversion(assets: list[dict]) -> bool:
    """Determine if we need architecture conversion."""
    return any("x86_64" in a["name"] for a in assets) or any("aarch64" in a["name"] for a in assets)


def generate_platform_specific_patterns(release: dict) -> dict[str, str | None]:
    """Generate platform-specific asset patterns."""
    assets = release["assets"]
    linux_assets = get_platform_assets(assets, "linux")
    macos_assets = get_platform_assets(assets, "macos")
    version = release["tag_name"].lstrip("v")

    patterns: dict[str, str | None] = {"linux": None, "macos": None}

    # Find pattern for each platform
    for platform, platform_assets in [("linux", linux_assets), ("macos", macos_assets)]:
        amd64_assets = [
            a for a in platform_assets if any(arch in a["name"] for arch in ["x86_64", "amd64"])
        ]

        if amd64_assets:
            # Use the first match
            pattern = amd64_assets[0]["name"]
            # Replace with placeholders
            patterns[platform] = _replace_pattern_placeholders(
                pattern,
                version,
                platform_found=True,
                arch_found=True,
            )

    return patterns


def _replace_pattern_placeholders(
    pattern: str,
    version: str,
    platform_found: bool = False,
    arch_found: bool = False,
) -> str:
    """Replace version, platform, and architecture placeholders in a pattern.

    Args:
        pattern: The asset filename pattern
        version: Version string to replace with {version}
        platform_found: Whether a platform was detected in the pattern
        arch_found: Whether an architecture was detected in the pattern

    Returns:
        The pattern with placeholders applied

    """
    # Replace version if present
    if version and version in pattern:
        pattern = pattern.replace(version, "{version}")

    # Replace platform if detected
    if platform_found:
        if "darwin" in pattern.lower():
            pattern = re.sub(r"(?i)darwin", "{platform}", pattern)
        elif "linux" in pattern.lower():
            pattern = re.sub(r"(?i)linux", "{platform}", pattern)

    # Replace architecture if detected
    if arch_found:
        if "x86_64" in pattern:
            pattern = pattern.replace("x86_64", "{arch}")
        elif "amd64" in pattern:
            pattern = pattern.replace("amd64", "{arch}")
        elif "aarch64" in pattern:
            pattern = pattern.replace("aarch64", "{arch}")
        elif "arm64" in pattern:
            pattern = pattern.replace("arm64", "{arch}")

    return pattern


def generate_single_pattern(release: dict) -> str:
    """Generate a single asset pattern for all platforms."""
    if not release["assets"]:
        msg = "No assets found in the release."
        raise ValueError(msg)

    asset_name = release["assets"][0]["name"]
    version = release["tag_name"].lstrip("v")

    # Detect if the pattern contains platform/arch info
    platform_found = any(p in asset_name.lower() for p in ["darwin", "linux", "macos"])
    arch_found = any(a in asset_name for a in ["x86_64", "amd64", "arm64", "aarch64"])

    return _replace_pattern_placeholders(
        asset_name,
        version,
        platform_found,
        arch_found,
    )
