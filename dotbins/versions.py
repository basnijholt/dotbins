"""Version tracking for installed tools."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.table import Table

from .utils import humanize_time_ago, log

if TYPE_CHECKING:
    from pathlib import Path

    from .config import Config


class VersionStore:
    """Manages version information for installed tools.

    This class tracks which versions of each tool are installed for each platform
    and architecture combination, along with timestamps of when they were last updated.
    This information is used to:

    1. Determine when updates are available
    2. Avoid unnecessary downloads of the same version
    3. Provide information about the installed tools through the 'status' command
    """

    def __init__(self, tools_dir: Path) -> None:
        """Initialize the VersionStore."""
        self.version_file = tools_dir / "versions.json"
        self.versions = self._load()

    def _load(self) -> dict[str, Any]:
        """Load version data from JSON file."""
        if not self.version_file.exists():
            return {}
        try:
            with self.version_file.open() as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}

    def save(self) -> None:
        """Save version data to JSON file."""
        self.version_file.parent.mkdir(parents=True, exist_ok=True)
        with self.version_file.open("w") as f:
            sorted_versions = dict(sorted(self.versions.items()))
            json.dump(sorted_versions, f, indent=2)

    def get_tool_info(self, tool: str, platform: str, arch: str) -> dict[str, Any] | None:
        """Get version info for a specific tool/platform/arch combination."""
        key = f"{tool}/{platform}/{arch}"
        return self.versions.get(key)

    def get_tool_version(self, tool: str, platform: str, arch: str) -> str | None:
        """Get version info for a specific tool/platform/arch combination."""
        info = self.get_tool_info(tool, platform, arch)
        return info["version"] if info else None

    def update_tool_info(
        self,
        tool: str,
        platform: str,
        arch: str,
        version: str,
        sha256: str = "",
    ) -> None:
        """Update version info for a tool.

        Args:
            tool: Tool name
            platform: Platform (e.g., 'linux', 'macos')
            arch: Architecture (e.g., 'amd64', 'arm64')
            version: Version string
            sha256: SHA256 hash of the downloaded archive (optional)

        """
        key = f"{tool}/{platform}/{arch}"
        self.versions[key] = {
            "version": version,
            "updated_at": datetime.now().isoformat(),
            "sha256": sha256,
        }
        self.save()

    def list_all(self) -> dict[str, Any]:
        """Return all version information."""
        return self.versions

    def print(self, platform: str = None, architecture: str = None) -> None:
        """Show versions of installed tools in a formatted table.

        Args:
            platform: Filter by platform (e.g., 'linux', 'macos')
            architecture: Filter by architecture (e.g., 'amd64', 'arm64')

        """
        versions = self.list_all()

        if not versions:
            log("No tool versions recorded yet.", "info")
            return

        console = Console()
        table = Table(title="Installed Tool Versions")

        # Add columns
        table.add_column("Tool", style="cyan")
        table.add_column("Platform", style="green")
        table.add_column("Architecture", style="green")
        table.add_column("Version", style="yellow")
        table.add_column("Last Updated", style="blue")
        table.add_column("SHA256", style="dim")

        # Add rows
        for key, info in sorted(versions.items()):
            tool, tool_platform, tool_arch = key.split("/")

            # Skip if not matching platform/architecture filters
            if platform and tool_platform != platform:
                continue
            if architecture and tool_arch != architecture:
                continue

            updated_str = humanize_time_ago(info["updated_at"])
            sha256 = info.get("sha256", "N/A")

            table.add_row(
                tool,
                tool_platform,
                tool_arch,
                info["version"],
                updated_str,
                sha256[:8] + "..." if sha256 and sha256 != "N/A" and len(sha256) > 16 else sha256,
            )

        # Print the table
        console.print(table)

    def print_condensed(self, platform: str = None, architecture: str = None) -> None:
        """Show a condensed view of installed tools with one line per tool.

        Args:
            platform: Filter by platform (e.g., 'linux', 'macos')
            architecture: Filter by architecture (e.g., 'amd64', 'arm64')

        """
        versions = self.list_all()

        if not versions:
            log("No tool versions recorded yet.", "info")
            return

        # Group versions by tool
        tools = defaultdict(list)
        for key, info in versions.items():
            tool, tool_platform, tool_arch = key.split("/")

            # Skip if not matching platform/architecture filters
            if platform and tool_platform != platform:
                continue
            if architecture and tool_arch != architecture:
                continue

            tools[tool].append(
                {
                    "platform": tool_platform,
                    "arch": tool_arch,
                    "version": info["version"],
                    "updated_at": info["updated_at"],
                },
            )

        if not tools:
            log("No tools found for the specified filters.", "info")
            return

        console = Console()
        table = Table(title="Installed Tools Summary")

        table.add_column("Tool", style="cyan")
        table.add_column("Version(s)", style="yellow")
        table.add_column("Platforms", style="green")
        table.add_column("Last Updated", style="blue")

        for tool_name, instances in sorted(tools.items()):
            # Collect unique versions and platforms
            versions = sorted({i["version"] for i in instances})
            platforms = sorted({f"{i['platform']}/{i['arch']}" for i in instances})

            # Find latest update time
            latest_update = max(instances, key=lambda x: x["updated_at"])
            updated_str = humanize_time_ago(latest_update["updated_at"])

            # Format version string (show multiple if they differ)
            if len(versions) == 1:
                version_str = versions[0]
            else:
                version_str = ", ".join(versions)

            # Format platforms string
            platforms_str = ", ".join(platforms)

            table.add_row(tool_name, version_str, platforms_str, updated_str)

        console.print(table)

    def print_with_missing(
        self,
        config: Config,
        condensed: bool = False,
        platform: str = None,
        architecture: str = None,
    ) -> None:
        """Show versions of installed tools and list missing tools defined in config.

        Args:
            config: Configuration containing tool definitions
            condensed: If True, show a condensed view with one line per tool
            platform: Filter by platform (e.g., 'linux', 'macos')
            architecture: Filter by architecture (e.g., 'amd64', 'arm64')

        """
        console = Console()

        if condensed:
            self.print_condensed(platform, architecture)
        else:
            self.print(platform, architecture)

        # Get all tools available for the specified platform/architecture
        available_tools = set(config.tools.keys())

        # Get all tools installed for the specified platform/architecture
        installed_keys = self.versions.keys()
        installed_tools = set()

        for key in installed_keys:
            tool, tool_platform, tool_arch = key.split("/")
            if platform and tool_platform != platform:
                continue
            if architecture and tool_arch != architecture:
                continue
            installed_tools.add(tool)

        missing_tools = [tool for tool in available_tools if tool not in installed_tools]

        if missing_tools:
            console.print("\n")

            missing_table = Table(title="Missing Tools (defined in config but not installed)")
            missing_table.add_column("Tool", style="cyan")
            missing_table.add_column("Repository", style="yellow")

            for tool in sorted(missing_tools):
                tool_config = config.tools[tool]
                missing_table.add_row(tool, tool_config.repo)

            console.print(missing_table)

            # Show install tip if there are missing tools
            platform_filter = f" --platform {platform}" if platform else ""
            arch_filter = f" --architecture {architecture}" if architecture else ""

            if platform or architecture:
                tip = f"\n[bold]Tip:[/] Run [cyan]dotbins sync{platform_filter}{arch_filter}[/] to install missing tools"
            else:
                tip = "\n[bold]Tip:[/] Run [cyan]dotbins sync[/] to install missing tools"

            console.print(tip)
