#!/usr/bin/env python3
# ruff: noqa: S603, S607
"""Documentation generation utilities for dotbins.

Provides functions to extract sections from README.md and transform
content for the documentation site. Docs templates are stored with
placeholder OUTPUT sections and processed during CI build.

Usage:
    uv run python docs/docs_gen.py              # Generate docs (process in-place)
    uv run python docs/docs_gen.py --reset      # Reset docs to templates (placeholders)
    uv run python docs/docs_gen.py --verify     # Verify docs have placeholders
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

# Path to README relative to this module (docs_gen.py is in docs/)
_MODULE_DIR = Path(__file__).parent
README_PATH = _MODULE_DIR.parent / "README.md"

# Placeholder for OUTPUT sections in docs templates
# The marker is checked by verify_placeholders() to ensure we don't commit generated content
OUTPUT_PLACEHOLDER_MARKER = "<!-- PLACEHOLDER -->"
OUTPUT_PLACEHOLDER = (
    f"{OUTPUT_PLACEHOLDER_MARKER} "
    "Output is generated during CI build. We don't commit generated content "
    "to keep docs copyable and avoid recursion. See docs/docs_gen.py"
)


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

    Raises:
        ValueError: If the section is not found in README.md

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
        # Remove first heading (# or ## or ###)
        section = re.sub(r"^#{1,3}\s+[^\n]+\n+", "", section, count=1)

    return _transform_readme_links(section)


def _transform_readme_links(content: str) -> str:
    """Transform README internal links to docs site links."""
    # Map README anchors to doc pages
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

    # Remove ToC link pattern [[ToC](#...)]
    return re.sub(r"\[\[ToC\]\([^)]+\)\]", "", content)


def _find_markdown_files_with_code_blocks(docs_dir: Path) -> list[Path]:
    """Find all markdown files containing markdown-code-runner markers."""
    files_with_code = []
    for md_file in docs_dir.rglob("*.md"):
        content = md_file.read_text()
        if "<!-- CODE:START -->" in content:
            files_with_code.append(md_file)
    return sorted(files_with_code)


def _run_markdown_code_runner(files: list[Path], repo_root: Path) -> bool:
    """Run markdown-code-runner on all files. Returns True if all succeeded."""
    if not files:
        print("No files with CODE:START markers found.")
        return True

    print(f"Found {len(files)} file(s) with auto-generated content:")
    for f in files:
        print(f"  - {f.relative_to(repo_root)}")
    print()

    # Set PYTHONPATH to include docs/ so this module is importable
    env = os.environ.copy()
    python_path = env.get("PYTHONPATH", "")
    docs_dir = str(repo_root / "docs")
    env["PYTHONPATH"] = f"{docs_dir}:{python_path}" if python_path else docs_dir

    all_success = True
    for file in files:
        rel_path = file.relative_to(repo_root)
        print(f"Updating {rel_path}...", end=" ", flush=True)
        result = subprocess.run(
            ["markdown-code-runner", "--standardize", str(file)],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )
        if result.returncode == 0:
            print("OK")
        else:
            print("FAILED")
            print(f"  Error: {result.stderr}")
            all_success = False

    return all_success


def reset_output_sections(file_path: Path) -> bool:
    """Reset all OUTPUT sections in a file to contain only the placeholder.

    Returns True if the file was modified.
    """
    content = file_path.read_text()
    original = content

    # Pattern to match OUTPUT sections and replace their content with placeholder
    # Matches: <!-- OUTPUT:START -->\n...content...\n<!-- OUTPUT:END -->
    pattern = re.compile(
        r"(<!-- OUTPUT:START -->)\n.*?\n(<!-- OUTPUT:END -->)",
        re.DOTALL,
    )

    replacement = rf"\1\n{OUTPUT_PLACEHOLDER}\n\2"
    content = pattern.sub(replacement, content)

    if content != original:
        file_path.write_text(content)
        return True
    return False


def verify_placeholders(file_path: Path) -> list[int]:
    """Verify that all OUTPUT sections contain the placeholder.

    Ignores OUTPUT markers inside fenced code blocks (examples).
    Returns list of line numbers where violations occur.
    """
    content = file_path.read_text()
    lines = content.split("\n")
    violations = []

    in_fence = False
    in_output = False
    output_start_line = 0

    for i, line in enumerate(lines, 1):
        # Track fence boundaries (``` or ~~~)
        stripped = line.lstrip()
        if stripped.startswith(("```", "~~~")):
            in_fence = not in_fence
            continue

        # Skip content inside fences (code examples)
        if in_fence:
            continue

        if "<!-- OUTPUT:START -->" in line:
            in_output = True
            output_start_line = i
        elif "<!-- OUTPUT:END -->" in line:
            in_output = False
        elif in_output:
            # Check if this is the placeholder line
            if OUTPUT_PLACEHOLDER_MARKER in line:
                continue
            # Allow empty lines
            if not line.strip():
                continue
            # Any other content is a violation
            violations.append(output_start_line)
            # Skip to end of this output section
            in_output = False

    return violations


def cmd_generate(repo_root: Path, *, include_readme: bool = True) -> int:
    """Generate docs by running markdown-code-runner on all files."""
    files = _find_markdown_files_with_code_blocks(repo_root / "docs")

    if include_readme:
        readme = repo_root / "README.md"
        if readme.exists() and "<!-- CODE:START -->" in readme.read_text():
            files.append(readme)

    success = _run_markdown_code_runner(files, repo_root)
    return 0 if success else 1


def cmd_reset(repo_root: Path) -> int:
    """Reset docs OUTPUT sections to placeholders."""
    docs_dir = repo_root / "docs"
    files = _find_markdown_files_with_code_blocks(docs_dir)

    if not files:
        print("No docs files with CODE:START markers found.")
        return 0

    print(f"Resetting {len(files)} file(s) to templates:")
    modified_count = 0
    for f in files:
        rel_path = f.relative_to(repo_root)
        if reset_output_sections(f):
            print(f"  ✓ {rel_path}")
            modified_count += 1
        else:
            print(f"  - {rel_path} (no changes)")

    print(f"\nReset {modified_count} file(s) to templates.")
    return 0


def cmd_verify(repo_root: Path) -> int:
    """Verify docs have placeholders (no processed content committed)."""
    docs_dir = repo_root / "docs"
    files = _find_markdown_files_with_code_blocks(docs_dir)

    if not files:
        print("No docs files with CODE:START markers found.")
        return 0

    print(f"Verifying {len(files)} docs file(s) have placeholders...")
    all_valid = True

    for f in files:
        rel_path = f.relative_to(repo_root)
        violations = verify_placeholders(f)
        if violations:
            print(f"  ✗ {rel_path}: OUTPUT sections at lines {violations} have content")
            all_valid = False
        else:
            print(f"  ✓ {rel_path}")

    if all_valid:
        print("\nAll docs files have placeholder OUTPUT sections.")
        return 0
    print("\nError: Some docs files have processed content.")
    print("Run 'uv run python docs/docs_gen.py --reset' to fix.")
    return 1


def main() -> int:
    """Main entry point with subcommands."""
    parser = argparse.ArgumentParser(
        description="Documentation generation utilities for dotbins.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run python docs/docs_gen.py              # Generate docs (process in-place)
  uv run python docs/docs_gen.py --reset      # Reset docs to templates
  uv run python docs/docs_gen.py --verify     # Verify docs have placeholders
""",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset docs OUTPUT sections to placeholders",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify docs have placeholder OUTPUT sections",
    )
    parser.add_argument(
        "--docs-only",
        action="store_true",
        help="Only process docs, not README.md",
    )

    args = parser.parse_args()
    repo_root = _MODULE_DIR.parent

    if args.reset:
        return cmd_reset(repo_root)
    if args.verify:
        return cmd_verify(repo_root)
    return cmd_generate(repo_root, include_readme=not args.docs_only)


if __name__ == "__main__":
    sys.exit(main())
