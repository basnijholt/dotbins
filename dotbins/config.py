"""Configuration for dotbins."""

from __future__ import annotations

import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import TypedDict

import requests
import yaml

from .detect_asset import create_system_detector
from .download import download_files_in_parallel, prepare_download_tasks, process_downloaded_files
from .readme import write_readme_file
from .summary import UpdateSummary, display_update_summary
from .utils import (
    current_platform,
    fetch_releases_in_parallel,
    github_url_to_raw_url,
    humanize_time_ago,
    log,
    replace_home_in_path,
    write_shell_scripts,
)
from .versions import VersionStore

if sys.version_info >= (3, 11):
    from typing import Required
else:  # pragma: no cover
    from typing_extensions import Required

DEFAULT_TOOLS_DIR = "~/.dotbins"


def _default_platforms() -> dict[str, list[str]]:
    platform, arch = current_platform()
    return {platform: [arch]}


@dataclass
class Config:
    """Overall configuration for dotbins."""

    tools_dir: Path = field(default=Path(os.path.expanduser(DEFAULT_TOOLS_DIR)))
    platforms: dict[str, list[str]] = field(default_factory=_default_platforms)
    tools: dict[str, ToolConfig] = field(default_factory=dict)
    config_path: Path | None = field(default=None, init=False)
    _bin_dir: Path | None = field(default=None, init=False)
    _update_summary: UpdateSummary = field(default_factory=UpdateSummary, init=False)
    _latest_releases: dict | None = field(default=None, init=False)

    def bin_dir(self, platform: str, arch: str, *, create: bool = False) -> Path:
        """Return the bin directory for a given platform and architecture."""
        bin_dir = (
            self.tools_dir / platform / arch / "bin" if self._bin_dir is None else self._bin_dir
        )
        if create:
            bin_dir.mkdir(parents=True, exist_ok=True)
        return bin_dir

    def set_latest_releases(
        self,
        tools: list[str] | None = None,
        github_token: str | None = None,
        verbose: bool = False,
    ) -> None:
        """Set the latest releases for all tools."""
        if tools is None:
            tools = list(self.tools)
        cfgs = [cfg for tool in tools if (cfg := self.tools[tool])._latest_release is None]
        repos = [cfg.repo for cfg in cfgs]
        releases = fetch_releases_in_parallel(repos, github_token, verbose)
        for cfg, release in zip(cfgs, releases):
            cfg._latest_release = release

    @cached_property
    def version_store(self) -> VersionStore:
        """Return the VersionStore object."""
        return VersionStore(self.tools_dir)

    def validate(self) -> None:
        """Check for missing repos, unknown platforms, etc."""
        for tool_name, tool_config in self.tools.items():
            _validate_tool_config(tool_name, tool_config)

    @classmethod
    def from_file(cls, config_path: str | Path | None = None) -> Config:
        """Load configuration from YAML, or return defaults if no file found."""
        return config_from_file(config_path)

    @classmethod
    def from_url(cls, config_url: str) -> Config:
        """Load configuration from a URL and return a Config object."""
        return config_from_url(config_url)

    @classmethod
    def from_dict(cls, config_dict: RawConfigDict) -> Config:
        """Load configuration from a dictionary and return a Config object."""
        return _config_from_dict(config_dict)

    def make_binaries_executable(self: Config) -> None:
        """Make all binaries executable."""
        for platform, architectures in self.platforms.items():
            for arch in architectures:
                bin_dir = self.bin_dir(platform, arch)
                if bin_dir.exists():
                    for binary in bin_dir.iterdir():
                        if binary.is_file():
                            binary.chmod(binary.stat().st_mode | 0o755)

    def generate_readme(self: Config, write_file: bool = True, verbose: bool = False) -> None:
        """Generate a README.md file in the tools directory with information about installed tools.

        Args:
            write_file: Whether to write the README to a file. If False, the README is only generated
                but not written to disk.
            verbose: Whether to print verbose output.

        """
        if write_file:
            write_readme_file(self, verbose=verbose)

    def update_tools(
        self: Config,
        tools: list[str] | None = None,
        platform: str | None = None,
        architecture: str | None = None,
        current: bool = False,
        force: bool = False,
        generate_readme: bool = True,
        copy_config_file: bool = False,
        github_token: str | None = None,
        verbose: bool = False,
    ) -> None:
        """Update tools.

        Args:
            tools: List of tools to update.
            platform: Platform to update, if not provided, all platforms will be updated.
            architecture: Architecture to update, if not provided, all architectures will be updated.
            current: Whether to update only the current platform and architecture. Overrides platform and architecture.
            force: Whether to force update.
            generate_readme: Whether to generate a README.md file with tool information.
            copy_config_file: Whether to write the config to the tools directory.
            github_token: GitHub token for better rate limiting.
            verbose: Whether to print verbose output.

        """
        if github_token is None and "GITHUB_TOKEN" in os.environ:  # pragma: no cover
            log("Using GitHub token for authentication", "info", "🔑")
            github_token = os.environ["GITHUB_TOKEN"]

        tools_to_update = _tools_to_update(self, tools)
        self.set_latest_releases(tools_to_update, github_token, verbose)
        platforms_to_update, architecture = _platforms_and_archs_to_update(
            platform,
            architecture,
            current,
        )
        download_tasks = prepare_download_tasks(
            self,
            tools_to_update,
            platforms_to_update,
            architecture,
            force,
            verbose,
        )
        download_successes = download_files_in_parallel(download_tasks, github_token, verbose)
        process_downloaded_files(
            download_tasks,
            download_successes,
            self.version_store,
            self._update_summary,
            verbose,
        )
        self.make_binaries_executable()

        # Display the summary
        display_update_summary(self._update_summary)

        if generate_readme:
            self.generate_readme(verbose=verbose)
        _maybe_copy_config_file(copy_config_file, self.config_path, self.tools_dir)

    def generate_shell_scripts(self: Config, print_shell_setup: bool = True) -> None:
        """Generate shell script files for different shells.

        Creates shell scripts in the tools_dir/shell directory that users
        can source in their shell configuration files.
        """
        write_shell_scripts(self.tools_dir, print_shell_setup)


