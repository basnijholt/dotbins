"""Configuration management for dotbins."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from rich.console import Console

console = Console()
logger = logging.getLogger(__name__)


@dataclass
class DotbinsConfig:
    """Configuration for dotbins."""

    dotfiles_dir: Path = field(
        default_factory=lambda: Path(os.path.expanduser("~/.dotfiles")),
    )
    tools_dir: Path = field(
        default_factory=lambda: Path(os.path.expanduser("~/.dotfiles/tools")),
    )
    platforms: list[str] = field(default_factory=lambda: ["linux", "macos"])
    architectures: list[str] = field(default_factory=lambda: ["amd64", "arm64"])
    tools: dict[str, Any] = field(default_factory=dict)

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
        required_fields = ["repo", "binary_name", "binary_path"]
        for _field in required_fields:
            if _field not in tool_config:
                console.print(
                    f"⚠️ [yellow]Tool {tool_name} is missing required field '{_field}'[/yellow]",
                )

        # Check for unknown fields
        known_fields = {
            *required_fields,
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

        # Check for asset_patterns
        if "asset_patterns" not in tool_config:
            console.print(
                f"⚠️ [yellow]Tool {tool_name} is missing required field 'asset_patterns'[/yellow]",
            )

        # Validate binary_name and binary_path are either strings or lists
        for _field in ["binary_name", "binary_path"]:
            if _field in tool_config and not isinstance(
                tool_config[_field],
                (str, list),
            ):
                console.print(
                    f"⚠️ [yellow]Tool {tool_name}: '{_field}' must be a string or a list of strings[/yellow]",
                )

        # Validate binary_path and binary_name have the same length if both are lists
        if (
            isinstance(tool_config.get("binary_name"), list)
            and isinstance(tool_config.get("binary_path"), list)
            and len(tool_config["binary_name"]) != len(tool_config["binary_path"])
        ):
            console.print(
                f"⚠️ [yellow]Tool {tool_name}: 'binary_name' and 'binary_path' lists must have the same length[/yellow]",
            )

        # Validate platform_map and arch_map are dictionaries if present
        for _field in ["platform_map", "arch_map"]:
            if _field in tool_config and not isinstance(tool_config[_field], dict):
                console.print(
                    f"⚠️ [yellow]Tool {tool_name}: '{_field}' must be a dictionary[/yellow]",
                )

        # Validate asset_patterns is a string or dictionary
        if "asset_patterns" in tool_config and not isinstance(
            tool_config["asset_patterns"],
            (str, dict),
        ):
            console.print(
                f"⚠️ [yellow]Tool {tool_name}: 'asset_patterns' must be a string or dictionary[/yellow]",
            )

    @classmethod
    def load_from_file(cls, config_path: str | None = None) -> DotbinsConfig:
        """Load configuration from YAML file."""
        if not config_path:
            config_path = os.path.join(os.path.dirname(__file__), "..", "tools.yaml")

        try:
            with open(config_path) as file:
                config_data = yaml.safe_load(file)

            # Expand paths
            if isinstance(config_data.get("dotfiles_dir"), str):
                config_data["dotfiles_dir"] = Path(
                    os.path.expanduser(config_data["dotfiles_dir"]),
                )
            if isinstance(config_data.get("tools_dir"), str):
                config_data["tools_dir"] = Path(
                    os.path.expanduser(config_data["tools_dir"]),
                )

            config = cls(**config_data)
            config.validate()
            return config  # noqa: TRY300

        except FileNotFoundError:
            console.print(
                f"⚠️ [yellow]Configuration file not found: {config_path}[/yellow]",
            )
            return cls()
        except yaml.YAMLError:
            console.print(
                f"❌ [bold red]Invalid YAML in configuration file: {config_path}[/bold red]",
            )
            console.print_exception()
            return cls()
        except Exception as e:  # noqa: BLE001
            console.print(f"❌ [bold red]Error loading configuration: {e}[/bold red]")
            console.print_exception()
            return cls()
