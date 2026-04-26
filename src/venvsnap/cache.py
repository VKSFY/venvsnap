"""Wheel cache, keyed by sha256."""

from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path


def _default_cache_root() -> Path:
    return Path.home() / ".venvsnap" / "cache"


@dataclass
class CacheStats:
    wheel_count: int
    total_bytes: int

    @property
    def human_size(self) -> str:
        return _format_bytes(self.total_bytes)


class Cache:
    """Wheels at ``<root>/wheels/<aa>/<sha256>/<filename>.whl``.

    The two-char bucket keeps directories shallow on case-insensitive
    filesystems.
    """

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or _default_cache_root()
        self.wheels_dir = self.root / "wheels"

    def wheel_path(self, sha256: str, filename: str) -> Path:
        if len(sha256) < 2:
            raise ValueError("sha256 must be a hex digest")
        return self.wheels_dir / sha256[:2] / sha256 / filename

    def has(self, sha256: str, filename: str) -> bool:
        return self.wheel_path(sha256, filename).is_file()

    def store(self, content: bytes, sha256: str, filename: str) -> Path:
        actual = hashlib.sha256(content).hexdigest()
        if actual != sha256:
            raise ValueError(f"hash mismatch for {filename}: expected {sha256}, got {actual}")
        path = self.wheel_path(sha256, filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".part")
        tmp.write_bytes(content)
        tmp.replace(path)
        return path

    def stats(self) -> CacheStats:
        if not self.wheels_dir.exists():
            return CacheStats(wheel_count=0, total_bytes=0)
        count = 0
        total = 0
        for whl in self.wheels_dir.rglob("*.whl"):
            count += 1
            total += whl.stat().st_size
        return CacheStats(wheel_count=count, total_bytes=total)

    def clean(self) -> CacheStats:
        stats = self.stats()
        if self.wheels_dir.exists():
            shutil.rmtree(self.wheels_dir)
        return stats


def _format_bytes(n: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(n)
    unit_idx = 0
    while size >= 1024 and unit_idx < len(units) - 1:
        size /= 1024
        unit_idx += 1
    if unit_idx == 0:
        return f"{int(size)} {units[unit_idx]}"
    return f"{size:.2f} {units[unit_idx]}"
