"""Tests for CLI README generation functionality."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from dotbins.cli import _generate_readme
from dotbins.config import Config


@patch("dotbins.cli.log")
@patch("dotbins.cli.generate_readme_content")
@patch("dotbins.cli.Console")
def test_generate_readme_cli(
    mock_console: MagicMock,
    mock_generate: MagicMock,
    mock_log: MagicMock,
) -> None:
    """Test the _generate_readme CLI function."""
    # Mock config
    config = MagicMock(spec=Config)
    config.tools_dir = MagicMock()

    # Mock generate_readme_content to return test content
    mock_generate.return_value = "# Test README content"

    # Call the function with default parameters (print and write)
    _generate_readme(config, print_content=True, write_file=True, verbose=True)

    # Verify generate_readme_content was called
    mock_generate.assert_called_once_with(config)

    # Verify console output was created
    mock_console.assert_called_once()

    # Verify the file was "written"
    assert config.tools_dir.__truediv__.called

    # Verify success log was output
    mock_log.assert_called_with("Generated README file with tool information", "success", "📝")

    # Reset mocks
    mock_generate.reset_mock()
    mock_console.reset_mock()
    mock_log.reset_mock()
    config.reset_mock()

    # Test with print_content=False
    _generate_readme(config, print_content=False, write_file=True, verbose=True)

    # Verify console was not used
    mock_console.assert_not_called()

    # Verify the file was still "written"
    assert config.tools_dir.__truediv__.called

    # Reset again
    mock_generate.reset_mock()
    mock_console.reset_mock()
    mock_log.reset_mock()
    config.reset_mock()

    # Test with write_file=False
    _generate_readme(config, print_content=True, write_file=False, verbose=True)

    # Verify console was used
    mock_console.assert_called_once()

    # Verify the file was not written
    assert not config.tools_dir.__truediv__.called


def test_cli_argument_parsing() -> None:
    """Test CLI argument parsing for readme and no-readme options."""
    from dotbins.cli import create_parser

    parser = create_parser()

    # Test readme command
    args = parser.parse_args(["readme"])
    assert args.command == "readme"

    # Test update with --no-readme
    args = parser.parse_args(["update", "--no-readme"])
    assert args.command == "update"
    assert args.no_readme is True

    # Test update without --no-readme (default)
    args = parser.parse_args(["update"])
    assert args.command == "update"
    assert args.no_readme is False
