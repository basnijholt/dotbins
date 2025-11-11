"""Regression tests for BinSpec.skip_download edge cases."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dotbins.config import Config, build_tool_config

if TYPE_CHECKING:  # pragma: no cover - type-only import for linters
    from pathlib import Path


def test_skip_download_respects_exe_extension_for_windows_target(tmp_path: Path) -> None:
    """Assert skip_download respects `.exe` when targeting Windows.

    On Windows, installed binaries typically have a `.exe` extension. This test
    ensures that a recorded manifest entry plus an on-disk `.exe` short-circuit
    the download even when the configured binary name omits the suffix.

    Expected: when `win-tool.exe` exists and the recorded tag matches, the
    method returns True (skip download) regardless of the host OS.
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


def test_skip_download_does_not_confuse_similar_binary_names(tmp_path: Path) -> None:
    """Ensure we require the exact binary name, not substring matches."""
    tool_name = "delta"
    platform = "linux"
    arch = "amd64"

    tool_config = build_tool_config(
        tool_name=tool_name,
        raw_data={
            "repo": "owner/repo",
            "binary_name": tool_name,
            "path_in_archive": tool_name,
        },
    )
    tool_config._release_info = {"tag_name": "v0.1.0", "assets": []}

    config = Config(
        tools_dir=tmp_path,
        tools={tool_name: tool_config},
        platforms={platform: [arch]},
    )

    dest_dir = config.bin_dir(platform, arch, create=True)
    # Create a different binary that merely contains the name as a substring.
    (dest_dir / "git-delta").write_text("dummy")

    config.manifest.update_tool_info(
        tool_name,
        platform,
        arch,
        "v0.1.0",
        "sha256",
        url="https://example.com",
    )

    bin_spec = tool_config.bin_spec(arch, platform)

    # Expected: False (needs download) because `delta` itself is missing.
    assert bin_spec.skip_download(config, force=False) is False
