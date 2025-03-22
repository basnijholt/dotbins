"""Command-line interface for dotbins."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rich_argparse import RichHelpFormatter

from . import __version__
from .config import Config, build_tool_config
from .readme import write_readme_file
from .utils import current_platform, log, replace_home_in_path


def _list_tools(config: Config) -> None:
    """List all tools defined in the configuration file.

    Prints each tool name along with its GitHub repository.
    """
    log("Available tools:", "info", "🔧")
    for tool, tool_config in config.tools.items():
        log(f"  {tool} (from {tool_config.repo})", "success")


def _sync_tools(
    config: Config,
    tools: list[str],
    platform: str | None,
    architecture: str | None,
    current: bool,
    force: bool,
    generate_readme: bool,
    copy_config_file: bool,
    generate_shell_scripts: bool,
    github_token: str | None,
    verbose: bool,
    cleanup: bool = False,
) -> None:
    """Install and update tools based on command line arguments.

    This function handles both installing tools for the first time and updating
    existing tools to their latest versions according to user-specified options.

    Args:
        config: Configuration containing all tool definitions
        tools: List of specific tools to process (all tools if None)
        platform: Filter to a specific platform (e.g., "linux", "macos")
        architecture: Filter to a specific architecture (e.g., "amd64", "arm64")
        current: Only process tools for the current platform/architecture
        force: Force reinstall even if already up to date
        generate_readme: Whether to generate a README.md file
        copy_config_file: Whether to copy the config file to tools directory
        generate_shell_scripts: Whether to generate shell integration scripts
        github_token: GitHub token for API authentication
        verbose: Whether to show detailed logs
        cleanup: Whether to remove binaries that are not in the configuration

    """
    config.sync_tools(
        tools,
        platform,
        architecture,
        current,
        force,
        generate_readme,
        copy_config_file,
        github_token,
        verbose,
        cleanup,
    )
    if generate_shell_scripts:
        config.generate_shell_scripts(print_shell_setup=False)
        log("To see the shell setup instructions, run `dotbins init`", "info", "ℹ️")  # noqa: RUF001


def _initialize(config: Config) -> None:
    """Initialize the tools directory structure and shell integration.

    Creates the necessary directories for all platforms and architectures,
    generates shell integration scripts, and creates a README.md file.
    """
    for platform, architectures in config.platforms.items():
        for arch in architectures:
            config.bin_dir(platform, arch, create=True)
    tools_dir = replace_home_in_path(config.tools_dir, "~")
    log(f"dotbins initialized tools directory structure in `tools_dir={tools_dir}`", "success", "🛠️")
    config.generate_shell_scripts()
    config.generate_readme()


def _get_tool(source: str, dest_dir: str | Path, name: str | None = None) -> None:
    """Get a specific tool and install it directly to a location.

    This command bypasses the standard configuration and tools directory,
    downloading a specific tool directly to the specified directory.
    Useful for quick one-off installations.

    Args:
        source: GitHub repository in the format 'owner/repo' or URL to a YAML configuration
        dest_dir: Directory to install the binary to (e.g., ~/.local/bin)
        name: Optional name to use for the binary (defaults to repo name)

    """
    platform, arch = current_platform()
    dest_dir_path = Path(dest_dir).expanduser()
    # Determine if source is a URL or a repo based on format
    if "://" in source and source.endswith(".yaml"):
        config = Config.from_url(source)
    else:
        tool_name = name or source.split("/")[-1]
        config = Config(
            tools_dir=dest_dir_path,
            platforms={platform: [arch]},
            tools={tool_name: build_tool_config(tool_name, {"repo": source})},
        )
    config._bin_dir = dest_dir_path
    config.sync_tools(current=True, force=True, generate_readme=False, copy_config_file=False)


def create_parser() -> argparse.ArgumentParser:
    """Create command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="dotbins - Download, manage, and update CLI tool binaries in your dotfiles repository",
        formatter_class=RichHelpFormatter,
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output with detailed logs and error messages",
    )
    parser.add_argument(
        "--tools-dir",
        type=str,
        help="Tools directory to use (overrides the value in the config file)",
    )
    parser.add_argument(
        "--config-file",
        type=str,
        help="Path to configuration file (default: looks in standard locations)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # list command
    _list_parser = subparsers.add_parser(
        "list",
        help="List all available tools defined in your configuration",
    )

    # sync command
    sync_parser = subparsers.add_parser(
        "sync",
        help="Install and update tools to their latest versions",
        formatter_class=RichHelpFormatter,
    )
    sync_parser.add_argument(
        "tools",
        nargs="*",
        help="Tools to install or update (if not specified, all tools will be processed)",
    )
    sync_parser.add_argument(
        "-p",
        "--platform",
        help="Only install or update for specific platform (e.g., linux, macos)",
        type=str,
    )
    sync_parser.add_argument(
        "-a",
        "--architecture",
        help="Only install or update for specific architecture (e.g., amd64, arm64)",
        type=str,
    )
    sync_parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Force install or update even if binary exists and is up to date",
    )
    sync_parser.add_argument(
        "-c",
        "--current",
        action="store_true",
        help="Only install or update for the current platform and architecture (convenient shorthand)",
    )
    sync_parser.add_argument(
        "--no-shell-scripts",
        action="store_true",
        help="Skip generating shell scripts that add the tools to your PATH",
    )
    sync_parser.add_argument(
        "--no-readme",
        action="store_true",
        help="Skip generating README.md file in the tools directory",
    )
    sync_parser.add_argument(
        "--no-copy-config-file",
        action="store_true",
        help="Skip copying the config file to the tools directory",
    )
    sync_parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Remove binaries that are not in the configuration",
    )
    sync_parser.add_argument(
        "--github-token",
        type=str,
        help="GitHub token to use for API requests (helps with rate limits and private repos)",
    )

    # init command
    _init_parser = subparsers.add_parser(
        "init",
        help="Initialize directory structure and generate shell integration scripts",
    )

    # version command
    _version_parser = subparsers.add_parser(
        "version",
        help="Print dotbins version information",
    )

    # versions command
    _versions_parser = subparsers.add_parser(
        "versions",
        help="Show installed tool versions and when they were last updated",
    )

    # Add readme command
    readme_parser = subparsers.add_parser(
        "readme",
        help="Generate README.md file with information about installed tools",
        formatter_class=RichHelpFormatter,
    )
    readme_parser.add_argument(
        "--no-print",
        action="store_true",
        help="Don't print the README content to the console (only write to file)",
    )
    readme_parser.add_argument(
        "--no-file",
        action="store_true",
        help="Don't write the README to a file (only print to console)",
    )

    # Add get command
    get_parser = subparsers.add_parser(
        "get",
        help="Download and install a tool directly without configuration file",
        formatter_class=RichHelpFormatter,
    )
    get_parser.add_argument(
        "source",
        help="GitHub repository (owner/repo) or URL to a YAML configuration file",
    )
    get_parser.add_argument(
        "--dest",
        default="~/.local/bin",
        help="Destination directory for the binary (default: ~/.local/bin)",
    )
    get_parser.add_argument(
        "--name",
        help="Name to use for the binary (defaults to repository name if not specified)"
        " and is ignored if source is a URL",
    )

    return parser


def main() -> None:  # pragma: no cover
    """Main function to parse arguments and execute commands."""
    parser = create_parser()
    args = parser.parse_args()

    try:
        if args.command == "get":
            _get_tool(args.source, args.dest, args.name)
            return
        if args.command is None:
            parser.print_help()
            return
        if args.command == "version":
            log(f"[yellow]dotbins[/] [bold]v{__version__}[/]")
            return

        config = Config.from_file(args.config_file)
        if args.tools_dir is not None:  # Override tools directory if specified
            config.tools_dir = Path(args.tools_dir)

        if args.command == "init":
            _initialize(config)
        elif args.command == "list":
            _list_tools(config)
        elif args.command == "sync":
            _sync_tools(
                config,
                args.tools,
                args.platform,
                args.architecture,
                args.current,
                args.force,
                not args.no_readme,
                not args.no_copy_config_file,
                not args.no_shell_scripts,
                args.github_token,
                args.verbose,
                args.cleanup,
            )
        elif args.command == "readme":
            write_readme_file(
                config,
                not args.no_print,
                not args.no_file,
                args.verbose,
            )
        elif args.command == "versions":
            config.version_store.print()

    except Exception as e:
        log(f"Error: {e!s}", "error", print_exception=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
