"""Restore a virtual environment from a lockfile."""

from __future__ import annotations

import hashlib
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import httpx

from venvsnap.cache import Cache
from venvsnap.lockfile import LockedPackage, Lockfile
from venvsnap.venv_utils import VenvError, create_venv, is_venv, venv_python


class RestoreError(Exception):
    pass


@dataclass
class RestoreResult:
    venv_path: Path
    installed: list[str]
    cache_hits: int
    cache_misses: int
    bytes_downloaded: int
    seconds_download: float = 0.0
    seconds_install: float = 0.0
    failed: list[tuple[str, str]] = field(default_factory=list)

    @property
    def total_packages(self) -> int:
        return len(self.installed)


def restore(
    lockfile: Lockfile,
    venv_path: Path,
    *,
    cache: Cache | None = None,
    workers: int = 8,
    progress: Callable[[str, str, str], None] | None = None,
) -> RestoreResult:
    """Install every wheel from ``lockfile`` into ``venv_path``."""
    cache = cache or Cache()
    cache.wheels_dir.mkdir(parents=True, exist_ok=True)

    if not lockfile.packages:
        if not is_venv(venv_path):
            create_venv(venv_path)
        return RestoreResult(
            venv_path=venv_path,
            installed=[],
            cache_hits=0,
            cache_misses=0,
            bytes_downloaded=0,
        )

    download_start = time.perf_counter()
    bytes_downloaded, hits, misses, failed = _ensure_wheels_cached(
        lockfile.packages, cache, workers=workers, progress=progress
    )
    download_elapsed = time.perf_counter() - download_start

    if failed:
        return RestoreResult(
            venv_path=venv_path,
            installed=[],
            cache_hits=hits,
            cache_misses=misses,
            bytes_downloaded=bytes_downloaded,
            seconds_download=download_elapsed,
            failed=failed,
        )

    if not is_venv(venv_path):
        try:
            create_venv(venv_path)
        except VenvError as exc:
            raise RestoreError(str(exc)) from exc

    install_start = time.perf_counter()
    _pip_install_local(venv_path, lockfile.packages, cache)
    install_elapsed = time.perf_counter() - install_start

    return RestoreResult(
        venv_path=venv_path,
        installed=[f"{p.name}=={p.version}" for p in lockfile.packages],
        cache_hits=hits,
        cache_misses=misses,
        bytes_downloaded=bytes_downloaded,
        seconds_download=download_elapsed,
        seconds_install=install_elapsed,
    )


def _ensure_wheels_cached(
    packages: list[LockedPackage],
    cache: Cache,
    *,
    workers: int,
    progress: Callable[[str, str, str], None] | None,
) -> tuple[int, int, int, list[tuple[str, str]]]:
    hits = 0
    misses = 0
    bytes_downloaded = 0
    failed: list[tuple[str, str]] = []
    to_download: list[LockedPackage] = []

    for pkg in packages:
        if cache.has(pkg.sha256, pkg.wheel_filename):
            hits += 1
            if progress:
                progress(pkg.name, pkg.version, "hit")
        else:
            misses += 1
            to_download.append(pkg)

    if not to_download:
        return bytes_downloaded, hits, misses, failed

    with (
        httpx.Client(follow_redirects=True, timeout=60.0) as client,
        ThreadPoolExecutor(max_workers=workers) as pool,
    ):
        futures = {
            pool.submit(_download_one, client, cache, pkg, progress): pkg for pkg in to_download
        }
        for fut in as_completed(futures):
            pkg = futures[fut]
            try:
                bytes_downloaded += fut.result()
            except Exception as exc:
                failed.append((f"{pkg.name}=={pkg.version}", str(exc)))
                if progress:
                    progress(pkg.name, pkg.version, f"failed: {exc}")

    return bytes_downloaded, hits, misses, failed


def _download_one(
    client: httpx.Client,
    cache: Cache,
    pkg: LockedPackage,
    progress: Callable[[str, str, str], None] | None,
) -> int:
    if progress:
        progress(pkg.name, pkg.version, "downloading")
    resp = client.get(pkg.wheel_url)
    resp.raise_for_status()
    content = resp.content
    actual = hashlib.sha256(content).hexdigest()
    if actual != pkg.sha256:
        raise RestoreError(
            f"hash mismatch for {pkg.wheel_filename}: "
            f"expected {pkg.sha256[:12]}…, got {actual[:12]}…"
        )
    cache.store(content, pkg.sha256, pkg.wheel_filename)
    if progress:
        progress(pkg.name, pkg.version, "downloaded")
    return len(content)


def _pip_install_local(venv_path: Path, packages: list[LockedPackage], cache: Cache) -> None:
    py = venv_python(venv_path)
    wheels = [str(cache.wheel_path(p.sha256, p.wheel_filename)) for p in packages]
    cmd = [
        str(py),
        "-m",
        "pip",
        "install",
        "--no-deps",
        "--no-index",
        "--disable-pip-version-check",
        "--quiet",
        *wheels,
    ]
    out = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if out.returncode != 0:
        raise RestoreError(f"pip install failed (exit {out.returncode}):\n{out.stderr.strip()}")