def _maybe_copy_config_file(
    copy_config_file: bool,
    config_path: Path | None,
    tools_dir: Path,
) -> None:
    if not copy_config_file or config_path is None:
        return
    assert config_path.exists()
    tools_config_path = tools_dir / "dotbins.yaml"
    if tools_config_path.exists():
        try:
            cfg1 = yaml.safe_load(config_path.read_text())
            cfg2 = yaml.safe_load(tools_config_path.read_text())
        except Exception:  # pragma: no cover
            return
        is_same = cfg1 == cfg2
        if is_same:
            return
    log("Copying config to tools directory as `dotbins.yaml`", "info")
    shutil.copy(config_path, tools_config_path)


def _platforms_and_archs_to_update(
    platform: str | None,
    architecture: str | None,
    current: bool,
) -> tuple[list[str] | None, str | None]:
    if current:
        platform, architecture = current_platform()
        platforms_to_update = [platform]
    else:
        platforms_to_update = [platform] if platform else None  # type: ignore[assignment]
    return platforms_to_update, architecture


def _tools_to_update(config: Config, tools: list[str] | None) -> list[str] | None:
    if tools:
        for tool in tools:
            if tool not in config.tools:
                log(f"Unknown tool: {tool}", "error")
                sys.exit(1)
        return tools
    return None


@dataclass
class ToolConfig:
    """Holds all config data for a single tool, without doing heavy logic."""

    tool_name: str
    repo: str
    binary_name: list[str] = field(default_factory=list)
    binary_path: list[str] = field(default_factory=list)
    extract_binary: bool | None = None
    asset_patterns: dict[str, dict[str, str | None]] = field(default_factory=dict)
    platform_map: dict[str, str] = field(default_factory=dict)
    arch_map: dict[str, str] = field(default_factory=dict)
    _latest_release: dict | None = field(default=None, init=False)

    def bin_spec(self, arch: str, platform: str) -> BinSpec:
        """Get a BinSpec object for the tool."""
        return BinSpec(tool_config=self, version=self.latest_version, arch=arch, platform=platform)

    @property
    def latest_version(self) -> str:
        """Get the latest version for the tool."""
        assert self._latest_release is not None
        return self._latest_release["tag_name"].lstrip("v")


