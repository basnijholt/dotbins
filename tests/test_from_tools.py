"""Tests based on tools defined in dotbins.yaml."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

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


@pytest.mark.parametrize(
    "key",
    ["repo", "binary_name"],
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
