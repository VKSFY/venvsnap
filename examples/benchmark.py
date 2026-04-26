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


def run(cmd):
    subprocess.run(cmd, check=True)


def time_run(label, cmd):
    print(f"-> {label} ...", flush=True)
    t0 = time.perf_counter()
    run(cmd)
    elapsed = time.perf_counter() - t0
    print(f"   {elapsed:.2f}s", flush=True)
    return elapsed


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
    venv_py = venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")

    run([py, "-m", "venv", str(venv)])
    pip_elapsed = time_run(
        "pip install -r requirements.txt",
        [str(venv_py), "-m", "pip", "install", "--quiet", "-r", str(reqs)],
    )

    time_run(
        "venvsnap snapshot",
        [*venvsnap, "snapshot", "--venv", str(venv), "--output", str(lock)],
    )

    shutil.rmtree(venv)
    if cache.exists():
        shutil.rmtree(cache)
    cold = time_run(
        "venvsnap restore (cold cache)",
        [*venvsnap, "restore", "--venv", str(venv), "--lockfile", str(lock), "--cache", str(cache)],
    )

    shutil.rmtree(venv)
    warm = time_run(
        "venvsnap restore (warm cache)",
        [*venvsnap, "restore", "--venv", str(venv), "--lockfile", str(lock), "--cache", str(cache)],
    )

    print()
    print("--- summary ---")
    print(f"pip install -r       : {pip_elapsed:6.2f}s")
    print(f"venvsnap restore cold: {cold:6.2f}s  ({pip_elapsed / cold:.1f}x)")
    print(f"venvsnap restore warm: {warm:6.2f}s  ({pip_elapsed / warm:.1f}x)")

    shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
