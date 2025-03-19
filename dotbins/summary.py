"""Dataclasses for representing tool update summaries."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


def _get_current_timestamp() -> str:
    """Get the current timestamp in ISO format.

    This function is used to allow for mocking in tests.
    """
    return datetime.now().isoformat()


@dataclass
class ToolSummaryBase:
    """Base dataclass for tool summary information."""

    tool: str
    platform: str
    arch: str
    version: str


@dataclass
class UpdatedToolSummary(ToolSummaryBase):
    """Summary information for an updated tool."""

    old_version: str = "none"
    timestamp: str = field(default_factory=_get_current_timestamp)


@dataclass
class SkippedToolSummary(ToolSummaryBase):
    """Summary information for a skipped tool."""

    reason: str = "Already up-to-date"


@dataclass
class FailedToolSummary(ToolSummaryBase):
    """Summary information for a failed tool."""

    version: str = "Unknown"
    reason: str = "Unknown error"


@dataclass
class UpdateSummary:
    """Complete summary of a tool update operation."""

    updated: list[UpdatedToolSummary] = field(default_factory=list)
    skipped: list[SkippedToolSummary] = field(default_factory=list)
    failed: list[FailedToolSummary] = field(default_factory=list)

    def to_dict(self) -> dict[str, list[dict[str, str]]]:
        """Convert the summary to a dictionary format for backward compatibility."""
        return {
            "updated": [self._tool_to_dict(item) for item in self.updated],
            "skipped": [self._tool_to_dict(item) for item in self.skipped],
            "failed": [self._tool_to_dict(item) for item in self.failed],
        }

    @staticmethod
    def _tool_to_dict(tool: ToolSummaryBase) -> dict[str, str]:
        """Convert a tool summary dataclass to a dictionary."""
        result = {
            "tool": tool.tool,
            "platform": tool.platform,
            "arch": tool.arch,
            "version": tool.version,
        }

        if isinstance(tool, UpdatedToolSummary):
            result["old_version"] = tool.old_version

        if isinstance(tool, (SkippedToolSummary, FailedToolSummary)):
            result["reason"] = tool.reason

        return result

    @classmethod
    def from_dict(cls, summary_dict: dict[str, list[dict[str, str]]]) -> UpdateSummary:
        """Create an UpdateSummary from a dictionary format."""
        summary = cls()

        for item in summary_dict.get("updated", []):
            summary.updated.append(
                UpdatedToolSummary(
                    tool=item["tool"],
                    platform=item["platform"],
                    arch=item["arch"],
                    version=item["version"],
                    old_version=item.get("old_version", "none"),
                ),
            )

        for item in summary_dict.get("skipped", []):
            summary.skipped.append(
                SkippedToolSummary(
                    tool=item["tool"],
                    platform=item["platform"],
                    arch=item["arch"],
                    version=item["version"],
                    reason=item.get("reason", "Already up-to-date"),
                ),
            )

        for item in summary_dict.get("failed", []):
            summary.failed.append(
                FailedToolSummary(
                    tool=item["tool"],
                    platform=item["platform"],
                    arch=item["arch"],
                    version=item.get("version", "Unknown"),
                    reason=item.get("reason", "Unknown error"),
                ),
            )

        return summary

    def add_updated_tool(
        self,
        tool: str,
        platform: str,
        arch: str,
        version: str,
        old_version: str = "none",
    ) -> None:
        """Add an updated tool to the summary."""
        self.updated.append(
            UpdatedToolSummary(
                tool=tool,
                platform=platform,
                arch=arch,
                version=version,
                old_version=old_version,
            ),
        )

    def add_skipped_tool(
        self,
        tool: str,
        platform: str,
        arch: str,
        version: str,
        reason: str = "Already up-to-date",
    ) -> None:
        """Add a skipped tool to the summary."""
        self.skipped.append(
            SkippedToolSummary(
                tool=tool,
                platform=platform,
                arch=arch,
                version=version,
                reason=reason,
            ),
        )

    def add_failed_tool(
        self,
        tool: str,
        platform: str,
        arch: str,
        version: str = "Unknown",
        reason: str = "Unknown error",
    ) -> None:
        """Add a failed tool to the summary."""
        self.failed.append(
            FailedToolSummary(
                tool=tool,
                platform=platform,
                arch=arch,
                version=version,
                reason=reason,
            ),
        )

    def has_entries(self) -> bool:
        """Check if the summary has any entries."""
        return bool(self.updated or self.skipped or self.failed)


def display_update_summary(summary: UpdateSummary) -> None:
    """Display a summary table of the update results using Rich.

    Args:
        summary: An UpdateSummary object with information about updated, failed, and skipped tools

    """
    from rich.console import Console
    from rich.table import Table

    console = Console()

    console.print("\n[bold]📊 Update Summary[/bold]\n")

    # Table for updated tools
    if summary.updated:
        table = Table(title="✅ Updated Tools")
        table.add_column("Tool", style="cyan")
        table.add_column("Platform", style="blue")
        table.add_column("Architecture", style="blue")
        table.add_column("Old Version", style="yellow")
        table.add_column("New Version", style="green")

        for updated_item in summary.updated:
            table.add_row(
                updated_item.tool,
                updated_item.platform,
                updated_item.arch,
                updated_item.old_version,
                updated_item.version,
            )

        console.print(table)
        console.print("")

    # Table for failed tools
    if summary.failed:
        table = Table(title="❌ Failed Updates")
        table.add_column("Tool", style="cyan")
        table.add_column("Platform", style="blue")
        table.add_column("Architecture", style="blue")
        table.add_column("Version", style="yellow")
        table.add_column("Reason", style="red")

        for failed_item in summary.failed:
            table.add_row(
                failed_item.tool,
                failed_item.platform,
                failed_item.arch,
                failed_item.version,
                failed_item.reason,
            )

        console.print(table)
        console.print("")

    # Table for skipped tools
    if summary.skipped:
        table = Table(title="⏭️ Skipped Tools")
        table.add_column("Tool", style="cyan")
        table.add_column("Platform", style="blue")
        table.add_column("Architecture", style="blue")
        table.add_column("Version", style="green")
        table.add_column("Reason", style="yellow")

        for skipped_item in summary.skipped:
            table.add_row(
                skipped_item.tool,
                skipped_item.platform,
                skipped_item.arch,
                skipped_item.version,
                skipped_item.reason,
            )

        console.print(table)

    console.print("")
