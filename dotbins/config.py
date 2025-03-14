"""Configuration management for dotbins."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeVar

import yaml

from .utils import log

DEFAULT_TOOLS_DIR = "~/.mydotbins/tools"
DEFAULT_PLATFORMS = {
    "linux": ["amd64", "arm64"],
    "macos": ["arm64"],
}


def _normalize_asset_patterns(
    patterns: str | dict[str, Any] | None,
    platforms: dict[str, list[str]],
) -> dict[str, dict[str, str]]:
    """Normalize asset patterns to dict[str, dict[str, str]] format for all supported platforms and architectures."""
    normalized: dict[str, dict[str, str]] = {
        platform: {arch: "" for arch in architectures}
        for platform, architectures in platforms.items()
    }
    if patterns is None:
        return normalized
    if isinstance(patterns, str):
        for platform, _architectures in normalized.items():
            for arch in _architectures:
                normalized[platform][arch] = patterns
        return normalized
    if isinstance(patterns, dict):
        for platform, platform_patterns in patterns.items():
            if platform not in platforms:
                continue
            if isinstance(platform_patterns, str):
                for arch in normalized[platform]:
                    normalized[platform][arch] = platform_patterns
            elif isinstance(platform_patterns, dict):
                for arch, pattern in platform_patterns.items():
                    if arch in normalized[platform]:
                        normalized[platform][arch] = pattern
    return normalized


@dataclass
class ToolConfig:
    """Configuration for a single tool."""

    def __init__(
        self,
        tool_name: str,
        repo: str,
        binary_name: str | list[str] | None = None,
        binary_path: str | list[str] | None = None,
        extract_binary: bool = True,
        asset_patterns: str | dict[str, Any] | None = None,
        platform_map: dict[str, str] | None = None,
        arch_map: dict[str, str] | None = None,
        platforms: dict[str, list[str]] = DEFAULT_PLATFORMS,
    ) -> None:
        """Initialize the tool config."""
        self.tool_name: str = tool_name
        self.repo: str = repo
        self.binary_name: list[str] = _ensure_list(binary_name) or [tool_name]
        self.binary_path: list[str] = _ensure_list(binary_path)
        self.extract_binary: bool = extract_binary
        self.asset_patterns: dict[str, dict[str, str]] = _normalize_asset_patterns(
            asset_patterns,
            platforms,
        )
        self.platform_map: dict[str, str] | None = platform_map
        self.arch_map: dict[str, str] | None = arch_map
        # Runtime fields - not required for initialization,
        self.version: str | None = None
        self.arch: str | None = None

    def copy(self, **updates: Any) -> ToolConfig:
        """Copy the tool config and update with new values."""
        cfg = ToolConfig(
            tool_name=self.tool_name,
            repo=self.repo,
            binary_name=self.binary_name,
            binary_path=self.binary_path,
            extract_binary=self.extract_binary,
            asset_patterns=self.asset_patterns,
            platform_map=self.platform_map,
            arch_map=self.arch_map,
        )
        cfg.version = self.version
        cfg.arch = self.arch
        for key, value in updates.items():
            setattr(cfg, key, value)
        return cfg


T = TypeVar("T")


def _ensure_list(value: T | list[T] | None) -> list[T]:
    """Ensure a value is a list."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


