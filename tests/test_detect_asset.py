"""Tests for the dotbins.detect_asset module."""

import pytest

from dotbins.detect_asset import (
    ArchAMD64,
    ArchArm,
    ArchArm64,
    ArchI386,
    ArchRiscv64,
    OSDarwin,
    OSLinux,
    _detect_system,
    _match_arch,
    _match_os,
    create_system_detector,
    detect_single_asset,
)


def test_os_match() -> None:
    """Test the match_os function."""
    # Test basic OS matching
    assert _match_os(OSDarwin, "darwin-amd64.tar.gz") is True
    assert _match_os(OSDarwin, "macos-amd64.tar.gz") is True
    assert _match_os(OSDarwin, "osx-amd64.tar.gz") is True
    assert _match_os(OSDarwin, "linux-amd64.tar.gz") is False

    # Test with anti-pattern
    assert _match_os(OSLinux, "linux-amd64.tar.gz") is True
    assert _match_os(OSLinux, "ubuntu-amd64.tar.gz") is True
    assert _match_os(OSLinux, "android-amd64.tar.gz") is False

    # Test with AppImage files
    assert _match_os(OSLinux, "app.appimage") is True  # AppImage files are always for Linux
    assert _match_os(OSLinux, "linux-app.appimage") is True


def test_arch_match() -> None:
    """Test the match_arch function."""
    # Test basic arch matching
    assert _match_arch(ArchAMD64, "linux-amd64.tar.gz")
    assert _match_arch(ArchAMD64, "linux-x86_64.tar.gz")
    assert _match_arch(ArchAMD64, "linux-x64.tar.gz")
    assert not _match_arch(ArchAMD64, "linux-386.tar.gz")

    # Test the `-64` and `_64` pattern additions
    assert _match_arch(ArchAMD64, "linux-64.tar.gz")
    assert _match_arch(ArchAMD64, "linux_64.tar.gz")
    assert _match_arch(ArchAMD64, "micromamba-linux-64")
    assert _match_arch(ArchAMD64, "app_linux_64")
    assert _match_arch(ArchAMD64, "linux-64bit.tar.gz")  # Not at word boundary

    # Verify we don't get false positives
    assert not _match_arch(ArchAMD64, "linux-arm64.tar.gz")  # Should match ARM64, not AMD64
    assert not _match_arch(ArchAMD64, "linux-riscv64.tar.gz")  # Should match RISCV64, not AMD64
    assert not _match_arch(
        ArchAMD64,
        "something-with-64-in-name.tar.gz",
    )  # Not matching the pattern
    assert not _match_arch(ArchAMD64, "with64suffix.tar.gz")  # Not at word boundary

    assert _match_arch(ArchI386, "linux-i386.tar.gz")
    assert _match_arch(ArchI386, "linux-386.tar.gz")
    assert _match_arch(ArchI386, "linux-x86_32.tar.gz")
    assert not _match_arch(ArchI386, "linux-amd64.tar.gz")

    assert _match_arch(ArchArm, "linux-arm.tar.gz")
    assert _match_arch(ArchArm, "linux-armv6.tar.gz")
    assert _match_arch(ArchArm, "linux-arm32.tar.gz")
    assert not _match_arch(ArchArm, "linux-amd64.tar.gz")

    assert _match_arch(ArchArm64, "linux-arm64.tar.gz")
    assert _match_arch(ArchArm64, "linux-aarch64.tar.gz")
    assert _match_arch(ArchArm64, "linux-armv8.tar.gz")
    assert not _match_arch(ArchArm64, "linux-amd64.tar.gz")

    assert _match_arch(ArchRiscv64, "linux-riscv64.tar.gz")
    assert not _match_arch(ArchRiscv64, "linux-amd64.tar.gz")


def test_single_asset_detector_detect() -> None:
    """Test the detect_single_asset function."""
    # Test exact match
    detector = detect_single_asset("app.tar.gz")
    match, candidates, error = detector(["app.tar.gz", "other.tar.gz"])
    assert match == "app.tar.gz"
    assert candidates is None
    assert error is None

    # Test partial match
    detector = detect_single_asset("app")
    match, candidates, error = detector(["app.tar.gz", "other.tar.gz"])
    assert match == "app.tar.gz"
    assert candidates is None
    assert error is None

    # Test multiple matches
    detector = detect_single_asset("app")
    match, candidates, error = detector(["app.tar.gz", "app.zip"])
    assert match == ""
    assert candidates == ["app.tar.gz", "app.zip"]
    assert error == "2 candidates found for asset `app`"

    # Test no matches
    detector = detect_single_asset("app")
    match, candidates, error = detector(["other.tar.gz", "another.zip"])
    assert match == ""
    assert candidates is None
    assert error == "asset `app` not found"

    # Test anti mode
    detector = detect_single_asset("app", anti=True)
    match, candidates, error = detector(["app.tar.gz", "other.tar.gz"])
    assert match == "other.tar.gz"
    assert candidates is None
    assert error is None

    # Test anti mode with multiple matches
    detector = detect_single_asset("app", anti=True)
    match, candidates, error = detector(
        ["app.tar.gz", "other1.tar.gz", "other2.tar.gz"],
    )
    assert match == ""
    assert candidates == ["other1.tar.gz", "other2.tar.gz"]
    assert error == "2 candidates found for asset `app`"


