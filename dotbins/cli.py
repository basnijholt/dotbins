"""Command-line interface for dotbins."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown

from . import __version__
from .analyze import analyze_tool
from .config import Config
from .readme import generate_readme_content
from .utils import log, print_shell_setup


def _list_tools(config: Config) -> None:
    """List available tools."""
    log("Available tools:", "info", "🔧")
    for tool, tool_config in config.tools.items():
        log(f"  {tool} (from {tool_config.repo})", "success")


def _update_tools(
    config: Config,
    tools: list[str],
    platform: str | None,
    architecture: str | None,
    current: bool,
    force: bool,
    shell_setup: bool,
    generate_readme: bool = True,
) -> None:
    """Update tools based on command line arguments."""
    config.update_tools(tools, platform, architecture, current, force, generate_readme)
    if shell_setup:
        print_shell_setup(config)


def _initialize(config: Config) -> None:
    """Initialize the tools directory structure."""
    for platform, architectures in config.platforms.items():
        for arch in architectures:
            config.bin_dir(platform, arch, create=True)

    log("dotbins initialized tools directory structure", "success", "🛠️")
    print_shell_setup(config)

    # Generate README file with shell integration instructions
    config.generate_readme()
    log("Generated README file with shell integration instructions", "success", "📝")


def _generate_readme(config: Config, print_content: bool = True, write_file: bool = True) -> None:
    """Generate README file with tool information."""
    # Generate the README content
    readme_content = generate_readme_content(config)

    # Write to file if requested
    if write_file:
        readme_path = config.tools_dir / "README.md"
        try:
            with open(readme_path, "w") as f:
                f.write(readme_content)
            log(f"Generated README at {readme_path}", "success", "📝")
        except OSError as e:
            log(f"Failed to write README: {e}", "error", print_exception=True)
            return

    # Print content if requested
    if print_content:
        console = Console()
        md = Markdown(readme_content)
        console.print(md)

    log("Generated README file with tool information", "success", "📝")


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
    update_parser.add_argument(
        "--no-readme",
        action="store_true",
        help="Skip generating README.md file",
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

    # Add readme command
    readme_parser = subparsers.add_parser(
        "readme",
        help="Generate README.md file with tool information",
    )
    readme_parser.add_argument(
        "--no-print",
        action="store_true",
        help="Don't print the README content to the console",
    )
    readme_parser.add_argument(
        "--no-file",
        action="store_true",
        help="Don't write the README to a file",
    )

    return parser


def main() -> None:  # pragma: no cover
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
                not args.no_readme,
            )
        elif args.command == "readme":
            _generate_readme(
                config,
                not args.no_print,
                not args.no_file,
            )
        elif args.command == "analyze":
            analyze_tool(args.repo, args.name)
        elif args.command == "versions":
            config.version_store.print()
        elif args.command == "version":
            log(f"[yellow]dotbins[/] [bold]v{__version__}[/]")
        else:
            parser.print_help()

    except Exception as e:
        log(f"Error: {e!s}", "error", print_exception=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