@dataclass
class Config:
    """Configuration for dotbins."""

    tools_dir: Path = field(default=Path(os.path.expanduser(DEFAULT_TOOLS_DIR)))
    platforms: dict[str, list[str]] = field(default_factory=lambda: DEFAULT_PLATFORMS)
    tools: dict[str, ToolConfig] = field(default_factory=dict)

    @property
    def platform_names(self) -> list[str]:
        """Return list of platform names."""
        return list(self.platforms.keys())

    def get_architectures(self, platform: str) -> list[str]:
        """Get architectures for a specific platform."""
        return self.platforms.get(platform, [])

    def validate(self) -> None:
        """Validate the configuration."""
        for tool_name, tool_config in self.tools.items():
            self._validate_tool_config(tool_name, tool_config)

    def _validate_tool_config(
        self,
        tool_name: str,
        tool_config: ToolConfig,
    ) -> None:
        """Validate a single tool configuration."""
        self._validate_required_fields(tool_name, tool_config)
        self._validate_binary_fields(tool_name, tool_config)
        self._validate_binary_lists_length(tool_name, tool_config)
        self._validate_asset_patterns_structure(tool_name, tool_config)

    def _validate_required_fields(
        self,
        tool_name: str,
        tool_config: ToolConfig,
    ) -> None:
        """Validate required fields are present."""
        if not tool_config.repo:
            log(
                f"Tool {tool_name} is missing required field 'repo'",
                "error",
                "⚠️",
            )

        if not tool_config.binary_path:
            log(
                f"Tool {tool_name} has no binary_path specified - will attempt auto-detection",
                "info",
                "ℹ️",  # noqa: RUF001
            )

    def _validate_binary_fields(
        self,
        tool_name: str,
        tool_config: ToolConfig,
    ) -> None:
        """Validate binary_name and binary_path fields."""
        for field_name, field_value in [
            ("binary_name", tool_config.binary_name),
            ("binary_path", tool_config.binary_path),
        ]:
            if field_value is not None and not isinstance(
                field_value,
                (str, list),
            ):
                log(
                    f"Tool {tool_name}: '{field_name}' must be a string or a list of strings",
                    "error",
                    "⚠️",
                )

    def _validate_binary_lists_length(
        self,
        tool_name: str,
        tool_config: ToolConfig,
    ) -> None:
        """Validate binary_name and binary_path lists have the same length."""
        if (
            tool_config.binary_name
            and tool_config.binary_path
            and len(tool_config.binary_name) != len(tool_config.binary_path)
        ):
            log(
                f"Tool {tool_name}: 'binary_name' and 'binary_path' lists must have the same length",
                "error",
                "⚠️",
            )

    def _validate_asset_patterns_structure(
        self,
        tool_name: str,
        tool_config: ToolConfig,
    ) -> None:
        """Validate asset_patterns structure."""
        patterns = tool_config.asset_patterns
        for platform, platform_patterns in patterns.items():
            if platform not in self.platforms:
                log(
                    f"Tool {tool_name}: 'asset_patterns' contains unknown platform '{platform}'",
                    "error",
                    "⚠️",
                )
            valid_architectures = self.get_architectures(platform)
            for arch in platform_patterns:
                if arch not in valid_architectures:
                    log(
                        f"Tool {tool_name}: 'asset_patterns[{platform}]' contains unknown architecture '{arch}'",
                        "error",
                        "⚠️",
                    )

    @classmethod
    def load_from_file(cls, config_path: str | Path | None = None) -> Config:
        """Load configuration from YAML file.

        Checks the following locations in order:
        1. Explicitly provided config_path (if specified)
        2. ./dotbins.yaml (current directory)
        3. ~/.config/dotbins/config.yaml (XDG config directory)
        4. ~/.config/dotbins.yaml (XDG config directory, flat)
        5. ~/.dotbins.yaml (home directory)
        6. ~/.mydotbins/dotbins.yaml (default dotfiles location)
        """
        config_path = _find_config_file(config_path)
        if config_path is None:
            return cls()
        try:
            with open(config_path) as file:
                config_data = yaml.safe_load(file)
            if isinstance(config_data.get("tools_dir"), str):
                config_data["tools_dir"] = Path(
                    os.path.expanduser(config_data["tools_dir"]),
                )
            if "tools" in config_data:
                config_data["tools"] = {
                    tool_name: ToolConfig(
                        tool_name,
                        **tool_data,
                        platforms=config_data.get("platforms", DEFAULT_PLATFORMS),
                    )
                    for tool_name, tool_data in config_data["tools"].items()
                }
            config = cls(**config_data)
            config.validate()
            return config

        except FileNotFoundError:
            log(f"Configuration file not found: {config_path}", "warning")
            return cls()
        except yaml.YAMLError:
            log(
                f"Invalid YAML in configuration file: {config_path}",
                "error",
                print_exception=True,
            )
            return cls()
        except Exception as e:
            log(f"Error loading configuration: {e}", "error", print_exception=True)
            return cls()


def _find_config_file(config_path: str | Path | None) -> Path | None:
    if config_path is not None:
        return Path(config_path)
    home = Path.home()
    config_paths = [
        Path.cwd() / "dotbins.yaml",
        home / ".config" / "dotbins" / "config.yaml",
        home / ".config" / "dotbins.yaml",
        home / ".dotbins.yaml",
        home / ".mydotbins" / "dotbins.yaml",
    ]
    for path in config_paths:
        if path.exists():
            log(f"Loading configuration from: {path}", "success", "📝")
            return path
    log("No configuration file found, using default settings", "warning")
    return None
