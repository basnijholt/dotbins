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

## Multiple Binaries

For tools that provide multiple binaries:

```yaml
uv:
  repo: astral-sh/uv
  binary_name: [uv, uvx]
  path_in_archive: [uv-*/uv, uv-*/uvx]
```

## Shell-Specific Configuration

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

```yaml
starship:
  repo: starship/starship
  shell_code:
    bash,zsh: eval "$(starship init __DOTBINS_SHELL__)"
    fish: starship init fish | source
```

## Example: 50+ Tools

See the [examples/examples.yaml](https://github.com/basnijholt/dotbins/blob/main/examples/examples.yaml) file for a list of 50+ tools that require no configuration.