@dataclass(frozen=True)
class BinSpec:
    """Specific arch and platform for a tool."""

    tool_config: ToolConfig
    version: str
    arch: str
    platform: str

    @property
    def tool_arch(self) -> str:
        """Get the architecture in the tool's convention."""
        return self.tool_config.arch_map.get(self.arch, self.arch)

    @property
    def tool_platform(self) -> str:
        """Get the platform in the tool's convention."""
        return self.tool_config.platform_map.get(self.platform, self.platform)

    def asset_pattern(self) -> str | None:
        """Get the formatted asset pattern for the tool."""
        return _maybe_asset_pattern(
            self.tool_config,
            self.platform,
            self.arch,
            self.version,
            self.tool_platform,
            self.tool_arch,
        )

    def matching_asset(self) -> _AssetDict | None:
        """Find a matching asset for the tool."""
        asset_pattern = self.asset_pattern()
        assert self.tool_config._latest_release is not None
        assets = self.tool_config._latest_release["assets"]
        if asset_pattern is None:
            return _auto_detect_asset(self.platform, self.arch, assets)
        return _find_matching_asset(asset_pattern, assets)

    def skip_download(self, config: Config, force: bool) -> bool:
        """Check if download should be skipped (binary already exists)."""
        tool_info = config.version_store.get_tool_info(
            self.tool_config.tool_name,
            self.platform,
            self.arch,
        )
        destination_dir = config.bin_dir(self.platform, self.arch)
        all_exist = all(
            (destination_dir / binary_name).exists() for binary_name in self.tool_config.binary_name
        )
        if tool_info and tool_info["version"] == self.version and all_exist and not force:
            dt = humanize_time_ago(tool_info["updated_at"])
            log(
                f"[b]{self.tool_config.tool_name} v{self.version}[/] for"
                f" [b]{self.platform}/{self.arch}[/] is already up to date"
                f" (installed [b]{dt}[/] ago) use --force to re-download.",
                "success",
            )
            return True
        return False


class RawConfigDict(TypedDict, total=False):
    """TypedDict for raw data passed to config_from_dict."""

    tools_dir: str
    platforms: dict[str, list[str]]
    tools: dict[str, str | RawToolConfigDict]


class RawToolConfigDict(TypedDict, total=False):
    """TypedDict for raw data passed to build_tool_config."""

    repo: Required[str]  # Repository in format "owner/repo"
    extract_binary: bool | None  # Whether to extract binary from archive
    platform_map: dict[str, str]  # Map from system platform to tool's platform name
    arch_map: dict[str, str]  # Map from system architecture to tool's architecture name
    binary_name: str | list[str]  # Name(s) of the binary file(s)
    binary_path: str | list[str]  # Path(s) to binary within archive
    asset_patterns: str | dict[str, str] | dict[str, dict[str, str | None]]


class _AssetDict(TypedDict):
    """TypedDict for an asset in the latest_release."""

    name: str
    browser_download_url: str


def build_tool_config(
    tool_name: str,
    raw_data: RawToolConfigDict,
    platforms: dict[str, list[str]] | None = None,
) -> ToolConfig:
    """Create a ToolConfig object from raw YAML data.

    Performing any expansions
    or normalization that used to happen inside the constructor.
    """
    if not platforms:
        platforms = _default_platforms()

    # Safely grab data from raw_data (or set default if missing).
    repo = raw_data.get("repo") or ""
    extract_binary = raw_data.get("extract_binary")
    platform_map = raw_data.get("platform_map", {})
    arch_map = raw_data.get("arch_map", {})
    # Might be str or list
    raw_binary_name = raw_data.get("binary_name", tool_name)
    raw_binary_path = raw_data.get("binary_path", [])

    # Convert to lists
    binary_name: list[str] = _ensure_list(raw_binary_name)
    binary_path: list[str] = _ensure_list(raw_binary_path)

    # Normalize asset patterns to dict[platform][arch].
    raw_patterns = raw_data.get("asset_patterns")
    asset_patterns = _normalize_asset_patterns(tool_name, raw_patterns, platforms)

    # Build our final data-class object
    return ToolConfig(
        tool_name=tool_name,
        repo=repo,
        binary_name=binary_name,
        binary_path=binary_path,
        extract_binary=extract_binary,
        asset_patterns=asset_patterns,
        platform_map=platform_map,
        arch_map=arch_map,
    )


