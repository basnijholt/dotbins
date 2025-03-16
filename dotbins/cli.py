"""Command-line interface for dotbins."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .analyze import analyze_tool
from .config import Config
from .download import (
    download_files_in_parallel,
    prepare_download_tasks,
    process_downloaded_files,
)
from .utils import current_platform, log, print_shell_setup


def _list_tools(config: Config) -> None:
    """List available tools."""
    log("Available tools:", "info", "🔧")
    for tool, tool_config in config.tools.items():
        log(f"  {tool} (from {tool_config.repo})", "success")


def _update_tools(
    config: Config,
    tools: list[str] | None = None,
    platform: str | None = None,
    architecture: str | None = None,
    current: bool = False,
    force: bool = False,
    shell_setup: bool = False,
) -> None:
    """Update tools based on command line arguments."""
    tools_to_update = _tools_to_update(config, tools)
    if current:
        platform, architecture = current_platform()
        platforms_to_update = [platform]
    else:
        platforms_to_update = [platform] if platform else None  # type: ignore[assignment]
    config.tools_dir.mkdir(parents=True, exist_ok=True)
    download_tasks, total_count = prepare_download_tasks(
        config,
        tools_to_update,
        platforms_to_update,
        architecture,
        force,
    )
    downloaded_tasks = download_files_in_parallel(download_tasks)
    success_count = process_downloaded_files(downloaded_tasks, config.version_store)
    config.make_binaries_executable()
    _print_completion_summary(config, success_count, total_count, shell_setup)


def _tools_to_update(config: Config, tools: list[str] | None) -> list[str] | None:
    """Determine which tools and platforms to update."""
    if tools:
        for tool in tools:
            if tool not in config.tools:
                log(f"Unknown tool: {tool}", "error")
                sys.exit(1)
        return tools
    return None


def _print_completion_summary(
    config: Config,
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


def _initialize(config: Config) -> None:
    """Initialize the tools directory structure."""
    for platform, architectures in config.platforms.items():
        for arch in architectures:
            config.bin_dir(platform, arch, create=True)

    log("dotbins initialized tools directory structure", "success", "🛠️")
    print_shell_setup(config)


def _show_versions(config: Config) -> None:
    """Show versions of installed tools."""
    versions = config.version_store.list_all()

    if not versions:
        log("No tool versions recorded yet.", "info")
        return

    log("Installed tool versions:", "info", "📋")
    for key, info in versions.items():
        tool, platform, arch = key.split("/")
        sha256_info = f" [SHA256: {info.get('sha256', 'N/A')}]" if info.get("sha256") else ""
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
    _list_parser = subparsers.add_parser("list", help="List available tools")

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
        type=str,
    )
    update_parser.add_argument(
        "-a",
        "--architecture",
        help="Only update for specific architecture",
        type=str,
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

    # init command
    _init_parser = subparsers.add_parser("init", help="Initialize directory structure")

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

    # version command
    _version_parser = subparsers.add_parser("version", help="Print version information")

    # versions command
    _versions_parser = subparsers.add_parser(
        "versions",
        help="Show installed tool versions and their last update times",
    )

    return parser


def main() -> None:
    """Main function to parse arguments and execute commands."""
    parser = create_parser()
    args = parser.parse_args()

    try:
        # Create config
        config = Config.from_file(args.config_file)

        # Override tools directory if specified
        if args.tools_dir is not None:
            config.tools_dir = Path(args.tools_dir)

        if args.command == "init":
            _initialize(config)
        elif args.command == "list":
            _list_tools(config)
        elif args.command == "update":
            _update_tools(
                config,
                args.tools,
                args.platform,
                args.architecture,
                args.current,
                args.force,
                args.shell_setup,
            )
        elif args.command == "analyze":
            analyze_tool(args.repo, args.name)
        elif args.command == "versions":
            _show_versions(config)
        elif args.command == "version":
            log(f"[yellow]dotbins[/] [bold]v{__version__}[/]")
        else:
            parser.print_help()

    except Exception as e:
        log(f"Error: {e!s}", "error", print_exception=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
