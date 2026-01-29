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

import requests
import yaml

# Add parent directory to path so we can import dotbins
sys.path.insert(0, str(Path(__file__).parent.parent))
from dotbins.utils import _maybe_github_token_header

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


def main() -> None:
    """Download release JSONs for all tools in examples.yaml."""
    # Ensure release_jsons directory exists
    release_jsons_dir = Path(__file__).parent / "release_jsons"
    release_jsons_dir.mkdir(exist_ok=True)

    # Read examples.yaml
    examples_yaml = Path(__file__).parent.parent / "examples" / "examples.yaml"
    with open(examples_yaml) as f:
        config = yaml.safe_load(f)

    # Get GitHub token if available
    github_token = os.environ.get("GITHUB_TOKEN")
    headers = _maybe_github_token_header(github_token)

    # Process each tool
    tools = dict(config.get("tools", {}))
    tools.update(EXTRA_TOOLS)
    total = len(tools)

    print(f"Downloading release JSONs for {total} tools...")

    for i, (tool_name, value) in enumerate(tools.items(), 1):
        # Skip if already downloaded
        json_file = release_jsons_dir / f"{tool_name}.json"
        if json_file.exists():
            print(f"[{i}/{total}] Skipping {tool_name} (already downloaded)")
            continue

        # Get repo
        repo = value if isinstance(value, str) else value.get("repo")
        if not repo:
            print(f"[{i}/{total}] Skipping {tool_name} (no repo found)")
            continue

        # Fetch release info
        print(f"[{i}/{total}] Downloading {tool_name} from {repo}...")
        if "tag" in value:
            url = f"https://api.github.com/repos/{repo}/releases/tags/{value['tag']}"
        else:
            url = f"https://api.github.com/repos/{repo}/releases/latest"

        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            release_data = response.json()

            # Save to file
            with open(json_file, "w") as f:
                json.dump(release_data, f, indent=2)

            print(f"[{i}/{total}] Downloaded {tool_name}")
        except requests.RequestException as e:
            print(f"[{i}/{total}] Error downloading {tool_name}: {e}")

    print(f"\nDownloaded release JSONs to {release_jsons_dir}")

    # Download releases lists for tools that need tag_pattern testing
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
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            releases_data = response.json()

            with open(json_file, "w") as f:
                json.dump(releases_data, f, indent=2)

            print(f"Downloaded {tool_name}_releases.json ({len(releases_data)} releases)")
        except requests.RequestException as e:
            print(f"Error downloading releases for {tool_name}: {e}")


if __name__ == "__main__":
    main()
