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
    ("bat", "linux:gnu", "amd64", "bat-v{version}-x86_64-unknown-linux-gnu.tar.gz"),
    ("bat", "linux:gnu", "arm64", "bat-v{version}-aarch64-unknown-linux-gnu.tar.gz"),
    ("bat", "linux:musl", "amd64", "bat-v{version}-x86_64-unknown-linux-musl.tar.gz"),
    ("bat", "linux:musl", "arm64", "bat-v{version}-aarch64-unknown-linux-musl.tar.gz"),
    ("bat", "macos", "arm64", "bat-v{version}-aarch64-apple-darwin.tar.gz"),
    ("bat", "windows:gnu", "amd64", "bat-v{version}-x86_64-pc-windows-gnu.zip"),
    ("bat", "windows:msvc", "amd64", "bat-v{version}-x86_64-pc-windows-msvc.zip"),
    ("bat", "linux:gnu", "i686", "bat-v{version}-i686-unknown-linux-gnu.tar.gz"),
    ("bat", "linux:musl", "i686", "bat-v{version}-i686-unknown-linux-musl.tar.gz"),
    ("bat", "windows:msvc", "i686", "bat-v{version}-i686-pc-windows-msvc.zip"),
    ("btm", "linux", "amd64", "bottom_x86_64-unknown-linux-musl.tar.gz"),
    ("btm", "linux", "arm64", "bottom_aarch64-unknown-linux-musl.tar.gz"),
    ("btm", "macos", "arm64", "bottom_aarch64-apple-darwin.tar.gz"),
    ("btm", "linux:gnu", "i686", "bottom_i686-unknown-linux-gnu.tar.gz"),
    ("btm", "linux:musl", "i686", "bottom_i686-unknown-linux-musl.tar.gz"),
    ("btm", "windows:msvc", "i686", "bottom_i686-pc-windows-msvc.zip"),
    ("btop", "linux", "amd64", "btop-x86_64-linux-musl.tbz"),
    ("btop", "linux", "arm64", "btop-aarch64-linux-musl.tbz"),
    ("btop", "linux", "i686", "btop-i686-linux-musl.tbz"),
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
    ("delta", "linux:gnu", "amd64", "delta-{version}-x86_64-unknown-linux-gnu.tar.gz"),
    ("delta", "linux:musl", "amd64", "delta-{version}-x86_64-unknown-linux-musl.tar.gz"),
    ("delta", "linux", "arm64", "delta-{version}-aarch64-unknown-linux-gnu.tar.gz"),
    ("delta", "macos", "arm64", "delta-{version}-aarch64-apple-darwin.tar.gz"),
    ("delta", "windows", "amd64", "delta-{version}-x86_64-pc-windows-msvc.zip"),
    ("delta", "linux:gnu", "i686", "delta-{version}-i686-unknown-linux-gnu.tar.gz"),
    ("difft", "linux:gnu", "amd64", "difft-x86_64-unknown-linux-gnu.tar.gz"),
    ("difft", "linux:musl", "amd64", "difft-x86_64-unknown-linux-musl.tar.gz"),
    ("difft", "linux", "arm64", "difft-aarch64-unknown-linux-gnu.tar.gz"),
    ("difft", "macos", "arm64", "difft-aarch64-apple-darwin.tar.gz"),
    ("difft", "windows", "amd64", "difft-x86_64-pc-windows-msvc.zip"),
    ("direnv", "linux", "amd64", "direnv.linux-amd64"),
    ("direnv", "linux", "arm64", "direnv.linux-arm64"),
    ("direnv", "macos", "arm64", "direnv.darwin-arm64"),
    ("dog", "linux", "amd64", "dog-v{version}-x86_64-unknown-linux-gnu.zip"),
    ("duf", "linux", "amd64", "duf_{version}_linux_x86_64.tar.gz"),
    ("duf", "linux", "arm64", "duf_{version}_linux_arm64.tar.gz"),
    ("duf", "linux", "386", "duf_{version}_linux_i386.tar.gz"),
    ("duf", "macos", "arm64", "duf_{version}_Darwin_arm64.tar.gz"),
    ("duf", "windows", "amd64", "duf_{version}_Windows_x86_64.zip"),
    ("duf", "windows", "386", "duf_{version}_Windows_i386.zip"),
    ("dust", "linux", "amd64", "dust-v{version}-x86_64-unknown-linux-musl.tar.gz"),
    ("dust", "linux", "arm64", "dust-v{version}-aarch64-unknown-linux-musl.tar.gz"),
    ("dust", "linux:gnu", "i686", "dust-v{version}-i686-unknown-linux-gnu.tar.gz"),
    ("dust", "linux:musl", "i686", "dust-v{version}-i686-unknown-linux-musl.tar.gz"),
    ("dust", "windows:gnu", "i686", "dust-v{version}-i686-pc-windows-gnu.zip"),
    ("dust", "windows:msvc", "i686", "dust-v{version}-i686-pc-windows-msvc.zip"),
    ("eget", "linux", "amd64", "eget-{version}-linux_amd64.tar.gz"),
    ("eget", "linux", "arm64", "eget-{version}-linux_arm64.tar.gz"),
    ("eget", "macos", "arm64", "eget-{version}-darwin_arm64.tar.gz"),
    ("eget", "windows", "amd64", "eget-{version}-windows_amd64.zip"),
    ("eza", "linux:gnu", "amd64", "eza_x86_64-unknown-linux-gnu.tar.gz"),
    ("eza", "linux:musl", "amd64", "eza_x86_64-unknown-linux-musl.tar.gz"),
    ("eza", "linux", "arm64", "eza_aarch64-unknown-linux-gnu.tar.gz"),
    ("eza", "macos", "arm64", None),
    ("fd", "linux:gnu", "amd64", "fd-v{version}-x86_64-unknown-linux-gnu.tar.gz"),
    ("fd", "linux:gnu", "arm64", "fd-v{version}-aarch64-unknown-linux-gnu.tar.gz"),
    ("fd", "linux:musl", "amd64", "fd-v{version}-x86_64-unknown-linux-musl.tar.gz"),
    ("fd", "linux:musl", "arm64", "fd-v{version}-aarch64-unknown-linux-musl.tar.gz"),
    ("fd", "macos", "arm64", "fd-v{version}-aarch64-apple-darwin.tar.gz"),
    ("fd", "windows:gnu", "amd64", "fd-v{version}-x86_64-pc-windows-gnu.zip"),
    ("fd", "windows:msvc", "amd64", "fd-v{version}-x86_64-pc-windows-msvc.zip"),
    ("fd", "windows:msvc", "i686", "fd-v{version}-i686-pc-windows-msvc.zip"),
    ("fd", "linux:gnu", "i686", "fd-v{version}-i686-unknown-linux-gnu.tar.gz"),
    ("fd", "linux:musl", "i686", "fd-v{version}-i686-unknown-linux-musl.tar.gz"),
    ("fzf", "linux", "amd64", "fzf-{version}-linux_amd64.tar.gz"),
    ("fzf", "linux", "arm64", "fzf-{version}-linux_arm64.tar.gz"),
    ("fzf", "macos", "arm64", "fzf-{version}-darwin_arm64.tar.gz"),
    ("fzf", "windows", "amd64", "fzf-{version}-windows_amd64.zip"),
    ("git-lfs", "linux", "amd64", "git-lfs-linux-amd64-v{version}.tar.gz"),
    ("git-lfs", "linux", "arm64", "git-lfs-linux-arm64-v{version}.tar.gz"),
    ("git-lfs", "macos", "arm64", "git-lfs-darwin-arm64-v{version}.zip"),
    ("git-lfs", "windows", "amd64", "git-lfs-windows-amd64-v{version}.zip"),
    ("glow", "linux", "amd64", "glow_{version}_Linux_x86_64.tar.gz"),
    ("glow", "linux", "arm64", "glow_{version}_Linux_arm64.tar.gz"),
    ("glow", "macos", "arm64", "glow_{version}_Darwin_arm64.tar.gz"),
    ("glow", "windows", "amd64", "glow_{version}_Windows_x86_64.zip"),
    ("glow", "linux", "386", "glow_{version}_Linux_i386.tar.gz"),
    ("glow", "windows", "386", "glow_{version}_Windows_i386.zip"),
    ("gping", "linux", "amd64", "gping-Linux-musl-x86_64.tar.gz"),
    ("gping", "linux", "arm64", "gping-Linux-musl-arm64.tar.gz"),
    ("gping", "macos", "arm64", "gping-macOS-arm64.tar.gz"),
    ("gping", "windows", "amd64", "gping-Windows-msvc-x86_64.zip"),
    ("grex", "linux", "amd64", "grex-v{version}-x86_64-unknown-linux-musl.tar.gz"),
    ("grex", "linux", "arm64", "grex-v{version}-aarch64-unknown-linux-musl.tar.gz"),
    ("grex", "macos", "arm64", "grex-v{version}-aarch64-apple-darwin.tar.gz"),
    ("grex", "windows", "amd64", "grex-v{version}-x86_64-pc-windows-msvc.zip"),
    ("gron", "linux", "amd64", "gron-linux-amd64-{version}.tgz"),
    ("gron", "linux", "arm64", "gron-linux-arm64-{version}.tgz"),
    ("gron", "macos", "arm64", "gron-darwin-arm64-{version}.tgz"),
    ("gron", "windows", "amd64", "gron-windows-amd64-{version}.zip"),
    ("hexyl", "linux:gnu", "amd64", "hexyl-v{version}-x86_64-unknown-linux-gnu.tar.gz"),
    ("hexyl", "linux:gnu", "arm64", "hexyl-v{version}-aarch64-unknown-linux-gnu.tar.gz"),
    ("hexyl", "linux:musl", "amd64", "hexyl-v{version}-x86_64-unknown-linux-musl.tar.gz"),
    ("hexyl", "macos", "arm64", "hexyl-v{version}-aarch64-apple-darwin.tar.gz"),
    ("hexyl", "windows", "amd64", "hexyl-v{version}-x86_64-pc-windows-msvc.zip"),
    ("hexyl", "linux:gnu", "i686", "hexyl-v{version}-i686-unknown-linux-gnu.tar.gz"),
    ("hexyl", "linux:musl", "i686", "hexyl-v{version}-i686-unknown-linux-musl.tar.gz"),
    ("hexyl", "windows:msvc", "i686", "hexyl-v{version}-i686-pc-windows-msvc.zip"),
    ("hx", "linux", "amd64", "helix-{version}-x86_64.AppImage"),
    ("hx", "linux", "arm64", "helix-{version}-aarch64-linux.tar.xz"),
    ("hx", "macos", "arm64", "helix-{version}-aarch64-macos.tar.xz"),
    ("hyperfine", "linux:gnu", "amd64", "hyperfine-v{version}-x86_64-unknown-linux-gnu.tar.gz"),
    ("hyperfine", "linux:musl", "amd64", "hyperfine-v{version}-x86_64-unknown-linux-musl.tar.gz"),
    ("hyperfine", "linux", "arm64", "hyperfine-v{version}-aarch64-unknown-linux-gnu.tar.gz"),
    ("hyperfine", "macos", "arm64", "hyperfine-v{version}-aarch64-apple-darwin.tar.gz"),
    ("hyperfine", "windows", "amd64", "hyperfine-v{version}-x86_64-pc-windows-msvc.zip"),
    ("hyperfine", "linux:gnu", "i686", "hyperfine-v{version}-i686-unknown-linux-gnu.tar.gz"),
    ("hyperfine", "linux:musl", "i686", "hyperfine-v{version}-i686-unknown-linux-musl.tar.gz"),
    ("hyperfine", "windows:msvc", "i686", "hyperfine-v{version}-i686-pc-windows-msvc.zip"),
    ("jc", "linux", "amd64", "jc-{version}-linux-x86_64.tar.gz"),
    ("jc", "linux", "arm64", "jc-{version}-linux-aarch64.tar.gz"),
    ("jc", "macos", "arm64", "jc-{version}-darwin-aarch64.tar.gz"),
    ("jless", "linux", "amd64", "jless-v{version}-x86_64-unknown-linux-gnu.zip"),
    ("jless", "macos", "arm64", "jless-v{version}-aarch64-apple-darwin.zip"),
    ("jq", "linux", "amd64", "jq-linux-amd64"),
    ("jq", "linux", "arm64", "jq-linux-arm64"),
    ("jq", "macos", "arm64", "jq-macos-arm64"),
    ("jq", "windows", "amd64", "jq-windows-amd64.exe"),
    ("jq", "linux", "386", "jq-linux-i386"),
    ("jq", "windows", "386", "jq-windows-i386.exe"),
    ("just", "linux", "amd64", "just-{version}-x86_64-unknown-linux-musl.tar.gz"),
    ("just", "linux", "arm64", "just-{version}-aarch64-unknown-linux-musl.tar.gz"),
    ("just", "macos", "arm64", "just-{version}-aarch64-apple-darwin.tar.gz"),
    ("k9s", "linux", "amd64", "k9s_Linux_amd64.tar.gz"),
    ("k9s", "linux", "arm64", "k9s_Linux_arm64.tar.gz"),
    ("k9s", "macos", "arm64", "k9s_Darwin_arm64.tar.gz"),
    ("k9s", "windows", "amd64", "k9s_Windows_amd64.zip"),
    ("lazygit", "linux", "amd64", "lazygit_{version}_Linux_x86_64.tar.gz"),
    ("lazygit", "linux", "arm64", "lazygit_{version}_Linux_arm64.tar.gz"),
    ("lazygit", "macos", "arm64", "lazygit_{version}_Darwin_arm64.tar.gz"),
    ("lazygit", "windows", "amd64", "lazygit_{version}_Windows_x86_64.zip"),
    ("lnav", "linux", "amd64", "lnav-{version}-linux-musl-x86_64.zip"),
    ("lnav", "linux", "arm64", "lnav-{version}-linux-musl-arm64.zip"),
    ("lnav", "macos", "arm64", "lnav-{version}-aarch64-macos.zip"),
    ("lsd", "linux:gnu", "amd64", "lsd-v{version}-x86_64-unknown-linux-gnu.tar.gz"),
    ("lsd", "linux:gnu", "arm64", "lsd-v{version}-aarch64-unknown-linux-gnu.tar.gz"),
    ("lsd", "linux:musl", "amd64", "lsd-v{version}-x86_64-unknown-linux-musl.tar.gz"),
    ("lsd", "linux:musl", "arm64", "lsd-v{version}-aarch64-unknown-linux-musl.tar.gz"),
    ("lsd", "macos", "arm64", "lsd-v{version}-aarch64-apple-darwin.tar.gz"),
    ("lsd", "windows", "amd64", "lsd-v{version}-x86_64-pc-windows-msvc.zip"),
    ("lsd", "windows", "amd64", "lsd-v{version}-x86_64-pc-windows-msvc.zip"),
    ("lsd", "linux:gnu", "i686", "lsd-v{version}-i686-unknown-linux-gnu.tar.gz"),
    ("lsd", "linux:musl", "i686", "lsd-v{version}-i686-unknown-linux-musl.tar.gz"),
    ("lsd", "windows:msvc", "i686", "lsd-v{version}-i686-pc-windows-msvc.zip"),
    ("mcfly", "linux", "amd64", "mcfly-v{version}-x86_64-unknown-linux-musl.tar.gz"),
    ("mcfly", "linux", "arm64", "mcfly-v{version}-aarch64-unknown-linux-musl.tar.gz"),
    ("mcfly", "linux", "i686", "mcfly-v{version}-i686-unknown-linux-musl.tar.gz"),
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
    ("nu", "linux:gnu", "amd64", "nu-{version}-x86_64-unknown-linux-gnu.tar.gz"),
    ("nu", "linux:gnu", "arm64", "nu-{version}-aarch64-unknown-linux-gnu.tar.gz"),
    ("nu", "linux:musl", "amd64", "nu-{version}-x86_64-unknown-linux-musl.tar.gz"),
    ("nu", "linux:musl", "arm64", "nu-{version}-aarch64-unknown-linux-musl.tar.gz"),
    ("nu", "macos", "arm64", "nu-{version}-aarch64-apple-darwin.tar.gz"),
    ("nu", "windows", "amd64", "nu-{version}-x86_64-pc-windows-msvc.zip"),
    ("pastel", "linux:gnu", "amd64", "pastel-v{version}-x86_64-unknown-linux-gnu.tar.gz"),
    ("pastel", "linux:musl", "amd64", "pastel-v{version}-x86_64-unknown-linux-musl.tar.gz"),
    ("pastel", "linux", "arm64", "pastel-v{version}-aarch64-unknown-linux-gnu.tar.gz"),
    ("pastel", "linux:gnu", "i686", "pastel-v{version}-i686-unknown-linux-gnu.tar.gz"),
    ("pastel", "linux:musl", "i686", "pastel-v{version}-i686-unknown-linux-musl.tar.gz"),
    ("pastel", "windows:msvc", "i686", "pastel-v{version}-i686-pc-windows-msvc.zip"),
    ("procs", "linux", "amd64", "procs-v{version}-x86_64-linux.zip"),
    ("procs", "linux", "arm64", "procs-v{version}-aarch64-linux.zip"),
    ("procs", "macos", "arm64", "procs-v{version}-aarch64-mac.zip"),
    ("procs", "windows", "amd64", "procs-v{version}-x86_64-windows.zip"),
    ("rg", "linux", "amd64", "ripgrep-{version}-x86_64-unknown-linux-musl.tar.gz"),
    ("rg", "linux", "arm64", "ripgrep-{version}-aarch64-unknown-linux-gnu.tar.gz"),
    ("rg", "macos", "arm64", "ripgrep-{version}-aarch64-apple-darwin.tar.gz"),
    ("rg", "windows:gnu", "amd64", "ripgrep-{version}-x86_64-pc-windows-gnu.zip"),
    ("rg", "windows:msvc", "amd64", "ripgrep-{version}-x86_64-pc-windows-msvc.zip"),
    ("rg", "windows:msvc", "i686", "ripgrep-{version}-i686-pc-windows-msvc.zip"),
    ("rip", "linux", "amd64", "rip-Linux-x86_64-musl.tar.gz"),
    ("rip", "linux", "arm64", "rip-Linux-aarch64-musl.tar.gz"),
    ("rip", "macos", "arm64", "rip-macOS-Darwin-aarch64.tar.gz"),
    ("rip", "windows", "amd64", "rip-Windows-x86_64.zip"),
    ("rip", "linux", "i686", "rip-Linux-i686-musl.tar.gz"),
    ("rip", "windows", "i686", "rip-Windows-i686.zip"),
    ("sd", "linux", "amd64", "sd-v{version}-x86_64-unknown-linux-musl.tar.gz"),
    ("sd", "linux", "arm64", "sd-v{version}-aarch64-unknown-linux-musl.tar.gz"),
    ("sd", "macos", "arm64", "sd-v{version}-aarch64-apple-darwin.tar.gz"),
    ("sd", "windows", "amd64", "sd-v{version}-x86_64-pc-windows-msvc.zip"),
    ("sk", "linux", "amd64", "skim-x86_64-unknown-linux-musl.tgz"),
    ("sk", "linux", "arm64", "skim-aarch64-unknown-linux-musl.tgz"),
    ("sk", "macos", "arm64", "skim-aarch64-apple-darwin.tgz"),
    ("starship", "linux", "amd64", "starship-x86_64-unknown-linux-musl.tar.gz"),
    ("starship", "linux", "arm64", "starship-aarch64-unknown-linux-musl.tar.gz"),
    ("starship", "macos", "arm64", "starship-aarch64-apple-darwin.tar.gz"),
    ("starship", "windows", "amd64", "starship-x86_64-pc-windows-msvc.zip"),
    ("starship", "linux", "i686", "starship-i686-unknown-linux-musl.tar.gz"),
    ("starship", "windows:msvc", "i686", "starship-i686-pc-windows-msvc.zip"),
    ("tldr", "linux", "amd64", "tealdeer-linux-x86_64-musl"),
    ("tldr", "linux", "arm64", "tealdeer-linux-aarch64-musl"),
    ("tldr", "macos", "arm64", "tealdeer-macos-aarch64"),
    ("tldr", "windows", "amd64", "tealdeer-windows-x86_64-msvc.exe"),
    ("tldr", "linux", "i686", "tealdeer-linux-i686-musl"),
    ("topgrade", "linux", "amd64", "topgrade-v{version}-x86_64-unknown-linux-musl.tar.gz"),
    ("topgrade", "linux", "arm64", "topgrade-v{version}-aarch64-unknown-linux-musl.tar.gz"),
    ("topgrade", "macos", "arm64", "topgrade-v{version}-aarch64-apple-darwin.tar.gz"),
    ("topgrade", "windows", "amd64", "topgrade-v{version}-x86_64-pc-windows-msvc.zip"),
    ("tre", "linux", "amd64", "tre-v{version}-x86_64-unknown-linux-musl.tar.gz"),
    ("tre", "macos", "arm64", "tre-v{version}-aarch64-apple-darwin.tar.gz"),
    ("tre", "windows", "amd64", "tre-v{version}-x86_64-pc-windows-msvc.zip"),
    ("tre", "windows:msvc", "i686", "tre-v{version}-i686-pc-windows-msvc.zip"),
    ("xh", "linux", "amd64", "xh-v{version}-x86_64-unknown-linux-musl.tar.gz"),
    ("xh", "linux", "arm64", "xh-v{version}-aarch64-unknown-linux-musl.tar.gz"),
    ("xh", "macos", "arm64", "xh-v{version}-aarch64-apple-darwin.tar.gz"),
    ("xh", "windows", "amd64", "xh-v{version}-x86_64-pc-windows-msvc.zip"),
    ("xplr", "linux", "arm64", "xplr-linux-aarch64.tar.gz"),
    ("xplr", "macos", "arm64", "xplr-macos-aarch64.tar.gz"),
    ("yazi", "linux", "amd64", "yazi-x86_64-unknown-linux-musl.zip"),
    ("yazi", "linux", "arm64", "yazi-aarch64-unknown-linux-musl.zip"),
    ("yazi", "macos", "arm64", "yazi-aarch64-apple-darwin.zip"),
    ("yazi", "windows", "amd64", "yazi-x86_64-pc-windows-msvc.zip"),
    ("yazi", "linux:gnu", "i686", "yazi-i686-unknown-linux-gnu.zip"),
    ("yq", "linux", "amd64", "yq_linux_amd64"),
    ("yq", "linux", "arm64", "yq_linux_arm64"),
    ("yq", "macos", "arm64", "yq_darwin_arm64"),
    ("yq", "windows", "amd64", "yq_windows_amd64.zip"),
    ("zellij", "linux", "amd64", "zellij-x86_64-unknown-linux-musl.tar.gz"),
    ("zellij", "linux", "arm64", "zellij-aarch64-unknown-linux-musl.tar.gz"),
    ("zellij", "macos", "arm64", "zellij-aarch64-apple-darwin.tar.gz"),
    ("zoxide", "linux", "amd64", "zoxide-{version}-x86_64-unknown-linux-musl.tar.gz"),
    ("zoxide", "linux", "arm64", "zoxide-{version}-aarch64-unknown-linux-musl.tar.gz"),
    ("zoxide", "macos", "arm64", "zoxide-{version}-aarch64-apple-darwin.tar.gz"),
    ("zoxide", "windows", "amd64", "zoxide-{version}-x86_64-pc-windows-msvc.zip"),
    ("zoxide", "linux", "i686", "zoxide-{version}-i686-unknown-linux-musl.tar.gz"),
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

    defaults = {
        "windows_abi": "msvc",
        "libc": "musl",
        "prefer_appimage": True,
    }
    if ":" in platform:
        platform, preference = platform.split(":")
        if platform == "windows":
            defaults["windows_abi"] = preference
        else:
            defaults["libc"] = preference

    # Create tool config
    tool_config = build_tool_config(
        tool_name=program,
        raw_data={"repo": f"example/{program}"},
        platforms={platform: [arch]},
        defaults=defaults,  # type: ignore[arg-type]
    )

    # Set the latest release data directly
    tool_config._release_info = release_data

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
