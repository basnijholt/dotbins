#!/usr/bin/env python3
"""Helper functions for documentation generation.

Provides the readme_section() function used by markdown-code-runner
to extract sections from README.md into the documentation.
"""

from __future__ import annotations

import re
from pathlib import Path

# Path to README relative to this module (docs_gen.py is in docs/)
README_PATH = Path(__file__).parent.parent / "README.md"


def readme_section(section_name: str, *, strip_heading: bool = True) -> str:
    """Extract a marked section from README.md.

    Sections are marked with HTML comments:
    <!-- SECTION:section_name:START -->
    content
    <!-- SECTION:section_name:END -->

    Args:
        section_name: The name of the section to extract
        strip_heading: If True, remove the first heading from the section

    Returns:
        The content between the section markers

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

    return _transform_readme_links(section)


def _transform_readme_links(content: str) -> str:
    """Transform README internal links to docs site links."""
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
        content = content.replace(f"]({old_link})", f"]({new_link})")

    return re.sub(r"\[\[ToC\]\([^)]+\)\]", "", content)
