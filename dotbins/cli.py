"""Command-line interface for dotbins."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

from rich.console import Console

from .analyze import analyze_tool
from .config import DotbinsConfig
from .download import download_tool, make_binaries_executable
from .utils import print_shell_setup, setup_logging

# Initialize rich console
console = Console()
logger = logging.getLogger(__name__)


def list_tools(_args: Any, config: DotbinsConfig) -> None:
    """List available tools."""
    console.print("🔧 [blue]Available tools:[/blue]")
    for tool, tool_config in config.tools.items():
        console.print(f"  [green]{tool}[/green] (from {tool_config['repo']})")


def update_tools(args: argparse.Namespace, config: DotbinsConfig) -> None:
    """Update tools based on command line arguments."""
    tools_to_update = args.tools if args.tools else list(config.tools.keys())
    platforms_to_update = [args.platform] if args.platform else config.platforms
    archs_to_update = [args.architecture] if args.architecture else config.architectures

    # Validate tools
    for tool in tools_to_update:
        if tool not in config.tools:
            console.print(f"❌ [bold red]Unknown tool: {tool}[/bold red]")
            sys.exit(1)

    # Create the tools directory structure
    config.tools_dir.mkdir(parents=True, exist_ok=True)

    success_count = 0
    total_count = 0

    for tool_name in tools_to_update:
        for platform in platforms_to_update:
            for arch in archs_to_update:
                total_count += 1
                if download_tool(tool_name, platform, arch, config, args.force):
                    success_count += 1

    make_binaries_executable(config)

    console.print(
        f"\n🔄 [blue]Completed: {success_count}/{total_count} tools updated successfully[/blue]",
    )

    if success_count > 0:
        console.print(
            "💾 [green]Don't forget to commit the changes to your dotfiles repository[/green]",
        )

    if args.shell_setup:
        print_shell_setup()


def initialize(_args: Any = None, config: DotbinsConfig | None = None) -> None:
    """Initialize the tools directory structure."""
    if config is None:
        config = DotbinsConfig.load_from_file()

    for platform in config.platforms:
        for arch in config.architectures:
            (config.tools_dir / platform / arch / "bin").mkdir(
                parents=True,
                exist_ok=True,
            )

    console.print("🛠️ [green]Initialized tools directory structure[/green]")
    print_shell_setup()


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
    list_parser.set_defaults(func=list_tools)

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
        "-s",
        "--shell-setup",
        action="store_true",
        help="Print shell setup instructions",
    )
    update_parser.set_defaults(func=update_tools)

    # init command
    init_parser = subparsers.add_parser("init", help="Initialize directory structure")
    init_parser.set_defaults(func=initialize)

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

    return parser


def main() -> None:
    """Main function to parse arguments and execute commands."""
    parser = create_parser()
    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose)

    try:
        # Create config
        config = DotbinsConfig.load_from_file(args.config_file)

        # Override tools directory if specified
        if args.tools_dir:
            config.tools_dir = Path(args.tools_dir)

        # Execute command or show help
        if hasattr(args, "func"):
            if args.func == analyze_tool:
                # analyze_tool doesn't need the config
                args.func(args)
            else:
                args.func(args, config)
        else:
            parser.print_help()

    except Exception as e:  # noqa: BLE001
        console.print(f"❌ [bold red]Error: {e!s}[/bold red]")
        console.print_exception()
        sys.exit(1)


if __name__ == "__main__":
    main()
