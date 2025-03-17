"""Binary detection utilities for dotbins.

Internal module for detecting and extracting binary files from archives.
"""

from __future__ import annotations

import os
import re
from pathlib import Path


def _is_definitely_not_exec(filename: str) -> bool:
    return bool(
        re.search(
            r"\.(txt|md|rst|json|yaml|yml|toml|ini|cfg|conf|html|css|js|py|sh|bash|zsh|fish"
            r"|rb|php|pl|lua|hs|cs|java|c|cpp|h|hpp|go|rs|ts|jsx|tsx|vue|svg|png|jpg|jpeg"
            r"|gif|webp|ico|woff|woff2|ttf|otf|eot|pdf|docx|xlsx|pptx|odt|ods|odp|log"
            r"|lock|sum|mod|d\.ts|map|gz\.asc|sha256|sig)$",
            filename.lower(),
        ),
    )


def _is_likely_exec(filename: str) -> bool:
    match = re.search(r"\.(exe|bin|appimage|run|out)$", filename.lower())
    return bool(match) or "." not in Path(filename).name


def _is_exec(filename: str, mode: int) -> bool:
    if _is_definitely_not_exec(filename):
        return False

    if mode & 0o111:
        return True

    return _is_likely_exec(filename)


def _binary_chooser(name: str, mode: int, target_name: str) -> tuple[bool, bool]:
    basename = Path(name).name

    is_direct = (
        basename in (target_name, f"{target_name}.exe", f"{target_name}.appimage")
    ) and _is_exec(name, mode)

    is_possible = _is_exec(name, mode)

    return is_direct, is_possible


def _substring_chooser(
    name: str,
    mode: int,
    substring: str,
) -> tuple[bool, bool]:
    basename = Path(name).name
    return False, substring.lower() in basename.lower() and _is_exec(name, mode)


def _find_best_binary_match(
    extracted_dir: Path,
    binary_name: str,
) -> Path | None:
    exact_matches = []
    bin_dir_matches = []
    substring_matches = []

    for root, _, files in os.walk(extracted_dir):
        for file in files:
            file_path = Path(root) / file
            rel_path = file_path.relative_to(extracted_dir)
            mode = file_path.stat().st_mode

            # Try exact match
            is_match, _ = _binary_chooser(str(rel_path), mode, binary_name)
            if is_match:
                exact_matches.append(rel_path)

            # Track bin directory matches
            if "bin/" in str(rel_path) and _is_exec(str(rel_path), mode):
                bin_dir_matches.append(rel_path)

            # Track substring matches
            _, is_match = _substring_chooser(str(rel_path), mode, binary_name)
            if is_match:
                substring_matches.append(rel_path)

    # Return results in order of preference
    exact_matches = sorted(exact_matches)
    if exact_matches:
        return exact_matches[0]

    bin_dir_matches = sorted(bin_dir_matches)
    if bin_dir_matches:
        # For bin_dir matches, prefer ones with the binary name in them
        named_matches = [p for p in bin_dir_matches if binary_name in p.name]
        if named_matches:
            return named_matches[0]
        return bin_dir_matches[0]

    substring_matches = sorted(substring_matches)
    if substring_matches:
        return substring_matches[0]

    return None


def auto_detect_binary_paths(extracted_dir: Path, binary_names: list[str]) -> list[str]:
    """Automatically detect binary paths for multiple binaries.

    Args:
        extracted_dir: Directory containing extracted files
        binary_names: List of binary names to find

    Returns:
        List of detected binary paths (relative to extracted_dir)

    """
    detected_paths = []

    for binary_name in binary_names:
        binary_path = _find_best_binary_match(extracted_dir, binary_name)
        if binary_path:
            detected_paths.append(str(binary_path))

    return detected_paths
