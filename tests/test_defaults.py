"""Tests for defaults in asset detection."""

from dotbins.detect_asset import _prioritize_assets, create_system_detector


def test_libc_preference() -> None:
    """Test that libc preference works correctly."""
    assets = [
        "ripgrep-13.0.0-x86_64-unknown-linux-gnu.tar.gz",
        "ripgrep-13.0.0-x86_64-unknown-linux-musl.tar.gz",
    ]

    # Test preference for glibc
    detector = create_system_detector("linux", "amd64", libc_preference="glibc")
    _asset, matches, err = detector(assets)
    assert err == "2 arch matches found"
    assert matches is not None
    assert "gnu" in matches[0]

    # Test preference for musl
    detector = create_system_detector("linux", "amd64", libc_preference="musl")
    _asset, matches, err = detector(assets)
    assert err == "2 arch matches found"
    assert matches is not None
    assert "musl" in matches[0]


def test_appimage_preference() -> None:
    """Test that AppImage preference works correctly."""
    assets = [
        "ripgrep-13.0.0-x86_64-unknown-linux-gnu.tar.gz",
        "ripgrep-13.0.0-x86_64-linux.AppImage",
    ]

    # Test preference for AppImage=True
    detector = create_system_detector("linux", "amd64", prefer_appimage=True)
    _asset, matches, err = detector(assets)
    assert err == "2 arch matches found"
    assert matches is not None
    assert matches[0].endswith(".AppImage")

    # Test preference for AppImage=False
    detector = create_system_detector("linux", "amd64", prefer_appimage=False)
    _asset, matches, err = detector(assets)
    assert err == "2 arch matches found"
    assert matches is not None
    assert not matches[0].endswith(".AppImage")


def test_arch_specific_preferences() -> None:
    """Test architecture-specific defaults."""
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

    # AMD64 should prefer AppImage
    detector = create_system_detector(
        "linux",
        "amd64",
        prefer_appimage=True,
        libc_preference="glibc",
    )
    _asset, matches, err = detector(amd64_assets)
    assert err == "3 arch matches found"
    assert matches is not None
    assert matches[0].endswith(".AppImage")

    # ARM64 should prefer musl and not AppImage
    detector = create_system_detector(
        "linux",
        "arm64",
        prefer_appimage=False,
        libc_preference="musl",
    )
    _asset, matches, err = detector(arm64_assets)
    assert err == "3 arch matches found"
    assert matches is not None
    assert "musl" in matches[0]
    assert not matches[0].endswith(".AppImage")


def test_prioritize_assets_with_preferences() -> None:
    """Test the _prioritize_assets function with different defaults."""
    assets = [
        "ripgrep-13.0.0-x86_64-unknown-linux-gnu.tar.gz",
        "ripgrep-13.0.0-x86_64-unknown-linux-musl.tar.gz",
        "ripgrep-13.0.0-x86_64-linux.AppImage",
        "ripgrep-13.0.0.deb",
    ]

    # Test with prefer_appimage=True
    prioritized = _prioritize_assets(
        assets,
        "linux",
        libc_preference="glibc",
        windows_abi="msvc",
        prefer_appimage=True,
    )
    assert prioritized is not None
    assert prioritized[0].endswith(".AppImage")

    # Test with prefer_appimage=False
    prioritized = _prioritize_assets(
        assets,
        "linux",
        libc_preference="glibc",
        windows_abi="msvc",
        prefer_appimage=False,
    )
    assert not prioritized[0].endswith(".AppImage")

    # Test libc preference
    prioritized = _prioritize_assets(
        assets,
        "linux",
        libc_preference="musl",
        windows_abi="msvc",
        prefer_appimage=False,
    )
    # First non-AppImage asset should be musl
    for asset in prioritized:
        if not asset.endswith(".AppImage") and not asset.endswith(".deb"):
            assert "musl" in asset
            break
