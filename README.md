# dotbins 🧰

![Build](https://github.com/basnijholt/dotbins/actions/workflows/pytest.yml/badge.svg)
[![Coverage](https://img.shields.io/codecov/c/github/basnijholt/dotbins)](https://codecov.io/gh/basnijholt/dotbins)
[![GitHub](https://img.shields.io/github/stars/basnijholt/dotbins.svg?style=social)](https://github.com/basnijholt/dotbins/stargazers)
[![PyPI](https://img.shields.io/pypi/v/dotbins.svg)](https://pypi.python.org/pypi/dotbins)
[![License](https://img.shields.io/github/license/basnijholt/dotbins)](https://github.com/basnijholt/dotbins/blob/main/LICENSE)
[![Downloads](https://img.shields.io/pypi/dm/dotbins)](https://pypi.python.org/pypi/dotbins)
![Open Issues](https://img.shields.io/github/issues-raw/basnijholt/dotbins)

Introducing `dotbins` - a utility for managing CLI tool binaries in your dotfiles repository.
It downloads and organizes binaries for popular tools across multiple platforms (macOS, Linux) and architectures (amd64, arm64), helping you maintain a consistent set of CLI utilities across all your environments.

Whether you work across multiple machines or just want a version-controlled setup for your essential command-line tools, dotbins makes it easy to keep everything synchronized and updated. 🚀

<details><summary><b><u>[ToC]</u></b> 📚</summary>

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [:bulb: Why I Created dotbins](#bulb-why-i-created-dotbins)
- [:star2: Features](#star2-features)
- [:books: Usage](#books-usage)
  - [Commands](#commands)
- [:hammer_and_wrench: Installation](#hammer_and_wrench-installation)
- [:gear: Configuration](#gear-configuration)
  - [Basic Configuration](#basic-configuration)
  - [Tool Configuration](#tool-configuration)
  - [Platform and Architecture Mapping](#platform-and-architecture-mapping)
  - [Pattern Variables](#pattern-variables)
  - [Multiple Binaries](#multiple-binaries)
  - [Configuration Examples](#configuration-examples)
    - [Standard Tool](#standard-tool)
    - [Tool with Multiple Binaries](#tool-with-multiple-binaries)
    - [Platform-Specific Tool](#platform-specific-tool)
  - [Full Configuration Example](#full-configuration-example)
- [:bulb: Examples](#bulb-examples)
- [:computer: Shell Integration](#computer-shell-integration)
- [:mag: Finding Tool Patterns](#mag-finding-tool-patterns)
- [:heart: Support and Contributions](#heart-support-and-contributions)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

</details>

## :bulb: Why I Created dotbins

As a developer who frequently works across multiple environments, I faced a common frustration: I'd carefully maintain my dotfiles repository with all my preferred configurations, only to find myself unable to use my favorite CLI tools when working on remote systems where I lacked admin permissions.

The scenario was always the same - I'd SSH into a server, clone my dotfiles, and then... hit a wall.
My aliases and configurations were there, but the actual tools they relied on (`fzf`, `bat`, `delta`, etc.) weren't available, and I couldn't easily install them without sudo access.

`dotbins` was born out of this frustration.
It allows me to:

1. Track pre-compiled binaries in a separate Git repository (using Git LFS for efficient storage)
2. Include this repository as a submodule in my dotfiles
3. Ensure all my essential tools are immediately available after cloning, regardless of system permissions

Now when I clone my dotfiles on any new system, I get not just my configurations but also all the CLI tools I depend on for productivity
No package manager, no sudo, no problem.

## :star2: Features

* 🌐 Supports multiple platforms (macOS, Linux) and architectures (amd64, arm64)
* 📦 Downloads and organizes binaries from GitHub releases
* 🔄 Updates tools to their latest versions with a single command
* 🧩 Extracts binaries from various archive formats (zip, tar.gz)
* 📂 Organizes tools by platform and architecture for easy access
* 🔍 Includes a tool to analyze GitHub releases to help configure new tools
* 🐙 Easy integration with your dotfiles repository for version control

## :books: Usage

> [!TIP]
> Use `uvx dotbins` and create a `~/.config/dotbins/config.yaml` file to store your configuration.

To use `dotbins`, you'll need to familiarize yourself with its commands:

```bash
dotbins --help
```

<!-- CODE:BASH:START -->
<!-- echo '```bash' -->
<!-- dotbins --help -->
<!-- echo '```' -->
<!-- CODE:END -->

<!-- OUTPUT:START -->
<!-- ⚠️ This content is auto-generated by `markdown-code-runner`. -->
```bash
usage: dotbins [-h] [-v] [--tools-dir TOOLS_DIR] [--config-file CONFIG_FILE]
               {list,update,init,analyze,version} ...

dotbins - Manage CLI tool binaries in your dotfiles repository

positional arguments:
  {list,update,init,analyze,version}
                        Command to execute
    list                List available tools
    update              Update tools
    init                Initialize directory structure
    analyze             Analyze GitHub releases for a tool
    version             Print version information

options:
  -h, --help            show this help message and exit
  -v, --verbose         Enable verbose output (default: False)
  --tools-dir TOOLS_DIR
                        Tools directory (default: None)
  --config-file CONFIG_FILE
                        Path to configuration file (default: None)
```

<!-- OUTPUT:END -->

### Commands

1. **init** - Initialize the tools directory structure
2. **list** - List available tools defined in your configuration
3. **update** - Download or update tools
4. **analyze** - Analyze GitHub releases to help configure new tools
5. **version** - Print version information

## :hammer_and_wrench: Installation

To install `dotbins`, simply use pip:

```bash
pip install dotbins
```

You'll also need to create or update your `dotbins.yaml` configuration file either in the same directory as the script or at a custom location specified with `--tools-dir`.

## :gear: Configuration

dotbins uses a YAML configuration file to define the tools and settings. The configuration file is searched in the following locations (in order):

1. Explicitly provided path (using `--config-file` option)
2. `./dotbins.yaml` (current directory)
3. `~/.config/dotbins/config.yaml` (XDG config directory)
4. `~/.config/dotbins.yaml` (XDG config directory, flat)
5. `~/.dotbins.yaml` (home directory)
6. `~/.dotfiles/dotbins.yaml` (default dotfiles location)

The first valid configuration file found will be used. If no configuration file is found, default settings will be used.

### Basic Configuration

```yaml
# Basic settings
dotfiles_dir: ~/.dotfiles
tools_dir: ~/.dotfiles/tools

# Target platforms and architectures
platforms:
  - linux
  - macos
architectures:
  - amd64
  - arm64

# Tool definitions
tools:
  # Tool configuration entries
```

### Tool Configuration

Each tool must be configured with these fields:

```yaml
tool-name:
  repo: owner/repo                 # Required: GitHub repository
  extract_binary: true             # Whether to extract from archive (true) or direct download (false)
  binary_name: executable-name     # Name of the resulting binary(ies)
  binary_path: path/to/binary      # Path to the binary within the archive
  # Option 1: Platform-specific patterns
  asset_patterns:                  # Required: Asset patterns for each platform
    linux: pattern-for-linux.tar.gz
    macos: pattern-for-macos.tar.gz
  # Option 2: Single pattern for all platforms
  asset_patterns: pattern-for-all-platforms.tar.gz  # Global pattern for all platforms
```

### Platform and Architecture Mapping

If the tool uses different naming for platforms or architectures:

```yaml
tool-name:
  # Basic fields...
  platform_map:                    # Optional: Platform name mapping
    macos: darwin                  # Converts "macos" to "darwin" in patterns
  arch_map:                        # Optional: Architecture name mapping
    amd64: x86_64                  # Converts "amd64" to "x86_64" in patterns
    arm64: aarch64                 # Converts "arm64" to "aarch64" in patterns
```

### Pattern Variables

In asset patterns, you can use these variables:
- `{version}` - Release version (without 'v' prefix)
- `{platform}` - Platform name (after applying platform_map)
- `{arch}` - Architecture name (after applying arch_map)

### Multiple Binaries

For tools that provide multiple binaries:

```yaml
tool-name:
  # Other fields...
  binary_name: [main-binary, additional-binary]
  binary_path: [path/to/main, path/to/additional]
```

### Configuration Examples

#### Standard Tool

```yaml
ripgrep:
  repo: BurntSushi/ripgrep
  extract_binary: true
  binary_name: rg
  binary_path: rg
  asset_patterns:
    linux: ripgrep-{version}-x86_64-unknown-linux-musl.tar.gz
    macos: ripgrep-{version}-x86_64-apple-darwin.tar.gz
  arch_map:
    amd64: x86_64
    arm64: aarch64
```

#### Tool with Multiple Binaries

```yaml
uv:
  repo: astral-sh/uv
  extract_binary: true
  binary_name: [uv, uvx]
  binary_path: [uv-*/uv, uv-*/uvx]
  asset_patterns:
    linux: uv-{arch}-unknown-linux-gnu.tar.gz
    macos: uv-{arch}-apple-darwin.tar.gz
  arch_map:
    amd64: x86_64
    arm64: aarch64
```

#### Platform-Specific Tool

```yaml
linux-only-tool:
  repo: owner/linux-tool
  extract_binary: true
  binary_name: linux-tool
  binary_path: bin/linux-tool
  asset_patterns:
    linux: linux-tool-{version}-{arch}.tar.gz
    macos: null  # No macOS version available
```

### Full Configuration Example

<!-- CODE:BASH:START -->
<!-- echo '```yaml' -->
<!-- cat dotbins.yaml -->
<!-- echo '```' -->
<!-- CODE:END -->

<!-- OUTPUT:START -->
<!-- ⚠️ This content is auto-generated by `markdown-code-runner`. -->
```yaml
# Configuration
dotfiles_dir: ~/.dotfiles
tools_dir: ~/.dotfiles/tools

# Target platforms and architectures
platforms:
  - linux
  - macos
architectures:
  - amd64
  - arm64

# Tool definitions
tools:
  fzf:
    repo: junegunn/fzf
    extract_binary: true
    binary_name: fzf
    binary_path: fzf
    asset_patterns: fzf-{version}-{platform}_{arch}.tar.gz
    platform_map:
      macos: darwin

  bat:
    repo: sharkdp/bat
    extract_binary: true
    binary_name: bat
    binary_path: bat-v{version}-{arch}-*/bat
    arch_map:
      amd64: x86_64
      arm64: aarch64
    asset_patterns:
      linux: bat-v{version}-{arch}-unknown-linux-gnu.tar.gz
      macos: bat-v{version}-{arch}-apple-darwin.tar.gz

  eza:
    repo: eza-community/eza
    extract_binary: true
    binary_name: eza
    binary_path: eza
    arch_map:
      amd64: x86_64
      arm64: aarch64
    asset_patterns:
      linux: eza_{arch}-unknown-linux-gnu.tar.gz
      macos: null  # No macOS binaries available as of now

  zoxide:
    repo: ajeetdsouza/zoxide
    extract_binary: true
    binary_name: zoxide
    binary_path: zoxide
    arch_map:
      amd64: x86_64
      arm64: aarch64
    asset_patterns:
      linux: zoxide-{version}-{arch}-unknown-linux-musl.tar.gz
      macos: zoxide-{version}-{arch}-apple-darwin.tar.gz

  delta:
    repo: dandavison/delta
    extract_binary: true
    binary_name: delta
    binary_path: delta-{version}-{arch}-*/delta
    arch_map:
      amd64: x86_64
      arm64: aarch64
    asset_patterns:
      linux: delta-{version}-{arch}-unknown-linux-gnu.tar.gz
      macos: delta-{version}-{arch}-apple-darwin.tar.gz

  uv:
    repo: astral-sh/uv
    extract_binary: true
    binary_name: [uv, uvx]
    binary_path: [uv-*/uv, uv-*/uvx]
    arch_map:
      amd64: x86_64
      arm64: aarch64
    asset_patterns:
      linux: uv-{arch}-unknown-linux-gnu.tar.gz
      macos: uv-{arch}-apple-darwin.tar.gz

  micromamba:
    repo: mamba-org/micromamba-releases
    extract_binary: true
    binary_name: micromamba
    binary_path: bin/micromamba
    arch_map:
      amd64: "64"
      arm64: arm64
    asset_patterns:
      linux: micromamba-linux-64.tar.bz2
      macos: micromamba-osx-arm64.tar.bz2
```

<!-- OUTPUT:END -->

## :bulb: Examples

List available tools:
```bash
dotbins list
```

Update all tools for all platforms:
```bash
dotbins update
```

Update specific tools only:
```bash
dotbins update fzf bat
```

Update tools for a specific platform/architecture:
```bash
dotbins update -p macos -a arm64
```

Analyze a GitHub repository to help configure a new tool:
```bash
dotbins analyze owner/repo
```

## :computer: Shell Integration

Add this to your shell configuration file (e.g., .bashrc, .zshrc) to use the platform-specific binaries:

<!-- CODE:BASH:START -->
<!-- echo '```bash' -->
<!-- dotbins init -->
<!-- echo '```' -->
<!-- CODE:END -->

<!-- OUTPUT:START -->
<!-- ⚠️ This content is auto-generated by `markdown-code-runner`. -->
```bash
📝 Loading configuration from: /home/runner/work/dotbins/dotbins/dotbins.yaml
# 🛠️ dotbins initialized tools directory structure

# Add this to your shell configuration file (e.g., .bashrc, .zshrc):

# dotbins - Add platform-specific binaries to PATH
_os=$(uname -s | tr '[:upper:]' '[:lower:]')
[[ "$_os" == "darwin" ]] && _os="macos"

_arch=$(uname -m)
[[ "$_arch" == "x86_64" ]] && _arch="amd64"
[[ "$_arch" == "aarch64" || "$_arch" == "arm64" ]] && _arch="arm64"

export PATH="$HOME/.dotfiles/tools/$_os/$_arch/bin:$PATH"

```

<!-- OUTPUT:END -->

## :mag: Finding Tool Patterns

To add a new tool, you can use the `analyze` command to examine GitHub release assets:

```bash
dotbins analyze sharkdp/bat
```

This will suggest a configuration for the tool based on its release assets.

## :heart: Support and Contributions

We appreciate your feedback and contributions! If you encounter any issues or have suggestions for improvements, please file an issue on the GitHub repository. We also welcome pull requests for bug fixes or new features.

Happy tooling! 🧰🛠️🎉
