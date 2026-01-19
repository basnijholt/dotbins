---
icon: lucide/settings
---

# Configuration

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

## Basic Configuration

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

## Directory Structure

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
└── manifest.json          # Version tracking information
```

## Tool Configuration

Each tool must be configured with at least a GitHub repository. Many other fields are optional and can be auto-detected.

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
  asset_patterns:                  # Optional: Asset patterns for each platform
    linux: pattern-for-linux.tar.gz
    macos: pattern-for-macos.tar.gz
```

## Pattern Variables

In asset patterns, you can use special variables that get replaced with actual values:

- `{version}` - Release version (without 'v' prefix)
- `{platform}` - Platform name (after applying platform_map)
- `{arch}` - Architecture name (after applying arch_map)

For example:

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

## Platform and Architecture Mapping

If the tool uses different naming for platforms or architectures:

```yaml
tool-name:
  platform_map:
    macos: darwin                  # Converts "macos" to "darwin" in patterns
  arch_map:
    amd64: x86_64                  # Converts "amd64" to "x86_64" in patterns
    arm64: aarch64                 # Converts "arm64" to "aarch64" in patterns
```

## Asset Auto-Detection Defaults

When multiple compatible assets are available, dotbins uses these defaults:

```yaml
defaults:
  prefer_appimage: true   # Prioritize AppImage format when available
  libc: musl              # Prefer musl over glibc on Linux
  windows_abi: msvc       # Prefer MSVC over GNU ABI on Windows
```

**Why these defaults?**

- **musl libc**: Statically linked musl binaries offer maximum portability across all Linux distributions regardless of the system's native C library. They eliminate glibc version conflicts (the notorious `GLIBC_X.YZ not found` errors), work on **both** glibc and musl-based distributions (like Alpine Linux), and generally provide a more reliable user experience.

- **AppImage**: AppImage bundles all dependencies in a single, self-contained file that works across different Linux distributions without installation, making it ideal for portable applications (such as neovim, which requires extra runtime files).

- **Windows ABI**: The MSVC ABI is the default on Windows as it's the most widely used and generally more stable. However, if you're using MinGW or prefer GNU tools, you can set this to "gnu".

### Example: libc selection

When requesting Linux amd64 and both of these assets are available:

- `ripgrep-13.0.0-x86_64-unknown-linux-gnu.tar.gz` (uses glibc)
- `ripgrep-13.0.0-x86_64-unknown-linux-musl.tar.gz` (uses musl)

With `libc="musl"`, dotbins selects the musl version.
With `libc="glibc"`, dotbins selects the gnu version.

### Example: AppImage preference

When both formats are available:

- `nvim-linux-x86_64.appimage`
- `nvim-linux-x86_64.tar.gz`

With `prefer_appimage=true`, dotbins selects the AppImage version.

### Example: Windows ABI

When requesting Windows x86_64 and both of these assets are available:

- `bat-v0.25.0-x86_64-pc-windows-gnu.zip` (uses GNU ABI)
- `bat-v0.25.0-x86_64-pc-windows-msvc.zip` (uses MSVC ABI)

With `windows_abi="msvc"`, dotbins selects the MSVC version.
With `windows_abi="gnu"`, dotbins selects the GNU version.

## Multiple Binaries

For tools that provide multiple binaries:

```yaml
uv:
  repo: astral-sh/uv
  binary_name: [uv, uvx]
  path_in_archive: [uv-*/uv, uv-*/uvx]
```

## Configuration Examples

### Minimal Tool Configuration

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

### Standard Tool

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

### Tool with Multiple Binaries

```yaml
uv:
  repo: astral-sh/uv
  binary_name: [uv, uvx]
  path_in_archive: [uv-*/uv, uv-*/uvx]
```

### Platform-Specific Tool

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

### Version-Pinned Tool

```yaml
bat:
  repo: sharkdp/bat
  tag: v0.23.0  # Pin to specific version instead of latest
```

### Shell-Specific Configuration

The auto-generated shell scripts will include tool-specific shell code if provided:

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

For multi-shell compatibility, use the `__DOTBINS_SHELL__` placeholder:

- **Separate entries per shell:** Define the code for each shell individually.
- **Comma-separated shells:** Define the same code for multiple shells by listing them separated by commas (e.g., `bash,zsh:`).
- **Placeholder:** Use the `__DOTBINS_SHELL__` placeholder within the shell code. This placeholder will be replaced by the actual shell name (`bash`, `zsh`, etc.) when the integration scripts are generated.

```yaml
starship:
  repo: starship/starship
  shell_code:
    bash,zsh: eval "$(starship init __DOTBINS_SHELL__)"
    fish: starship init fish | source
```

## Full Configuration Example

This is the author's configuration file (and resulting [`basnijholt/.dotbins`](https://github.com/basnijholt/.dotbins) repo):

<details><summary>Click to view author's full dotbins.yaml</summary>

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

  bat:
    repo: sharkdp/bat
    shell_code:
      bash,zsh: |
        alias bat="bat --paging=never"
        alias cat="bat --plain --paging=never"
  direnv:
    repo: direnv/direnv
    shell_code:
      bash,zsh: |
        eval "$(direnv hook __DOTBINS_SHELL__)"
  eza:
    repo: eza-community/eza
    shell_code:
      bash,zsh: |
        alias l="eza --long --all --git --icons=auto"
  fzf:
    repo: junegunn/fzf
    shell_code:
      zsh: |
        source <(fzf --zsh)
      bash: |
        eval "$(fzf --bash)"
  lazygit:
    repo: jesseduffield/lazygit
    shell_code:
      bash,zsh: |
        alias lg="lazygit"
  micromamba:
    repo: mamba-org/micromamba-releases
    shell_code:
      bash,zsh: |
        alias mm="micromamba"
  starship:
    repo: starship/starship
    shell_code:
      bash,zsh: |
        eval "$(starship init __DOTBINS_SHELL__)"
  zoxide:
    repo: ajeetdsouza/zoxide
    shell_code:
      bash,zsh: |
        eval "$(zoxide init __DOTBINS_SHELL__)"
  atuin:
    repo: atuinsh/atuin
    shell_code:
      bash,zsh: |
        eval "$(atuin init __DOTBINS_SHELL__ --disable-up-arrow)"

  keychain:
    repo: danielrobbins/keychain
    asset_patterns: keychain

  uv:
    repo: astral-sh/uv
    binary_name: [uv, uvx]
    path_in_archive: [uv-*/uv, uv-*/uvx]
```

</details>

## Example: 50+ Tools

See the [examples/examples.yaml](https://github.com/basnijholt/dotbins/blob/main/examples/examples.yaml) file for a list of 50+ tools that require no configuration.
