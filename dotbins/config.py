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
    arch_maps: dict[str, dict[str, str]] = field(default_factory=dict)
    platform_maps: dict[str, str] = field(default_factory=dict)

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
        required_fields = ["repo", "binary_name"]
        for _field in required_fields:
            if _field not in tool_config:
                console.print(
                    f"⚠️ [yellow]Tool {tool_name} is missing required field '{_field}'[/yellow]",
                )

        # Check that either asset_pattern or asset_patterns is defined
        if "asset_pattern" not in tool_config and "asset_patterns" not in tool_config:
            console.print(
                f"⚠️ [yellow]Tool {tool_name} has neither 'asset_pattern' nor 'asset_patterns' defined[/yellow]",
            )

        # Validate asset_patterns if present
        if "asset_patterns" in tool_config:
            patterns = tool_config["asset_patterns"]
            for platform in self.platforms:
                if platform not in patterns:
                    console.print(
                        f"⚠️ [yellow]Tool {tool_name} is missing asset pattern for platform '{platform}'[/yellow]",
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