def config_from_file(config_path: str | Path | None = None) -> Config:
    """Load configuration from YAML, or return defaults if no file found."""
    path = _find_config_file(config_path)
    if path is None:
        return Config()

    try:
        with open(path) as f:
            data: RawConfigDict = yaml.safe_load(f) or {}  # type: ignore[assignment]
    except FileNotFoundError:  # pragma: no cover
        log(f"Configuration file not found: {path}", "warning")
        return Config()
    except yaml.YAMLError:  # pragma: no cover
        log(
            f"Invalid YAML in configuration file: {path}",
            "error",
            print_exception=True,
        )
        return Config()
    cfg = _config_from_dict(data)
    cfg.config_path = path
    return cfg


def _config_from_dict(data: RawConfigDict) -> Config:
    tools_dir = data.get("tools_dir", DEFAULT_TOOLS_DIR)
    platforms = data.get("platforms", _default_platforms())
    raw_tools = data.get("tools", {})

    tools_dir_path = Path(os.path.expanduser(tools_dir))

    tool_configs: dict[str, ToolConfig] = {}
    for tool_name, tool_data in raw_tools.items():
        if isinstance(tool_data, str):
            tool_data = {"repo": tool_data}  # noqa: PLW2901
        tool_configs[tool_name] = build_tool_config(tool_name, tool_data, platforms)

    config = Config(tools_dir=tools_dir_path, platforms=platforms, tools=tool_configs)
    config.validate()
    return config


def config_from_url(config_url: str) -> Config:
    """Download a configuration file from a URL and return a Config object."""
    from .config import Config

    config_url = github_url_to_raw_url(config_url)
    try:
        response = requests.get(config_url, timeout=30)
        response.raise_for_status()
        yaml_data = yaml.safe_load(response.content)
        return Config.from_dict(yaml_data)
    except requests.RequestException as e:  # pragma: no cover
        log(f"Failed to download configuration: {e}", "error", print_exception=True)
        sys.exit(1)
    except yaml.YAMLError as e:  # pragma: no cover
        log(f"Invalid YAML configuration: {e}", "error", print_exception=True)
        sys.exit(1)
    except Exception as e:  # pragma: no cover
        log(f"Error processing tools from URL: {e}", "error", print_exception=True)
        sys.exit(1)


def _normalize_asset_patterns(  # noqa: PLR0912
    tool_name: str,
    patterns: str | dict[str, str] | dict[str, dict[str, str | None]] | None,
    platforms: dict[str, list[str]],
) -> dict[str, dict[str, str | None]]:
    """Normalize the asset_patterns into a dict.

    Of the form:
    ```{ platform: { arch: pattern_str } }```.
    """
    # Start by initializing empty patterns for each platform/arch
    normalized: dict[str, dict[str, str | None]] = {
        platform: dict.fromkeys(arch_list) for platform, arch_list in platforms.items()
    }
    if not patterns:
        return normalized

    # If user gave a single string, apply it to all platform/arch combos
    if isinstance(patterns, str):
        for platform, arch_list in normalized.items():
            for arch in arch_list:
                normalized[platform][arch] = patterns
        return normalized

    # If user gave a dict, it might be "platform: pattern" or "platform: {arch: pattern}"
    if isinstance(patterns, dict):
        for platform, p_val in patterns.items():
            # Skip unknown platforms
            if platform not in normalized:
                log(
                    f"Tool [b]{tool_name}[/]: [b]'asset_patterns'[/] uses unknown platform [b]'{platform}'[/]",
                    "error",
                )
                continue

            # If p_val is a single string, apply to all arch
            if isinstance(p_val, str):
                for arch in normalized[platform]:
                    normalized[platform][arch] = p_val
            # Otherwise it might be {arch: pattern}
            elif isinstance(p_val, dict):
                for arch, pattern_str in p_val.items():
                    if arch in normalized[platform]:
                        normalized[platform][arch] = pattern_str
                    else:
                        log(
                            f"Tool [b]{tool_name}[/]: [b]'asset_patterns'[/] uses unknown arch [b]'{arch}'[/]",
                            "error",
                        )
    return normalized


