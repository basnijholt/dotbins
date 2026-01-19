---
icon: lucide/heart-handshake
---

# Contributing

We appreciate your feedback and contributions! If you encounter any issues or have suggestions for improvements, please file an issue on the GitHub repository.

## How to Contribute

1. **Report Issues**: Found a bug or have a feature request? [Open an issue](https://github.com/basnijholt/dotbins/issues)
2. **Submit Pull Requests**: Bug fixes and new features are welcome
3. **Improve Documentation**: Help us make the docs better
4. **Share Your Config**: Show us your creative `dotbins.yaml` configurations

## Development Setup

```bash
# Clone the repository
git clone https://github.com/basnijholt/dotbins.git
cd dotbins

# Install development dependencies with uv
uv sync --group dev

# Run tests
uv run pytest

# Run linting
uv run ruff check .
```

## Code Style

This project uses:

- **Ruff** for linting and formatting
- **pytest** for testing
- Type hints throughout the codebase

## Questions?

Join the [GitHub Discussions](https://github.com/basnijholt/dotbins/discussions) for help and community support.
