"""Configuration management for dotbins."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from rich.console import Console

console = Console()


@dataclass
class DotbinsConfig:
    """Configuration for dotbins."""

    tools_dir: Path = field(
        default_factory=lambda: Path(os.path.expanduser("~/.dotfiles/tools")),
    )
    platforms: dict[str, list[str]] = field(
        default_factory=lambda: {
            "linux": ["amd64", "arm64"],
            "macos": ["amd64", "arm64"],
        },
    )
    tools: dict[str, Any] = field(default_factory=dict)

    @property
    def platform_names(self) -> list[str]:
        """Return list of platform names."""
        return list(self.platforms.keys())

    def get_architectures(self, platform: str) -> list[str]:
        """Get architectures for a specific platform."""
        return self.platforms.get(platform, [])

    def validate(self) -> None:
        """Validate the configuration."""
        # Validate tool configurations
        for tool_name, tool_config in self.tools.items():
            self._validate_tool_config(tool_name, tool_config)

    def _validate_tool_config(
        self,
        tool_name: str,
        tool_config: dict[str, Any],
    ) -> None:
        """Validate a single tool configuration."""
        self._validate_required_fields(tool_name, tool_config)
        self._validate_unknown_fields(tool_name, tool_config)
        self._validate_asset_patterns_presence(tool_name, tool_config)
        self._validate_binary_fields(tool_name, tool_config)
        self._validate_binary_lists_length(tool_name, tool_config)
        self._validate_map_fields(tool_name, tool_config)
        self._validate_asset_patterns_structure(tool_name, tool_config)

    def _validate_required_fields(
        self,
        tool_name: str,
        tool_config: dict[str, Any],
    ) -> None:
        """Validate required fields are present."""
        required_fields = ["repo", "binary_name"]  # Remove binary_path from required
        for _field in required_fields:
            if _field not in tool_config:
                console.print(
                    f"⚠️ [red]Tool {tool_name} is missing required field '{_field}'[/yellow]",
                )

        if "binary_path" not in tool_config:
            console.print(
                f"ℹ️ [blue]Tool {tool_name} has no binary_path specified - will attempt auto-detection[/blue]",  # noqa: RUF001
            )

    def _validate_unknown_fields(
        self,
        tool_name: str,
        tool_config: dict[str, Any],
    ) -> None:
        """Validate there are no unknown fields."""
        known_fields = {
            "repo",
            "binary_name",
            "binary_path",
            "extract_binary",
            "asset_patterns",
            "platform_map",
            "arch_map",
        }
        unknown_fields = set(tool_config.keys()) - known_fields
        for _field in unknown_fields:
            console.print(
                f"⚠️ [yellow]Tool {tool_name} has unknown field '{_field}' that will be ignored[/yellow]",
            )

    def _validate_asset_patterns_presence(
        self,
        tool_name: str,
        tool_config: dict[str, Any],
    ) -> None:
        """Validate asset_patterns field is present."""
        if "asset_patterns" not in tool_config:
            console.print(
                f"⚠️ [yellow]Tool {tool_name} is missing required field 'asset_patterns'[/yellow]",
            )

    def _validate_binary_fields(
        self,
        tool_name: str,
        tool_config: dict[str, Any],
    ) -> None:
        """Validate binary_name and binary_path fields."""
        for _field in ["binary_name", "binary_path"]:
            if _field in tool_config and not isinstance(
                tool_config[_field],
                (str, list),
            ):
                console.print(
                    f"⚠️ [yellow]Tool {tool_name}: '{_field}' must be a string or a list of strings[/yellow]",
                )

    def _validate_binary_lists_length(
        self,
        tool_name: str,
        tool_config: dict[str, Any],
    ) -> None:
        """Validate binary_name and binary_path lists have the same length."""
        if (
            isinstance(tool_config.get("binary_name"), list)
            and isinstance(tool_config.get("binary_path"), list)
            and len(tool_config["binary_name"]) != len(tool_config["binary_path"])
        ):
            console.print(
                f"⚠️ [yellow]Tool {tool_name}: 'binary_name' and 'binary_path' lists must have the same length[/yellow]",
            )

    def _validate_map_fields(self, tool_name: str, tool_config: dict[str, Any]) -> None:
        """Validate platform_map and arch_map fields."""
        for _field in ["platform_map", "arch_map"]:
            if _field in tool_config and not isinstance(tool_config[_field], dict):
                console.print(
                    f"⚠️ [yellow]Tool {tool_name}: '{_field}' must be a dictionary[/yellow]",
                )

    def _validate_asset_patterns_structure(
        self,
        tool_name: str,
        tool_config: dict[str, Any],
    ) -> None:
        """Validate asset_patterns structure."""
        if "asset_patterns" not in tool_config:
            return

        patterns = tool_config["asset_patterns"]
        if isinstance(patterns, dict):
            for platform, platform_patterns in patterns.items():
                if platform not in self.platforms and platform != "default":
                    console.print(
                        f"⚠️ [yellow]Tool {tool_name}: 'asset_patterns' contains unknown platform '{platform}'[/yellow]",
                    )
                if isinstance(platform_patterns, dict):
                    # Get architectures for this platform
                    valid_architectures = self.get_architectures(platform)
                    for arch in platform_patterns:
                        if arch not in valid_architectures and arch != "default":
                            console.print(
                                f"⚠️ [yellow]Tool {tool_name}: 'asset_patterns[{platform}]' contains unknown architecture '{arch}'[/yellow]",
                            )

    @classmethod
    def load_from_file(cls, config_path: str | Path | None = None) -> DotbinsConfig:
        """Load configuration from YAML file.

        Checks the following locations in order:
        1. Explicitly provided config_path (if specified)
        2. ./dotbins.yaml (current directory)
        3. ~/.config/dotbins/config.yaml (XDG config directory)
        4. ~/.config/dotbins.yaml (XDG config directory, flat)
        5. ~/.dotbins.yaml (home directory)
        6. ~/.dotfiles/dotbins.yaml (default dotfiles location)
        """
        if config_path:
            config_paths = [Path(config_path)]
        else:
            # Define common configuration file locations
            home = Path.home()
            config_paths = [
                Path.cwd() / "dotbins.yaml",
                home / ".config" / "dotbins" / "config.yaml",
                home / ".config" / "dotbins.yaml",
                home / ".dotbins.yaml",
                home / ".dotfiles" / "dotbins.yaml",
            ]
            # Find the first existing config file
            for path in config_paths:
                if path.exists():
                    console.print(
                        f"📝 [green]Loading configuration from: {path}[/green]",
                    )
                    config_paths = [path]
                    break
            else:
                # No config file found
                console.print(
                    "⚠️ [yellow]No configuration file found, using default settings[/yellow]",
                )
                return cls()

        # At this point, config_paths only contains one path that's either:
        # - the explicitly provided path, or
        # - the first existing path from the common locations
        try:
            with open(config_paths[0]) as file:
                config_data = yaml.safe_load(file)

            # Expand paths
            if isinstance(config_data.get("tools_dir"), str):
                config_data["tools_dir"] = Path(
                    os.path.expanduser(config_data["tools_dir"]),
                )

            config = cls(**config_data)
            config.validate()
            return config  # noqa: TRY300

        except FileNotFoundError:
            console.print(
                f"⚠️ [yellow]Configuration file not found: {config_paths[0]}[/yellow]",
            )
            return cls()
        except yaml.YAMLError:
            console.print(
                f"❌ [bold red]Invalid YAML in configuration file: {config_paths[0]}[/bold red]",
            )
            console.print_exception()
            return cls()
        except Exception as e:  # noqa: BLE001
            console.print(f"❌ [bold red]Error loading configuration: {e}[/bold red]")
            console.print_exception()
            return cls()
