"""Tests for dotbins.utils."""

from dotbins.utils import github_url_to_raw_url


def test_github_url_to_raw_url() -> None:
    """Test that github_url_to_raw_url converts a GitHub repository URL to a raw URL."""
    original_url = "https://github.com/basnijholt/dotbins/blob/main/dotbins.yaml"
    raw_url = "https://raw.githubusercontent.com/basnijholt/dotbins/refs/heads/main/dotbins.yaml"
    assert github_url_to_raw_url(original_url) == raw_url
    assert github_url_to_raw_url(raw_url) == raw_url
    untouched_url = "https://github.com/basnijholt/dotbins"
    assert github_url_to_raw_url(untouched_url) == untouched_url
