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
    tools = config.get("tools", {})
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


if __name__ == "__main__":
    main()
