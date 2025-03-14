"""Command-line interface for dotbins."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .analyze import analyze_tool
from .config import DotbinsConfig
from .download import (
    download_files_in_parallel,
    make_binaries_executable,
    prepare_download_tasks,
    process_downloaded_files,
)
from .utils import current_platform, log, print_shell_setup
from .versions import VersionStore


def _list_tools(_args: Any, config: DotbinsConfig) -> None:
    """List available tools."""
    log("Available tools:", "info", "🔧")
    for tool, tool_config in config.tools.items():
        log(f"  {tool} (from {tool_config.repo})", "success")


def _update_tools(args: argparse.Namespace, config: DotbinsConfig) -> None:
    """Update tools based on command line arguments."""
    version_store = VersionStore(config.tools_dir)
    tools_to_update, platforms_to_update = _determine_update_targets(args, config)
    architecture = args.architecture
    if args.current:
        platform, architecture = current_platform()
        platforms_to_update = [platform]
    _validate_tools(tools_to_update, config)
    config.tools_dir.mkdir(parents=True, exist_ok=True)
    download_tasks, total_count = prepare_download_tasks(
        tools_to_update,
        platforms_to_update,
        architecture,
        config,
        version_store,
        args.force,
    )
    downloaded_tasks = download_files_in_parallel(download_tasks)
    success_count = process_downloaded_files(downloaded_tasks, version_store)
    make_binaries_executable(config)
    _print_completion_summary(config, success_count, total_count, args.shell_setup)


def _determine_update_targets(
    args: argparse.Namespace,
    config: DotbinsConfig,
) -> tuple[list[str], list[str]]:
    """Determine which tools and platforms to update."""
    tools_to_update = args.tools if args.tools else list(config.tools.keys())
    platforms_to_update = [args.platform] if args.platform else config.platform_names
    return tools_to_update, platforms_to_update


def _validate_tools(tools_to_update: list[str], config: DotbinsConfig) -> None:
    """Validate that all tools exist in the configuration."""
    for tool in tools_to_update:
        if tool not in config.tools:
            log(f"Unknown tool: {tool}", "error")
            sys.exit(1)


def _print_completion_summary(
    config: DotbinsConfig,
    success_count: int,
    total_count: int,
    shell_setup: bool,
) -> None:
    """Print completion summary and additional instructions."""
    log(
        f"Completed: {success_count}/{total_count} tools updated successfully",
        "info",
        "🔄",
    )

    if success_count > 0:
        log(
            "Don't forget to commit the changes to your dotfiles repository",
            "success",
            "💾",
        )

    if shell_setup:
        print_shell_setup(config)


def _initialize(_args: Any, config: DotbinsConfig) -> None:
    """Initialize the tools directory structure."""
    for platform, architectures in config.platforms.items():
        for arch in architectures:
            (config.tools_dir / platform / arch / "bin").mkdir(
                parents=True,
                exist_ok=True,
            )

    log("dotbins initialized tools directory structure", "success", "🛠️")
    print_shell_setup(config)


def _show_versions(_args: Any, config: DotbinsConfig) -> None:
    """Show versions of installed tools."""
    version_store = VersionStore(config.tools_dir)
    versions = version_store.list_all()

    if not versions:
        log("No tool versions recorded yet.", "info")
        return

    log("Installed tool versions:", "info", "📋")
    for key, info in versions.items():
        tool, platform, arch = key.split("/")
        sha256_info = (
            f" [SHA256: {info.get('sha256', 'N/A')}]" if info.get("sha256") else ""
        )
        log(
            f"  {tool} ({platform}/{arch}): {info['version']} - Updated on {info['updated_at']}{sha256_info}",
            "success",
        )


def create_parser() -> argparse.ArgumentParser:
    """Create command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="dotbins - Manage CLI tool binaries in your dotfiles repository",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--tools-dir",
        type=str,
        help="Tools directory",
    )
    parser.add_argument(
        "--config-file",
        type=str,
        help="Path to configuration file",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # list command
    list_parser = subparsers.add_parser("list", help="List available tools")
    list_parser.set_defaults(func=_list_tools)

    # update command
    update_parser = subparsers.add_parser("update", help="Update tools")
    update_parser.add_argument(
        "tools",
        nargs="*",
        help="Tools to update (all if not specified)",
    )
    update_parser.add_argument(
        "-p",
        "--platform",
        help="Only update for specific platform",
    )
    update_parser.add_argument(
        "-a",
        "--architecture",
        help="Only update for specific architecture",
    )
    update_parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Force update even if binary exists",
    )
    update_parser.add_argument(
        "-c",
        "--current",
        action="store_true",
        help="Only update for the current platform and architecture",
    )
    update_parser.add_argument(
        "-s",
        "--shell-setup",
        action="store_true",
        help="Print shell setup instructions",
    )
    update_parser.set_defaults(func=_update_tools)

    # init command
    init_parser = subparsers.add_parser("init", help="Initialize directory structure")
    init_parser.set_defaults(func=_initialize)

    # analyze command for discovering new tools
    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Analyze GitHub releases for a tool",
    )
    analyze_parser.add_argument(
        "repo",
        help="GitHub repository in the format 'owner/repo'",
    )
    analyze_parser.add_argument("--name", help="Name to use for the tool")
    analyze_parser.set_defaults(func=analyze_tool)

    # version command
    version_parser = subparsers.add_parser("version", help="Print version information")
    version_parser.set_defaults(
        func=lambda _, __: log(f"[yellow]dotbins[/] [bold]v{__version__}[/]"),
    )

    # versions command
    versions_parser = subparsers.add_parser(
        "versions",
        help="Show installed tool versions and their last update times",
    )
    versions_parser.set_defaults(func=_show_versions)

    return parser


def main() -> None:
    """Main function to parse arguments and execute commands."""
    parser = create_parser()
    args = parser.parse_args()

    try:
        # Create config
        config = DotbinsConfig.load_from_file(args.config_file)

        # Override tools directory if specified
        if args.tools_dir:
            config.tools_dir = Path(args.tools_dir)

        # Execute command or show help
        if hasattr(args, "func"):
            args.func(args, config)
        else:
            parser.print_help()

    except Exception as e:
        log(f"Error: {e!s}", "error", print_exception=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
