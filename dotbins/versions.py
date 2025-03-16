"""Version tracking for installed tools."""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import TYPE_CHECKING, Any

from .utils import log

if TYPE_CHECKING:
    from pathlib import Path


class VersionStore:
    """Manages version information for installed tools.

    This class tracks which versions of each tool are installed for each platform
    and architecture combination, along with timestamps of when they were last updated.
    This information is used to:

    1. Determine when updates are available
    2. Avoid unnecessary downloads of the same version
    3. Provide information about the installed tools through the 'versions' command
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
            with open(self.version_file) as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}

    def save(self) -> None:
        """Save version data to JSON file."""
        os.makedirs(self.version_file.parent, exist_ok=True)
        with open(self.version_file, "w") as f:
            json.dump(self.versions, f, indent=2)

    def get_tool_info(
        self,
        tool: str,
        platform: str,
        arch: str,
    ) -> dict[str, Any] | None:
        """Get version info for a specific tool/platform/arch combination."""
        key = f"{tool}/{platform}/{arch}"
        return self.versions.get(key)

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

    def print(self) -> None:
        """Show versions of installed tools."""
        versions = self.list_all()

        if not versions:
            log("No tool versions recorded yet.", "info")
            return

        log("Installed tool versions:", "info", "📋")
        for key, info in versions.items():
            tool, platform, arch = key.split("/")
            sha256_info = f" [SHA256: {info.get('sha256', 'N/A')}]" if info.get("sha256") else ""
            log(
                f"  {tool} ({platform}/{arch}): {info['version']} - Updated on {info['updated_at']}{sha256_info}",
                "success",
            )
