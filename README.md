# dotbins 🧰

![Build Status](https://github.com/basnijholt/dotbins/actions/workflows/pytest.yml/badge.svg)
[![Coverage](https://img.shields.io/codecov/c/github/basnijholt/dotbins)](https://codecov.io/gh/basnijholt/dotbins)
[![GitHub](https://img.shields.io/github/stars/basnijholt/dotbins.svg?style=social)](https://github.com/basnijholt/dotbins/stargazers)
[![PyPI](https://img.shields.io/pypi/v/dotbins.svg)](https://pypi.python.org/pypi/dotbins)
[![License](https://img.shields.io/github/license/basnijholt/dotbins)](https://github.com/basnijholt/dotbins/blob/main/LICENSE)
[![Downloads](https://img.shields.io/pypi/dm/dotbins)](https://pypi.python.org/pypi/dotbins)
![Open Issues](https://img.shields.io/github/issues-raw/basnijholt/dotbins)

**dotbins** manages CLI tool binaries in your dotfiles repository, offering:

- ✅ Cross-platform binary management (macOS, Linux, Windows)
- ✅ No admin privileges required
- ✅ Version-controlled CLI tools
- ✅ Downloads from GitHub releases
- ✅ Perfect for dotfiles synchronization

No package manager, no sudo, no problem.

See this example `.dotbins` repository: [basnijholt/.dotbins](https://github.com/basnijholt/.dotbins) completely managed with `dotbins`.

> [!NOTE]
> 💡 **What makes dotbins different?** Unlike similar tools, dotbins uniquely integrates tool-specific shell configurations
> (aliases, completions, etc.) directly in your dotfiles workflow, not just binary downloads, and allows a Git workflow for managing binaries.

<details><summary><b><u>[ToC]</u></b> 📚</summary>

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [:zap: Quick Start](#zap-quick-start)
- [:star2: Features](#star2-features)
- [:bulb: Why I Created dotbins](#bulb-why-i-created-dotbins)
- [:books: Usage](#books-usage)
  - [Commands](#commands)
  - [Update Process with `dotbins sync`](#update-process-with-dotbins-sync)
  - [Quick Install with `dotbins get`](#quick-install-with-dotbins-get)
  - [Initializing with `dotbins init`](#initializing-with-dotbins-init)
- [:hammer_and_wrench: Installation](#hammer_and_wrench-installation)
- [:gear: Configuration](#gear-configuration)
  - [Basic Configuration](#basic-configuration)
  - [Directory Structure](#directory-structure)
  - [Tool Configuration](#tool-configuration)
  - [Pattern Variables](#pattern-variables)
  - [Platform and Architecture Mapping](#platform-and-architecture-mapping)
  - [Asset auto-detection defaults](#asset-auto-detection-defaults)
    - [Example: libc selection](#example-libc-selection)
    - [Example: AppImage preference](#example-appimage-preference)
    - [Example: Windows ABI](#example-windows-abi)
  - [Multiple Binaries](#multiple-binaries)
  - [Configuration Examples](#configuration-examples)
    - [Minimal Tool Configuration](#minimal-tool-configuration)
    - [Standard Tool](#standard-tool)
    - [Tool with Multiple Binaries](#tool-with-multiple-binaries)
    - [Platform-Specific Tool](#platform-specific-tool)
    - [Version-Pinned Tool](#version-pinned-tool)
    - [Shell-Specific Configuration](#shell-specific-configuration)
  - [Full Configuration Example](#full-configuration-example)
- [:bulb: Examples](#bulb-examples)
- [:computer: Shell Integration](#computer-shell-integration)
  - [What's in the Shell Scripts?](#whats-in-the-shell-scripts)
  - [Shell Startup Integration](#shell-startup-integration)
- [:books: Examples with 50+ Tools](#books-examples-with-50-tools)
- [:wrench: Troubleshooting](#wrench-troubleshooting)
  - [Common Issues](#common-issues)
    - [GitHub API Rate Limits](#github-api-rate-limits)
    - [Windows-Specific Issues](#windows-specific-issues)
  - [Getting Help](#getting-help)
- [:thinking: Comparison with Alternatives](#thinking-comparison-with-alternatives)
  - [Key Alternatives](#key-alternatives)
    - [Version Managers (e.g., `binenv`, `asdf`)](#version-managers-eg-binenv-asdf)
    - [Binary Downloaders (e.g., `eget`)](#binary-downloaders-eg-eget)
    - [System Package Managers (`apt`, `brew`, etc.)](#system-package-managers-apt-brew-etc)
  - [The `dotbins` Difference](#the-dotbins-difference)
- [:heart: Support and Contributions](#heart-support-and-contributions)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

</details>

## :zap: Quick Start

Using the amazing [`uv`](https://docs.astral.sh/uv/) package manager (`uv tool install dotbins`):

```bash
# Create a sample configuration file to get started
dotbins init

# Install/update tools using a config file (to tools_dir, e.g., ~/.dotbins)
dotbins sync

# Install a single tool (defaults to ~/.local/bin) - No config needed!
dotbins get junegunn/fzf

# Install tools from a remote config (defaults to ~/.local/bin)
dotbins get https://github.com/basnijholt/.dotbins/blob/main/dotbins.yaml
```

**See it in action:**

[![asciicast](https://asciinema.org/a/709229.svg)](https://asciinema.org/a/709229)

## :star2: Features

- 🌐 Supports multiple platforms (macOS, Linux, Windows) and architectures (amd64, arm64, etc.)
- 📦 Downloads and organizes binaries from GitHub releases
- 🔄 Installs and updates tools to their latest versions with a single command
- 📌 Pin tools to specific versions with the `tag` parameter
- 📊 Tracks installed versions and update timestamps for all tools
- 🧩 Extracts binaries from various archive formats (zip, tar.gz)
- 📂 Organizes tools by platform and architecture for easy access
- 🐙 Easy integration with your dotfiles repository for version control
- ⚙️ **Automatic PATH & Shell Code:** Configures `PATH` and applies custom shell snippets (`shell_code`).

## :bulb: Why I Created dotbins

I frequently works across multiple environments where I clone my dotfiles repository with all my preferred configurations.
I faced a common frustration: some of my favorite tools (`fzf`, `bat`, `zoxide`, etc.) were not available on the new system and installing them with a package manager is too much work or even not possible.
`dotbins` was born out of this frustration.

It allows me to:

1. Track pre-compiled binaries in a [separate Git repository](https://github.com/basnijholt/.dotbins) (using Git LFS for efficient storage)
2. Include that repository as a submodule in my dotfiles
3. Ensure all my essential tools are _immediately_ available after cloning, regardless of system permissions

Now when I clone my dotfiles on any new system, I get not just my configurations but also all the CLI tools I depend on for productivity, **ready to use with their specific aliases and shell initializations automatically configured**.

**_No package manager, no sudo, no problem!_**

---

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
Usage: dotbins [-h] [-v] [--tools-dir TOOLS_DIR] [--config-file CONFIG_FILE]
               {get,sync,init,list,status,readme,version} ...

dotbins - Download, manage, and update CLI tool binaries in your dotfiles
repository

Positional Arguments:
  {get,sync,init,list,status,readme,version}
                        Command to execute
    get                 Download and install a tool directly without
                        configuration file
    sync                Install and update tools to their latest versions
    init                Initialize directory structure and generate shell
                        integration scripts
    list                List all available tools defined in your configuration
    status              Show installed tool versions and when they were last
                        updated
    readme              Generate README.md file with information about
                        installed tools
    version             Print dotbins version information

Options:
  -h, --help            show this help message and exit
  -v, --verbose         Enable verbose output with detailed logs and error
                        messages
  --tools-dir TOOLS_DIR
                        Tools directory to use (overrides the value in the
                        config file)
  --config-file CONFIG_FILE
                        Path to configuration file (default: looks in standard
                        locations)
```

<!-- OUTPUT:END -->

### Commands

1. **sync** - Install and update tools to their latest versions
2. **get** - Download and install a tool directly without using a configuration file
3. **init** - Initialize the tools directory structure and generate a sample configuration file
4. **list** - List available tools defined in your configuration
5. **version** - Print version information
6. **status** - Show detailed information about available and installed tool versions

### Update Process with `dotbins sync`

The `sync` command is the core of dotbins, keeping your tools up-to-date across platforms.
Here's what happens during `dotbins sync`:

1. **Version Detection**:

   - Checks each tool's current version in `versions.json`
   - Queries GitHub API for the latest release of each tool

2. **Smart Updates**:

   - Only downloads tools with newer versions available
   - Skips up-to-date tools (unless `--force` is used)
   - Reports which tools were updated, skipped, or failed

3. **Multi-Platform Management**:

   - Processes each platform/architecture combination configured
   - Can be filtered to specific platforms: `dotbins sync -p linux`
   - Can be limited to current system only: `dotbins sync -c`

4. **File Generation**:
   - Updates `versions.json` with new version information
   - Regenerates shell integration scripts with PATH and tool configurations
   - Creates a README in the tools directory with installation status

Example update workflow:

```bash
# Update all tools for all configured platforms
dotbins sync

# Update only specific tools
dotbins sync fzf bat

# Update tools only for current platform
dotbins sync --current

# Force reinstall everything, even if up to date
dotbins sync --force

# See what would be updated without making changes
dotbins status
```

After updating, a summary is displayed showing what was installed, skipped, or had errors.

### Quick Install with `dotbins get`

The `get` command allows you to quickly download and install tools directly from GitHub or from a remote configuration file:

```bash
# Install fzf to the default location (~/.local/bin)
dotbins get junegunn/fzf

# Install ripgrep with a custom binary name
dotbins get BurntSushi/ripgrep --name rg

# Install bat to a specific location
dotbins get sharkdp/bat --dest ~/bin

# Install multiple tools from a remote config URL/local path
dotbins get https://example.com/my-tools.yaml --dest ~/.local/bin
```

This is perfect for:

- Quickly installing tools on a new system
- One-off installations without needing a configuration file
- Adding tools to PATH in standard locations like `~/.local/bin`
- Bootstrapping with a pre-configured set of tools using a remote configuration URL or local config

The `get` command automatically detects whether you're providing a GitHub repository or a configuration URL/path.
When using a URL/path, it will download all tools defined in the configuration for your current platform and architecture.

### Initializing with `dotbins init`

The fastest way to get started with dotbins is to use the `init` command:

```bash
dotbins init
```

This command:

- Creates the directory structure for all configured platforms and architectures
- Generates shell integration scripts for your system
- If no config exists, creates a sample `dotbins.yaml` with sensible defaults

The generated sample config includes popular tools like `fzf`, `bat`, and `zoxide`, with support for multiple platforms:

Sample config generated by `dotbins init`:

<!-- CODE:BASH:START -->
<!-- echo '```yaml' -->
<!-- python3 -c "import dotbins.cli; print(dotbins.cli._SAMPLE_CONFIG)" -->
<!-- echo '```' -->
<!-- CODE:END -->

<!-- OUTPUT:START -->
<!-- ⚠️ This content is auto-generated by `markdown-code-runner`. -->
```yaml
# dotbins sample configuration
# Generated by `dotbins init`
# See https://github.com/basnijholt/dotbins for more information

# Directory where tool binaries will be stored
tools_dir: ~/.dotbins

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

```

<!-- OUTPUT:END -->

This provides a good starting point that you can customize with your preferred tools and configurations.

---

## :hammer_and_wrench: Installation

We highly recommend to use [`uv`](https://docs.astral.sh/uv/) to install/run `dotbins`:

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

---

## :gear: Configuration

dotbins uses a YAML configuration file to define the tools and settings. The configuration file is searched in the following locations (in order):

1. Explicitly provided path (using `--config-file` option)
2. `./dotbins.yaml` (current directory)
3. `~/.config/dotbins/config.yaml` (XDG config directory)
4. `~/.config/dotbins.yaml` (XDG config directory, flat)
5. `~/.dotbins.yaml` (home directory)
6. `~/.dotbins/dotbins.yaml` (default dotfiles location)

The first valid configuration file found will be used. If no configuration file is found, default settings will be used.

> [!TIP]
> To create a starter configuration file, run `dotbins init`. This will generate a sample config with common tools in your tools directory.

### Basic Configuration

```yaml
# Basic settings
tools_dir: ~/.dotbins # (optional, ~/.dotbins by default)

# Target platforms and architectures (optional, current system by default)
platforms:
  linux:
    - amd64
    - arm64
  macos:
    - arm64 # Only arm64 for macOS

# Tool definitions
tools:
  # Tool configuration entries
```

### Directory Structure

When you run `dotbins sync`, it creates a directory structure that organizes binaries by platform and architecture, and generates shell integration scripts.

Here's what gets created:

```bash
~/.dotbins/                # Root tools directory (configurable)
├── README.md              # Auto-generated documentation
├── dotbins.yaml           # Your configuration file (if copied)
├── linux/                 # Platform-specific directories
│   ├── amd64/bin/         # Architecture-specific binaries
│   │   ├── bat
│   │   ├── fzf
│   │   └── ...
│   └── arm64/bin/
│       ├── bat
│       ├── fzf
│       └── ...
├── macos/
│   └── arm64/bin/
│       ├── bat
│       ├── fzf
│       └── ...
├── shell/                 # Shell integration scripts
│   ├── bash.sh
│   ├── fish.fish
│   ├── nushell.nu
│   ├── powershell.ps1
│   └── zsh.sh
└── versions.json          # Version tracking information
```

### Tool Configuration

Each tool must be configured with at least a GitHub repository.
Many other fields are optional and can be auto-detected.

The simplest configuration is:

```yaml
tools:
  # tool-name: owner/repo
  zoxide: ajeetdsouza/zoxide
  fzf: junegunn/fzf
```

dotbins will auto-detect the latest release, choose the appropriate asset for your platform, and install binaries to the specified `tools_dir` (defaults to `~/.dotbins`).

> [!NOTE]
> dotbins excels at auto-detecting the correct assets and binary paths for many tools.
> Always try the minimal configuration first!

When auto-detection isn't possible or you want more control, you can provide detailed configuration:

```yaml
tool-name:
  repo: owner/repo                 # Required: GitHub repository
  tag: v1.2.3                      # Optional: Specific release tag to use (defaults to latest)
  binary_name: executable-name     # Optional: Name of the resulting binary(ies) (defaults to tool-name)
  extract_archive: true            # Optional: Whether to extract from archive (true) or direct download (false) (auto-detected if not specified)
  path_in_archive: path/to/binary  # Optional: Path to the binary within the archive (auto-detected if not specified)

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

Asset patterns support variables like `{version}`, `{platform}`, and `{arch}` that are automatically replaced with the appropriate values (see Pattern Variables section for details).

### Pattern Variables

In asset patterns, you can use special variables that get replaced with actual values when dotbins searches for the correct asset to download:

- `{version}` - Release version (without 'v' prefix)
- `{platform}` - Platform name (after applying platform_map)
- `{arch}` - Architecture name (after applying arch_map)

For example, if a tool release has version `v2.4.0` and you're on `linux/amd64`:

```yaml
mytool:
  repo: owner/mytool
  asset_patterns: mytool-{version}-{platform}_{arch}.tar.gz
```

This would search for an asset named: `mytool-2.4.0-linux_amd64.tar.gz`

With platform and architecture mapping:

```yaml
mytool:
  repo: owner/mytool
  platform_map:
    macos: darwin # Convert "macos" to "darwin" in patterns
  arch_map:
    amd64: x86_64 # Convert "amd64" to "x86_64" in patterns
  asset_patterns: mytool-{version}-{platform}_{arch}.tar.gz
```

For macOS/amd64, this would search for: `mytool-2.4.0-darwin_x86_64.tar.gz`

**Real-world example:**

```yaml
ripgrep:
  repo: BurntSushi/ripgrep
  binary_name: rg
  arch_map:
    amd64: x86_64
    arm64: aarch64
  asset_patterns:
    linux: ripgrep-{version}-{arch}-unknown-linux-musl.tar.gz
    macos: ripgrep-{version}-{arch}-apple-darwin.tar.gz
```

For Linux/amd64, this would search for: `ripgrep-14.1.1-x86_64-unknown-linux-musl.tar.gz`
For macOS/arm64, this would search for: `ripgrep-14.1.1-aarch64-apple-darwin.tar.gz`

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

### Asset auto-detection defaults

When multiple compatible assets are available for your platform and architecture, dotbins uses these settings to determine which one to select:

```yaml
# Global defaults for all tools
defaults:
  prefer_appimage: true   # Prioritize AppImage format when available
  libc: musl              # Prefer musl over glibc on Linux
  windows_abi: msvc       # Prefer MSVC over GNU ABI on Windows
```

These are also the built-in defaults if no custom settings are provided.

**Why these defaults?**

- **musl libc**: Statically linked musl binaries offer maximum portability across all Linux distributions regardless of the system's native C library. They eliminate glibc version conflicts (the notorious `GLIBC_X.YZ not found` errors), work on **both** glibc and musl-based distributions (like Alpine Linux), and generally provide a more reliable user experience.

- **AppImage**: AppImage bundles all dependencies in a single, self-contained file that works across different Linux distributions without installation, making it ideal for portable applications, (such as neovim, which requires extra runtime files.)

- **Windows ABI**: The MSVC ABI is the default on Windows as it's the most widely used and generally more stable. However, if you're using MinGW or prefer GNU tools, you can set this to "gnu".

#### Example: libc selection

When requesting Linux amd64 and both of these assets are available:

- `ripgrep-13.0.0-x86_64-unknown-linux-gnu.tar.gz` (uses glibc)
- `ripgrep-13.0.0-x86_64-unknown-linux-musl.tar.gz` (uses musl)

With `libc="musl"`, dotbins selects the musl version.
With `libc="glibc"`, dotbins selects the gnu version.

#### Example: AppImage preference

When both formats are available:

- `nvim-linux-x86_64.appimage`
- `nvim-linux-x86_64.tar.gz`

With `prefer_appimage=true`, dotbins selects the AppImage version.

#### Example: Windows ABI

When requesting Windows x86_64 and both of these assets are available:

- `bat-v0.25.0-x86_64-pc-windows-gnu.zip` (uses GNU ABI)
- `bat-v0.25.0-x86_64-pc-windows-msvc.zip` (uses MSVC ABI)

With `windows_abi="msvc"`, dotbins selects the MSVC version.
With `windows_abi="gnu"`, dotbins selects the GNU version.

### Multiple Binaries

For tools that provide multiple binaries:

```yaml
tool-name:
  # Other fields...
  binary_name: [main-binary, additional-binary]
  path_in_archive: [path/to/main, path/to/additional]
```

### Configuration Examples

#### Minimal Tool Configuration

```yaml
direnv:
  repo: direnv/direnv
```

or

```yaml
ripgrep:
  repo: BurntSushi/ripgrep
  binary_name: rg # Only specify if different from tool name
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
  path_in_archive: [uv-*/uv, uv-*/uvx]
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
    macos: null # No macOS version available
```

#### Version-Pinned Tool

```yaml
bat:
  repo: sharkdp/bat
  tag: v0.23.0  # Pin to specific version instead of latest
```

#### Shell-Specific Configuration

The auto-generated shell scripts that add the binaries to your PATH will include the tool-specific shell code if provided.

For example, see the following configuration:

```yaml
tools:
  fzf:
    repo: junegunn/fzf
    shell_code: |
      source <(fzf --zsh)

  zoxide:
    repo: ajeetdsouza/zoxide
    shell_code: |
      eval "$(zoxide init zsh)"

  eza:
    repo: eza-community/eza
    shell_code: |
      alias l="eza -lah --git"
```

If you want to make your config compatible with multiple shells (e.g., zsh, bash, fish), you can use the following syntax:

```yaml
starship:
  repo: starship/starship
  shell_code:
    zsh: eval "$(starship init zsh)"
    bash: eval "$(starship init bash)"
    fish: starship init fish | source
```

### Full Configuration Example

This is the author's configuration file (and resulting [`basnijholt/.dotbins`](https://github.com/basnijholt/.dotbins) repo):

<details><summary>Click to view author's full dotbins.yaml</summary>

<!-- CODE:BASH:START -->
<!-- echo '```yaml' -->
<!-- cat dotbins.yaml -->
<!-- echo '```' -->
<!-- CODE:END -->

<!-- OUTPUT:START -->
<!-- ⚠️ This content is auto-generated by `markdown-code-runner`. -->
```yaml
tools_dir: ~/.dotbins

platforms:
  linux:
    - amd64
    - arm64
  macos:
    - arm64

tools:
  delta: dandavison/delta
  duf: muesli/duf
  dust: bootandy/dust
  fd: sharkdp/fd
  git-lfs: git-lfs/git-lfs
  hyperfine: sharkdp/hyperfine
  rg: BurntSushi/ripgrep
  yazi: sxyazi/yazi

  atuin:
    repo: atuinsh/atuin
    shell_code:
      zsh: |
        source <(atuin init zsh --disable-up-arrow)
  bat:
    repo: sharkdp/bat
    shell_code:
      zsh: |
        alias bat="bat --paging=never"
        alias cat="bat --plain --paging=never"
  direnv:
    repo: direnv/direnv
    shell_code:
      zsh: |
        eval "$(direnv hook zsh)"
  eza:
    repo: eza-community/eza
    shell_code:
      zsh: |
        alias l="eza -lah --git --icons"
  fzf:
    repo: junegunn/fzf
    shell_code:
      zsh: |
        source <(fzf --zsh)
  lazygit:
    repo: jesseduffield/lazygit
    shell_code:
      zsh: |
        alias lg="lazygit"
  micromamba:
    repo: mamba-org/micromamba-releases
    shell_code:
      zsh: |
        alias mm="micromamba"
  starship:
    repo: starship/starship
    shell_code:
      zsh: |
        eval "$(starship init zsh)"
  zoxide:
    repo: ajeetdsouza/zoxide
    shell_code:
      zsh: |
        eval "$(zoxide init zsh)"

  uv:
    repo: astral-sh/uv
    binary_name: [uv, uvx]
    path_in_archive: [uv-*/uv, uv-*/uvx]
```

<!-- OUTPUT:END -->

</details>

---

## :bulb: Examples

List all available tools in your configuration:

```bash
dotbins list
```

Install or update all tools for all configured platforms:

```bash
dotbins sync
```

Install or update specific tools only:

```bash
dotbins sync fzf bat ripgrep
```

Install or update tools for a specific platform/architecture:

```bash
dotbins sync -p macos -a arm64
```

Install or update tools only for the current system's platform and architecture, skipping others defined in the config:

```bash
dotbins sync -c
```

Force reinstall even if tools are up to date:

```bash
dotbins sync --force
```

Install tools from a remote configuration:

```bash
dotbins get https://raw.githubusercontent.com/username/dotbins-config/main/tools.yaml --dest ~/bin
```

Show status (installed, missing tools, last updated) for all installed tools:

```bash
dotbins status
```

Show a compact view of installed tools (one line per tool):

```bash
dotbins status --compact
```

Show tools only for the current platform/architecture:

```bash
dotbins status --current
```

Filter tools by platform or architecture:

```bash
dotbins status --platform macos
dotbins status --architecture arm64
```

---

## :computer: Shell Integration

dotbins creates shell scripts that add binaries to your `PATH` and apply your custom tool configurations.

After running `dotbins sync` or `dotbins init`, shell integration scripts are created in `~/.dotbins/shell/` for various shells (Bash, Zsh, Fish, Nushell, and PowerShell)

### What's in the Shell Scripts?

The generated shell scripts do two main things:

1. **Add binaries to PATH** - Makes tool binaries available for your platform/architecture
2. **Apply your tool-specific shell_code** - Sets up aliases, completions, and initializations

For example, with this configuration:

```yaml
fzf:
  repo: junegunn/fzf
  shell_code: |
    source <(fzf --zsh)

bat:
  repo: sharkdp/bat
  shell_code: |
    alias bat="bat --paging=never"
    alias cat="bat --plain --paging=never"
```

The generated `zsh.sh` will include:

```bash
#!/usr/bin/env zsh
# dotbins - Add platform-specific binaries to PATH
_os=$(uname -s | tr '[:upper:]' '[:lower:]')
[[ "$_os" == "darwin" ]] && _os="macos"

_arch=$(uname -m)
[[ "$_arch" == "x86_64" ]] && _arch="amd64"
[[ "$_arch" == "aarch64" || "$_arch" == "arm64" ]] && _arch="arm64"

export PATH="$HOME/.dotbins/$_os/$_arch/bin:$PATH"

# Tool-specific configurations
# Configuration for fzf
if command -v fzf >/dev/null 2>&1; then
    source <(fzf --zsh)
fi

# Configuration for bat
if command -v bat >/dev/null 2>&1; then
    alias bat="bat --paging=never"
    alias cat="bat --plain --paging=never"
fi
```

### Shell Startup Integration

Add this line to your shell's startup file to integrate dotbins:

```bash
# For Zsh (~/.zshrc)
source "$HOME/.dotbins/shell/zsh.sh"

# For Bash (~/.bashrc)
source "$HOME/.dotbins/shell/bash.sh"

# For Fish (~/.config/fish/config.fish)
source "$HOME/.dotbins/shell/fish.fish"

# For Nushell
source $env.HOME/.dotbins/shell/nushell.nu
```

---

## :books: Examples with 50+ Tools

See the [examples/examples.yaml](examples/examples.yaml) file for a list of >50 tools that require no configuration.

<!-- CODE:BASH:START -->
<!-- echo '```yaml' -->
<!-- cat examples/examples.yaml -->
<!-- echo '```' -->
<!-- CODE:END -->

<!-- OUTPUT:START -->
<!-- ⚠️ This content is auto-generated by `markdown-code-runner`. -->
```yaml
tools_dir: ~/.dotbins-examples

# List of tools that require no configuration

tools:
  atuin: atuinsh/atuin            # Shell history and recording tool
  bandwhich: imsnif/bandwhich     # Terminal bandwidth utilization tool
  bat: sharkdp/bat                # Cat clone with syntax highlighting and Git integration
  btm: ClementTsang/bottom        # Graphical system monitor
  btop: aristocratos/btop         # Resource monitor and process viewer
  caddy: caddyserver/caddy        # Web server with automatic HTTPS
  choose: theryangeary/choose     # Cut alternative with a simpler syntax
  croc: schollz/croc              # File transfer tool with end-to-end encryption
  ctop: bcicen/ctop               # Container metrics and monitoring
  curlie: rs/curlie               # Curl wrapper with httpie-like syntax
  delta: dandavison/delta         # Syntax-highlighting pager for git and diff output
  difft: Wilfred/difftastic       # Structural diff tool that understands syntax
  direnv: direnv/direnv           # Environment switcher for the shell
  dog: ogham/dog                  # Command-line DNS client like dig
  duf: muesli/duf                 # Disk usage analyzer with pretty output
  dust: bootandy/dust             # More intuitive version of du (disk usage)
  eget: zyedidia/eget             # Go single file downloader (similar to Dotbins)
  eza: eza-community/eza          # Modern replacement for ls
  fd: sharkdp/fd                  # Simple, fast alternative to find
  fzf: junegunn/fzf               # Command-line fuzzy finder
  git-lfs: git-lfs/git-lfs        # Git extension for versioning large files
  glow: charmbracelet/glow        # Markdown renderer for the terminal
  gping: orf/gping                # Ping with a graph
  grex: pemistahl/grex            # Command-line tool for generating regular expressions from user-provided examples
  gron: tomnomnom/gron            # Make JSON greppable
  hexyl: sharkdp/hexyl            # Command-line hex viewer
  hx: helix-editor/helix          # Modern text editor
  hyperfine: sharkdp/hyperfine    # Command-line benchmarking tool
  jc: kellyjonbrazil/jc           # JSON CLI output converter
  jless: PaulJuliusMartinez/jless # Command-line JSON viewer
  jq: jqlang/jq                   # Lightweight JSON processor
  just: casey/just                # Command runner alternative to make
  k9s: derailed/k9s               # Kubernetes CLI to manage clusters
  lazygit: jesseduffield/lazygit  # Simple terminal UI for git commands
  lnav: tstack/lnav               # Log file navigator
  lsd: lsd-rs/lsd                 # Next-gen ls command with icons and colors
  mcfly: cantino/mcfly            # Fly through your shell history
  micro: zyedidia/micro           # Modern and intuitive terminal-based text editor
  micromamba: mamba-org/micromamba-releases # Conda-like distribution
  navi: denisidoro/navi           # Interactive cheatsheet tool for the CLI
  neovim: neovim/neovim           # Modern text editor
  nu: nushell/nushell             # Modern shell for the GitHub era
  pastel: sharkdp/pastel          # A command-line tool to generate, convert and manipulate colors
  procs: dalance/procs            # Modern replacement for ps
  rg: BurntSushi/ripgrep          # Fast grep alternative
  rip: MilesCranmer/rip2          # A safe and ergonomic alternative to rm
  sd: chmln/sd                    # Find & replace CLI
  sk: skim-rs/skim                # Fuzzy finder for the terminal in Rust (similar to fzf)
  starship: starship/starship     # Minimal, fast, customizable prompt for any shell
  tldr: tealdeer-rs/tealdeer      # Fast tldr client in Rust
  topgrade: topgrade-rs/topgrade  # Upgrade all your tools at once
  tre: dduan/tre                  # Tree command with git awareness
  xh: ducaale/xh                  # Friendly and fast tool for sending HTTP requests
  xplr: sayanarijit/xplr          # Hackable, minimal, fast TUI file explorer
  yazi: sxyazi/yazi               # Terminal file manager with image preview
  yq: mikefarah/yq                # YAML/XML/TOML processor similar to jq
  zellij: zellij-org/zellij       # Terminal multiplexer
  zoxide: ajeetdsouza/zoxide      # Smarter cd command with learning

platforms:
  linux:
    - amd64
    - arm64
  macos:
    - arm64
```

<!-- OUTPUT:END -->

---

## :wrench: Troubleshooting

### Common Issues

#### GitHub API Rate Limits

**Issue**: `Failed to fetch latest release: rate limit exceeded`
**Solution**:

- Create a GitHub token with `public_repo` scope
- Use the token with: `dotbins sync --github-token YOUR_TOKEN`
- Or set the environment variable: `GITHUB_TOKEN=YOUR_TOKEN dotbins sync`
- **Tip:** Use `GITHUB_TOKEN=$(gh auth token) dotbins sync` to use your existing GitHub CLI token

#### Windows-Specific Issues

**Issue**: PowerShell execution policy preventing script execution
**Solution**:

- Run PowerShell as administrator
- Execute: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

### Getting Help

- Enable verbose logging with `-v` flag: `dotbins sync -v`
- Check all installed tool versions with: `dotbins status`
- Join GitHub Discussions for help: https://github.com/basnijholt/dotbins/discussions

---

## :thinking: Comparison with Alternatives

`dotbins` fills a specific niche in the binary management ecosystem. Here's how it compares to key alternatives:

| Tool          | Version Management                 | Shell Integration             | Dotfiles Integration           | Primary Use Case           |
| ------------- | ---------------------------------- | ----------------------------- | ------------------------------ | -------------------------- |
| **dotbins**   | Latest only                        | **Built-in via `shell_code`** | **First-class with Git (LFS)** | Complete dotfiles solution |
| **binenv**    | Multiple versions with constraints | Separate completion scripts   | Not focused on                 | Development environments   |
| **eget**      | Latest or specific only            | None                          | Not focused on                 | Quick one-off installs     |
| **asdf/aqua** | Multiple plugins & versions        | Plugin-specific               | Not focused on                 | Development environments   |
| **apt/brew**  | System packages                    | None                          | Not possible                   | System-wide management     |

---

### Key Alternatives

#### Version Managers (e.g., `binenv`, `asdf`)

- **Pros:** Advanced version management (constraints like `>=1.2.3`), multiple versions side-by-side
- **Cons vs. `dotbins`:**
  - Focus on version management rather than dotfiles integration
  - **Separate configuration needed for shell integration** (aliases, completions)
  - Often use shims or more complex architecture
- **When to choose:** For development environments where you need multiple versions of tools

#### Binary Downloaders (e.g., `eget`)

- **Pros:** Lightweight, fast for one-off downloads
- **Cons vs. `dotbins`:**
  - No configuration for multiple tools
  - **No shell integration** for aliases or environment setup
  - No version tracking between sessions
- **When to choose:** For quick installation of individual tools without configuration needs

#### System Package Managers (`apt`, `brew`, etc.)

- **Pros:** System-wide installation, dependency management
- **Cons vs. `dotbins`:**
  - Require admin privileges
  - Not portable across systems
  - Cannot be version-controlled in dotfiles
- **When to choose:** For system-wide software needed by multiple users

### The `dotbins` Difference

`dotbins` uniquely combines:

1. **Binary management** - Downloading from GitHub Releases
2. **Shell configuration** - Defining aliases and shell setup in the same file:
   ```yaml
   bat:
     repo: sharkdp/bat
     shell_code: |
       alias cat="bat --plain --paging=never"
   ```
3. **Dotfiles integration** - Designed to be version-controlled as a Git repository
4. **Cross-platform portability** - Works the same across Linux, macOS, Windows

This makes it perfect for users who want to manage their complete shell environment in a version-controlled dotfiles repository that can be easily deployed on any system.

---

## :heart: Support and Contributions

We appreciate your feedback and contributions! If you encounter any issues or have suggestions for improvements, please file an issue on the GitHub repository. We also welcome pull requests for bug fixes or new features.

Happy tooling! 🧰🛠️🎉
