# dotbins 🧰

![Build](https://github.com/basnijholt/dotbins/actions/workflows/pytest.yml/badge.svg)
[![Coverage](https://img.shields.io/codecov/c/github/basnijholt/dotbins)](https://codecov.io/gh/basnijholt/dotbins)
[![GitHub](https://img.shields.io/github/stars/basnijholt/dotbins.svg?style=social)](https://github.com/basnijholt/dotbins/stargazers)
[![PyPI](https://img.shields.io/pypi/v/dotbins.svg)](https://pypi.python.org/pypi/dotbins)
[![License](https://img.shields.io/github/license/basnijholt/dotbins)](https://github.com/basnijholt/dotbins/blob/main/LICENSE)
[![Downloads](https://img.shields.io/pypi/dm/dotbins)](https://pypi.python.org/pypi/dotbins)
![Open Issues](https://img.shields.io/github/issues-raw/basnijholt/dotbins)

Introducing `dotbins` - a utility for managing CLI tool binaries in your dotfiles repository. It downloads and organizes binaries for popular tools across multiple platforms (macOS, Linux) and architectures (amd64, arm64), helping you maintain a consistent set of CLI utilities across all your environments.

Whether you work across multiple machines or just want a version-controlled setup for your essential command-line tools, dotbins makes it easy to keep everything synchronized and updated. 🚀

<details><summary><b><u>[ToC]</u></b> 📚</summary>

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [:star2: Features](#star2-features)
- [:books: Usage](#books-usage)
  - [Commands](#commands)
- [:hammer_and_wrench: Installation](#hammer_and_wrench-installation)
- [:gear: Configuration](#gear-configuration)
- [:bulb: Examples](#bulb-examples)
- [:computer: Shell Integration](#computer-shell-integration)
- [:mag: Finding Tool Patterns](#mag-finding-tool-patterns)
- [:heart: Support and Contributions](#heart-support-and-contributions)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

</details>

## :star2: Features

* 🌐 Supports multiple platforms (macOS, Linux) and architectures (amd64, arm64)
* 📦 Downloads and organizes binaries from GitHub releases
* 🔄 Updates tools to their latest versions with a single command
* 🧩 Extracts binaries from various archive formats (zip, tar.gz)
* 📂 Organizes tools by platform and architecture for easy access
* 🔍 Includes a tool to analyze GitHub releases to help configure new tools
* 🐙 Easy integration with your dotfiles repository for version control

## :books: Usage

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
               {list,update,init,analyze} ...

dotbins - Manage CLI tool binaries in your dotfiles repository

positional arguments:
  {list,update,init,analyze}
                        Command to execute
    list                List available tools
    update              Update tools
    init                Initialize directory structure
    analyze             Analyze GitHub releases for a tool

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

## :hammer_and_wrench: Installation

To install `dotbins`, simply use pip:

```bash
pip install dotbins
```

You'll also need to create or update your `tools.yaml` configuration file either in the same directory as the script or at a custom location specified with `--tools-dir`.

## :gear: Configuration

dotbins uses a YAML configuration file (`tools.yaml`) to define the tools and settings:

<!-- CODE:BASH:START -->
<!-- echo '```yaml' -->
<!-- cat tools.yaml -->
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

# Architecture mappings (our naming -> tool release naming)
arch_maps:
  bat:
    amd64: x86_64
    arm64: aarch64
  eza:
    amd64: x86_64
    arm64: aarch64
  zoxide:
    amd64: x86_64
    arm64: aarch64

# Platform naming conversions
platform_maps:
  macos: darwin

# Tool definitions
tools:
  fzf:
    repo: junegunn/fzf
    extract_binary: true
    binary_name: fzf
    binary_path: fzf  # The binary is directly in the root of the archive
    asset_pattern: fzf-{version}-{platform}_{arch}.tar.gz
    platform_map: macos:darwin

  bat:
    repo: sharkdp/bat
    extract_binary: true
    binary_name: bat
    binary_path: bat-v{version}-{arch}-*/bat  # The actual path in the archive
    asset_patterns:
      linux: bat-v{version}-{arch}-unknown-linux-gnu.tar.gz
      macos: bat-v{version}-{arch}-apple-darwin.tar.gz

  eza:
    repo: eza-community/eza
    extract_binary: true
    binary_name: eza
    binary_path: eza  # The binary is directly in the root of the archive
    asset_patterns:
      linux: eza_{arch}-unknown-linux-gnu.tar.gz
      macos: null  # No macOS binaries available as of now

  zoxide:
    repo: ajeetdsouza/zoxide
    extract_binary: true
    binary_name: zoxide
    binary_path: zoxide  # The binary is directly in the root of the archive
    arch_map:
      amd64: x86_64
      arm64: aarch64
    asset_patterns:
      linux: zoxide-{version}-{arch}-unknown-linux-musl.tar.gz
      macos: zoxide-{version}-{arch}-apple-darwin.tar.gz

  uv:
    repo: astral-sh/uv
    extract_binary: true
    binary_name: uv
    binary_path: uv-*/uv
    arch_map:
      amd64: x86_64
      arm64: aarch64
    asset_patterns:
      linux: uv-{arch}-unknown-linux-gnu.tar.gz
      macos: uv-{arch}-apple-darwin.tar.gz
```

<!-- OUTPUT:END -->

Each tool definition includes:
- **repo**: GitHub repository in the format owner/repo
- **extract_binary**: Whether to extract from an archive (true) or download directly (false)
- **binary_name**: Name of the resulting binary
- **binary_path**: Path to the binary within the archive
- **asset_pattern**: Pattern to match the GitHub release asset
- **platform_map**: Optional mapping between dotbins platform names and the tool's naming

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
🛠️ Initialized tools directory structure

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
