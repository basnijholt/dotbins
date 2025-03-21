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
    generate_readme: bool,
    copy_config_file: bool,
    generate_shell_scripts: bool,
    github_token: str | None,
    verbose: bool,
) -> None:
    """Update tools based on command line arguments."""
    config.update_tools(
        tools,
        platform,
        architecture,
        current,
        force,
        generate_readme,
        copy_config_file,
        github_token,
        verbose,
    )
    if generate_shell_scripts:
        config.generate_shell_scripts(print_shell_setup=False)
        log("To see the shell setup instructions, run `dotbins init`", "info", "ℹ️")  # noqa: RUF001


def _initialize(config: Config) -> None:
    """Initialize the tools directory structure."""
    for platform, architectures in config.platforms.items():
        for arch in architectures:
            config.bin_dir(platform, arch, create=True)
    tools_dir = replace_home_in_path(config.tools_dir, "~")
    log(f"dotbins initialized tools directory structure in `tools_dir={tools_dir}`", "success", "🛠️")
    config.generate_shell_scripts()
    config.generate_readme()


def _get_tool(source: str, dest_dir: str | Path, name: str | None = None) -> None:
    """Get a specific tool from a GitHub repository and install it directly.

    This command bypasses the configuration file and installs the tool directly
    to the specified directory.

    Args:
        source: GitHub repository in the format 'owner/repo' or URL to a YAML configuration file
        dest_dir: Directory to install the binary to
        name: Name to use for the tool (if different from repo name)

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
    config.update_tools(current=True, force=True, generate_readme=False, copy_config_file=False)


def create_parser() -> argparse.ArgumentParser:
    """Create command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="dotbins - Manage CLI tool binaries in your dotfiles repository",
        formatter_class=RichHelpFormatter,
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
    _list_parser = subparsers.add_parser(
        "list",
        help="List available tools",
    )

    # update command
    update_parser = subparsers.add_parser(
        "update",
        help="Update tools",
        formatter_class=RichHelpFormatter,
    )
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
        "--no-shell-scripts",
        action="store_true",
        help="Skip generating shell scripts that can be sourced in shell configuration files",
    )
    update_parser.add_argument(
        "--no-readme",
        action="store_true",
        help="Skip generating README.md file",
    )
    update_parser.add_argument(
        "--no-copy-config-file",
        action="store_true",
        help="Skip writing the config file to the tools directory",
    )
    update_parser.add_argument(
        "--github-token",
        type=str,
        help="GitHub token to use for private repositories",
    )

    # init command
    _init_parser = subparsers.add_parser(
        "init",
        help="Initialize directory structure",
    )

    # version command
    _version_parser = subparsers.add_parser(
        "version",
        help="Print version information",
    )

    # versions command
    _versions_parser = subparsers.add_parser(
        "versions",
        help="Show installed tool versions and their last update times",
    )

    # Add readme command
    readme_parser = subparsers.add_parser(
        "readme",
        help="Generate README.md file with tool information",
        formatter_class=RichHelpFormatter,
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

    # Add get command
    get_parser = subparsers.add_parser(
        "get",
        help="Download and install a tool directly from GitHub or from a remote configuration",
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
        help="Name to use for the tool when installing from a repository (ignored for config URLs)",
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
        elif args.command == "update":
            _update_tools(
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
