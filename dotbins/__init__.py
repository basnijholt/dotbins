"""dotbins - Dotfiles Binary Manager.

A utility for managing CLI tool binaries in your dotfiles repository.
Downloads and organizes binaries for popular tools across multiple
platforms (macOS, Linux, etc.) and architectures (amd64, arm64, etc.).

This tool helps maintain a consistent set of CLI utilities across all your
environments, with binaries tracked in your dotfiles git repository.
"""

from __future__ import annotations

from importlib.metadata import version

__version__ = version("dotbins")

# Re-export commonly used functions
from . import analyze, cli, config, download, utils

__all__ = [
    "__version__",
    "analyze",
    "cli",
    "config",
    "download",
    "utils",
]
