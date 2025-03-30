"""Version tracking for installed tools."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from typing import TYPE_CHECKING, Any, NamedTuple

from rich.console import Console
from rich.table import Table

from .utils import humanize_time_ago, log

if TYPE_CHECKING:
    from pathlib import Path

    from .config import Config


class _Spec(NamedTuple):
    name: str
    platform: str
    architecture: str

    @classmethod
    def from_key(cls, key: str) -> _Spec:
        """Create a _Spec from a key."""
        return cls(*key.split("/"))


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
        with self.version_file.open("w", encoding="utf-8") as f:
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
        sha256: str,
    ) -> None:
        """Update version info for a tool.

        Args:
            tool: Tool name
            platform: Platform (e.g., 'linux', 'macos')
            arch: Architecture (e.g., 'amd64', 'arm64')
            version: Version string
            sha256: SHA256 hash of the downloaded archive

        """
        key = f"{tool}/{platform}/{arch}"
        self.versions[key] = {
            "version": version,
            "updated_at": datetime.now().isoformat(),
            "sha256": sha256,
        }
        self.save()

    def _print_full(self, platform: str | None = None, architecture: str | None = None) -> None:
        """Show versions of installed tools in a formatted table.

        Args:
            platform: Filter by platform (e.g., 'linux', 'macos')
            architecture: Filter by architecture (e.g., 'amd64', 'arm64')

        """
        if not self.versions:
            log("No tool versions recorded yet.", "info")
            return

        console = Console()
        table = Table(title="✅ Installed Tool Versions")

        table.add_column("Tool", style="cyan")
        table.add_column("Platform", style="green")
        table.add_column("Architecture", style="green")
        table.add_column("Version", style="yellow")
        table.add_column("Last Updated", style="magenta")
        table.add_column("SHA256", style="dim")

        installed_tools = _installed_tools(self.versions, platform, architecture)
        if not installed_tools:
            log("No tools found for the specified filters.", "info")
            return

        for spec in installed_tools:
            info = self.get_tool_info(spec.name, spec.platform, spec.architecture)
            assert info is not None

            updated_str = humanize_time_ago(info["updated_at"])

            table.add_row(
                spec.name,
                spec.platform,
                spec.architecture,
                info["version"],
                updated_str,
                info["sha256"][:8],
            )

        console.print(table)

    def _print_compact(
        self,
        platform: str | None = None,
        architecture: str | None = None,
    ) -> None:
        """Show a compact view of installed tools with one line per tool.

        Args:
            platform: Filter by platform (e.g., 'linux', 'macos')
            architecture: Filter by architecture (e.g., 'amd64', 'arm64')

        """
        if not self.versions:
            log("No tool versions recorded yet.", "info")
            return

        tools = defaultdict(list)
        installed_tools = _installed_tools(self.versions, platform, architecture)

        for spec in installed_tools:
            info = self.get_tool_info(spec.name, spec.platform, spec.architecture)
            assert info is not None
            tools[spec.name].append(
                {
                    "platform": spec.platform,
                    "arch": spec.architecture,
                    "version": info["version"],
                    "updated_at": info["updated_at"],
                },
            )

        if not tools:
            log("No tools found for the specified filters.", "info")
            return

        console = Console()
        table = Table(title="✅ Installed Tools Summary")

        table.add_column("Tool", style="cyan")
        table.add_column("Version(s)", style="yellow")
        table.add_column("Platforms", style="green")
        table.add_column("Last Updated", style="magenta")

        for tool_name, instances in sorted(tools.items()):
            version_list = sorted({i["version"] for i in instances})
            platforms = sorted({f"{i['platform']}/{i['arch']}" for i in instances})
            latest_update = max(instances, key=lambda x: x["updated_at"])
            updated_str = humanize_time_ago(latest_update["updated_at"])
            version_str = version_list[0] if len(version_list) == 1 else ", ".join(version_list)
            platforms_str = ", ".join(platforms)
            table.add_row(tool_name, version_str, platforms_str, updated_str)

        console.print(table)

    def print(
        self,
        config: Config,
        compact: bool = False,
        platform: str | None = None,
        architecture: str | None = None,
    ) -> None:
        """Show versions of installed tools and list missing tools defined in config.

        Args:
            config: Configuration containing tool definitions
            compact: If True, show a compact view with one line per tool
            platform: Filter by platform (e.g., 'linux', 'macos')
            architecture: Filter by architecture (e.g., 'amd64', 'arm64')

        """
        console = Console()

        if compact:
            self._print_compact(platform, architecture)
        else:
            self._print_full(platform, architecture)

        expected_tools = _expected_tools(config, platform, architecture)
        installed_tools = _installed_tools(self.versions, platform, architecture)
        missing_tools = [tool for tool in expected_tools if tool not in installed_tools]

        if missing_tools:
            console.print("\n")

            missing_table = Table(title="❌ Missing Tools (defined in config but not installed)")
            missing_table.add_column("Tool", style="cyan")
            missing_table.add_column("Repository", style="yellow")
            missing_table.add_column("Platform", style="red")
            missing_table.add_column("Architecture", style="red")

            for name, _platform, _arch in sorted(missing_tools):
                tool_config = config.tools[name]
                missing_table.add_row(name, tool_config.repo, _platform, _arch)

            console.print(missing_table)

            platform_filter = f" --platform {platform}" if platform else ""
            arch_filter = f" --architecture {architecture}" if architecture else ""

            if platform or architecture:
                tip = f"\n[bold]Tip:[/] Run [cyan]dotbins sync{platform_filter}{arch_filter}[/] to install missing tools"
            else:
                tip = "\n[bold]Tip:[/] Run [cyan]dotbins sync[/] to install missing tools"

            console.print(tip)


def _filter_tools(
    tools: list[_Spec],
    platform: str | None = None,
    architecture: str | None = None,
) -> list[_Spec]:
    """Filter tools based on platform and architecture."""
    return [
        spec
        for spec in tools
        if (spec.platform == platform or platform is None)
        and (spec.architecture == architecture or architecture is None)
    ]


def _expected_tools(
    config: Config,
    platform: str | None = None,
    architecture: str | None = None,
) -> list[_Spec]:
    """Return a list of tools that are expected to be installed."""
    expected_tools = [
        _Spec(tool_name, platform, arch)
        for tool_name in config.tools
        for platform, architectures in config.platforms.items()
        for arch in architectures
    ]
    if platform or architecture:
        expected_tools = _filter_tools(expected_tools, platform, architecture)
    return expected_tools


def _installed_tools(
    versions: dict[str, Any],
    platform: str | None = None,
    architecture: str | None = None,
) -> list[_Spec]:
    """Return a list of tools that are installed."""
    installed_tools = [_Spec.from_key(key) for key in versions]
    if platform or architecture:
        installed_tools = _filter_tools(installed_tools, platform, architecture)
    return installed_tools
