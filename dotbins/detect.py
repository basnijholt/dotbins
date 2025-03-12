"""Detectors are used to select an asset from a list of possibilities."""

from __future__ import annotations

import os.path
import re
from dataclasses import dataclass
from re import Pattern


class Detector:
    """A Detector selects an asset from a list of possibilities."""

    def detect(self, assets: list[str]) -> tuple[str, list[str] | None, str | None]:
        """Takes a list of possible assets and returns a direct match.
        If a single direct match is not found, it returns a list of candidates
        and an error message explaining what happened.

        Returns:
            tuple: (match, candidates, error)

        """  # noqa: D205
        msg = "Subclasses must implement detect()"
        raise NotImplementedError(msg)


@dataclass
class DetectorChain(Detector):
    """A DetectorChain is a list of detectors that are used to select an asset from a list of possibilities."""

    detectors: list[Detector]
    system: Detector

    def detect(self, assets: list[str]) -> tuple[str, list[str] | None, str | None]:
        """Detect an asset from a list of assets."""
        for d in self.detectors:
            choice, candidates, err = d.detect(assets)
            if len(candidates or []) == 0 and err is not None:
                return "", None, err
            if len(candidates or []) == 0:
                return choice, None, None
            if candidates is not None:
                assets = candidates

        choice, candidates, err = self.system.detect(assets)
        if len(candidates or []) == 0 and err is not None:
            return "", None, err
        if len(candidates or []) == 0:
            return choice, None, None
        if candidates is not None and len(candidates) >= 1:
            assets = candidates

        return "", assets, f"{len(assets)} candidates found for asset chain"


@dataclass
class OS:
    """An OS represents a target operating system."""

    name: str
    regex: Pattern
    anti: Pattern | None = None
    priority: Pattern | None = None

    def match(self, s: str) -> tuple[bool, bool]:
        """Match returns true if the given archive name is likely to store a binary for
        this OS. Also returns if this is a priority match.
        """  # noqa: D205
        if self.anti is not None and self.anti.search(s):
            return False, False
        if self.priority is not None:
            # The first value should be True for the priority to apply
            main_match = self.regex.search(s) is not None
            priority_match = self.priority.search(s) is not None
            return main_match, main_match and priority_match
        return self.regex.search(s) is not None, False


@dataclass
class Arch:
    """An Arch represents a system architecture, such as amd64, i386, arm or others."""

    name: str
    regex: Pattern

    def match(self, s: str) -> bool:
        """Returns True if the architecture matches the given string."""
        return bool(self.regex.search(s))


# Define OS constants
OSDarwin = OS(name="darwin", regex=re.compile(r"(?i)(darwin|mac.?(os)?|osx)"))
OSWindows = OS(name="windows", regex=re.compile(r"(?i)([^r]win|windows)"))
OSLinux = OS(
    name="linux",
    regex=re.compile(r"(?i)(linux|ubuntu)"),
    anti=re.compile(r"(?i)(android)"),
    priority=re.compile(r"\.appimage$"),
)
OSNetBSD = OS(name="netbsd", regex=re.compile(r"(?i)(netbsd)"))
OSFreeBSD = OS(name="freebsd", regex=re.compile(r"(?i)(freebsd)"))
OSOpenBSD = OS(name="openbsd", regex=re.compile(r"(?i)(openbsd)"))
OSAndroid = OS(name="android", regex=re.compile(r"(?i)(android)"))
OSIllumos = OS(name="illumos", regex=re.compile(r"(?i)(illumos)"))
OSSolaris = OS(name="solaris", regex=re.compile(r"(?i)(solaris)"))
OSPlan9 = OS(name="plan9", regex=re.compile(r"(?i)(plan9)"))

mapping: dict[str, OS] = {
    "darwin": OSDarwin,
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
ArchAMD64 = Arch(name="amd64", regex=re.compile(r"(?i)(x64|amd64|x86(-|_)?64)"))
ArchI386 = Arch(name="386", regex=re.compile(r"(?i)(x32|amd32|x86(-|_)?32|i?386)"))
ArchArm = Arch(name="arm", regex=re.compile(r"(?i)(arm32|armv6|arm\b)"))
ArchArm64 = Arch(name="arm64", regex=re.compile(r"(?i)(arm64|armv8|aarch64)"))
ArchRiscv64 = Arch(name="riscv64", regex=re.compile(r"(?i)(riscv64)"))

# a map from GOARCH values to internal architecture matchers
archmapping: dict[str, Arch] = {
    "amd64": ArchAMD64,
    "386": ArchI386,
    "arm": ArchArm,
    "arm64": ArchArm64,
    "riscv64": ArchRiscv64,
}


@dataclass
class AllDetector(Detector):
    """A detector that matches any asset."""

    def detect(self, assets: list[str]) -> tuple[str, list[str] | None, str | None]:
        """Detect any asset from a list of assets."""
        if len(assets) == 1:
            return assets[0], None, None
        return "", assets, f"{len(assets)} matches found"


@dataclass
class SingleAssetDetector(Detector):
    """A detector that matches a single asset."""

    asset: str
    anti: bool = False

    def detect(self, assets: list[str]) -> tuple[str, list[str] | None, str | None]:
        """Detect a single asset from a list of assets."""
        candidates = []
        for a in assets:
            if not self.anti and os.path.basename(a) == self.asset:
                return a, None, None
            if not self.anti and self.asset in os.path.basename(a):
                candidates.append(a)
            if self.anti and self.asset not in os.path.basename(a):
                candidates.append(a)

        if len(candidates) == 1:
            return candidates[0], None, None
        if len(candidates) > 1:
            return (
                "",
                candidates,
                f"{len(candidates)} candidates found for asset `{self.asset}`",
            )
        return "", None, f"asset `{self.asset}` not found"


@dataclass
class SystemDetector(Detector):
    """A detector that matches an OS and architecture."""

    os: OS
    arch: Arch

    @classmethod
    def new_system_detector(
        cls,
        sos: str,
        sarch: str,
    ) -> tuple[SystemDetector | None, str | None]:
        """Create a new system detector for a given OS and architecture."""
        if sos not in mapping:
            return None, f"unsupported target OS: {sos}"
        if sarch not in archmapping:
            return None, f"unsupported target arch: {sarch}"
        return cls(mapping[sos], archmapping[sarch]), None

    def detect(  # noqa: PLR0911
        self,
        assets: list[str],
    ) -> tuple[str, list[str] | None, str | None]:
        """Detect an asset from a list of assets."""
        priority = []
        matches = []
        candidates = []
        all_assets = []

        for a in assets:
            if a.endswith((".sha256", ".sha256sum")):
                # skip checksums (they will be checked later by the verifier)
                continue

            os_match, extra = self.os.match(a)
            if extra:
                priority.append(a)

            arch_match = self.arch.match(a)
            if os_match and arch_match:
                matches.append(a)

            if os_match:
                candidates.append(a)

            all_assets.append(a)

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
            return (
                "",
                candidates,
                f"{len(candidates)} candidates found (unsure architecture)",
            )
        if len(all_assets) == 1:
            return all_assets[0], None, None

        return "", all_assets, "no candidates found"
