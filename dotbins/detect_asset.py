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
    priority: Pattern | None = None


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
    priority=re.compile(r"\.appimage$"),
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
    "amd64": ArchAMD64,
    "386": ArchI386,
    "arm": ArchArm,
    "arm64": ArchArm64,
    "aarch64": ArchArm64,  # alias for arm64
    "riscv64": ArchRiscv64,
}


def _match_os(os_obj: _OS, asset: str) -> tuple[bool, bool]:
    """Match returns true if the asset name matches the OS. Also returns if this is a priority match."""
    if os_obj.anti is not None and os_obj.anti.search(asset):
        return False, False
    if os_obj.priority is not None:
        main_match = os_obj.regex.search(asset) is not None
        priority_match = os_obj.priority.search(asset) is not None
        return main_match, main_match and priority_match
    return os_obj.regex.search(asset) is not None, False


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


def _detect_system(os_obj: _OS, arch: _Arch) -> DetectFunc:
    """Returns a function that detects based on OS and architecture."""

    def detector(assets: Assets) -> DetectResult:  # noqa: PLR0911
        priority = []
        matches = []
        candidates = []
        all_assets = []

        for a in assets:
            if a.endswith((".sha256", ".sha256sum", ".deb")):
                continue

            os_match, extra = _match_os(os_obj, a)
            if extra:
                priority.append(a)

            arch_match = _match_arch(arch, a)
            if os_match and arch_match:
                matches.append(a)

            if os_match:
                candidates.append(a)

            all_assets.append(a)

        candidates = sorted(candidates)
        matches = sorted(matches)
        priority = sorted(priority)

        if len(priority) == 1:
            return priority[0], None, None
        if len(priority) > 1:
            return "", priority, f"{len(priority)} priority matches found"
        if len(matches) == 1:
            return matches[0], None, None
        if len(matches) > 1:
            return "", matches, f"{len(matches)} matches found"
        if len(candidates) == 1:
            return candidates[0], None, None
        if len(candidates) > 1:
            return ("", candidates, f"{len(candidates)} candidates found (unsure architecture)")
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
