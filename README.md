# dotbins 🧰

![Build](https://github.com/basnijholt/dotbins/actions/workflows/pytest.yml/badge.svg)
[![Coverage](https://img.shields.io/codecov/c/github/basnijholt/dotbins)](https://codecov.io/gh/basnijholt/dotbins)
[![GitHub](https://img.shields.io/github/stars/basnijholt/dotbins.svg?style=social)](https://github.com/basnijholt/dotbins/stargazers)
[![PyPI](https://img.shields.io/pypi/v/dotbins.svg)](https://pypi.python.org/pypi/dotbins)
[![License](https://img.shields.io/github/license/basnijholt/dotbins)](https://github.com/basnijholt/dotbins/blob/main/LICENSE)
[![Downloads](https://img.shields.io/pypi/dm/dotbins)](https://pypi.python.org/pypi/dotbins)
![Open Issues](https://img.shields.io/github/issues-raw/basnijholt/dotbins)

Introducing `dotbins` - a utility for managing CLI tool binaries in your dotfiles repository.
It downloads and organizes binaries for popular tools across multiple platforms (macOS, Linux, etc.) and architectures (amd64, arm64, etc.), helping you maintain a consistent set of CLI utilities across all your environments.

Whether you work across multiple machines or just want a version-controlled setup for your essential command-line tools, dotbins makes it easy to keep everything synchronized and updated. 🚀

No package manager, no sudo, no problem.

## :zap: Quick Start

Using the amazing [`uv`](https://docs.astral.sh/uv/) package manager:

```bash
# Download and install a tool directly
uvx dotbins get junegunn/fzf  # Installs to ~/.local/bin

# Or set up a configuration file for managing multiple tools
# See examples in the Configuration section
```

**See it in action:**

[![asciicast](https://asciinema.org/a/707563.svg)](https://asciinema.org/a/707563)

<details><summary><b><u>[ToC]</u></b> 📚</summary>

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [:bulb: Why I Created dotbins](#bulb-why-i-created-dotbins)
- [:star2: Features](#star2-features)
- [:books: Usage](#books-usage)
  - [Commands](#commands)
  - [Quick Install with `dotbins get`](#quick-install-with-dotbins-get)
- [:hammer_and_wrench: Installation](#hammer_and_wrench-installation)
- [:gear: Configuration](#gear-configuration)
  - [Basic Configuration](#basic-configuration)
  - [Tool Configuration](#tool-configuration)
  - [Platform and Architecture Mapping](#platform-and-architecture-mapping)
  - [Pattern Variables](#pattern-variables)
  - [Multiple Binaries](#multiple-binaries)
  - [Configuration Examples](#configuration-examples)
    - [Minimal Tool Configuration](#minimal-tool-configuration)
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

1. Track pre-compiled binaries in a [separate Git repository](https://github.com/basnijholt/.dotbins) (using Git LFS for efficient storage)
2. Include this repository as a submodule in my dotfiles
3. Ensure all my essential tools are immediately available after cloning, regardless of system permissions

Now when I clone my dotfiles on any new system, I get not just my configurations but also all the CLI tools I depend on for productivity
No package manager, no sudo, no problem.


## :star2: Features

* 🌐 Supports multiple platforms (macOS, Linux, etc.) and architectures (amd64, arm64, etc.)
* 📦 Downloads and organizes binaries from GitHub releases
* 🔄 Updates tools to their latest versions with a single command
* 📊 Tracks installed versions and update timestamps for all tools
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
               {list,update,init,analyze,version,versions,readme,get} ...

dotbins - Manage CLI tool binaries in your dotfiles repository

positional arguments:
  {list,update,init,analyze,version,versions,readme,get}
                        Command to execute
    list                List available tools
    update              Update tools
    init                Initialize directory structure
    analyze             Analyze GitHub releases for a tool
    version             Print version information
    versions            Show installed tool versions and their last update
                        times
    readme              Generate README.md file with tool information
    get                 Download and install a tool directly without using a
                        configuration file

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
6. **versions** - Show detailed information about installed tool versions
7. **get** - Download and install a tool directly without using a configuration file

### Quick Install with `dotbins get`

The `get` command allows you to quickly download and install tools directly from GitHub without setting up a configuration file:

```bash
# Install fzf to the default location (~/.local/bin)
dotbins get junegunn/fzf

# Install ripgrep with a custom binary name
dotbins get BurntSushi/ripgrep --name rg

# Install bat to a specific location
dotbins get sharkdp/bat --dest ~/bin
```

This is perfect for:
- Quickly installing tools on a new system
- One-off installations without needing a configuration file
- Adding tools to PATH in standard locations like `~/.local/bin`

The `get` command automatically detects your current platform and architecture, finds the appropriate release asset, and installs it to the specified location.

## :hammer_and_wrench: Installation

We highly recommend to use [`uv`](https://docs.astral.sh/uv/) to run `dotbins`:

```bash
uvx dotbins
```

or install as a global command:

```bash
uv tool install dotbins
```

Otherwise, simply use pip:

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
6. `~/.dotbins/dotbins.yaml` (default dotfiles location)

The first valid configuration file found will be used. If no configuration file is found, default settings will be used.

### Basic Configuration

```yaml
# Basic settings
tools_dir: ~/.dotbins

# Target platforms and architectures
platforms:
  linux:
    - amd64
    - arm64
  macos:
    - arm64  # Only arm64 for macOS

# Tool definitions
tools:
  # Tool configuration entries
```

### Tool Configuration

Each tool must be configured with at least a GitHub repository. Many other fields are optional and can be auto-detected:

```yaml
tool-name:
  repo: owner/repo                 # Required: GitHub repository
  extract_binary: true             # Optional: Whether to extract from archive (true) or direct download (false)
  binary_name: executable-name     # Optional: Name of the resulting binary(ies) (defaults to tool-name)
  binary_path: path/to/binary      # Optional: Path to the binary within the archive (auto-detected if not specified)

  # Asset patterns - Optional with auto-detection
  # Option 1: Platform-specific patterns
  asset_patterns:                  # Optional: Asset patterns for each platform
    linux: pattern-for-linux.tar.gz
    macos: pattern-for-macos.tar.gz
  # Option 2: Single pattern for all platforms
  asset_patterns: pattern-for-all-platforms.tar.gz  # Global pattern for all platforms
  # Option 3: Explicit platform patterns for different architectures
  asset_patterns:
    linux:
      amd64: pattern-for-linux-amd64.tar.gz
      arm64: pattern-for-linux-arm64.tar.gz
    macos:
      amd64: pattern-for-macos-amd64.tar.gz
      arm64: pattern-for-macos-arm64.tar.gz
```

If you don't specify `binary_path` or `asset_patterns`, `dotbins` will attempt to auto-detect the appropriate values for you. This often works well for standard tool releases.

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

#### Minimal Tool Configuration
```yaml
ripgrep:
  repo: BurntSushi/ripgrep
  binary_name: rg  # Only specify if different from tool name
```

#### Standard Tool

```yaml
atuin:
  repo: atuinsh/atuin
  arch_map:
    amd64: x86_64
    arm64: aarch64
  asset_patterns:
    linux: atuin-{arch}-unknown-linux-gnu.tar.gz
    macos: atuin-{arch}-apple-darwin.tar.gz
```

#### Tool with Multiple Binaries

```yaml
uv:
  repo: astral-sh/uv
  binary_name: [uv, uvx]
  binary_path: [uv-*/uv, uv-*/uvx]
```

#### Platform-Specific Tool

```yaml
eza:
  repo: eza-community/eza
  arch_map:
    amd64: x86_64
    arm64: aarch64
  asset_patterns:
    linux: eza_{arch}-unknown-linux-gnu.tar.gz
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
tools_dir: ~/.dotbins

platforms:
  linux:
    - amd64
    - arm64
  macos:
    - arm64

# Tool definitions
tools:
  fzf:
    repo: junegunn/fzf

  bat:
    repo: sharkdp/bat

  eza:
    repo: eza-community/eza
    arch_map:
      amd64: x86_64
      arm64: aarch64
    asset_patterns:
      linux: eza_{arch}-unknown-linux-gnu.tar.gz
      macos: null  # No macOS binaries available as of now

  zoxide:
    repo: ajeetdsouza/zoxide

  delta:
    repo: dandavison/delta

  uv:
    repo: astral-sh/uv
    binary_name: [uv, uvx]
    binary_path: [uv-*/uv, uv-*/uvx]

  micromamba:
    repo: mamba-org/micromamba-releases
    extract_binary: false
    binary_path: bin/micromamba
    arch_map:
      amd64: 64
      arm64: aarch64
    asset_patterns:
      linux: micromamba-linux-{arch}
      macos: micromamba-osx-arm64

  atuin:
    repo: atuinsh/atuin
    arch_map:
      amd64: x86_64
      arm64: aarch64
    asset_patterns:
      linux: atuin-{arch}-unknown-linux-gnu.tar.gz
      macos: atuin-{arch}-apple-darwin.tar.gz

  git-lfs:
    repo: git-lfs/git-lfs

  ripgrep:
    repo: BurntSushi/ripgrep
    binary_name: rg

  eget:
    repo: zyedidia/eget

  direnv:
    repo: direnv/direnv
    extract_binary: false

  lazygit:
    repo: jesseduffield/lazygit

  fd:
    repo: sharkdp/fd

  duf:
    repo: muesli/duf
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
✅ Loading configuration from: /home/runner/work/dotbins/dotbins/dotbins.yaml
🛠️ dotbins initialized tools directory structure

# Add this to your shell configuration file (e.g., .bashrc, .zshrc):

# dotbins - Add platform-specific binaries to PATH
_os=$(uname -s | tr '[:upper:]' '[:lower:]')
[[ "$_os" == "darwin" ]] && _os="macos"

_arch=$(uname -m)
[[ "$_arch" == "x86_64" ]] && _arch="amd64"
[[ "$_arch" == "aarch64" || "$_arch" == "arm64" ]] && _arch="arm64"

export PATH="$HOME/.dotbins/$_os/$_arch/bin:$PATH"

📝 Generated README at /home/runner/.dotbins/README.md
📝 Generated README file with shell integration instructions
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
