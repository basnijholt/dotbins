#!/usr/bin/env -S uv run
"""Script to download GitHub release JSONs for testing purposes.

This script will download the JSON from the latest GitHub release for each tool
listed in examples/examples.yaml and save it to tests/release_jsons/.
"""
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
from typing import Any

import requests
import yaml

# Add parent directory to path so we can import dotbins
sys.path.insert(0, str(Path(__file__).parent.parent))
from dotbins.utils import _maybe_github_token_header, fetch_release_info

# Extra repos that power tests but are not part of the public examples file.
EXTRA_TOOLS = {
    "bun": {"repo": "oven-sh/bun"},
    "codex": {"repo": "openai/codex"},
    "keychain": {"repo": "funtoo/keychain", "tag": "2.9.2"},
}

# Tools that need the full releases list (for testing tag_pattern filtering).
# These repos release multiple products from the same repository.
RELEASES_LIST_TOOLS = {
    "bw": {"repo": "bitwarden/clients", "per_page": 30},
}


def _download_tool_release(
    tool_name: str,
    value: str | dict[str, Any],
    release_jsons_dir: Path,
    github_token: str | None,
    index: int,
    total: int,
) -> None:
    json_file = release_jsons_dir / f"{tool_name}.json"
    if json_file.exists():
        print(f"[{index}/{total}] Skipping {tool_name} (already downloaded)")
        return

    repo = value if isinstance(value, str) else value.get("repo")
    if not repo:
        print(f"[{index}/{total}] Skipping {tool_name} (no repo found)")
        return

    tag = value.get("tag") if isinstance(value, dict) else None
    tag_pattern = value.get("tag_pattern") if isinstance(value, dict) else None

    print(f"[{index}/{total}] Downloading {tool_name} from {repo}...")
    try:
        release_data = fetch_release_info(
            repo=repo,
            tag=tag,
            tag_pattern=tag_pattern,
            github_token=github_token,
        )
        with open(json_file, "w") as f:
            json.dump(release_data, f, indent=2)
        print(f"[{index}/{total}] Downloaded {tool_name}")
    except (requests.RequestException, RuntimeError) as e:
        print(f"[{index}/{total}] Error downloading {tool_name}: {e}")


def _download_releases_lists(
    release_jsons_dir: Path,
    headers: dict[str, str],
) -> None:
    print(f"\nDownloading releases lists for {len(RELEASES_LIST_TOOLS)} tools...")
    for tool_name, tool_cfg in RELEASES_LIST_TOOLS.items():
        json_file = release_jsons_dir / f"{tool_name}_releases.json"
        if json_file.exists():
            print(f"Skipping {tool_name}_releases.json (already downloaded)")
            continue

        repo = tool_cfg["repo"]
        per_page = tool_cfg.get("per_page", 30)
        url = f"https://api.github.com/repos/{repo}/releases?per_page={per_page}"

        print(f"Downloading releases list for {tool_name} from {repo}...")
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            releases_data = response.json()

            with open(json_file, "w") as f:
                json.dump(releases_data, f, indent=2)

            print(f"Downloaded {tool_name}_releases.json ({len(releases_data)} releases)")
        except requests.RequestException as e:
            print(f"Error downloading releases for {tool_name}: {e}")


def main() -> None:
    """Download release JSONs for all tools in examples.yaml."""
    release_jsons_dir = Path(__file__).parent / "release_jsons"
    release_jsons_dir.mkdir(exist_ok=True)

    examples_yaml = Path(__file__).parent.parent / "examples" / "examples.yaml"
    with open(examples_yaml) as f:
        config = yaml.safe_load(f)

    github_token = os.environ.get("GITHUB_TOKEN")
    headers = _maybe_github_token_header(github_token)

    tools: dict[str, Any] = dict(config.get("tools", {}))
    tools.update(EXTRA_TOOLS)
    total = len(tools)

    print(f"Downloading release JSONs for {total} tools...")
    for i, (tool_name, value) in enumerate(tools.items(), 1):
        _download_tool_release(tool_name, value, release_jsons_dir, github_token, i, total)

    print(f"\nDownloaded release JSONs to {release_jsons_dir}")
    _download_releases_lists(release_jsons_dir, headers)


if __name__ == "__main__":
    main()
