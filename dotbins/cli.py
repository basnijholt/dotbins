"""Command-line interface for dotbins."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rich_argparse import RichHelpFormatter

from . import __version__
from .config import DEFAULT_TOOLS_DIR, Config, build_tool_config
from .utils import current_platform, log, replace_home_in_path


def _list_tools(config: Config) -> None:
    """List all tools defined in the configuration file.

    Prints each tool name along with its GitHub repository.
    """
    log("Available tools:", "info", "🔧")
    for tool, tool_config in config.tools.items():
        log(f"  {tool} (from {tool_config.repo})", "success")


_SAMPLE_CONFIG = f"""\
# dotbins sample configuration
# Generated by `dotbins init`
# See https://github.com/basnijholt/dotbins for more information

# Directory where tool binaries will be stored
tools_dir: {DEFAULT_TOOLS_DIR}

# Target platforms and architectures for which to download binaries
# These determine which system binaries will be downloaded and managed
platforms:
  linux:
    - amd64  # x86_64
    - arm64  # aarch64
  macos:
    - arm64  # Apple Silicon
  windows:
    - amd64  # 64-bit Windows

# Tool definitions
# Format: tool_name: owner/repo or detailed configuration
tools:
  # Essential CLI tools with minimal configuration
  bat: sharkdp/bat           # Syntax-highlighted cat replacement
  fzf: junegunn/fzf          # Fuzzy finder for the terminal
  zoxide: ajeetdsouza/zoxide # Smarter cd command with frecency

  # Example with shell customization
  # starship:
  #   repo: starship/starship
  #   shell_code: |
  #     eval "$(starship init bash)"  # Change to your shell

# For more configuration options, visit:
# https://github.com/basnijholt/dotbins#gear-configuration
"""


def _initialize(config: Config) -> None:
    """Initialize the tools directory structure and shell integration.

    If no config file is provided, a simple config file will be created in the
    default tools directory (~/.dotbins/config.yaml).

    Creates the necessary directories for all platforms and architectures,
    generates shell integration scripts, and creates a README.md file.
    """
    tools_dir = replace_home_in_path(config.tools_dir, "~")
    if config.config_path is None:
        config_file = config.tools_dir / "dotbins.yaml"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(_SAMPLE_CONFIG)
        log(
            "No config file provided, creating a [bold green]sample config file[/]"
            f" in the tools directory at [red bold]{config_file}[/] with the following contents:",
            "info",
            "🔧",
        )
        log(f"[yellow]{config_file.read_text()}[/]", "default")

    for platform, architectures in config.platforms.items():
        for arch in architectures:
            config.bin_dir(platform, arch, create=True)
    log(f"dotbins initialized tools directory structure in `tools_dir={tools_dir}`", "success", "🛠️")
    config.generate_shell_scripts()
    config.generate_readme()


def _get_tool(
    source: str,
    dest_dir: str | Path,
    name: str | None = None,
    tag: str | None = None,
) -> None:
    """Get a specific tool and install it directly to a location.

    This command bypasses the standard configuration and tools directory,
    downloading a specific tool directly to the specified directory.
    Useful for quick one-off installations.

    Args:
        source: GitHub repository in the format 'owner/repo' or URL/path to a YAML configuration file.
        dest_dir: Directory to install the binary to (e.g., ~/.local/bin)
        name: Optional name to use for the binary (defaults to repo name)
        tag: Optional tag to use for the binary (if None, the latest release will be used)

    """
    platform, arch = current_platform()
    dest_dir_path = Path(dest_dir).expanduser()
    # Determine if source is a URL or a repo based on format
    if "://" in source and source.endswith(".yaml"):
        config = Config.from_url(source)
    elif Path(source).exists():
        config = Config.from_file(source)
    else:
        tool_name = name or source.split("/")[-1]
        config = Config(
            tools_dir=dest_dir_path,
            platforms={platform: [arch]},
            tools={tool_name: build_tool_config(tool_name, {"repo": source, "tag": tag})},
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

    # Add get command
    get_parser = subparsers.add_parser(
        "get",
        help="Download and install a tool directly without configuration file",
        formatter_class=RichHelpFormatter,
    )
    get_parser.add_argument(
        "source",
        help="GitHub repository (owner/repo) or URL/path to a YAML configuration file",
    )
    get_parser.add_argument(
        "--dest",
        default="~/.local/bin",
        help="Destination directory for the binary (default: ~/.local/bin)",
    )
    get_parser.add_argument(
        "--name",
        help="Name to use for the binary (defaults to repository name if not specified) and is ignored if source is a URL",
    )
    get_parser.add_argument(
        "--tag",
        help="Tag to use for the binary (if None, the latest release will be used)",
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
        "--pin-to-manifest",
        action="store_true",
        help="Use the tags from the `manifest.json` file instead of the latest release"
        " or the tag specified in the config file",
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
        "--github-token",
        type=str,
        help="GitHub token to use for API requests (helps with rate limits and private repos)",
    )

    # init command
    _init_parser = subparsers.add_parser(
        "init",
        help="Initialize directory structure and generate shell integration scripts",
    )

    # list command
    _list_parser = subparsers.add_parser(
        "list",
        help="List all available tools defined in your configuration",
    )

    # status command
    _status_parser = subparsers.add_parser(
        "status",
        help="Show installed tool versions and when they were last updated",
        formatter_class=RichHelpFormatter,
    )
    _status_parser.add_argument(
        "-c",
        "--compact",
        action="store_true",
        help="Show a compact view with one line per tool (default)",
    )
    _status_parser.add_argument(
        "-f",
        "--full",
        action="store_true",
        help="Show the full detailed view (overrides --compact)",
    )
    _status_parser.add_argument(
        "--current",
        action="store_true",
        help="Only show tools for the current platform/architecture",
    )
    _status_parser.add_argument(
        "-p",
        "--platform",
        type=str,
        help="Filter by platform (e.g., linux, macos)",
    )
    _status_parser.add_argument(
        "-a",
        "--architecture",
        type=str,
        help="Filter by architecture (e.g., amd64, arm64)",
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

    # version command
    _version_parser = subparsers.add_parser(
        "version",
        help="Print dotbins version information",
    )

    return parser


def main() -> None:  # pragma: no cover
    """Main function to parse arguments and execute commands."""
    parser = create_parser()
    args = parser.parse_args()

    try:
        if args.command == "get":
            _get_tool(args.source, args.dest, args.name, args.tag)
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
            config.sync_tools(
                tools=args.tools,
                platform=args.platform,
                architecture=args.architecture,
                current=args.current,
                force=args.force,
                generate_readme=not args.no_readme,
                copy_config_file=not args.no_copy_config_file,
                github_token=args.github_token,
                verbose=args.verbose,
                generate_shell_scripts=not args.no_shell_scripts,
                pin_to_manifest=args.pin_to_manifest,
            )
        elif args.command == "readme":
            config.generate_readme(not args.no_file, args.verbose)
        elif args.command == "status":
            platform = args.platform
            arch = args.architecture

            if args.current:
                platform, arch = current_platform()

            # If both --compact and --full are specified, --compact takes precedence
            config.manifest.print(
                config,
                compact=not args.full,
                platform=platform,
                architecture=arch,
            )

    except Exception as e:
        log(f"Error: {e!s}", "error", print_exception=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
