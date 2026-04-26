"""Command-line interface."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Optional

# Windows consoles often default to cp1252, which can't print the unicode
# checkmarks below. Try to switch to UTF-8 and ignore the failure if the
# stream doesn't support it (e.g. captured pipes).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, OSError):
        pass

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from venvsnap._version import __version__
from venvsnap.cache import Cache
from venvsnap.lockfile import DEFAULT_LOCKFILE_NAME, Lockfile, LockfileError
from venvsnap.restore import RestoreError
from venvsnap.restore import restore as run_restore
from venvsnap.snapshot import snapshot as run_snapshot
from venvsnap.venv_utils import VenvError, is_venv, list_installed

app = typer.Typer(
    add_completion=False,
    help="Snapshot a Python venv into a lockfile and restore it from a cache.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
cache_app = typer.Typer(help="Inspect and manage the wheel cache.")
app.add_typer(cache_app, name="cache")

console = Console(legacy_windows=False)
err_console = Console(stderr=True, legacy_windows=False)


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"venvsnap [bold]{__version__}[/bold]")
        raise typer.Exit()


@app.callback()
def _root(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-V",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    pass


@app.command("snapshot")
def snapshot(
    venv_path: Path = typer.Option(
        Path(".venv"), "--venv", "-e", help="Virtual environment to snapshot."
    ),
    output: Path = typer.Option(
        Path(DEFAULT_LOCKFILE_NAME), "--output", "-o", help="Where to write the lockfile."
    ),
    workers: int = typer.Option(
        8, "--workers", "-j", min=1, max=32, help="Concurrent PyPI requests."
    ),
) -> None:
    """Write a venvsnap.lock from the current venv."""
    if not is_venv(venv_path):
        err_console.print(f"[red]error:[/red] no virtual environment at {venv_path}")
        raise typer.Exit(code=2)

    console.print(f"[bold cyan]venvsnap[/bold cyan] snapshotting [bold]{venv_path}[/bold]")
    start = time.perf_counter()
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console,
            transient=True,
        ) as bar:
            task = bar.add_task("Resolving wheels", total=None)

            def on_progress(name: str, version: str, status: str) -> None:
                if status == "resolved":
                    bar.update(task, advance=1, description=f"Resolved {name}")
                elif status.startswith("skipped"):
                    bar.update(task, advance=1, description=f"Skipped {name}")

            result = run_snapshot(venv_path, workers=workers, progress=on_progress)
    except VenvError as exc:
        err_console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    result.lockfile.save(output)
    elapsed = time.perf_counter() - start

    console.print()
    console.print(
        f"[green]✓[/green] wrote [bold]{output}[/bold] "
        f"with [bold]{len(result.lockfile.packages)}[/bold] packages "
        f"in [bold]{elapsed:.2f}s[/bold]"
    )
    if result.skipped:
        console.print(
            f"[yellow]![/yellow] skipped {len(result.skipped)} packages (no wheels on PyPI):"
        )
        for name, version, reason in result.skipped:
            console.print(f"   - [bold]{name}[/bold]=={version}: {reason}")


@app.command("restore")
def restore(
    venv_path: Path = typer.Option(
        Path(".venv"), "--venv", "-e", help="Where to materialize the venv."
    ),
    lockfile_path: Path = typer.Option(
        Path(DEFAULT_LOCKFILE_NAME),
        "--lockfile",
        "-l",
        help="Lockfile to restore from.",
    ),
    workers: int = typer.Option(8, "--workers", "-j", min=1, max=32, help="Concurrent downloads."),
    cache_dir: Optional[Path] = typer.Option(
        None,
        "--cache",
        help="Override the cache directory (default: ~/.venvsnap/cache).",
    ),
) -> None:
    """Restore a venv from a lockfile."""
    try:
        lockfile = Lockfile.load(lockfile_path)
    except LockfileError as exc:
        err_console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    cache = Cache(cache_dir)

    cached = sum(1 for p in lockfile.packages if cache.has(p.sha256, p.wheel_filename))
    needed = len(lockfile.packages) - cached
    console.print(
        f"[bold cyan]venvsnap[/bold cyan] restoring "
        f"[bold]{len(lockfile.packages)}[/bold] packages -> [bold]{venv_path}[/bold]"
    )
    console.print(
        f"   cache: [bold green]{cached}[/bold green] hits, "
        f"[bold yellow]{needed}[/bold yellow] to download"
    )

    overall_start = time.perf_counter()
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console,
            transient=True,
        ) as bar:
            dl_task = bar.add_task("Downloading", total=needed)

            def on_progress(name: str, version: str, status: str) -> None:
                if status == "downloaded":
                    bar.update(dl_task, advance=1, description=f"Got {name}")
                elif status.startswith("failed"):
                    bar.update(dl_task, advance=1, description=f"Failed {name}")

            result = run_restore(
                lockfile,
                venv_path,
                cache=cache,
                workers=workers,
                progress=on_progress,
            )
    except RestoreError as exc:
        err_console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    overall_elapsed = time.perf_counter() - overall_start

    if result.failed:
        err_console.print(f"[red]error:[/red] {len(result.failed)} packages failed:")
        for spec, reason in result.failed:
            err_console.print(f"   - {spec}: {reason}")
        raise typer.Exit(code=1)

    mb = result.bytes_downloaded / (1024 * 1024)
    console.print()
    console.print(
        f"[green]✓[/green] restored [bold]{result.total_packages}[/bold] packages "
        f"in [bold]{overall_elapsed:.2f}s[/bold]"
    )
    console.print(
        f"   cache: [bold green]{result.cache_hits}[/bold green] hits, "
        f"[bold yellow]{result.cache_misses}[/bold yellow] downloads "
        f"([bold]{mb:.1f} MB[/bold] in {result.seconds_download:.2f}s)"
    )
    console.print(f"   install: [bold]{result.seconds_install:.2f}s[/bold]")


@app.command("verify")
def verify(
    venv_path: Path = typer.Option(
        Path(".venv"), "--venv", "-e", help="Virtual environment to check."
    ),
    lockfile_path: Path = typer.Option(
        Path(DEFAULT_LOCKFILE_NAME),
        "--lockfile",
        "-l",
        help="Lockfile to compare against.",
    ),
) -> None:
    """Compare a venv against a lockfile and report drift."""
    try:
        lockfile = Lockfile.load(lockfile_path)
    except LockfileError as exc:
        err_console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    if not is_venv(venv_path):
        err_console.print(f"[red]error:[/red] no virtual environment at {venv_path}")
        raise typer.Exit(code=2)

    try:
        installed = {name.lower(): version for name, version in list_installed(venv_path)}
    except VenvError as exc:
        err_console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    locked = {p.name.lower(): p.version for p in lockfile.packages}

    missing = [n for n in locked if n not in installed]
    extra = [n for n in installed if n not in locked]
    mismatched = [
        (n, installed[n], locked[n]) for n in locked if n in installed and installed[n] != locked[n]
    ]

    if not (missing or extra or mismatched):
        console.print(f"[green]✓[/green] venv matches lockfile ({len(locked)} packages)")
        return

    console.print(f"[yellow]drift detected[/yellow] vs {lockfile_path}:")
    if missing:
        console.print(f"   [red]missing[/red] ({len(missing)}): " + ", ".join(missing))
    if extra:
        console.print(f"   [blue]extra[/blue] ({len(extra)}): " + ", ".join(extra))
    if mismatched:
        console.print(f"   [yellow]version mismatch[/yellow] ({len(mismatched)}):")
        for name, have, want in mismatched:
            console.print(f"      - {name}: have {have}, lockfile {want}")
    raise typer.Exit(code=1)


@cache_app.command("info")
def cache_info(
    cache_dir: Optional[Path] = typer.Option(None, "--cache", help="Override the cache directory."),
) -> None:
    """Show cache location and size."""
    cache = Cache(cache_dir)
    stats = cache.stats()
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold")
    table.add_column()
    table.add_row("path", str(cache.root))
    table.add_row("wheels", str(stats.wheel_count))
    table.add_row("size", stats.human_size)
    console.print(table)


@cache_app.command("clean")
def cache_clean(
    cache_dir: Optional[Path] = typer.Option(None, "--cache", help="Override the cache directory."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation."),
) -> None:
    """Delete every wheel from the local cache."""
    cache = Cache(cache_dir)
    stats = cache.stats()
    if stats.wheel_count == 0:
        console.print("cache is already empty")
        return
    if not yes:
        confirmed = typer.confirm(
            f"Delete {stats.wheel_count} wheels ({stats.human_size}) from {cache.root}?"
        )
        if not confirmed:
            console.print("aborted")
            raise typer.Exit(code=1)
    removed = cache.clean()
    console.print(f"[green]✓[/green] removed {removed.wheel_count} wheels ({removed.human_size})")


def main() -> None:
    try:
        app()
    except KeyboardInterrupt:
        err_console.print("[red]aborted[/red]")
        sys.exit(130)
