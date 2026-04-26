"""Snapshot a venv into a lockfile."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import httpx

from venvsnap.lockfile import LockedPackage, Lockfile
from venvsnap.pypi import PypiError, fetch_release, select_wheel
from venvsnap.venv_utils import (
    current_platform_tag,
    get_python_version,
    list_installed,
)


@dataclass
class SnapshotResult:
    lockfile: Lockfile
    skipped: list[tuple[str, str, str]]  # (name, version, reason)


def snapshot(
    venv_path: Path,
    *,
    workers: int = 8,
    progress: Callable[[str, str, str], None] | None = None,
) -> SnapshotResult:
    """Walk ``venv_path`` with pip list and look every package up on PyPI."""
    installed = list_installed(venv_path)
    python_version = get_python_version(venv_path)
    platform_tag = current_platform_tag()

    locked: list[LockedPackage] = []
    skipped: list[tuple[str, str, str]] = []

    if not installed:
        return SnapshotResult(
            lockfile=Lockfile(
                python_version=python_version,
                platform=platform_tag,
                packages=[],
            ),
            skipped=[],
        )

    with (
        httpx.Client(http2=False, follow_redirects=True) as client,
        ThreadPoolExecutor(max_workers=workers) as pool,
    ):
        futures = {
            pool.submit(_resolve_one, client, name, version): (name, version)
            for name, version in installed
        }
        for fut in as_completed(futures):
            name, version = futures[fut]
            if progress:
                progress(name, version, "resolving")
            try:
                resolved = fut.result()
            except PypiError as exc:
                skipped.append((name, version, str(exc)))
                if progress:
                    progress(name, version, f"skipped: {exc}")
                continue
            if resolved is None:
                reason = "no compatible wheel on PyPI"
                skipped.append((name, version, reason))
                if progress:
                    progress(name, version, f"skipped: {reason}")
                continue
            locked.append(resolved)
            if progress:
                progress(name, version, "resolved")

    locked.sort(key=lambda p: p.name.lower())
    lockfile = Lockfile(
        python_version=python_version,
        platform=platform_tag,
        packages=locked,
    )
    return SnapshotResult(lockfile=lockfile, skipped=skipped)


def _resolve_one(client: httpx.Client, name: str, version: str) -> LockedPackage | None:
    artifacts = fetch_release(client, name, version)
    if not artifacts:
        return None
    chosen = select_wheel(artifacts)
    if chosen is None:
        return None
    return LockedPackage(
        name=name,
        version=version,
        sha256=chosen.sha256,
        wheel_filename=chosen.filename,
        wheel_url=chosen.url,
        requires_python=chosen.requires_python,
    )
