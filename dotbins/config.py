"""Configuration management for dotbins."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import TypedDict, TypeVar

import yaml

from .utils import log
from .versions import VersionStore

DEFAULT_TOOLS_DIR = "~/.mydotbins/tools"
DEFAULT_PLATFORMS = {
    "linux": ["amd64", "arm64"],
    "macos": ["arm64"],
}

T = TypeVar("T")


@dataclass
class Config:
    """Overall configuration for dotbins."""

    tools_dir: Path = field(default=Path(os.path.expanduser(DEFAULT_TOOLS_DIR)))
    platforms: dict[str, list[str]] = field(default_factory=lambda: DEFAULT_PLATFORMS)
    tools: dict[str, ToolConfig] = field(default_factory=dict)

    def bin_dir(self, platform: str, arch: str, *, create: bool = False) -> Path:
        """Return the bin directory for a given platform and architecture."""
        bin_dir = self.tools_dir / platform / arch / "bin"
        if create:
            bin_dir.mkdir(parents=True, exist_ok=True)
        return bin_dir

    @cached_property
    def version_store(self) -> VersionStore:
        """Return the VersionStore object."""
        return VersionStore(self.tools_dir)

    def validate(self) -> None:
        """Check for missing repos, unknown platforms, etc."""
        for tool_name, tool_config in self.tools.items():
            _validate_tool_config(self.platforms, tool_name, tool_config)

    @classmethod
    def from_file(cls, config_path: str | Path | None = None) -> Config:
        """Load configuration from YAML, or return defaults if no file found."""
        return config_from_file(config_path)


@dataclass(frozen=True)
class ToolConfig:
    """Holds all config data for a single tool, without doing heavy logic."""

    tool_name: str
    repo: str
    binary_name: list[str] = field(default_factory=list)
    binary_path: list[str] = field(default_factory=list)
    extract_binary: bool = True
    asset_patterns: dict[str, dict[str, str | None]] = field(default_factory=dict)
    platform_map: dict[str, str] = field(default_factory=dict)
    arch_map: dict[str, str] = field(default_factory=dict)

    def bin_spec(self, arch: str, platform: str) -> BinSpec:
        """Get a BinSpec object for the tool."""
        return BinSpec(tool_config=self, version=self.latest_version, arch=arch, platform=platform)

    @cached_property
    def latest_release(self) -> dict:
        """Get the latest release for the tool."""
        from .utils import get_latest_release

        return get_latest_release(self.repo)

    @cached_property
    def latest_version(self) -> str:
        """Get the latest version for the tool."""
        return self.latest_release["tag_name"].lstrip("v")


@dataclass
class BinSpec:
    """Specific arch and platform for a tool."""

    tool_config: ToolConfig
    version: str
    arch: str
    platform: str

    @property
    def tool_arch(self) -> str:
        """Get the architecture in the tool's convention."""
        return self.tool_config.arch_map.get(self.arch, self.arch)

    @property
    def tool_platform(self) -> str:
        """Get the platform in the tool's convention."""
        return self.tool_config.platform_map.get(self.platform, self.platform)

    @property
    def asset_pattern(self) -> str | None:
        """Get the asset pattern for the tool."""
        return self.tool_config.asset_patterns[self.platform][self.arch]

    @property
    def search_pattern(self) -> str | None:
        """Get the formatted asset pattern for the tool."""
        asset_pattern = self.asset_pattern
        if asset_pattern is None:
            log(f"No asset pattern found for {self.platform}/{self.arch}", "warning")
            return None
        return asset_pattern.format(
            version=self.version,
            platform=self.tool_platform,
            arch=self.tool_arch,
        )

    @property
    def matching_asset(self) -> dict | None:
        """Find a matching asset for the tool."""
        search_pattern = self.search_pattern
        if search_pattern is None:
            return None
        assets = self.tool_config.latest_release["assets"]

        regex_pattern = (
            search_pattern.replace("{version}", ".*")
            .replace("{arch}", ".*")
            .replace("{platform}", ".*")
        )
        log(f"Looking for asset with pattern: {regex_pattern}", "info", "🔍")

        for asset in assets:
            if re.search(regex_pattern, asset["name"]):
                log(f"Found matching asset: {asset['name']}", "success")
                return asset

        log(f"No asset matching '{search_pattern}' found", "warning")
        return None

    def skip_download(self, config: Config, force: bool) -> bool:
        """Check if download should be skipped (binary already exists)."""
        tool_info = config.version_store.get_tool_info(
            self.tool_config.tool_name,
            self.platform,
            self.arch,
        )
        destination_dir = config.bin_dir(self.platform, self.arch)
        all_exist = _exists_in_destination_dir(destination_dir, self.tool_config)
        if tool_info and tool_info["version"] == self.version and all_exist and not force:
            log(
                f"{self.tool_config.tool_name} {self.version} for {self.platform}/{self.arch} is already"
                f" up to date (installed on {tool_info['updated_at']}) use --force to re-download.",
                "success",
            )
            return True
        return False


