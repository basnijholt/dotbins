---
icon: lucide/book-open
---

# Usage

To use dotbins, you'll need to familiarize yourself with its commands.

## CLI Help

<!-- CODE:BASH:START -->
<!-- echo '```bash' -->
<!-- dotbins --help -->
<!-- echo '```' -->
<!-- CODE:END -->
<!-- OUTPUT:START -->
<!-- PLACEHOLDER --> Output is generated during CI build. We don't commit generated content to keep docs copyable and avoid recursion. See docs/docs_gen.py
<!-- OUTPUT:END -->

## Commands

1. **sync** - Install and update tools to their latest versions
2. **get** - Download and install a tool directly without using a configuration file
3. **init** - Initialize the tools directory structure and generate a sample configuration file
4. **list** - List available tools defined in your configuration
5. **version** - Print version information
6. **status** - Show detailed information about available and installed tool versions

## Update Process with `dotbins sync`

The `sync` command is the core of dotbins, keeping your tools up-to-date across platforms.

Here's what happens during `dotbins sync`:

1. **Version Detection**: Checks each tool's current version and queries GitHub for latest releases
2. **Smart Updates**: Only downloads tools with newer versions (unless `--force` is used)
3. **Multi-Platform Management**: Processes each platform/architecture combination
4. **File Generation**: Updates `manifest.json`, shell scripts, and README

```bash
# Update all tools for all configured platforms
dotbins sync

# Update only specific tools
dotbins sync fzf bat

# Update tools only for current platform
dotbins sync --current

# Force reinstall everything
dotbins sync --force

# Use versions from manifest.json
dotbins sync --pin-to-manifest
```

## Quick Install with `dotbins get`

The `get` command allows quick installation without a configuration file:

```bash
# Install fzf to the default location (~/.local/bin)
dotbins get junegunn/fzf

# Install ripgrep with a custom binary name
dotbins get BurntSushi/ripgrep --name rg

# Install bat to a specific location
dotbins get sharkdp/bat --dest ~/bin

# Install from a remote config URL
dotbins get https://example.com/my-tools.yaml --dest ~/.local/bin
```

Perfect for:

- Quickly installing tools on a new system
- One-off installations without needing a configuration file
- Adding tools to PATH in standard locations like `~/.local/bin`
- Bootstrapping with a pre-configured set of tools

## Initializing with `dotbins init`

The fastest way to get started:

```bash
dotbins init
```

This command:

- Creates the directory structure for all configured platforms and architectures
- Generates shell integration scripts for your system
- If no config exists, creates a sample `dotbins.yaml` with sensible defaults

## Examples

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

Install or update tools only for the current system:

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

Show status for all installed tools:

```bash
dotbins status
```

Show a compact view (one line per tool):

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
