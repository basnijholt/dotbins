"""Tests for the summary module."""

from dotbins.summary import (
    FailedToolSummary,
    SkippedToolSummary,
    ToolSummaryBase,
    UpdatedToolSummary,
    UpdateSummary,
    display_update_summary,
)


def test_tool_summary_base() -> None:
    """Test the ToolSummaryBase dataclass."""
    summary = ToolSummaryBase(
        tool="test-tool",
        platform="linux",
        arch="amd64",
        version="1.0.0",
    )
    assert summary.tool == "test-tool"
    assert summary.platform == "linux"
    assert summary.arch == "amd64"
    assert summary.version == "1.0.0"


def test_updated_tool_summary() -> None:
    """Test the UpdatedToolSummary dataclass."""
    # Create summary with explicit timestamp
    fixed_timestamp = "2023-01-01T12:00:00"
    summary = UpdatedToolSummary(
        tool="test-tool",
        platform="linux",
        arch="amd64",
        version="1.0.0",
        old_version="0.9.0",
        timestamp=fixed_timestamp,
    )
    assert summary.tool == "test-tool"
    assert summary.platform == "linux"
    assert summary.arch == "amd64"
    assert summary.version == "1.0.0"
    assert summary.old_version == "0.9.0"
    assert summary.timestamp == fixed_timestamp
    # Test default values
    # Note: We can't easily test the auto-generated timestamp as it depends on current time


def test_skipped_tool_summary() -> None:
    """Test the SkippedToolSummary dataclass."""
    summary = SkippedToolSummary(
        tool="test-tool",
        platform="linux",
        arch="amd64",
        version="1.0.0",
        reason="Custom reason",
    )
    assert summary.tool == "test-tool"
    assert summary.platform == "linux"
    assert summary.arch == "amd64"
    assert summary.version == "1.0.0"
    assert summary.reason == "Custom reason"

    # Test default values
    summary = SkippedToolSummary(
        tool="test-tool",
        platform="linux",
        arch="amd64",
        version="1.0.0",
    )
    assert summary.reason == "Already up-to-date"


def test_failed_tool_summary() -> None:
    """Test the FailedToolSummary dataclass."""
    summary = FailedToolSummary(
        tool="test-tool",
        platform="linux",
        arch="amd64",
        version="1.0.0",
        reason="Custom error",
    )
    assert summary.tool == "test-tool"
    assert summary.platform == "linux"
    assert summary.arch == "amd64"
    assert summary.version == "1.0.0"
    assert summary.reason == "Custom error"

    # Test default values
    summary = FailedToolSummary(
        tool="test-tool",
        platform="linux",
        arch="amd64",
    )
    assert summary.version == "Unknown"
    assert summary.reason == "Unknown error"


def test_update_summary_creation() -> None:
    """Test creating an UpdateSummary."""
    summary = UpdateSummary()
    assert summary.updated == []
    assert summary.skipped == []
    assert summary.failed == []
    assert not summary.has_entries()


def test_update_summary_add_methods() -> None:
    """Test the add_* methods of UpdateSummary."""
    summary = UpdateSummary()

    # Add an updated tool
    summary.add_updated_tool(
        tool="tool1",
        platform="linux",
        arch="amd64",
        version="1.0.0",
        old_version="0.9.0",
    )
    assert len(summary.updated) == 1
    assert summary.updated[0].tool == "tool1"
    assert summary.updated[0].old_version == "0.9.0"

    # Add a skipped tool
    summary.add_skipped_tool(
        tool="tool2",
        platform="macos",
        arch="arm64",
        version="1.0.0",
        reason="Already installed",
    )
    assert len(summary.skipped) == 1
    assert summary.skipped[0].tool == "tool2"
    assert summary.skipped[0].reason == "Already installed"

    # Add a failed tool
    summary.add_failed_tool(
        tool="tool3",
        platform="linux",
        arch="arm64",
        version="0.9.0",
        reason="Download failed",
    )
    assert len(summary.failed) == 1
    assert summary.failed[0].tool == "tool3"
    assert summary.failed[0].reason == "Download failed"

    # Check has_entries
    assert summary.has_entries()

    display_update_summary(summary)


def test_update_summary_to_dict() -> None:
    """Test converting an UpdateSummary to a dictionary."""
    summary = UpdateSummary()
    summary.add_updated_tool(
        tool="tool1",
        platform="linux",
        arch="amd64",
        version="1.0.0",
        old_version="0.9.0",
    )
    summary.add_skipped_tool(
        tool="tool2",
        platform="macos",
        arch="arm64",
        version="1.0.0",
    )
    summary.add_failed_tool(
        tool="tool3",
        platform="linux",
        arch="arm64",
        version="0.9.0",
        reason="Download failed",
    )

    result = summary.to_dict()

    assert len(result["updated"]) == 1
    assert result["updated"][0]["tool"] == "tool1"
    assert result["updated"][0]["old_version"] == "0.9.0"

    assert len(result["skipped"]) == 1
    assert result["skipped"][0]["tool"] == "tool2"
    assert result["skipped"][0]["reason"] == "Already up-to-date"

    assert len(result["failed"]) == 1
    assert result["failed"][0]["tool"] == "tool3"
    assert result["failed"][0]["reason"] == "Download failed"


def test_update_summary_from_dict() -> None:
    """Test creating an UpdateSummary from a dictionary."""
    # Create a dictionary with the expected format
    summary_dict = {
        "updated": [
            {
                "tool": "tool1",
                "platform": "linux",
                "arch": "amd64",
                "version": "1.0.0",
                "old_version": "0.9.0",
            },
        ],
        "skipped": [
            {
                "tool": "tool2",
                "platform": "macos",
                "arch": "arm64",
                "version": "1.0.0",
                "reason": "Already installed",
            },
        ],
        "failed": [
            {
                "tool": "tool3",
                "platform": "linux",
                "arch": "arm64",
                "version": "0.9.0",
                "reason": "Download failed",
            },
        ],
    }

    summary = UpdateSummary.from_dict(summary_dict)

    assert len(summary.updated) == 1
    assert summary.updated[0].tool == "tool1"
    assert summary.updated[0].old_version == "0.9.0"

    assert len(summary.skipped) == 1
    assert summary.skipped[0].tool == "tool2"
    assert summary.skipped[0].reason == "Already installed"

    assert len(summary.failed) == 1
    assert summary.failed[0].tool == "tool3"
    assert summary.failed[0].reason == "Download failed"


def test_round_trip_conversion() -> None:
    """Test that to_dict and from_dict are inverse operations."""
    original = UpdateSummary()
    original.add_updated_tool("tool1", "linux", "amd64", "1.0.0", "0.9.0")
    original.add_skipped_tool("tool2", "macos", "arm64", "1.0.0", "Custom reason")
    original.add_failed_tool("tool3", "linux", "arm64", "0.9.0", "Download failed")

    dict_format = original.to_dict()
    reconstructed = UpdateSummary.from_dict(dict_format)

    # Check that the reconstructed summary has the same content
    assert len(reconstructed.updated) == len(original.updated)
    assert reconstructed.updated[0].tool == original.updated[0].tool
    assert reconstructed.updated[0].version == original.updated[0].version

    assert len(reconstructed.skipped) == len(original.skipped)
    assert reconstructed.skipped[0].tool == original.skipped[0].tool
    assert reconstructed.skipped[0].reason == original.skipped[0].reason

    assert len(reconstructed.failed) == len(original.failed)
    assert reconstructed.failed[0].tool == original.failed[0].tool
    assert reconstructed.failed[0].reason == original.failed[0].reason