def _find_config_file(config_path: str | Path | None) -> Path | None:
    """Look for the user-specified path or common defaults."""
    if config_path is not None:
        path = Path(config_path)
        if path.exists():
            log(f"Loading configuration from: {replace_home_in_path(path, '~')}", "success")
            return path
        log(f"Config path provided but not found: {path}", "warning")
        return None

    home = Path.home()
    candidates = [
        Path.cwd() / "dotbins.yaml",
        home / ".config" / "dotbins" / "config.yaml",
        home / ".config" / "dotbins.yaml",
        home / ".dotbins.yaml",
        home / ".dotbins" / "dotbins.yaml",
    ]
    for candidate in candidates:
        if candidate.exists():
            log(f"Loading configuration from: {replace_home_in_path(candidate, '~')}", "success")
            return candidate

    log("No configuration file found, using default settings", "warning")
    return None


def _ensure_list(value: str | list[str]) -> list[str]:
    if isinstance(value, list):
        return value
    return [value]


def _validate_tool_config(tool_name: str, tool_config: ToolConfig) -> None:
    # Basic checks
    if not tool_config.repo:
        log(f"Tool [b]{tool_name}[/] is missing required field [b]'repo'[/]", "error")

    # If binary lists differ in length, log an error
    if len(tool_config.binary_name) != len(tool_config.binary_path) and tool_config.binary_path:
        log(
            f"Tool [b]{tool_name}[/]: [b]'binary_name'[/] and [b]'binary_path'[/] must have the same length if both are specified as lists.",
            "error",
        )


def _maybe_asset_pattern(
    tool_config: ToolConfig,
    platform: str,
    arch: str,
    version: str,
    tool_platform: str,
    tool_arch: str,
) -> str | None:
    """Get the formatted asset pattern for the tool."""
    search_pattern = tool_config.asset_patterns[platform][arch]
    if search_pattern is None:
        log(
            f"No [b]asset_pattern[/] provided for [b]{platform}/{arch}[/]",
            "info",
            "ℹ️",  # noqa: RUF001
        )
        return None
    return (
        search_pattern.format(
            version=version,
            platform=tool_platform,
            arch=tool_arch,
        )
        .replace("{version}", ".*")
        .replace("{arch}", ".*")
        .replace("{platform}", ".*")
    )


def _auto_detect_asset(
    platform: str,
    arch: str,
    assets: list[_AssetDict],
) -> _AssetDict | None:
    """Auto-detect an asset for the tool."""
    log(f"Auto-detecting asset for [b]{platform}/{arch}[/]", "info", "🔍")
    detect_fn = create_system_detector(platform, arch)
    asset_names = [x["name"] for x in assets]
    asset_name, candidates, err = detect_fn(asset_names)
    if err is not None:
        if err.endswith("matches found"):
            assert candidates is not None
            log(f"Found multiple candidates: {candidates}, selecting first", "info")
            asset_name = sorted(candidates)[0]
        else:
            if candidates:
                log(f"Found multiple candidates: {candidates}, manually select one", "info", "⁉️")
            log(f"Error detecting asset: {err}", "error")
            return None
    asset = assets[asset_names.index(asset_name)]
    log(f"Found asset: {asset['name']}", "success")
    return asset


def _find_matching_asset(
    asset_pattern: str,
    assets: list[_AssetDict],
) -> _AssetDict | None:
    """Find a matching asset for the tool."""
    log(f"Looking for asset with pattern: {asset_pattern}", "info", "🔍")
    for asset in assets:
        if re.search(asset_pattern, asset["name"]):
            log(f"Found matching asset: {asset['name']}", "success")
            return asset
    log(f"No asset matching '{asset_pattern}' found in {assets}", "warning")
    return None
