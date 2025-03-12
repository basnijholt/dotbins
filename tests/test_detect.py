from dotbins.detect import (
    AllDetector,
    ArchAMD64,
    ArchArm,
    ArchArm64,
    ArchI386,
    ArchRiscv64,
    DetectorChain,
    OSDarwin,
    OSLinux,
    SingleAssetDetector,
    SystemDetector,
)


def test_os_match() -> None:
    """Test the OSDetector.match method."""
    # Test basic OS matching
    assert OSDarwin.match("darwin-amd64.tar.gz") == (True, False)
    assert OSDarwin.match("macos-amd64.tar.gz") == (True, False)
    assert OSDarwin.match("osx-amd64.tar.gz") == (True, False)
    assert OSDarwin.match("linux-amd64.tar.gz") == (False, False)

    # Test with anti-pattern
    assert OSLinux.match("linux-amd64.tar.gz") == (True, False)
    assert OSLinux.match("ubuntu-amd64.tar.gz") == (True, False)
    assert OSLinux.match("android-amd64.tar.gz") == (False, False)

    # Test with priority pattern
    assert OSLinux.match("app.appimage") == (False, False)  # No Linux in name
    assert OSLinux.match("linux-app.appimage") == (True, True)


def test_arch_match() -> None:
    """Test the ArchDetector.match method."""
    # Test basic arch matching
    assert ArchAMD64.match("linux-amd64.tar.gz")
    assert ArchAMD64.match("linux-x86_64.tar.gz")
    assert ArchAMD64.match("linux-x64.tar.gz")
    assert not ArchAMD64.match("linux-386.tar.gz")

    assert ArchI386.match("linux-i386.tar.gz")
    assert ArchI386.match("linux-386.tar.gz")
    assert ArchI386.match("linux-x86_32.tar.gz")
    assert not ArchI386.match("linux-amd64.tar.gz")

    assert ArchArm.match("linux-arm.tar.gz")
    assert ArchArm.match("linux-armv6.tar.gz")
    assert ArchArm.match("linux-arm32.tar.gz")
    assert not ArchArm.match("linux-amd64.tar.gz")

    assert ArchArm64.match("linux-arm64.tar.gz")
    assert ArchArm64.match("linux-aarch64.tar.gz")
    assert ArchArm64.match("linux-armv8.tar.gz")
    assert not ArchArm64.match("linux-amd64.tar.gz")

    assert ArchRiscv64.match("linux-riscv64.tar.gz")
    assert not ArchRiscv64.match("linux-amd64.tar.gz")


def test_all_detector_detect() -> None:
    """Test the AllDetector.detect method."""
    detector = AllDetector()

    # Single asset
    match, candidates, error = detector.detect(["app.tar.gz"])
    assert match == "app.tar.gz"
    assert candidates is None
    assert error is None

    # Multiple assets
    match, candidates, error = detector.detect(["app1.tar.gz", "app2.tar.gz"])
    assert match == ""
    assert candidates == ["app1.tar.gz", "app2.tar.gz"]
    assert error == "2 matches found"


def test_single_asset_detector_detect() -> None:
    """Test the SingleAssetDetector.detect method."""
    # Test exact match
    detector = SingleAssetDetector("app.tar.gz")
    match, candidates, error = detector.detect(["app.tar.gz", "other.tar.gz"])
    assert match == "app.tar.gz"
    assert candidates is None
    assert error is None

    # Test partial match
    detector = SingleAssetDetector("app")
    match, candidates, error = detector.detect(["app.tar.gz", "other.tar.gz"])
    assert match == "app.tar.gz"
    assert candidates is None
    assert error is None

    # Test multiple matches
    detector = SingleAssetDetector("app")
    match, candidates, error = detector.detect(["app.tar.gz", "app.zip"])
    assert match == ""
    assert candidates == ["app.tar.gz", "app.zip"]
    assert error == "2 candidates found for asset `app`"

    # Test no matches
    detector = SingleAssetDetector("app")
    match, candidates, error = detector.detect(["other.tar.gz", "another.zip"])
    assert match == ""
    assert candidates is None
    assert error == "asset `app` not found"

    # Test anti mode
    detector = SingleAssetDetector("app", anti=True)
    match, candidates, error = detector.detect(["app.tar.gz", "other.tar.gz"])
    assert match == "other.tar.gz"
    assert candidates is None
    assert error is None

    # Test anti mode with multiple matches
    detector = SingleAssetDetector("app", anti=True)
    match, candidates, error = detector.detect(
        ["app.tar.gz", "other1.tar.gz", "other2.tar.gz"],
    )
    assert match == ""
    assert candidates == ["other1.tar.gz", "other2.tar.gz"]
    assert error == "2 candidates found for asset `app`"


