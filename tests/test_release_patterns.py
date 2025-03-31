"""Tests for pattern matching against downloaded GitHub release JSONs."""

import json
import re
import sys
from pathlib import Path

import pytest

from dotbins.config import build_tool_config

CASES = [
    ("atuin", "linux", "amd64", "atuin-x86_64-unknown-linux-musl.tar.gz"),
    ("atuin", "linux", "arm64", "atuin-aarch64-unknown-linux-musl.tar.gz"),
    ("atuin", "macos", "arm64", "atuin-aarch64-apple-darwin.tar.gz"),
    ("bandwhich", "linux", "amd64", "bandwhich-v{version}-x86_64-unknown-linux-musl.tar.gz"),
    ("bandwhich", "linux", "arm64", "bandwhich-v{version}-aarch64-unknown-linux-musl.tar.gz"),
    ("bandwhich", "macos", "arm64", "bandwhich-v{version}-aarch64-apple-darwin.tar.gz"),
    ("bat", "linux", "amd64", "bat-v{version}-x86_64-unknown-linux-musl.tar.gz"),
    ("bat", "linux", "arm64", "bat-v{version}-aarch64-unknown-linux-musl.tar.gz"),
    ("bat", "macos", "arm64", "bat-v{version}-aarch64-apple-darwin.tar.gz"),
    ("btm", "linux", "amd64", "bottom_x86_64-unknown-linux-musl.tar.gz"),
    ("btm", "linux", "arm64", "bottom_aarch64-unknown-linux-musl.tar.gz"),
    ("btm", "macos", "arm64", "bottom_aarch64-apple-darwin.tar.gz"),
    ("btop", "linux", "amd64", "btop-x86_64-linux-musl.tbz"),
    ("btop", "linux", "arm64", "btop-aarch64-linux-musl.tbz"),
    ("caddy", "linux", "amd64", "caddy_{version}_linux_amd64.tar.gz"),
    ("caddy", "linux", "arm64", "caddy_{version}_linux_arm64.tar.gz"),
    ("caddy", "macos", "arm64", "caddy_{version}_mac_arm64.tar.gz"),
    ("choose", "linux", "amd64", "choose-x86_64-unknown-linux-musl"),
    ("choose", "linux", "arm64", "choose-aarch64-unknown-linux-gnu"),
    ("choose", "macos", "arm64", "choose-aarch64-apple-darwin"),
    ("croc", "linux", "amd64", "croc_v{version}_Linux-64bit.tar.gz"),
    ("croc", "linux", "arm64", "croc_v{version}_Linux-ARM64.tar.gz"),
    ("croc", "macos", "arm64", "croc_v{version}_macOS-ARM64.tar.gz"),
    ("ctop", "linux", "amd64", "ctop-{version}-linux-amd64"),
    ("ctop", "linux", "arm64", "ctop-{version}-linux-arm64"),
    ("ctop", "macos", "arm64", "ctop-{version}-darwin-amd64"),
    ("curlie", "linux", "amd64", "curlie_{version}_linux_amd64.tar.gz"),
    ("curlie", "linux", "arm64", "curlie_{version}_linux_arm64.tar.gz"),
    ("curlie", "macos", "arm64", "curlie_{version}_darwin_arm64.tar.gz"),
    ("delta", "linux", "amd64", "delta-{version}-x86_64-unknown-linux-musl.tar.gz"),
    ("delta", "linux", "arm64", "delta-{version}-aarch64-unknown-linux-gnu.tar.gz"),
    ("delta", "macos", "arm64", "delta-{version}-aarch64-apple-darwin.tar.gz"),
    ("difft", "linux", "amd64", "difft-x86_64-unknown-linux-musl.tar.gz"),
    ("difft", "linux", "arm64", "difft-aarch64-unknown-linux-gnu.tar.gz"),
    ("difft", "macos", "arm64", "difft-aarch64-apple-darwin.tar.gz"),
    ("direnv", "linux", "amd64", "direnv.linux-amd64"),
    ("direnv", "linux", "arm64", "direnv.linux-arm64"),
    ("direnv", "macos", "arm64", "direnv.darwin-arm64"),
    ("dog", "linux", "amd64", "dog-v{version}-x86_64-unknown-linux-gnu.zip"),
    ("duf", "linux", "amd64", "duf_{version}_linux_x86_64.tar.gz"),
    ("duf", "linux", "arm64", "duf_{version}_linux_arm64.tar.gz"),
    ("duf", "macos", "arm64", "duf_{version}_Darwin_arm64.tar.gz"),
    ("dust", "linux", "amd64", "dust-v{version}-x86_64-unknown-linux-musl.tar.gz"),
    ("dust", "linux", "arm64", "dust-v{version}-aarch64-unknown-linux-musl.tar.gz"),
    ("eget", "linux", "amd64", "eget-{version}-linux_amd64.tar.gz"),
    ("eget", "linux", "arm64", "eget-{version}-linux_arm64.tar.gz"),
    ("eget", "macos", "arm64", "eget-{version}-darwin_arm64.tar.gz"),
    ("eza", "linux", "amd64", "eza_x86_64-unknown-linux-musl.tar.gz"),
    ("eza", "linux", "arm64", "eza_aarch64-unknown-linux-gnu.tar.gz"),
    ("eza", "macos", "arm64", None),
    ("fd", "linux", "amd64", "fd-v{version}-x86_64-unknown-linux-musl.tar.gz"),
    ("fd", "linux", "arm64", "fd-v{version}-aarch64-unknown-linux-musl.tar.gz"),
    ("fd", "macos", "arm64", "fd-v{version}-aarch64-apple-darwin.tar.gz"),
    ("fzf", "linux", "amd64", "fzf-{version}-linux_amd64.tar.gz"),
    ("fzf", "linux", "arm64", "fzf-{version}-linux_arm64.tar.gz"),
    ("fzf", "macos", "arm64", "fzf-{version}-darwin_arm64.tar.gz"),
    ("git-lfs", "linux", "amd64", "git-lfs-linux-amd64-v{version}.tar.gz"),
    ("git-lfs", "linux", "arm64", "git-lfs-linux-arm64-v{version}.tar.gz"),
    ("git-lfs", "macos", "arm64", "git-lfs-darwin-arm64-v{version}.zip"),
    ("glow", "linux", "amd64", "glow_{version}_Linux_x86_64.tar.gz"),
    ("glow", "linux", "arm64", "glow_{version}_Linux_arm64.tar.gz"),
    ("glow", "macos", "arm64", "glow_{version}_Darwin_arm64.tar.gz"),
    ("gping", "linux", "amd64", "gping-Linux-musl-x86_64.tar.gz"),
    ("gping", "linux", "arm64", "gping-Linux-musl-arm64.tar.gz"),
    ("gping", "macos", "arm64", "gping-macOS-arm64.tar.gz"),
    ("grex", "linux", "amd64", "grex-v{version}-x86_64-unknown-linux-musl.tar.gz"),
    ("grex", "linux", "arm64", "grex-v{version}-aarch64-unknown-linux-musl.tar.gz"),
    ("grex", "macos", "arm64", "grex-v{version}-aarch64-apple-darwin.tar.gz"),
    ("gron", "linux", "amd64", "gron-linux-amd64-{version}.tgz"),
    ("gron", "linux", "arm64", "gron-linux-arm64-{version}.tgz"),
    ("gron", "macos", "arm64", "gron-darwin-arm64-{version}.tgz"),
    ("hexyl", "linux", "amd64", "hexyl-v{version}-x86_64-unknown-linux-musl.tar.gz"),
    ("hexyl", "linux", "arm64", "hexyl-v{version}-aarch64-unknown-linux-gnu.tar.gz"),
    ("hexyl", "macos", "arm64", "hexyl-v{version}-aarch64-apple-darwin.tar.gz"),
    ("hx", "linux", "amd64", "helix-{version}-x86_64.AppImage"),
    ("hx", "linux", "arm64", "helix-{version}-aarch64-linux.tar.xz"),
    ("hx", "macos", "arm64", "helix-{version}-aarch64-macos.tar.xz"),
    ("hyperfine", "linux", "amd64", "hyperfine-v{version}-x86_64-unknown-linux-musl.tar.gz"),
    ("hyperfine", "linux", "arm64", "hyperfine-v{version}-aarch64-unknown-linux-gnu.tar.gz"),
    ("hyperfine", "macos", "arm64", "hyperfine-v{version}-aarch64-apple-darwin.tar.gz"),
    ("jc", "linux", "amd64", "jc-{version}-linux-x86_64.tar.gz"),
    ("jc", "linux", "arm64", "jc-{version}-linux-aarch64.tar.gz"),
    ("jc", "macos", "arm64", "jc-{version}-darwin-aarch64.tar.gz"),
    ("jless", "linux", "amd64", "jless-v{version}-x86_64-unknown-linux-gnu.zip"),
    ("jless", "macos", "arm64", "jless-v{version}-aarch64-apple-darwin.zip"),
    ("jq", "linux", "amd64", "jq-linux-amd64"),
    ("jq", "linux", "arm64", "jq-linux-arm64"),
    ("jq", "macos", "arm64", "jq-macos-arm64"),
    ("just", "linux", "amd64", "just-{version}-x86_64-unknown-linux-musl.tar.gz"),
    ("just", "linux", "arm64", "just-{version}-aarch64-unknown-linux-musl.tar.gz"),
    ("just", "macos", "arm64", "just-{version}-aarch64-apple-darwin.tar.gz"),
    ("k9s", "linux", "amd64", "k9s_Linux_amd64.tar.gz"),
    ("k9s", "linux", "arm64", "k9s_Linux_arm64.tar.gz"),
    ("k9s", "macos", "arm64", "k9s_Darwin_arm64.tar.gz"),
    ("lazygit", "linux", "amd64", "lazygit_{version}_Linux_x86_64.tar.gz"),
    ("lazygit", "linux", "arm64", "lazygit_{version}_Linux_arm64.tar.gz"),
    ("lazygit", "macos", "arm64", "lazygit_{version}_Darwin_arm64.tar.gz"),
    ("lnav", "linux", "amd64", "lnav-{version}-linux-musl-x86_64.zip"),
    ("lnav", "linux", "arm64", "lnav-{version}-linux-musl-arm64.zip"),
    ("lnav", "macos", "arm64", "lnav-{version}-aarch64-macos.zip"),
    ("lsd", "linux", "amd64", "lsd-v{version}-x86_64-unknown-linux-musl.tar.gz"),
    ("lsd", "linux", "arm64", "lsd-v{version}-aarch64-unknown-linux-musl.tar.gz"),
    ("lsd", "macos", "arm64", "lsd-v{version}-aarch64-apple-darwin.tar.gz"),
    ("mcfly", "linux", "amd64", "mcfly-v{version}-x86_64-unknown-linux-musl.tar.gz"),
    ("mcfly", "linux", "arm64", "mcfly-v{version}-aarch64-unknown-linux-musl.tar.gz"),
    ("micro", "linux", "amd64", "micro-{version}-linux64-static.tar.gz"),
    ("micro", "linux", "arm64", "micro-{version}-linux-arm64.tar.gz"),
    ("micro", "macos", "arm64", "micro-{version}-macos-arm64.tar.gz"),
    ("micromamba", "linux", "amd64", "micromamba-linux-64"),
    ("micromamba", "linux", "arm64", "micromamba-linux-aarch64"),
    ("micromamba", "macos", "arm64", "micromamba-osx-arm64"),
    ("navi", "linux", "amd64", "navi-v{version}-x86_64-unknown-linux-musl.tar.gz"),
    ("navi", "linux", "arm64", "navi-v{version}-aarch64-unknown-linux-gnu.tar.gz"),
    ("neovim", "linux", "amd64", "nvim-linux-x86_64.appimage"),
    ("neovim", "linux", "arm64", "nvim-linux-arm64.appimage"),
    ("neovim", "macos", "amd64", "nvim-macos-x86_64.tar.gz"),
    ("neovim", "macos", "arm64", "nvim-macos-arm64.tar.gz"),
    ("nu", "linux", "amd64", "nu-{version}-x86_64-unknown-linux-musl.tar.gz"),
    ("nu", "linux", "arm64", "nu-{version}-aarch64-unknown-linux-musl.tar.gz"),
    ("nu", "macos", "arm64", "nu-{version}-aarch64-apple-darwin.tar.gz"),
    ("pastel", "linux", "amd64", "pastel-v{version}-x86_64-unknown-linux-musl.tar.gz"),
    ("pastel", "linux", "arm64", "pastel-v{version}-aarch64-unknown-linux-gnu.tar.gz"),
    ("procs", "linux", "amd64", "procs-v{version}-x86_64-linux.zip"),
    ("procs", "linux", "arm64", "procs-v{version}-aarch64-linux.zip"),
    ("procs", "macos", "arm64", "procs-v{version}-aarch64-mac.zip"),
    ("rg", "linux", "amd64", "ripgrep-{version}-x86_64-unknown-linux-musl.tar.gz"),
    ("rg", "linux", "arm64", "ripgrep-{version}-aarch64-unknown-linux-gnu.tar.gz"),
    ("rg", "macos", "arm64", "ripgrep-{version}-aarch64-apple-darwin.tar.gz"),
    ("rip", "linux", "amd64", "rip-Linux-x86_64-musl.tar.gz"),
    ("rip", "linux", "arm64", "rip-Linux-aarch64-musl.tar.gz"),
    ("rip", "macos", "arm64", "rip-macOS-Darwin-aarch64.tar.gz"),
    ("sd", "linux", "amd64", "sd-v{version}-x86_64-unknown-linux-musl.tar.gz"),
    ("sd", "linux", "arm64", "sd-v{version}-aarch64-unknown-linux-musl.tar.gz"),
    ("sd", "macos", "arm64", "sd-v{version}-aarch64-apple-darwin.tar.gz"),
    ("sk", "linux", "amd64", "skim-x86_64-unknown-linux-musl.tgz"),
    ("sk", "linux", "arm64", "skim-aarch64-unknown-linux-musl.tgz"),
    ("sk", "macos", "arm64", "skim-aarch64-apple-darwin.tgz"),
    ("starship", "linux", "amd64", "starship-x86_64-unknown-linux-musl.tar.gz"),
    ("starship", "linux", "arm64", "starship-aarch64-unknown-linux-musl.tar.gz"),
    ("starship", "macos", "arm64", "starship-aarch64-apple-darwin.tar.gz"),
    ("tldr", "linux", "amd64", "tealdeer-linux-x86_64-musl"),
    ("tldr", "linux", "arm64", "tealdeer-linux-aarch64-musl"),
    ("tldr", "macos", "arm64", "tealdeer-macos-aarch64"),
    ("topgrade", "linux", "amd64", "topgrade-v{version}-x86_64-unknown-linux-musl.tar.gz"),
    ("topgrade", "linux", "arm64", "topgrade-v{version}-aarch64-unknown-linux-musl.tar.gz"),
    ("topgrade", "macos", "arm64", "topgrade-v{version}-aarch64-apple-darwin.tar.gz"),
    ("tre", "linux", "amd64", "tre-v{version}-x86_64-unknown-linux-musl.tar.gz"),
    ("tre", "macos", "arm64", "tre-v{version}-aarch64-apple-darwin.tar.gz"),
    ("xh", "linux", "amd64", "xh-v{version}-x86_64-unknown-linux-musl.tar.gz"),
    ("xh", "linux", "arm64", "xh-v{version}-aarch64-unknown-linux-musl.tar.gz"),
    ("xh", "macos", "arm64", "xh-v{version}-aarch64-apple-darwin.tar.gz"),
    ("xplr", "linux", "arm64", "xplr-linux-aarch64.tar.gz"),
    ("xplr", "macos", "arm64", "xplr-macos-aarch64.tar.gz"),
    ("yazi", "linux", "amd64", "yazi-x86_64-unknown-linux-musl.zip"),
    ("yazi", "linux", "arm64", "yazi-aarch64-unknown-linux-musl.zip"),
    ("yazi", "macos", "arm64", "yazi-aarch64-apple-darwin.zip"),
    ("yq", "linux", "amd64", "yq_linux_amd64"),
    ("yq", "linux", "arm64", "yq_linux_arm64"),
    ("yq", "macos", "arm64", "yq_darwin_arm64"),
    ("zellij", "linux", "amd64", "zellij-x86_64-unknown-linux-musl.tar.gz"),
    ("zellij", "linux", "arm64", "zellij-aarch64-unknown-linux-musl.tar.gz"),
    ("zellij", "macos", "arm64", "zellij-aarch64-apple-darwin.tar.gz"),
    ("zoxide", "linux", "amd64", "zoxide-{version}-x86_64-unknown-linux-musl.tar.gz"),
    ("zoxide", "linux", "arm64", "zoxide-{version}-aarch64-unknown-linux-musl.tar.gz"),
    ("zoxide", "macos", "arm64", "zoxide-{version}-aarch64-apple-darwin.tar.gz"),
]


