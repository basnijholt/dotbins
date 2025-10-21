"""Windows-specific regression test for skip_download (.exe handling)."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from dotbins.config import Config, build_tool_config

if TYPE_CHECKING:  # pragma: no cover - type-only import for linters
    from pathlib import Path


@pytest.mark.skipif(os.name != "nt", reason="Windows-only regression test")
def test_skip_download_respects_exe_extension_on_windows(tmp_path: Path) -> None:
    """Assert skip_download respects `.exe` on Windows.

    On Windows, installed binaries typically have a `.exe` extension. Currently,
    `BinSpec.skip_download` checks only for plain `binary_name` and misses
    `binary_name.exe`, causing unnecessary re-downloads.

    Expected: when `win-tool.exe` exists and the recorded tag matches, the
    method returns True. On Windows CI, this should fail prior to the fix.
    """
    tool_name = "win-tool"

    tool_config = build_tool_config(
        tool_name=tool_name,
        raw_data={
            "repo": "owner/repo",
            "binary_name": tool_name,
            # Not used by skip_download, but set for completeness
            "path_in_archive": tool_name,
        },
    )

    # Provide release info so bin_spec.latest_tag works
    tool_config._release_info = {"tag_name": "v1.2.3", "assets": []}

    config = Config(
        tools_dir=tmp_path,
        tools={tool_name: tool_config},
        platforms={"windows": ["amd64"]},
    )

    # Simulate an installed Windows binary: win-tool.exe
    dest_dir = config.bin_dir("windows", "amd64", create=True)
    exe_path = dest_dir / f"{tool_name}.exe"
    exe_path.write_text("dummy")

    # Record the installed tag so skip_download can compare
    config.manifest.update_tool_info(
        tool_name,
        "windows",
        "amd64",
        "v1.2.3",
        "sha256",
        url="https://example.com/owner/repo/download/v1.2.3/win-tool.zip",
    )

    # Build the spec and check the skip logic
    bin_spec = tool_config.bin_spec("amd64", "windows")

    # Expected: True (skip download) because win-tool.exe exists and tag matches
    assert bin_spec.skip_download(config, force=False) is True