class RawToolConfigDict(TypedDict, total=False):
    """TypedDict for raw data passed to build_tool_config."""

    repo: str  # Repository in format "owner/repo"
    extract_binary: bool  # Whether to extract binary from archive
    platform_map: dict[str, str]  # Map from system platform to tool's platform name
    arch_map: dict[str, str]  # Map from system architecture to tool's architecture name
    binary_name: str | list[str]  # Name(s) of the binary file(s)
    binary_path: str | list[str]  # Path(s) to binary within archive
    asset_patterns: str | dict[str, str] | dict[str, dict[str, str | None]]


def build_tool_config(
    tool_name: str,
    raw_data: RawToolConfigDict,
    platforms: dict[str, list[str]] | None = None,
) -> ToolConfig:
    """Create a ToolConfig object from raw YAML data.

    Performing any expansions
    or normalization that used to happen inside the constructor.
    """
    if not platforms:
        platforms = DEFAULT_PLATFORMS

    # Safely grab data from raw_data (or set default if missing).
    repo = raw_data.get("repo") or ""
    extract_binary = raw_data.get("extract_binary", True)
    platform_map = raw_data.get("platform_map", {})
    arch_map = raw_data.get("arch_map", {})
    # Might be str or list
    raw_binary_name = raw_data.get("binary_name", tool_name)
    raw_binary_path = raw_data.get("binary_path", [])

    # Convert to lists
    binary_name: list[str] = _ensure_list(raw_binary_name)
    binary_path: list[str] = _ensure_list(raw_binary_path)

    # Normalize asset patterns to dict[platform][arch].
    raw_patterns = raw_data.get("asset_patterns")
    asset_patterns = _normalize_asset_patterns(raw_patterns, platforms)

    # Build our final data-class object
    return ToolConfig(
        tool_name=tool_name,
        repo=repo,
        binary_name=binary_name,
        binary_path=binary_path,
        extract_binary=extract_binary,
        asset_patterns=asset_patterns,
        platform_map=platform_map,
        arch_map=arch_map,
    )


def config_from_file(config_path: str | Path | None = None) -> Config:
    """Load configuration from YAML, or return defaults if no file found."""
    path = _find_config_file(config_path)
    if path is None:
        return Config()

    try:
        with open(path) as f:
            data = yaml.safe_load(f) or {}
    except FileNotFoundError:
        log(f"Configuration file not found: {path}", "warning")
        return Config()
    except yaml.YAMLError:
        log(
            f"Invalid YAML in configuration file: {path}",
            "error",
            print_exception=True,
        )
        return Config()

    tools_dir = data.get("tools_dir", DEFAULT_TOOLS_DIR)
    platforms = data.get("platforms", DEFAULT_PLATFORMS)
    raw_tools = data.get("tools", {})

    tools_dir_path = Path(os.path.expanduser(tools_dir))

    tool_configs: dict[str, ToolConfig] = {}
    for tool_name, tool_data in raw_tools.items():
        tool_configs[tool_name] = build_tool_config(tool_name, tool_data, platforms)

    config_obj = Config(tools_dir=tools_dir_path, platforms=platforms, tools=tool_configs)
    config_obj.validate()
    return config_obj


