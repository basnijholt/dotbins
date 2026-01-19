#!/usr/bin/env python3
"""Documentation generation for dotbins.

Run this script to generate all documentation content:
    uv run python docs/docs_gen.py
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
README_PATH = REPO_ROOT / "README.md"


def readme_section(section_name: str, *, strip_heading: bool = True) -> str:
    """Extract a marked section from README.md.

    Sections are marked with HTML comments:
    <!-- SECTION:section_name:START -->
    content
    <!-- SECTION:section_name:END -->
    """
    content = README_PATH.read_text()

    start_marker = f"<!-- SECTION:{section_name}:START -->"
    end_marker = f"<!-- SECTION:{section_name}:END -->"

    start_idx = content.find(start_marker)
    if start_idx == -1:
        msg = f"Section '{section_name}' not found in README.md"
        raise ValueError(msg)

    end_idx = content.find(end_marker, start_idx)
    if end_idx == -1:
        msg = f"End marker for section '{section_name}' not found"
        raise ValueError(msg)

    section = content[start_idx + len(start_marker) : end_idx].strip()

    if strip_heading:
        section = re.sub(r"^#{1,3}\s+[^\n]+\n+", "", section, count=1)

    # Transform README links to docs links
    link_map = {
        "#zap-quick-start": "getting-started.md#quick-start",
        "#hammer_and_wrench-installation": "getting-started.md#installation",
        "#gear-configuration": "configuration.md",
        "#computer-shell-integration": "shell-integration.md",
        "#books-usage": "usage.md",
        "#bulb-examples": "usage.md#examples",
        "#wrench-troubleshooting": "troubleshooting.md",
        "#thinking-comparison-with-alternatives": "index.md#comparison-with-alternatives",
        "#heart-support-and-contributions": "index.md#support-and-contributions",
        "#star2-features": "index.md#features",
        "#bulb-why-i-created-dotbins": "index.md#why-i-created-dotbins",
    }
    for old_link, new_link in link_map.items():
        section = section.replace(f"]({old_link})", f"]({new_link})")

    return re.sub(r"\[\[ToC\]\([^)]+\)\]", "", section)


def main() -> int:
    """Generate all documentation content."""
    docs_dir = REPO_ROOT / "docs"
    files = list(docs_dir.glob("*.md")) + [README_PATH]

    # Set PYTHONPATH so markdown-code-runner can import this module
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{docs_dir}:{env.get('PYTHONPATH', '')}"

    print(f"Generating content for {len(files)} files...")
    for f in files:
        print(f"  {f.relative_to(REPO_ROOT)}")
        result = subprocess.run(
            ["markdown-code-runner", str(f)],
            env=env,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"    ERROR: {result.stderr}")
            return 1

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
