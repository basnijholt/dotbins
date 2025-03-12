"""Tests for the dotbins.detect module."""

from dotbins.detect import (
    ArchAMD64,
    ArchArm,
    ArchArm64,
    ArchI386,
    ArchRiscv64,
    OSDarwin,
    OSLinux,
    chain_detectors,
    create_system_detector,
    detect_all,
    detect_single_asset,
    detect_system,
    match_arch,
    match_os,
)


def test_os_match() -> None:
    """Test the match_os function."""
    # Test basic OS matching
    assert match_os(OSDarwin, "darwin-amd64.tar.gz") == (True, False)
    assert match_os(OSDarwin, "macos-amd64.tar.gz") == (True, False)
    assert match_os(OSDarwin, "osx-amd64.tar.gz") == (True, False)
    assert match_os(OSDarwin, "linux-amd64.tar.gz") == (False, False)

    # Test with anti-pattern
    assert match_os(OSLinux, "linux-amd64.tar.gz") == (True, False)
    assert match_os(OSLinux, "ubuntu-amd64.tar.gz") == (True, False)
    assert match_os(OSLinux, "android-amd64.tar.gz") == (False, False)

    # Test with priority pattern
    assert match_os(OSLinux, "app.appimage") == (False, False)  # No Linux in name
    assert match_os(OSLinux, "linux-app.appimage") == (True, True)


def test_arch_match() -> None:
    """Test the match_arch function."""
    # Test basic arch matching
    assert match_arch(ArchAMD64, "linux-amd64.tar.gz")
    assert match_arch(ArchAMD64, "linux-x86_64.tar.gz")
    assert match_arch(ArchAMD64, "linux-x64.tar.gz")
    assert not match_arch(ArchAMD64, "linux-386.tar.gz")

    assert match_arch(ArchI386, "linux-i386.tar.gz")
    assert match_arch(ArchI386, "linux-386.tar.gz")
    assert match_arch(ArchI386, "linux-x86_32.tar.gz")
    assert not match_arch(ArchI386, "linux-amd64.tar.gz")

    assert match_arch(ArchArm, "linux-arm.tar.gz")
    assert match_arch(ArchArm, "linux-armv6.tar.gz")
    assert match_arch(ArchArm, "linux-arm32.tar.gz")
    assert not match_arch(ArchArm, "linux-amd64.tar.gz")

    assert match_arch(ArchArm64, "linux-arm64.tar.gz")
    assert match_arch(ArchArm64, "linux-aarch64.tar.gz")
    assert match_arch(ArchArm64, "linux-armv8.tar.gz")
    assert not match_arch(ArchArm64, "linux-amd64.tar.gz")

    assert match_arch(ArchRiscv64, "linux-riscv64.tar.gz")
    assert not match_arch(ArchRiscv64, "linux-amd64.tar.gz")


def test_all_detector_detect() -> None:
    """Test the detect_all function."""
    # Single asset
    match, candidates, error = detect_all(["app.tar.gz"])
    assert match == "app.tar.gz"
    assert candidates is None
    assert error is None

    # Multiple assets
    match, candidates, error = detect_all(["app1.tar.gz", "app2.tar.gz"])
    assert match == ""
    assert candidates == ["app1.tar.gz", "app2.tar.gz"]
    assert error == "2 matches found"


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
    detector_fn, error = create_system_detector("linux", "amd64")
    assert detector_fn is not None
    assert error is None

    # We can't directly check the detector's internal state anymore,
    # so we'll test it by using it to detect an asset
    match, candidates, err = detector_fn(["app-linux-amd64.tar.gz"])
    assert match == "app-linux-amd64.tar.gz"
    assert candidates is None
    assert err is None

    # Invalid OS
    detector_fn, error = create_system_detector("invalid", "amd64")
    assert detector_fn is None
    assert error == "unsupported target OS: invalid"

    # Invalid arch
    detector_fn, error = create_system_detector("linux", "invalid")
    assert detector_fn is None
    assert error == "unsupported target arch: invalid"


def test_system_detector_detect() -> None:
    """Test the detect_system function."""
    detector = detect_system(OSLinux, ArchAMD64)

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
    assert error == "2 matches found"

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
    assert candidates == ["app-linux-arm64.tar.gz", "app-linux-arm.tar.gz"]
    assert error == "2 candidates found (unsure architecture)"

    # No OS or arch match
    assets = ["app-darwin-arm64.tar.gz", "app-windows-386.exe"]
    match, candidates, error = detector(assets)
    assert match == ""
    assert candidates == ["app-darwin-arm64.tar.gz", "app-windows-386.exe"]
    assert error == "no candidates found"

    # Priority match
    assets = ["app-linux-amd64.tar.gz", "app-linux.appimage"]
    match, candidates, error = detector(assets)
    assert match == "app-linux.appimage"
    assert candidates is None
    assert error is None

    # Multiple priority matches
    assets = [
        "app1-linux.appimage",
        "app2-linux.appimage",
    ]
    match, candidates, error = detector(assets)
    assert match == ""
    assert candidates == ["app1-linux.appimage", "app2-linux.appimage"]
    assert error == "2 priority matches found"

    # Skip checksum files
    assets = [
        "app-linux-amd64.tar.gz",
        "app-linux-amd64.tar.gz.sha256",
        "app-darwin-amd64.tar.gz",
    ]
    match, candidates, error = detector(assets)
    assert match == "app-linux-amd64.tar.gz"
    assert candidates is None
    assert error is None


def test_detector_chain() -> None:
    """Test the chain_detectors function."""
    # Set up a chain of detectors
    system_detector_fn, _ = create_system_detector("linux", "amd64")
    assert system_detector_fn is not None
    asset_detector_fn = detect_single_asset("app")

    chain_fn = chain_detectors(detectors=[asset_detector_fn], system=system_detector_fn)

    # Test successful chain
    assets = [
        "app-linux-amd64.tar.gz",
        "app-darwin-amd64.tar.gz",
        "other-linux-amd64.tar.gz",
    ]
    match, candidates, error = chain_fn(assets)
    assert match == "app-linux-amd64.tar.gz"
    assert candidates is None
    assert error is None

    # Test chain that narrows down but then has multiple matches
    chain_fn = chain_detectors(
        detectors=[detect_single_asset("app")],
        system=system_detector_fn,
    )
    assets = [
        "app-linux-amd64.tar.gz",
        "app-linux-x86_64.tar.gz",
        "other-linux-amd64.tar.gz",
    ]
    match, candidates, error = chain_fn(assets)
    assert match == ""
    assert candidates == ["app-linux-amd64.tar.gz", "app-linux-x86_64.tar.gz"]
    assert error == "2 candidates found for asset chain"

    # Test chain with error in first detector
    chain_fn = chain_detectors(
        detectors=[detect_single_asset("missing")],
        system=system_detector_fn,
    )
    assets = ["app-linux-amd64.tar.gz", "other-linux-amd64.tar.gz"]
    match, candidates, error = chain_fn(assets)
    assert match == ""
    assert candidates is None
    assert error == "asset `missing` not found"