def _normalize_asset_patterns(
    patterns: str | dict[str, str] | dict[str, dict[str, str | None]] | None,
    platforms: dict[str, list[str]],
) -> dict[str, dict[str, str | None]]:
    """Normalize the asset_patterns into a dict.

    Of the form:
    ```{ platform: { arch: pattern_str } }```.
    """
    # Start by initializing empty patterns for each platform/arch
    normalized: dict[str, dict[str, str | None]] = {
        platform: {arch: None for arch in arch_list} for platform, arch_list in platforms.items()
    }
    if not patterns:
        return normalized

    # If user gave a single string, apply it to all platform/arch combos
    if isinstance(patterns, str):
        for platform, arch_list in normalized.items():
            for arch in arch_list:
                normalized[platform][arch] = patterns
        return normalized

    # If user gave a dict, it might be "platform: pattern" or "platform: {arch: pattern}"
    if isinstance(patterns, dict):
        for platform, p_val in patterns.items():
            # Skip unknown platforms
            if platform not in normalized:
                continue

            # If p_val is a single string, apply to all arch
            if isinstance(p_val, str):
                for arch in normalized[platform]:
                    normalized[platform][arch] = p_val
            # Otherwise it might be {arch: pattern}
            elif isinstance(p_val, dict):
                for arch, pattern_str in p_val.items():
                    if arch in normalized[platform]:
                        normalized[platform][arch] = pattern_str
    return normalized


def _find_config_file(config_path: str | Path | None) -> Path | None:
    """Look for the user-specified path or common defaults."""
    if config_path is not None:
        path = Path(config_path)
        if path.exists():
            log(f"Loading configuration from: {path}", "success")
            return path
        log(f"Config path provided but not found: {path}", "warning")
        return None

    home = Path.home()
    candidates = [
        Path.cwd() / "dotbins.yaml",
        home / ".config" / "dotbins" / "config.yaml",
        home / ".config" / "dotbins.yaml",
        home / ".dotbins.yaml",
        home / ".mydotbins" / "dotbins.yaml",
    ]
    for candidate in candidates:
        if candidate.exists():
            log(f"Loading configuration from: {candidate}", "success")
            return candidate

    log("No configuration file found, using default settings", "warning")
    return None


def _ensure_list(value: T | list[T] | None) -> list[T]:
    """Convert a single value or None into a list, if not already a list."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _validate_tool_config(
    platforms: dict[str, list[str]],
    tool_name: str,
    tool_config: ToolConfig,
) -> None:
    # Basic checks
    if not tool_config.repo:
        log(f"Tool {tool_name} is missing required field 'repo'", "error")

    # If no binary_path, we rely on auto-detection (just an info, not fatal):
    if not tool_config.binary_path:
        log(
            f"Tool {tool_name} has no binary_path specified - will attempt auto-detection",
            "info",
        )

    # If binary lists differ in length, log an error
    if len(tool_config.binary_name) != len(tool_config.binary_path) and tool_config.binary_path:
        log(
            f"Tool {tool_name}: 'binary_name' and 'binary_path' must have the same length if both are specified as lists.",
            "error",
        )

    # Check for unknown platforms/arch in asset_patterns
    for platform, pattern_map in tool_config.asset_patterns.items():
        if platform not in platforms:
            log(
                f"Tool {tool_name}: 'asset_patterns' uses unknown platform '{platform}'",
                "error",
            )
            continue

        for arch in pattern_map:
            if arch not in platforms[platform]:
                log(
                    f"Tool {tool_name}: 'asset_patterns[{platform}]' uses unknown arch '{arch}'",
                    "error",
                )


def _exists_in_destination_dir(destination_dir: Path, tool_config: ToolConfig) -> bool:
    return all((destination_dir / binary_name).exists() for binary_name in tool_config.binary_name)