def test_create_system_detector() -> None:
    """Test the create_system_detector function."""
    # Valid OS and arch
    detector_fn = create_system_detector("linux", "amd64")

    # We can't directly check the detector's internal state anymore,
    # so we'll test it by using it to detect an asset
    match, candidates, err = detector_fn(["app-linux-amd64.tar.gz"])
    assert match == "app-linux-amd64.tar.gz"
    assert candidates is None
    assert err is None

    # Invalid OS
    with pytest.raises(ValueError, match="unsupported target OS: invalid"):
        create_system_detector("invalid", "amd64")

    # Invalid arch
    with pytest.raises(ValueError, match="unsupported target arch: invalid"):
        create_system_detector("linux", "invalid")


def test_system_detector_detect() -> None:
    """Test the detect_system function."""
    detector = _detect_system(OSLinux, ArchAMD64, "musl", "msvc", True)

    # Perfect match
    assets = [
        "app-linux-amd64.tar.gz",
        "app-darwin-amd64.tar.gz",
        "app-windows-amd64.exe",
    ]
    match, candidates, error = detector(assets)
    assert match == "app-linux-amd64.tar.gz"
    assert candidates is None
    assert error is None

    # Multiple perfect matches
    assets = [
        "app-linux-amd64.tar.gz",
        "app-linux-x86_64.tar.gz",
        "app-darwin-amd64.tar.gz",
    ]
    match, candidates, error = detector(assets)
    assert match == ""
    assert candidates == ["app-linux-amd64.tar.gz", "app-linux-x86_64.tar.gz"]
    assert error == "2 arch matches found"

    # OS match but no arch match
    assets = ["app-linux-arm64.tar.gz", "app-darwin-amd64.tar.gz"]
    match, candidates, error = detector(assets)
    assert match == "app-linux-arm64.tar.gz"
    assert candidates is None
    assert error is None

    # Multiple OS matches but no arch match
    assets = [
        "app-linux-arm64.tar.gz",
        "app-linux-arm.tar.gz",
        "app-darwin-amd64.tar.gz",
    ]
    match, candidates, error = detector(assets)
    assert match == ""
    assert candidates == ["app-linux-arm.tar.gz", "app-linux-arm64.tar.gz"]
    assert error == "2 candidates found (unsure architecture)"

    # No OS or arch match
    assets = ["app-darwin-arm64.tar.gz", "app-windows-386.exe"]
    match, candidates, error = detector(assets)
    assert match == ""
    assert candidates == ["app-darwin-arm64.tar.gz", "app-windows-386.exe"]
    assert error == "no candidates found"

    # AppImage priority match (AppImages should be prioritized)
    assets = ["app-linux-amd64.tar.gz", "app-linux-amd64.appimage"]
    match, candidates, error = detector(assets)
    # Since we're checking multiple assets with the same OS/ARCH,
    # the result should be a prioritized list, not a single match
    assert match == ""
    assert candidates == ["app-linux-amd64.appimage", "app-linux-amd64.tar.gz"]
    assert error == "2 arch matches found"

    # Package vs archive priority
    # Test that archive formats (.tar.gz) are prioritized over package formats (.deb)
    assets = ["app-linux-amd64.deb", "app-linux-amd64.tar.gz"]
    match, candidates, error = detector(assets)
    assert match == ""
    assert candidates == ["app-linux-amd64.tar.gz", "app-linux-amd64.deb"]
    assert error == "2 arch matches found"

    # Skip signature files
    assets = [
        "app-linux-amd64.tar.gz",
        "app-linux-amd64.tar.gz.sha256",
        "app-darwin-amd64.tar.gz",
    ]
    match, candidates, error = detector(assets)
    assert match == "app-linux-amd64.tar.gz"
    assert candidates is None
    assert error is None


def test_system_detector_single_asset_fallback() -> None:
    """Test that when there's only one asset, it's returned even if it doesn't match criteria."""
    detector = _detect_system(OSLinux, ArchAMD64, "musl", "msvc", True)

    # Single asset with a name that doesn't match any OS or arch patterns
    assets = ["completely-unrelated-name.zip"]
    match, candidates, error = detector(assets)
    assert match == "completely-unrelated-name.zip"
    assert candidates is None
    assert error is None

    # Make sure filtered files don't count in the single asset check
    assets = ["completely-unrelated-name.sha256"]
    match, candidates, error = detector(assets)
    assert match == ""
    assert candidates == []
    assert error == "no candidates found"


def test_sort_arch_order() -> None:
    """Test the sort_arch function."""
    detector = _detect_system(OSLinux, ArchI386, "musl", "msvc", True)
    assets = [
        "app-linux-i386.tar.gz",
        "app-linux-i486.tar.gz",
        "app-linux-i586.tar.gz",
        "app-linux-i686.tar.gz",
        "app-linux-arm.tar.gz",
    ]
    match, candidates, error = detector(assets)
    assert not match
    assert candidates == [
        "app-linux-i686.tar.gz",
        "app-linux-i586.tar.gz",
        "app-linux-i486.tar.gz",
        "app-linux-i386.tar.gz",
    ]
    assert error == "4 arch matches found"
