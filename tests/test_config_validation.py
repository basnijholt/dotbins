"""Tests for the config validation."""

from dotbins.config import DotbinsConfig, ToolConfig


def test_validate_unknown_architecture() -> None:
    """Test validation when an unknown architecture is specified in asset_patterns."""
    # Create a config with a tool that has an unknown architecture in asset_patterns
    config = DotbinsConfig(
        platforms={"linux": ["amd64", "arm64"]},
        tools={
            "test-tool": ToolConfig(
                repo="test/repo",
                binary_name="test-tool",
                binary_path="test-tool",
                asset_patterns={
                    "linux": {
                        "unknown_arch": "test-{version}-linux_unknown.tar.gz",
                    },
                },
            ),
        },
    )

    # This should not raise an exception but should log a warning
    config.validate()
