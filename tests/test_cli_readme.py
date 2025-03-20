"""Tests for CLI README generation functionality."""

from __future__ import annotations


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
