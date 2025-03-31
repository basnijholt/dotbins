"""Tests for preferences in asset detection."""

from dotbins.detect_asset import _prioritize_assets, create_system_detector


def test_libc_preference():
    """Test that libc preference works correctly."""
    assets = [
        "ripgrep-13.0.0-x86_64-unknown-linux-gnu.tar.gz",
        "ripgrep-13.0.0-x86_64-unknown-linux-musl.tar.gz",
    ]

    # Test preference for glibc
    preferences = {"linux": {"libc": "glibc"}}
    detector = create_system_detector("linux", "amd64", preferences=preferences)
    asset, _, _ = detector(assets)
    assert "gnu" in asset

    # Test preference for musl
    preferences = {"linux": {"libc": "musl"}}
    detector = create_system_detector("linux", "amd64", preferences=preferences)
    asset, _, _ = detector(assets)
    assert "musl" in asset


def test_appimage_preference():
    """Test that AppImage preference works correctly."""
    assets = [
        "ripgrep-13.0.0-x86_64-unknown-linux-gnu.tar.gz",
        "ripgrep-13.0.0-x86_64-linux.AppImage",
    ]

    # Test preference for AppImage=True
    preferences = {"linux": {"prefer_appimage": True}}
    detector = create_system_detector("linux", "amd64", preferences=preferences)
    asset, _, _ = detector(assets)
    assert asset.endswith(".AppImage")

    # Test preference for AppImage=False
    preferences = {"linux": {"prefer_appimage": False}}
    detector = create_system_detector("linux", "amd64", preferences=preferences)
    asset, _, _ = detector(assets)
    assert not asset.endswith(".AppImage")


def test_arch_specific_preferences():
    """Test architecture-specific preferences."""
    amd64_assets = [
        "ripgrep-13.0.0-x86_64-unknown-linux-gnu.tar.gz",
        "ripgrep-13.0.0-x86_64-unknown-linux-musl.tar.gz",
        "ripgrep-13.0.0-x86_64-linux.AppImage",
    ]

    arm64_assets = [
        "ripgrep-13.0.0-aarch64-unknown-linux-gnu.tar.gz",
        "ripgrep-13.0.0-aarch64-unknown-linux-musl.tar.gz",
        "ripgrep-13.0.0-arm64-linux.AppImage",
    ]

    # Test different preferences for different architectures
    preferences = {
        "linux": {
            "amd64": {
                "prefer_appimage": True,
                "libc": "glibc",
            },
            "arm64": {
                "prefer_appimage": False,
                "libc": "musl",
            },
        },
    }

    # AMD64 should prefer AppImage
    detector = create_system_detector("linux", "amd64", preferences=preferences)
    asset, _, _ = detector(amd64_assets)
    assert asset.endswith(".AppImage")

    # ARM64 should prefer musl and not AppImage
    detector = create_system_detector("linux", "arm64", preferences=preferences)
    asset, _, _ = detector(arm64_assets)
    assert "musl" in asset
    assert not asset.endswith(".AppImage")


def test_prioritize_assets_with_preferences():
    """Test the _prioritize_assets function with different preferences."""
    assets = [
        "ripgrep-13.0.0-x86_64-unknown-linux-gnu.tar.gz",
        "ripgrep-13.0.0-x86_64-unknown-linux-musl.tar.gz",
        "ripgrep-13.0.0-x86_64-linux.AppImage",
        "ripgrep-13.0.0.deb",
    ]

    # Test with prefer_appimage=True
    prioritized = _prioritize_assets(assets, "linux", libc_preference="glibc", prefer_appimage=True)
    assert prioritized[0].endswith(".AppImage")

    # Test with prefer_appimage=False
    prioritized = _prioritize_assets(
        assets, "linux", libc_preference="glibc", prefer_appimage=False
    )
    assert not prioritized[0].endswith(".AppImage")

    # Test libc preference
    prioritized = _prioritize_assets(assets, "linux", libc_preference="musl", prefer_appimage=False)
    # First non-AppImage asset should be musl
    for asset in prioritized:
        if not asset.endswith(".AppImage") and not asset.endswith(".deb"):
            assert "musl" in asset
            break
