"""Time pip install -r vs venvsnap restore (cold cache, then warm cache).

    python examples/benchmark.py

Numbers depend on bandwidth and hardware.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REQUIREMENTS = [
    "requests==2.31.0",
    "rich==13.7.0",
    "httpx==0.27.0",
    "click==8.1.7",
    "pydantic==2.6.0",
]


def time_block(label: str):
    class _T:
        def __enter__(self):
            self.t0 = time.perf_counter()
            print(f"-> {label} ...", flush=True)
            return self

        def __exit__(self, *exc):
            self.elapsed = time.perf_counter() - self.t0
            print(f"   {label}: {self.elapsed:.2f}s", flush=True)

    return _T()


def run(cmd: list[str], cwd: Path | None = None) -> None:
    subprocess.run(cmd, check=True, cwd=cwd)


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="venvsnap-bench-"))
    cache = tmp / "cache"
    venv = tmp / ".venv"
    lock = tmp / "venvsnap.lock"
    reqs = tmp / "requirements.txt"
    reqs.write_text("\n".join(REQUIREMENTS) + "\n")

    print(f"workspace: {tmp}\n")

    py = sys.executable
    venvsnap = [py, "-m", "venvsnap"]

    # 1. baseline: pip install -r
    run([py, "-m", "venv", str(venv)])
    venv_py = (
        venv
        / ("Scripts" if sys.platform == "win32" else "bin")
        / ("python.exe" if sys.platform == "win32" else "python")
    )
    with time_block("pip install -r requirements.txt") as t_pip:
        run([str(venv_py), "-m", "pip", "install", "--quiet", "-r", str(reqs)])

    # 2. snapshot
    with time_block("venvsnap snapshot"):
        run([*venvsnap, "snapshot", "--venv", str(venv), "--output", str(lock)])

    # 3. cold restore
    shutil.rmtree(venv)
    if cache.exists():
        shutil.rmtree(cache)
    with time_block("venvsnap restore (cold cache)") as t_cold:
        run(
            [
                *venvsnap,
                "restore",
                "--venv",
                str(venv),
                "--lockfile",
                str(lock),
                "--cache",
                str(cache),
            ]
        )

    # 4. warm restore
    shutil.rmtree(venv)
    with time_block("venvsnap restore (warm cache)") as t_warm:
        run(
            [
                *venvsnap,
                "restore",
                "--venv",
                str(venv),
                "--lockfile",
                str(lock),
                "--cache",
                str(cache),
            ]
        )

    print()
    print("--- summary ---")
    print(f"pip install -r       : {t_pip.elapsed:6.2f}s")
    print(
        f"venvsnap restore cold: {t_cold.elapsed:6.2f}s  "
        f"({t_pip.elapsed / t_cold.elapsed:.1f}x faster)"
    )
    print(
        f"venvsnap restore warm: {t_warm.elapsed:6.2f}s  "
        f"({t_pip.elapsed / t_warm.elapsed:.1f}x faster)"
    )

    shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
