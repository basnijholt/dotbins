"""Detectors are used to select an asset from a list of possibilities."""

from __future__ import annotations

import os.path
import re
import sys
from re import Pattern
from typing import Callable, NamedTuple, Optional

if sys.version_info >= (3, 10):
    from typing import TypeAlias
else:  # pragma: no cover
    from typing_extensions import TypeAlias

Asset: TypeAlias = str
Assets: TypeAlias = list[str]
DetectResult: TypeAlias = tuple[
    Asset,
    Optional[Assets],  # candidates
    Optional[str],  # error
]
DetectFunc: TypeAlias = Callable[[Assets], DetectResult]


class _OS(NamedTuple):
    """An OS represents a target operating system."""

    name: str
    regex: Pattern
    anti: Pattern | None = None


class _Arch(NamedTuple):
    """An Arch represents a system architecture, such as amd64, i386, arm or others."""

    name: str
    regex: Pattern


# Define OS constants
OSDarwin = _OS(name="darwin", regex=re.compile(r"(?i)(darwin|mac.?(os)?|osx)"))
OSWindows = _OS(name="windows", regex=re.compile(r"(?i)([^r]win|windows)"))
OSLinux = _OS(
    name="linux",
    regex=re.compile(r"(?i)(linux|ubuntu)"),
    anti=re.compile(r"(?i)(android)"),
)
OSNetBSD = _OS(name="netbsd", regex=re.compile(r"(?i)(netbsd)"))
OSFreeBSD = _OS(name="freebsd", regex=re.compile(r"(?i)(freebsd)"))
OSOpenBSD = _OS(name="openbsd", regex=re.compile(r"(?i)(openbsd)"))
OSAndroid = _OS(name="android", regex=re.compile(r"(?i)(android)"))
OSIllumos = _OS(name="illumos", regex=re.compile(r"(?i)(illumos)"))
OSSolaris = _OS(name="solaris", regex=re.compile(r"(?i)(solaris)"))
OSPlan9 = _OS(name="plan9", regex=re.compile(r"(?i)(plan9)"))

# Define OS mapping
os_mapping: dict[str, _OS] = {
    "darwin": OSDarwin,
    "macos": OSDarwin,  # alias for darwin
    "windows": OSWindows,
    "linux": OSLinux,
    "netbsd": OSNetBSD,
    "openbsd": OSOpenBSD,
    "freebsd": OSFreeBSD,
    "android": OSAndroid,
    "illumos": OSIllumos,
    "solaris": OSSolaris,
    "plan9": OSPlan9,
}

# Define Arch constants
ArchAMD64 = _Arch(name="amd64", regex=re.compile(r"(?i)(x64|amd64|x86(-|_)?64)"))
ArchI386 = _Arch(name="386", regex=re.compile(r"(?i)(x32|amd32|x86(-|_)?32|i?386)"))
ArchArm = _Arch(name="arm", regex=re.compile(r"(?i)(arm32|armv6|arm\b)"))
ArchArm64 = _Arch(name="arm64", regex=re.compile(r"(?i)(arm64|armv8|aarch64)"))
ArchRiscv64 = _Arch(name="riscv64", regex=re.compile(r"(?i)(riscv64)"))

# Define Arch mapping
arch_mapping: dict[str, _Arch] = {
    "amd64": ArchAMD64,  # 64-bit (2000s-now)
    "386": ArchI386,  # 32-bit (1980s-2000s)
    "arm": ArchArm,  # 32-bit (1990s-2010s)
    "arm64": ArchArm64,  # 64-bit (2010s-now)
    "aarch64": ArchArm64,  # alias for arm64 (2010s-now)
    "riscv64": ArchRiscv64,  # 64-bit (2010s-now)
}


def _match_os(os_obj: _OS, asset: str) -> bool:
    """Match returns true if the asset name matches the OS."""
    if os_obj.anti is not None and os_obj.anti.search(asset):
        return False
    return os_obj.regex.search(asset) is not None


def _match_arch(arch: _Arch, asset: str) -> bool:
    """Returns True if the architecture matches the given string."""
    return bool(arch.regex.search(asset))


