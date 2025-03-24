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

<details><summary><b><u>[ToC]</u></b> 📚</summary>

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [:zap: Quick Start](#zap-quick-start)
- [:star2: Features](#star2-features)
- [:bulb: Why I Created dotbins](#bulb-why-i-created-dotbins)
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
    - [Shell-Specific Configuration](#shell-specific-configuration)
  - [Full Configuration Example](#full-configuration-example)
- [:bulb: Examples](#bulb-examples)
- [:computer: Shell Integration](#computer-shell-integration)
- [:books: Examples with 50+ Tools](#books-examples-with-50-tools)
- [:heart: Support and Contributions](#heart-support-and-contributions)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

</details>

## :zap: Quick Start

Using the amazing [`uv`](https://docs.astral.sh/uv/) package manager:

```bash
# Install directly to ~/.local/bin (no configuration needed)
uvx dotbins get junegunn/fzf

# Set up multiple tools with a config file (creates ~/.dotbins)
uvx dotbins sync

# Bootstrap a collection of tools from a remote config
uvx dotbins get https://github.com/basnijholt/.dotbins/blob/main/dotbins.yaml
```

**See it in action:**

[![asciicast](https://asciinema.org/a/709229.svg)](https://asciinema.org/a/709229)

## :star2: Features

* 🌐 Supports multiple platforms (macOS, Linux, etc.) and architectures (amd64, arm64, etc.)
* 📦 Downloads and organizes binaries from GitHub releases
* 🔄 Installs and updates tools to their latest versions with a single command
* 📊 Tracks installed versions and update timestamps for all tools
* 🧩 Extracts binaries from various archive formats (zip, tar.gz)
* 📂 Organizes tools by platform and architecture for easy access
* 🐙 Easy integration with your dotfiles repository for version control

## :bulb: Why I Created dotbins

I frequently works across multiple environments where I clone my dotfiles repository with all my preferred configurations.
I faced a common frustration: some of my favorite tools (`fzf`, `bat`, `zoxide`, etc.) were not available on the new system and installing them with a package manager is too much work or even not possible.
`dotbins` was born out of this frustration.

It allows me to:

1. Track pre-compiled binaries in a [separate Git repository](https://github.com/basnijholt/.dotbins) (using Git LFS for efficient storage)
2. Include this repository as a submodule in my dotfiles
3. Ensure all my essential tools are immediately available after cloning, regardless of system permissions

Now when I clone my dotfiles on any new system, I get not just my configurations but also all the CLI tools I depend on for productivity.

**_No package manager, no sudo, no problem!_**

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
               {list,sync,init,version,status,readme,get} ...

dotbins - Download, manage, and update CLI tool binaries in your dotfiles
repository

Positional Arguments:
  {list,sync,init,version,status,readme,get}
                        Command to execute
    list                List all available tools defined in your configuration
    sync                Install and update tools to their latest versions
    init                Initialize directory structure and generate shell
                        integration scripts
    version             Print dotbins version information
    status              Show installed tool versions and when they were last
                        updated
    readme              Generate README.md file with information about
                        installed tools
    get                 Download and install a tool directly without
                        configuration file

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
3. **init** - Initialize the tools directory structure
4. **list** - List available tools defined in your configuration
5. **version** - Print version information
6. **status** - Show detailed information about available and installed tool versions

### Quick Install with `dotbins get`

The `get` command allows you to quickly download and install tools directly from GitHub or from a remote configuration file:

```bash
# Install fzf to the default location (~/.local/bin)
dotbins get junegunn/fzf

# Install ripgrep with a custom binary name
dotbins get BurntSushi/ripgrep --name rg

# Install bat to a specific location
dotbins get sharkdp/bat --dest ~/bin

# Install multiple tools from a remote config URL
dotbins get https://example.com/my-tools.yaml --dest ~/.local/bin
```

This is perfect for:
- Quickly installing tools on a new system
- One-off installations without needing a configuration file
- Adding tools to PATH in standard locations like `~/.local/bin`
- Bootstrapping with a pre-configured set of tools using a remote configuration URL

The `get` command automatically detects whether you're providing a GitHub repository or a configuration URL.
When using a URL, it will download all tools defined in the configuration for your current platform and architecture.

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

When auto-detection isn't possible or you want more control, you can provide detailed configuration:

```yaml
tool-name:
  repo: owner/repo                 # Required: GitHub repository
  extract_binary: true             # Optional: Whether to extract from archive (true) or direct download (false) (auto-detected if not specified)
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
direnv:
  repo: direnv/direnv
```
or
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

This is the author's configuration file:

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
  fd: sharkdp/fd
  git-lfs: git-lfs/git-lfs
  yazi: sxyazi/yazi

  bat:
    repo: sharkdp/bat
    shell_code: |
      alias bat="bat --paging=never"
      alias cat="bat --plain --paging=never"
  direnv:
    repo: direnv/direnv
    shell_code: |
      eval "$(direnv hook zsh)"
  fzf:
    repo: junegunn/fzf
    shell_code: |
      source <(fzf --zsh)
  lazygit:
    repo: jesseduffield/lazygit
    shell_code: |
      alias lg="lazygit"
  zoxide:
    repo: ajeetdsouza/zoxide
    shell_code: |
      eval "$(zoxide init zsh)"

  ripgrep:
    repo: BurntSushi/ripgrep
    binary_name: rg

  atuin:
    repo: atuinsh/atuin
    arch_map:
      amd64: x86_64
      arm64: aarch64
    asset_patterns:
      linux: atuin-{arch}-unknown-linux-gnu.tar.gz
      macos: atuin-{arch}-apple-darwin.tar.gz
    shell_code: |
      source <(atuin init zsh --disable-up-arrow)

  eza:
    repo: eza-community/eza
    arch_map:
      amd64: x86_64
      arm64: aarch64
    asset_patterns:
      linux: eza_{arch}-unknown-linux-gnu.tar.gz
      macos: null  # No macOS binaries available as of now
    shell_code: |
      alias l="eza -lah --git"

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
    shell_code: |
      alias mm="micromamba"

  uv:
    repo: astral-sh/uv
    binary_name: [uv, uvx]
    binary_path: [uv-*/uv, uv-*/uvx]
    shell_code: |
      eval "$(uv generate-shell-completion zsh)"

  starship:
    repo: starship/starship
    shell_code: |
      eval "$(starship init zsh)"
```

<!-- OUTPUT:END -->

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

Install tools only for your current system:
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

## :computer: Shell Integration

dotbins creates shell scripts that you can source to automatically add the correct binaries to your `PATH`.

After running `dotbins sync` or `dotbins init`, shell integration scripts are created in `~/.dotbins/shell/` for various shells.

Check the output of `dotbins init` to see which shell scripts were created and how to add them to your shell configuration file:

<!-- CODE:BASH:START -->
<!-- echo '```bash' -->
<!-- dotbins init -->
<!-- echo '```' -->
<!-- CODE:END -->

<!-- OUTPUT:START -->
<!-- ⚠️ This content is auto-generated by `markdown-code-runner`. -->
```bash
✅ Loading configuration from: ~/work/dotbins/dotbins/dotbins.yaml
🛠️ dotbins initialized tools directory structure in `tools_dir=~/.dotbins`
📝 Generated shell scripts in ~/.dotbins/shell/
🔍 Add this to your shell config:
👉   Bash:    source $HOME/.dotbins/shell/bash.sh
👉   Zsh:     source $HOME/.dotbins/shell/zsh.sh
👉   Fish:    source $HOME/.dotbins/shell/fish.fish
👉   Nushell: source $HOME/.dotbins/shell/nushell.nu
ℹ️ To see the shell setup instructions, run `dotbins init`
📝 Generated README at ~/.dotbins/README.md
```

<!-- OUTPUT:END -->

## :books: Examples with 50+ Tools

See the [examples/dotbins.yaml](examples/dotbins.yaml) file for a list of >50 tools that require no configuration.

<!-- CODE:BASH:START -->
<!-- echo '```yaml' -->
<!-- cat examples/dotbins.yaml -->
<!-- echo '```' -->
<!-- CODE:END -->

<!-- OUTPUT:START -->
<!-- ⚠️ This content is auto-generated by `markdown-code-runner`. -->
```yaml
tools_dir: ~/.dotbins-examples

# List of tools that require no configuration

tools:
  bandwhich: imsnif/bandwhich     # Terminal bandwidth utilization tool
  bat: sharkdp/bat                # Cat clone with syntax highlighting and Git integration
  btm: ClementTsang/bottom        # Graphical system monitor
  btop: aristocratos/btop         # Resource monitor and process viewer
  caddy: caddyserver/caddy        # Web server with automatic HTTPS
  choose: theryangeary/choose     # Cut alternative with a simpler syntax
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
  tealdeer: tealdeer-rs/tealdeer  # Fast tldr client in Rust
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

## :heart: Support and Contributions

We appreciate your feedback and contributions! If you encounter any issues or have suggestions for improvements, please file an issue on the GitHub repository. We also welcome pull requests for bug fixes or new features.

Happy tooling! 🧰🛠️🎉