def test_system_detector_new_system_detector() -> None:
    """Test the SystemDetector.new_system_detector method."""
    # Valid OS and arch
    detector, error = SystemDetector.new_system_detector("linux", "amd64")
    assert detector is not None
    assert error is None
    assert detector.os == OSLinux
    assert detector.arch == ArchAMD64

    # Invalid OS
    detector, error = SystemDetector.new_system_detector("invalid", "amd64")
    assert detector is None
    assert error == "unsupported target OS: invalid"

    # Invalid arch
    detector, error = SystemDetector.new_system_detector("linux", "invalid")
    assert detector is None
    assert error == "unsupported target arch: invalid"


def test_system_detector_detect() -> None:
    """Test the SystemDetector.detect method."""
    detector = SystemDetector(OSLinux, ArchAMD64)

    # Perfect match
    assets = [
        "app-linux-amd64.tar.gz",
        "app-darwin-amd64.tar.gz",
        "app-windows-amd64.exe",
    ]
    match, candidates, error = detector.detect(assets)
    assert match == "app-linux-amd64.tar.gz"
    assert candidates is None
    assert error is None

    # Multiple perfect matches
    assets = [
        "app-linux-amd64.tar.gz",
        "app-linux-x86_64.tar.gz",
        "app-darwin-amd64.tar.gz",
    ]
    match, candidates, error = detector.detect(assets)
    assert match == ""
    assert candidates == ["app-linux-amd64.tar.gz", "app-linux-x86_64.tar.gz"]
    assert error == "2 matches found"

    # OS match but no arch match
    assets = ["app-linux-arm64.tar.gz", "app-darwin-amd64.tar.gz"]
    match, candidates, error = detector.detect(assets)
    assert match == "app-linux-arm64.tar.gz"
    assert candidates is None
    assert error is None

    # Multiple OS matches but no arch match
    assets = [
        "app-linux-arm64.tar.gz",
        "app-linux-arm.tar.gz",
        "app-darwin-amd64.tar.gz",
    ]
    match, candidates, error = detector.detect(assets)
    assert match == ""
    assert candidates == ["app-linux-arm64.tar.gz", "app-linux-arm.tar.gz"]
    assert error == "2 candidates found (unsure architecture)"

    # No OS or arch match
    assets = ["app-darwin-arm64.tar.gz", "app-windows-386.exe"]
    match, candidates, error = detector.detect(assets)
    assert match == ""
    assert candidates == ["app-darwin-arm64.tar.gz", "app-windows-386.exe"]
    assert error == "no candidates found"

    # Priority match
    assets = ["app-linux-amd64.tar.gz", "app-linux.appimage"]
    match, candidates, error = detector.detect(assets)
    assert match == "app-linux.appimage"
    assert candidates is None
    assert error is None

    # Multiple priority matches
    assets = [
        "app1-linux.appimage",
        "app2-linux.appimage",
    ]
    match, candidates, error = detector.detect(assets)
    assert match == ""
    assert candidates == ["app1-linux.appimage", "app2-linux.appimage"]
    assert error == "2 priority matches found"

    # Skip checksum files
    assets = [
        "app-linux-amd64.tar.gz",
        "app-linux-amd64.tar.gz.sha256",
        "app-darwin-amd64.tar.gz",
    ]
    match, candidates, error = detector.detect(assets)
    assert match == "app-linux-amd64.tar.gz"
    assert candidates is None
    assert error is None


def test_detector_chain_detect() -> None:
    """Test the DetectorChain.detect method."""
    # Set up a chain of detectors
    system_detector, _ = SystemDetector.new_system_detector("linux", "amd64")
    asset_detector = SingleAssetDetector("app")
    AllDetector()

    chain = DetectorChain(detectors=[asset_detector], system=system_detector)

    # Test successful chain
    assets = [
        "app-linux-amd64.tar.gz",
        "app-darwin-amd64.tar.gz",
        "other-linux-amd64.tar.gz",
    ]
    match, candidates, error = chain.detect(assets)
    assert match == "app-linux-amd64.tar.gz"
    assert candidates is None
    assert error is None

    # Test chain that narrows down but then has multiple matches
    chain = DetectorChain(
        detectors=[SingleAssetDetector("app")],
        system=system_detector,
    )
    assets = [
        "app-linux-amd64.tar.gz",
        "app-linux-x86_64.tar.gz",
        "other-linux-amd64.tar.gz",
    ]
    match, candidates, error = chain.detect(assets)
    assert match == ""
    assert candidates == ["app-linux-amd64.tar.gz", "app-linux-x86_64.tar.gz"]
    assert error == "2 candidates found for asset chain"

    # Test chain with error in first detector
    chain = DetectorChain(
        detectors=[SingleAssetDetector("missing")],
        system=system_detector,
    )
    assets = ["app-linux-amd64.tar.gz", "other-linux-amd64.tar.gz"]
    match, candidates, error = chain.detect(assets)
    assert match == ""
    assert candidates is None
    assert error == "asset `missing` not found"
