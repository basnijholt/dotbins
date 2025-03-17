"""Tests that analyze tools defined in dotbins.yaml and compare with existing configuration."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest

from dotbins.analyze import generate_tool_configuration
from dotbins.config import Config

if TYPE_CHECKING:
    from dotbins.config import ToolConfig

TOOLS = ["fzf", "bat", "eza", "zoxide", "uv"]


@pytest.fixture
def tools_config() -> dict[str, ToolConfig]:
    """Load tools configuration from dotbins.yaml."""
    script_dir = Path(__file__).parent.parent
    tools_yaml_path = script_dir / "dotbins.yaml"

    config = Config.from_file(tools_yaml_path)
    return config.tools


@pytest.mark.parametrize("tool_name", TOOLS)
def test_tool_has_repo_defined(
    tools_config: dict[str, ToolConfig],
    tool_name: str,
) -> None:
    """Test that each tool has a repository defined."""
    assert tool_name in tools_config, f"Tool {tool_name} not found in configuration"

    tool_config = tools_config[tool_name]
    assert tool_config.repo, f"Tool {tool_name} has empty repository value"

    # Validate repo format (owner/repo)
    assert re.match(
        r"^[^/]+/[^/]+$",
        tool_config.repo,
    ), f"Tool {tool_name} repo '{tool_config.repo}' is not in owner/repo format"


# Mock the GitHub API call to ensure tests pass consistently
@pytest.mark.parametrize("tool_name", TOOLS)
@patch("dotbins.utils.latest_release_info")
def test_config_generation_with_mocked_release(
    mock_get_latest_release: Any,
    tools_config: dict[str, ToolConfig],
    tool_name: str,
) -> None:
    """Test config generation using mocked GitHub release data."""
    tool_config = tools_config[tool_name]
    repo = tool_config.repo

    # Create a mock release based on the tool config
    mock_release = {
        "tag_name": "v1.0.0",
        "name": f"{tool_name} 1.0.0",
        "assets": [
            {
                "name": f"{tool_name}-1.0.0-linux_amd64.tar.gz",
                "browser_download_url": f"https://example.com/{tool_name}-1.0.0-linux_amd64.tar.gz",
            },
            {
                "name": f"{tool_name}-1.0.0-darwin_amd64.tar.gz",
                "browser_download_url": f"https://example.com/{tool_name}-1.0.0-darwin_amd64.tar.gz",
            },
        ],
    }

    mock_get_latest_release.return_value = mock_release

    # Generate the suggested config
    suggested_config = generate_tool_configuration(repo, tool_name, mock_release)

    # Verify basic structure (not comparing to existing since we're using mock data)
    assert suggested_config, f"No configuration generated for {tool_name}"
    assert suggested_config.repo == repo
    assert suggested_config.extract_binary
    assert suggested_config.binary_name
    assert suggested_config.binary_name == [tool_name]


@pytest.mark.parametrize(
    "key",
    ["repo", "extract_binary", "binary_name"],
)
@pytest.mark.parametrize("tool_name", TOOLS)
def test_tool_config_has_required_fields(
    tools_config: dict[str, ToolConfig],
    tool_name: str,
    key: str,
) -> None:
    """Test that each tool configuration has the required fields."""
    tool_config = tools_config[tool_name]
    assert getattr(tool_config, key)
    assert tool_config.repo


@pytest.mark.parametrize("tool_name", TOOLS)
def test_tool_config_has_asset_pattern(
    tools_config: dict[str, ToolConfig],
    tool_name: str,
) -> None:
    """Test that each tool configuration has asset_patterns."""
    tool_config = tools_config[tool_name]
    assert tool_config.asset_patterns
    assert any(tool_config.asset_patterns.values())
