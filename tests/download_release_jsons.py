#!/usr/bin/env -S uv run
"""Script to download GitHub release JSONs for testing purposes.

This script will download the JSON from the latest GitHub release for each tool
listed in examples/examples.yaml and save it to tests/release_jsons/.
"""

from __future__ import annotations

# /// script
# dependencies = [
#   "requests",
#   "pyyaml",
#   "dotbins",
# ]
# ///
import json
import os
import sys
from pathlib import Path

import requests
import yaml

# Add parent directory to path so we can import dotbins
sys.path.insert(0, str(Path(__file__).parent.parent))

# Extra repos that power tests but are not part of the public examples file.
EXTRA_TOOLS = {
    "bun": {"repo": "oven-sh/bun"},
    "codex": {"repo": "openai/codex"},
    "bw": {"repo": "bitwarden/clients"},
}

# Tools that need the full releases list (for testing tag_pattern filtering).
# These repos release multiple products from the same repository.
RELEASES_LIST_TOOLS = {
    "bw": {"repo": "bitwarden/clients", "per_page": 30},
}


def _release_jsons_dir() -> Path:
    """Return the directory used to store cached release JSONs."""
    release_jsons_dir = Path(__file__).parent / "release_jsons"
    release_jsons_dir.mkdir(exist_ok=True)
    return release_jsons_dir


def _load_tools() -> dict[str, str | dict[str, str]]:
    """Load tool definitions from examples.yaml plus test-only extras."""
    examples_yaml = Path(__file__).parent.parent / "examples" / "examples.yaml"
    with open(examples_yaml) as f:
        config = yaml.safe_load(f)

    tools = dict(config.get("tools", {}))
    tools.update(EXTRA_TOOLS)
    return tools


def _github_headers() -> dict[str, str]:
    """Build GitHub headers using the optional token from the environment."""
    from dotbins.utils import _maybe_github_token_header

    github_token = os.environ.get("GITHUB_TOKEN")
    return _maybe_github_token_header(github_token)


def _download_json(url: str, destination: Path, headers: dict[str, str]) -> list | dict:
    """Fetch JSON data and write it to disk."""
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    data = response.json()

    with open(destination, "w") as f:
        json.dump(data, f, indent=2)

    return data


def _download_tool_release_jsons(
    release_jsons_dir: Path,
    tools: dict[str, str | dict[str, str]],
    headers: dict[str, str],
) -> None:
    """Download latest-release JSON blobs for each configured tool."""
    total = len(tools)
    print(f"Downloading release JSONs for {total} tools...")

    for i, (tool_name, value) in enumerate(tools.items(), 1):
        json_file = release_jsons_dir / f"{tool_name}.json"
        if json_file.exists():
            print(f"[{i}/{total}] Skipping {tool_name} (already downloaded)")
            continue

        repo = value if isinstance(value, str) else value.get("repo")
        if not repo:
            print(f"[{i}/{total}] Skipping {tool_name} (no repo found)")
            continue

        print(f"[{i}/{total}] Downloading {tool_name} from {repo}...")
        url = (
            f"https://api.github.com/repos/{repo}/releases/tags/{value['tag']}"
            if isinstance(value, dict) and "tag" in value
            else f"https://api.github.com/repos/{repo}/releases/latest"
        )

        try:
            _download_json(url, json_file, headers)
            print(f"[{i}/{total}] Downloaded {tool_name}")
        except requests.RequestException as e:
            print(f"[{i}/{total}] Error downloading {tool_name}: {e}")


def _download_release_lists(release_jsons_dir: Path, headers: dict[str, str]) -> None:
    """Download full release lists for repos that need tag-pattern tests."""
    print(f"\nDownloading releases lists for {len(RELEASES_LIST_TOOLS)} tools...")
    for tool_name, config in RELEASES_LIST_TOOLS.items():
        json_file = release_jsons_dir / f"{tool_name}_releases.json"
        if json_file.exists():
            print(f"Skipping {tool_name}_releases.json (already downloaded)")
            continue

        repo = config["repo"]
        per_page = config.get("per_page", 30)
        url = f"https://api.github.com/repos/{repo}/releases?per_page={per_page}"

        print(f"Downloading releases list for {tool_name} from {repo}...")
        try:
            releases_data = _download_json(url, json_file, headers)
            print(f"Downloaded {tool_name}_releases.json ({len(releases_data)} releases)")
        except requests.RequestException as e:
            print(f"Error downloading releases for {tool_name}: {e}")


def main() -> None:
    """Download release JSONs for all tools in examples.yaml."""
    release_jsons_dir = _release_jsons_dir()
    tools = _load_tools()
    headers = _github_headers()

    _download_tool_release_jsons(release_jsons_dir, tools, headers)
    print(f"\nDownloaded release JSONs to {release_jsons_dir}")
    _download_release_lists(release_jsons_dir, headers)


if __name__ == "__main__":
    main()