def detect_single_asset(asset: str, anti: bool = False) -> DetectFunc:
    """Returns a function that detects a single asset."""

    def detector(assets: Assets) -> DetectResult:
        candidates = []
        for a in assets:
            if not anti and os.path.basename(a) == asset:
                return a, None, None
            if not anti and asset in os.path.basename(a):
                candidates.append(a)
            if anti and asset not in os.path.basename(a):
                candidates.append(a)

        if len(candidates) == 1:
            return candidates[0], None, None
        if len(candidates) > 1:
            return (
                "",
                candidates,
                f"{len(candidates)} candidates found for asset `{asset}`",
            )
        return "", None, f"asset `{asset}` not found"

    return detector


def _prioritize_assets(assets: Assets, os_name: str) -> Assets:
    """Prioritize assets based on predefined rules.

    Priority order:
    1. For Linux: .appimage files
    2. Files with no extension
    3. Archive files (.tar.gz, .tgz, .zip, etc.)
    4. Others
    5. Package formats (.deb, .rpm, .apk, etc.) - lowest priority
    """
    # Sort assets into priority groups
    appimages = []
    no_extension = []
    archives = []
    package_formats = []
    others = []

    # Known package formats to deprioritize (lowest priority)
    package_exts = {".deb", ".rpm", ".apk", ".pkg"}

    # Known archive formats to prioritize (high priority)
    archive_exts = {".tar.gz", ".tgz", ".zip", ".tar.bz2", ".tbz2", ".tar.xz", ".txz", ".7z", ".tar"}

    # These extensions should be ignored when considering if a file is an archive
    ignored_exts = {".sig", ".sha256", ".sha256sum", ".sbom", ".pem"}

    for asset in assets:
        basename = os.path.basename(asset)
        lower_basename = basename.lower()

        # Skip signature, checksum files, and other metadata
        if any(lower_basename.endswith(ext) for ext in ignored_exts):
            continue

        # Check if it's a Linux AppImage (highest priority for Linux)
        if os_name == "linux" and lower_basename.endswith(".appimage"):
            appimages.append(asset)
            continue

        # Check if it has no extension
        if "." not in basename or basename.rindex(".") == 0:
            no_extension.append(asset)
            continue

        # Check if it's an archive format (high priority)
        if any(lower_basename.endswith(ext) for ext in archive_exts):
            archives.append(asset)
            continue

        # Check if it's a package format (lowest priority)
        if any(lower_basename.endswith(ext) for ext in package_exts):
            package_formats.append(asset)
            continue

        # Everything else goes here
        others.append(asset)

    # Return assets in priority order - package formats have lowest priority
    return appimages + no_extension + archives + others + package_formats


def _detect_system(os_obj: _OS, arch: _Arch) -> DetectFunc:
    """Returns a function that detects based on OS and architecture."""

    def detector(assets: Assets) -> DetectResult:
        matches = []
        candidates = []
        all_assets = []

        for a in assets:
            if a.endswith((".sha256", ".sha256sum")):
                continue

            os_match = _match_os(os_obj, a)
            arch_match = _match_arch(arch, a)

            # Track OS+Arch matches specifically - highest priority
            if os_match and arch_match:
                matches.append(a)

            # Still track other matches for fallback
            if os_match:
                candidates.append(a)

            all_assets.append(a)

        # Apply prioritization when multiple matches are found
        if len(matches) > 0:
            prioritized = _prioritize_assets(matches, os_obj.name)
            if len(prioritized) == 1:
                return prioritized[0], None, None
            return "", prioritized, f"{len(prioritized)} arch matches found"

        # Fallbacks when no exact arch match is found
        if len(candidates) == 1:
            return candidates[0], None, None
        if len(candidates) > 1:
            prioritized = _prioritize_assets(candidates, os_obj.name)
            return ("", prioritized, f"{len(prioritized)} candidates found (unsure architecture)")
        if len(all_assets) == 1:
            return all_assets[0], None, None

        return "", all_assets, "no candidates found"

    return detector


def create_system_detector(
    os_name: str,
    arch_name: str,
) -> DetectFunc:
    """Create a OS detector function for a given OS and architecture."""
    if os_name not in os_mapping:
        msg = f"unsupported target OS: {os_name}"
        raise ValueError(msg)
    if arch_name not in arch_mapping:
        msg = f"unsupported target arch: {arch_name}"
        raise ValueError(msg)
    return _detect_system(os_mapping[os_name], arch_mapping[arch_name])
