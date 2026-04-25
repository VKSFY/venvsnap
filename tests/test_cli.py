from pathlib import Path

from typer.testing import CliRunner

from venvsnap._version import __version__
from venvsnap.cli import app
from venvsnap.lockfile import Lockfile

runner = CliRunner()


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_help_lists_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "snapshot" in result.output
    assert "restore" in result.output
    assert "cache" in result.output


def test_cache_info_on_empty_dir(tmp_path: Path) -> None:
    result = runner.invoke(app, ["cache", "info", "--cache", str(tmp_path)])
    assert result.exit_code == 0
    assert "wheels" in result.output
    assert "0" in result.output


def test_restore_missing_lockfile_errors(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "restore",
            "--lockfile",
            str(tmp_path / "missing.lock"),
            "--venv",
            str(tmp_path / ".venv"),
        ],
    )
    assert result.exit_code == 2


def test_restore_empty_lockfile_creates_venv(tmp_path: Path) -> None:
    lock = Lockfile(python_version="3.10.0", platform="any", packages=[])
    lock_path = tmp_path / "venvsnap.lock"
    lock.save(lock_path)
    venv_path = tmp_path / ".venv"

    result = runner.invoke(
        app,
        [
            "restore",
            "--lockfile",
            str(lock_path),
            "--venv",
            str(venv_path),
            "--cache",
            str(tmp_path / "cache"),
        ],
    )
    assert result.exit_code == 0, result.output
    # Empty lockfile still creates a venv.
    assert venv_path.exists()


def test_snapshot_missing_venv_errors(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "snapshot",
            "--venv",
            str(tmp_path / "nope"),
            "--output",
            str(tmp_path / "out.lock"),
        ],
    )
    assert result.exit_code == 2
