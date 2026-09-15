"""Every profile under one directory, re-read when its file changes.

A deployment adds a vendor by dropping a file into `profiles/`, and the next document
is matched against it — without restarting anything (ADR-0008). The registry therefore
caches by modification time rather than forever: a cached profile is returned only while
its own file and the shared defaults are untouched.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from invoice_extractor.profile.loader import DEFAULTS_ID, PROFILES_ROOT, load_profile
from invoice_extractor.profile.schema import Profile, ProfileError


@dataclass(frozen=True, slots=True)
class _Cached:
    """One profile and the modification times that were true when it was read."""

    profile: Profile
    stamps: tuple[float, float]


class ProfileRegistry:
    """The profiles a deployment has. Construct one per run, not one per document."""

    def __init__(self, root: Path = PROFILES_ROOT) -> None:
        """Raises `ProfileError` where `root` is not a directory of vendor profiles.

        Refusing here is the point. A registry pointed at a directory that does not exist
        would list no vendors, match no document, and report every one of them as
        `profile_not_detected` — which is the same answer a real unrecognised invoice
        gets. A caller would have no way of telling a misconfigured deployment from a
        vendor nobody has described yet, and the misconfiguration is the likelier of the
        two. So a missing directory, or one with no shared defaults in it, says so now.

        An existing directory holding no vendors *is* allowed: a deployment that adds its
        first profile while running is what `ADR-0008` and the mtime cache are for.
        """
        _readable(root)
        self._root = root
        self._cache: dict[str, _Cached] = {}

    @property
    def root(self) -> Path:
        return self._root

    def ids(self) -> tuple[str, ...]:
        """Every profile id under the root, in name order. The defaults are not a profile."""
        return tuple(
            sorted(path.stem for path in self._root.glob("*.json") if path.stem != DEFAULTS_ID)
        )

    def get(self, profile_id: str) -> Profile:
        """The profile, read again if its file or the shared defaults have changed since."""
        stamps = self._stamps(profile_id)
        cached = self._cache.get(profile_id)
        if cached is not None and cached.stamps == stamps:
            return cached.profile
        profile = load_profile(profile_id, self._root)
        self._cache[profile_id] = _Cached(profile=profile, stamps=stamps)
        return profile

    def all(self) -> Sequence[Profile]:
        """Every profile the root holds, in id order."""
        return tuple(self.get(profile_id) for profile_id in self.ids())

    def _stamps(self, profile_id: str) -> tuple[float, float]:
        return (self._mtime(f"{profile_id}.json"), self._mtime(f"{DEFAULTS_ID}.json"))

    def _mtime(self, name: str) -> float:
        path = self._root / name
        try:
            return path.stat().st_mtime_ns / 1e9
        except OSError as missing:
            raise ProfileError(f"no profile at {path}") from missing


def _readable(root: Path) -> None:
    """A directory, with the defaults every vendor is laid over. Otherwise, why."""
    if not root.is_dir():
        raise ProfileError(f"no profile directory at {root}")
    if not (root / f"{DEFAULTS_ID}.json").is_file():
        raise ProfileError(f"{root} holds no {DEFAULTS_ID}.json, so no profile can be read")