@pytest.mark.parametrize(
    ("program", "platform", "arch", "expected_asset"),
    CASES,
)
@pytest.mark.skipif(sys.platform.startswith("win"), reason="Skip on Windows due to cache issues")
def test_autodetect_asset(program: str, platform: str, arch: str, expected_asset: str) -> None:
    """Test that the correct asset is selected from the release JSON.

    This test:
    1. Loads a real release JSON from the tests/release_jsons directory
    2. Creates a ToolConfig for the tool
    3. Verifies that we can find a matching asset for each platform/arch combination
    """
    # Load the release JSON
    json_file = Path(__file__).parent / "release_jsons" / f"{program}.json"
    with open(json_file) as f:
        release_data = json.load(f)

    # Create tool config
    tool_config = build_tool_config(
        tool_name=program,
        raw_data={"repo": f"example/{program}"},
        platforms={platform: [arch]},
    )

    # Set the latest release data directly
    tool_config._latest_release = release_data

    # Test asset selection
    bin_spec = tool_config.bin_spec(arch, platform)
    matching_asset = bin_spec.matching_asset()

    if expected_asset is None:
        # For cases where we expect ambiguous detection, assert that no asset is found
        assert matching_asset is None, (
            f"Expected no match due to ambiguity, but found: {matching_asset}"
        )
    else:
        # For normal cases, assert that the correct asset is found
        assert matching_asset is not None

        # Handle {version} placeholders by replacing with actual version or regex pattern
        if "{version}" in expected_asset:
            pattern = re.escape(expected_asset).replace(r"\{version\}", r"[\d\.]+")
            assert re.match(pattern, matching_asset["name"])
        else:
            # For assets without version placeholders, do exact match
            assert matching_asset["name"] == expected_asset


@pytest.mark.skipif(sys.platform.startswith("win"), reason="Skip on Windows due to cache issues")
def test_if_complete_tests() -> None:
    """Checks whether the parametrize test_autodetect_asset are complete (see tests/release_jsons)."""
    # Get all test files in tests/release_jsons
    test_files_dir = Path(__file__).parent / "release_jsons"
    test_files = list(test_files_dir.glob("*.json"))

    # Extract tool names from JSON files
    json_tool_names = {file.stem for file in test_files}

    # Extract tool names directly from CASES
    tested_tool_names = {program for program, _, _, _ in CASES}

    # Find any missing tools
    missing_tools = json_tool_names - tested_tool_names

    # Assert that all tools with release JSONs are being tested
    assert not missing_tools, f"These tools have release JSONs but no tests: {missing_tools}"
