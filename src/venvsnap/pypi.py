"""PyPI JSON API client."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
from packaging.tags import Tag, sys_tags

PYPI_JSON_URL = "https://pypi.org/pypi/{name}/{version}/json"


class PypiError(Exception):
    pass


@dataclass(frozen=True)
class WheelArtifact:
    filename: str
    url: str
    sha256: str
    requires_python: str | None
    tags: tuple[Tag, ...]


def fetch_release(client: httpx.Client, name: str, version: str) -> list[WheelArtifact]:
    """Return the wheel artifacts for ``name==version``."""
    url = PYPI_JSON_URL.format(name=name, version=version)
    try:
        resp = client.get(url, timeout=30.0)
    except httpx.HTTPError as exc:
        raise PypiError(f"network error fetching {name}=={version}: {exc}") from exc
    if resp.status_code == 404:
        raise PypiError(f"release not found on PyPI: {name}=={version}")
    if resp.status_code != 200:
        raise PypiError(f"PyPI returned HTTP {resp.status_code} for {name}=={version}")
    try:
        data: dict[str, Any] = resp.json()
    except ValueError as exc:
        raise PypiError(f"invalid JSON from PyPI for {name}=={version}: {exc}") from exc

    artifacts: list[WheelArtifact] = []
    for entry in data.get("urls", []):
        if entry.get("packagetype") != "bdist_wheel":
            continue
        filename = entry.get("filename")
        if not filename or not filename.endswith(".whl"):
            continue
        digests = entry.get("digests") or {}
        sha256 = digests.get("sha256")
        url_ = entry.get("url")
        if not sha256 or not url_:
            continue
        artifacts.append(
            WheelArtifact(
                filename=filename,
                url=url_,
                sha256=sha256,
                requires_python=entry.get("requires_python"),
                tags=tuple(_tags_from_filename(filename)),
            )
        )
    return artifacts


def select_wheel(
    artifacts: list[WheelArtifact],
    compatible_tags: list[Tag] | None = None,
) -> WheelArtifact | None:
    """Pick the highest-priority wheel matching the current interpreter and platform.

    A platform-specific wheel beats ``py3-none-any``, since the latter shows up
    last in ``packaging.tags.sys_tags()``.
    """
    if not artifacts:
        return None
    if compatible_tags is None:
        compatible_tags = list(sys_tags())
    priority: dict[Tag, int] = {tag: i for i, tag in enumerate(compatible_tags)}

    best: tuple[int, WheelArtifact] | None = None
    for art in artifacts:
        for tag in art.tags:
            score = priority.get(tag)
            if score is None:
                continue
            if best is None or score < best[0]:
                best = (score, art)
            break
    return best[1] if best else None


def _tags_from_filename(filename: str) -> list[Tag]:
    """Parse PEP 425 tags out of a wheel filename."""
    stem = filename[:-4] if filename.endswith(".whl") else filename
    # name-version[-build]-python-abi-platform
    parts = stem.split("-")
    if len(parts) < 5:
        return []
    pythons, abis, platforms = parts[-3], parts[-2], parts[-1]
    out: list[Tag] = []
    for py in pythons.split("."):
        for abi in abis.split("."):
            for plat in platforms.split("."):
                out.append(Tag(py, abi, plat))
    return out
