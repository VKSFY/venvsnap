"""Helpers for inspecting and creating virtual environments."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import venv
from pathlib import Path


class VenvError(Exception):
    """Raised when a venv operation fails."""


def venv_python(venv_path: Path) -> Path:
    """Return the path to the Python interpreter inside ``venv_path``."""
    if os.name == "nt":
        candidate = venv_path / "Scripts" / "python.exe"
    else:
        candidate = venv_path / "bin" / "python"
    return candidate


def is_venv(path: Path) -> bool:
    return venv_python(path).is_file()


def create_venv(path: Path, with_pip: bool = True) -> None:
    """Create a fresh virtual environment at ``path``."""
    if path.exists() and not is_venv(path):
        raise VenvError(f"refusing to overwrite non-venv directory: {path}")
    builder = venv.EnvBuilder(with_pip=with_pip, clear=False, upgrade_deps=False)
    builder.create(str(path))


def get_python_version(venv_path: Path) -> str:
    """Return the ``major.minor.patch`` version of the venv's interpreter."""
    py = venv_python(venv_path)
    if not py.is_file():
        raise VenvError(f"no python interpreter found at {py}")
    out = subprocess.run(
        [str(py), "-c", "import sys;print('.'.join(map(str,sys.version_info[:3])))"],
        capture_output=True,
        text=True,
        check=False,
    )
    if out.returncode != 0:
        raise VenvError(f"failed to query venv python version: {out.stderr.strip()}")
    return out.stdout.strip()


def list_installed(venv_path: Path) -> list[tuple[str, str]]:
    """Return ``(name, version)`` for every package installed in the venv."""
    py = venv_python(venv_path)
    if not py.is_file():
        raise VenvError(f"no python interpreter found at {py}")
    out = subprocess.run(
        [str(py), "-m", "pip", "list", "--format=json", "--disable-pip-version-check"],
        capture_output=True,
        text=True,
        check=False,
    )
    if out.returncode != 0:
        raise VenvError(f"pip list failed: {out.stderr.strip()}")
    try:
        data = json.loads(out.stdout)
    except json.JSONDecodeError as exc:
        raise VenvError(f"could not parse pip list output: {exc}") from exc

    skip = {"pip", "setuptools", "wheel", "venvsnap"}
    return [
        (entry["name"], entry["version"]) for entry in data if entry["name"].lower() not in skip
    ]


def current_platform_tag() -> str:
    """A short string describing the current platform for the lockfile."""
    return f"{platform.system().lower()}-{platform.machine().lower()}"


def current_python_version() -> str:
    return ".".join(str(v) for v in sys.version_info[:3])
