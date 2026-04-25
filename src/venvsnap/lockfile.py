"""Read and write venvsnap lockfiles."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import tomli_w

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

LOCKFILE_VERSION = 1
DEFAULT_LOCKFILE_NAME = "venvsnap.lock"


class LockfileError(Exception):
    """Raised when a lockfile is malformed or incompatible."""


@dataclass
class LockedPackage:
    name: str
    version: str
    sha256: str
    wheel_filename: str
    wheel_url: str
    requires_python: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "name": self.name,
            "version": self.version,
            "sha256": self.sha256,
            "wheel_filename": self.wheel_filename,
            "wheel_url": self.wheel_url,
        }
        if self.requires_python:
            d["requires_python"] = self.requires_python
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> LockedPackage:
        try:
            return cls(
                name=d["name"],
                version=d["version"],
                sha256=d["sha256"],
                wheel_filename=d["wheel_filename"],
                wheel_url=d["wheel_url"],
                requires_python=d.get("requires_python"),
            )
        except KeyError as exc:
            raise LockfileError(f"package entry missing field: {exc.args[0]}") from exc


@dataclass
class Lockfile:
    python_version: str
    platform: str
    packages: list[LockedPackage] = field(default_factory=list)
    version: int = LOCKFILE_VERSION
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )

    def to_toml(self) -> str:
        data: dict[str, Any] = {
            "version": self.version,
            "python_version": self.python_version,
            "platform": self.platform,
            "created_at": self.created_at,
            "package": [p.to_dict() for p in self.packages],
        }
        return tomli_w.dumps(data)

    @classmethod
    def from_toml(cls, text: str) -> Lockfile:
        try:
            data = tomllib.loads(text)
        except tomllib.TOMLDecodeError as exc:
            raise LockfileError(f"invalid TOML: {exc}") from exc

        version = data.get("version")
        if version != LOCKFILE_VERSION:
            raise LockfileError(
                f"unsupported lockfile version {version!r} (expected {LOCKFILE_VERSION})"
            )

        try:
            packages = [LockedPackage.from_dict(p) for p in data.get("package", [])]
            return cls(
                version=version,
                python_version=data["python_version"],
                platform=data["platform"],
                created_at=data.get(
                    "created_at",
                    datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                ),
                packages=packages,
            )
        except KeyError as exc:
            raise LockfileError(f"lockfile missing field: {exc.args[0]}") from exc

    def save(self, path: Path) -> None:
        path.write_text(self.to_toml(), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> Lockfile:
        if not path.exists():
            raise LockfileError(f"lockfile not found: {path}")
        return cls.from_toml(path.read_text(encoding="utf-8"))
