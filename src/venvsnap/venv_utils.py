"""venv inspection and creation."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import venv
from pathlib import Path


class VenvError(Exception):
    pass


def venv_python(venv_path: Path) -> Path:
    if os.name == "nt":
        return venv_path / "Scripts" / "python.exe"
    return venv_path / "bin" / "python"


def is_venv(path: Path) -> bool:
    return venv_python(path).is_file()


def create_venv(path: Path, with_pip: bool = True) -> None:
    if path.exists() and not is_venv(path):
        raise VenvError(f"refusing to overwrite non-venv directory: {path}")
    builder = venv.EnvBuilder(with_pip=with_pip, clear=False, upgrade_deps=False)
    builder.create(str(path))


def get_python_version(venv_path: Path) -> str:
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
    return f"{platform.system().lower()}-{platform.machine().lower()}"
