"""Tests for the config validation."""

import pytest

from dotbins.config import Config, _config_from_dict, build_tool_config


def test_validate_unknown_architecture(capsys: pytest.CaptureFixture[str]) -> None:
    """Test validation when an unknown architecture is specified in asset_patterns."""
    # Create a config with a tool that has an unknown architecture in asset_patterns
    platforms = {"macos": ["amd64", "arm64"], "linux": ["amd64", "arm64"]}
    config = Config(
        platforms=platforms,
        tools={
            "test-tool": build_tool_config(
                tool_name="test-tool",
                raw_data={
                    "repo": "test/repo",
                    "binary_name": "test-tool",
                    "path_in_archive": "test-tool",
                    "asset_patterns": {  # type: ignore[typeddict-item]
                        "macos": {"unknown_arch": "test-{version}-linux_unknown.tar.gz"},
                    },
                },
                platforms=platforms,
            ),
        },
    )

    # This should not raise an exception but should log a warning
    config.validate()

    out = capsys.readouterr().out
    assert "uses unknown arch" in out


def test_validate_unknown_platform(capsys: pytest.CaptureFixture[str]) -> None:
    """Test validation when an unknown platform is specified in asset_patterns."""
    platforms = {"linux": ["amd64", "arm64"]}
    config = Config(
        platforms=platforms,
        tools={
            "test-tool": build_tool_config(
                tool_name="test-tool",
                raw_data={
                    "repo": "test/repo",
                    "binary_name": "test-tool",
                    "path_in_archive": "test-tool",
                    "asset_patterns": {  # type: ignore[typeddict-item]
                        "unknown_platform": "test-{version}-macos_amd64.tar.gz",
                    },
                },
                platforms=platforms,
            ),
        },
    )
    config.validate()

    out = capsys.readouterr().out
    assert "uses unknown platform" in out


def test_validate_missing_repo(capsys: pytest.CaptureFixture[str]) -> None:
    """Test validation when a repo is missing."""
    config = Config(
        platforms={"linux": ["amd64", "arm64"]},
        tools={"test-tool": build_tool_config(tool_name="test-tool", raw_data={})},  # type: ignore[typeddict-item]
    )
    config.validate()
    captured = capsys.readouterr()
    assert "missing required field 'repo'" in captured.out


def test_validate_binary_name_and_path_length_mismatch(capsys: pytest.CaptureFixture[str]) -> None:
    """Test validation when binary_name and path_in_archive have different lengths."""
    config = Config(
        platforms={"linux": ["amd64", "arm64"]},
        tools={
            "test-tool": build_tool_config(
                tool_name="test-tool",
                raw_data={
                    "repo": "test/repo",
                    "binary_name": ["test-tool"],
                    "path_in_archive": ["test-tool", "test-tool2"],
                },
            ),
        },
    )
    config.validate()
    captured = capsys.readouterr()
    assert "must have the same" in captured.out


def test_asset_patterns_uses_unknown_arch() -> None:
    """Test validation when asset_patterns uses an unknown architecture."""
    platforms = {"linux": ["amd64", "arm64"]}
    config = Config(
        platforms=platforms,
        tools={
            "test-tool": build_tool_config(
                tool_name="test-tool",
                raw_data={
                    "repo": "test/repo",
                    "asset_patterns": {  # type: ignore[typeddict-item]
                        "linux": {
                            "unknown_arch": "test-{version}-linux_unknown.tar.gz",  # will be ignored
                            "amd64": "test-{version}-linux_amd64.tar.gz",  # will be used
                        },
                    },
                },
                platforms=platforms,
            ),
        },
    )
    assert config.tools["test-tool"].asset_patterns == {
        "linux": {
            "amd64": "test-{version}-linux_amd64.tar.gz",
            "arm64": None,  # not specified but in platforms
        },
    }
    config.validate()


def test_api_url_from_config_dict() -> None:
    """Test that api_url is correctly parsed from config dict."""
    config = _config_from_dict(
        {
            "tools": {
                "tea": {
                    "repo": "gitea/tea",
                    "api_url": "https://gitea.com/api/v1",
                },
                "fzf": "junegunn/fzf",
            },
        },
    )
    assert config.tools["tea"].api_url == "https://gitea.com/api/v1"
    assert config.tools["fzf"].api_url is None


def test_api_url_in_build_tool_config() -> None:
    """Test that api_url is correctly set via build_tool_config."""
    tool = build_tool_config(
        tool_name="tea",
        raw_data={"repo": "gitea/tea", "api_url": "https://gitea.com/api/v1"},
    )
    assert tool.api_url == "https://gitea.com/api/v1"


def test_api_url_defaults_to_none() -> None:
    """Test that api_url defaults to None when not specified."""
    tool = build_tool_config(
        tool_name="fzf",
        raw_data={"repo": "junegunn/fzf"},
    )
    assert tool.api_url is None
