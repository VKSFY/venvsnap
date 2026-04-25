from pathlib import Path

import pytest

from venvsnap.lockfile import (
    LOCKFILE_VERSION,
    LockedPackage,
    Lockfile,
    LockfileError,
)


def make_pkg(name: str = "requests", version: str = "2.31.0") -> LockedPackage:
    return LockedPackage(
        name=name,
        version=version,
        sha256="a" * 64,
        wheel_filename=f"{name}-{version}-py3-none-any.whl",
        wheel_url=f"https://files.pythonhosted.org/packages/{name}/{name}-{version}-py3-none-any.whl",
        requires_python=">=3.7",
    )


def test_roundtrip_preserves_packages() -> None:
    original = Lockfile(
        python_version="3.11.5",
        platform="linux-x86_64",
        packages=[make_pkg("requests", "2.31.0"), make_pkg("rich", "13.7.0")],
    )
    text = original.to_toml()
    restored = Lockfile.from_toml(text)
    assert restored.python_version == "3.11.5"
    assert restored.platform == "linux-x86_64"
    assert [p.name for p in restored.packages] == ["requests", "rich"]
    assert restored.packages[0].sha256 == "a" * 64


def test_save_and_load(tmp_path: Path) -> None:
    lock = Lockfile(
        python_version="3.10.0",
        platform="darwin-arm64",
        packages=[make_pkg()],
    )
    target = tmp_path / "venvsnap.lock"
    lock.save(target)

    loaded = Lockfile.load(target)
    assert loaded.packages[0].wheel_url == lock.packages[0].wheel_url


def test_load_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(LockfileError, match="not found"):
        Lockfile.load(tmp_path / "missing.lock")


def test_unsupported_version_raises() -> None:
    text = """
    version = 999
    python_version = "3.11.0"
    platform = "linux-x86_64"
    """
    with pytest.raises(LockfileError, match="unsupported lockfile version"):
        Lockfile.from_toml(text)


def test_omits_requires_python_when_none() -> None:
    pkg = LockedPackage(
        name="x",
        version="1.0",
        sha256="b" * 64,
        wheel_filename="x-1.0-py3-none-any.whl",
        wheel_url="https://example.com/x.whl",
        requires_python=None,
    )
    assert "requires_python" not in pkg.to_dict()


def test_default_version_is_current() -> None:
    lock = Lockfile(python_version="3.11.0", platform="any")
    assert lock.version == LOCKFILE_VERSION
