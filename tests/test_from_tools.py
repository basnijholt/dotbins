"""Tests that analyze tools defined in tools.yaml and compare with existing configuration."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import requests
import yaml

from dotbins.analyze import generate_tool_configuration
from dotbins.download import download_file, find_asset
from dotbins.utils import get_latest_release

TOOLS = ["fzf", "bat", "eza", "zoxide", "uv"]


@pytest.fixture
def ensure_bin_dir() -> Path:
    """Ensure the tests/bin directory exists."""
    bin_dir = Path(__file__).parent / "bin"
    bin_dir.mkdir(exist_ok=True)
    return bin_dir


@pytest.fixture
def tools_config() -> dict[str, Any]:
    """Load tools configuration from tools.yaml."""
    script_dir = Path(__file__).parent.parent
    tools_yaml_path = script_dir / "tools.yaml"

    with open(tools_yaml_path) as f:
        config = yaml.safe_load(f)

    return config.get("tools", {})


def find_and_download_asset(
    tool_name: str,
    tool_config: dict[str, Any],
    bin_dir: Path,
) -> tuple[Path | None, dict[str, Any] | None]:
    """Find and download an appropriate asset for a tool.

    Returns
    -------
        Tuple containing the path to the downloaded asset and the release info (or None if failed)

    """
    tool_path = bin_dir / f"{tool_name}.tar.gz"

    # Skip if already downloaded
    if tool_path.exists():
        logging.info("Using existing downloaded asset for %s", tool_name)
        return tool_path, None

    repo = tool_config.get("repo")
    if not repo:
        logging.info("Skipping %s - no repo defined", tool_name)
        return None, None

    try:
        # Get latest release info
        release = get_latest_release(repo)

        # Find an appropriate asset
        asset = find_matching_asset(tool_config, release)

        if asset:
            logging.info("Downloading %s for %s", asset["name"], tool_name)
            download_file(asset["browser_download_url"], str(tool_path))
            return tool_path, release
        logging.info("No suitable asset found for %s", tool_name)
        return None, release  # noqa: TRY300

    except requests.exceptions.RequestException:
        logging.exception("Error downloading %s", tool_name)
        return None, None


def find_matching_asset(
    tool_config: dict[str, Any],
    release: dict[str, Any],
) -> dict[str, Any] | None:
    """Find an asset that matches the tool configuration."""
    asset = None
    version = release["tag_name"].lstrip("v")

    # Try asset_patterns
    if "asset_patterns" in tool_config:
        # If asset_patterns is a dictionary
        if (
            isinstance(tool_config["asset_patterns"], dict)
            and "linux" in tool_config["asset_patterns"]
        ):
            pattern = tool_config["asset_patterns"]["linux"]
            if pattern:
                search_pattern = pattern.format(
                    version=version,
                    platform="linux",
                    arch="x86_64",
                )
                asset = find_asset(release["assets"], search_pattern)
        # If asset_patterns is a string (global pattern)
        elif isinstance(tool_config["asset_patterns"], str):
            pattern = tool_config["asset_patterns"]
            search_pattern = pattern.format(
                version=version,
                platform="linux",
                arch="x86_64",
            )
            asset = find_asset(release["assets"], search_pattern)

    # Fallback to generic Linux asset
    if not asset:
        for a in release["assets"]:
            if (
                "linux" in a["name"].lower()
                and ("x86_64" in a["name"] or "amd64" in a["name"])
                and a["name"].endswith((".tar.gz", ".tgz", ".zip"))
            ):
                asset = a
                break

    return asset


def analyze_tool_with_dotbins(repo: str, tool_name: str) -> dict:
    """Run the analyze function and return the suggested configuration."""
    try:
        # Get the release first
        release = get_latest_release(repo)
        # Use the release in the configuration generation
        return generate_tool_configuration(repo, tool_name, release)
    except Exception:
        logging.exception("Error analyzing %s", tool_name)
        return {}


def compare_configs(existing: dict, suggested: dict) -> list[str]:
    """Compare existing and suggested configurations and return differences."""
    differences = []

    # Compare basic properties
    for key in ["repo", "extract_binary", "binary_name"]:
        if key in existing and key in suggested and existing[key] != suggested[key]:
            differences.append(  # noqa: PERF401
                f"{key}: existing='{existing[key]}', suggested='{suggested[key]}'",
            )

    # Compare binary_path (allowing for some variation)
    if "binary_path" in existing and "binary_path" in suggested:
        existing_path = existing["binary_path"]
        suggested_path = suggested["binary_path"]
        if existing_path != suggested_path:
            differences.append(
                f"binary_path: existing='{existing_path}', suggested='{suggested_path}'",
            )

    # Compare asset patterns
    if "asset_patterns" in existing and "asset_patterns" in suggested:
        # If both are dictionaries
        if isinstance(existing["asset_patterns"], dict) and isinstance(
            suggested["asset_patterns"],
            dict,
        ):
            for platform in ["linux", "macos"]:
                existing_pattern = existing["asset_patterns"].get(platform)
                suggested_pattern = suggested["asset_patterns"].get(platform)
                if existing_pattern != suggested_pattern:
                    differences.append(
                        f"asset_patterns[{platform}]: existing='{existing_pattern}', suggested='{suggested_pattern}'",
                    )
        # If both are strings
        elif isinstance(existing["asset_patterns"], str) and isinstance(
            suggested["asset_patterns"],
            str,
        ):
            if existing["asset_patterns"] != suggested["asset_patterns"]:
                differences.append(
                    f"asset_patterns: existing='{existing['asset_patterns']}', suggested='{suggested['asset_patterns']}'",
                )
        # If formats are different
        else:
            differences.append(
                "Config format different: existing and suggested asset_patterns have different formats (string vs dict)",
            )

    return differences


@pytest.mark.parametrize("tool_name", TOOLS)
def test_tool_has_repo_defined(tools_config: dict, tool_name: str) -> None:
    """Test that each tool has a repository defined."""
    assert tool_name in tools_config, f"Tool {tool_name} not found in configuration"

    tool_config = tools_config[tool_name]
    assert "repo" in tool_config, f"Tool {tool_name} has no repository defined"
    assert tool_config["repo"], f"Tool {tool_name} has empty repository value"

    # Validate repo format (owner/repo)
    assert re.match(
        r"^[^/]+/[^/]+$",
        tool_config["repo"],
    ), f"Tool {tool_name} repo '{tool_config['repo']}' is not in owner/repo format"


# Mock the GitHub API call to ensure tests pass consistently
@pytest.mark.parametrize("tool_name", TOOLS)
@patch("dotbins.utils.get_latest_release")
def test_config_generation_with_mocked_release(
    mock_get_latest_release: Any,
    tools_config: dict,
    tool_name: str,
) -> None:
    """Test config generation using mocked GitHub release data."""
    tool_config = tools_config[tool_name]
    repo = tool_config["repo"]

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
    suggested_config = generate_tool_configuration(
        repo,
        tool_name,
        mock_release,
    )

    # Verify basic structure (not comparing to existing since we're using mock data)
    assert suggested_config, f"No configuration generated for {tool_name}"
    assert "repo" in suggested_config
    assert suggested_config["repo"] == repo
    assert "extract_binary" in suggested_config
    assert "binary_name" in suggested_config
    assert suggested_config["binary_name"] == tool_name


@pytest.mark.parametrize(
    "key",
    ["repo", "extract_binary", "binary_name", "binary_path"],
)
@pytest.mark.parametrize("tool_name", TOOLS)
def test_tool_config_has_required_fields(
    tools_config: dict,
    tool_name: str,
    key: str,
) -> None:
    """Test that each tool configuration has the required fields."""
    tool_config = tools_config[tool_name]
    assert key in tool_config, f"Tool {tool_name} missing required field '{key}'"

    # For repo field, validate it's not empty
    if key == "repo":
        assert tool_config[key], f"Tool {tool_name} has empty '{key}' field"


@pytest.mark.parametrize("tool_name", TOOLS)
def test_tool_config_has_asset_pattern(tools_config: dict, tool_name: str) -> None:
    """Test that each tool configuration has asset_patterns."""
    tool_config = tools_config[tool_name]

    assert (
        "asset_patterns" in tool_config
    ), f"Tool {tool_name} is missing 'asset_patterns'"

    # Make sure asset_patterns is not empty
    if isinstance(tool_config["asset_patterns"], dict):
        assert any(
            tool_config["asset_patterns"].values(),
        ), f"Tool {tool_name} has empty asset_patterns dictionary"
    elif isinstance(tool_config["asset_patterns"], str):
        assert tool_config[
            "asset_patterns"
        ], f"Tool {tool_name} has empty asset_patterns string"
