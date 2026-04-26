# venvsnap

Snapshot a Python virtual environment into a lockfile, then restore it from a
local cache. Once the wheels are cached, restoring an env doesn't touch PyPI.

[![CI](https://github.com/VKSFY/venvsnap/actions/workflows/ci.yml/badge.svg)](https://github.com/VKSFY/venvsnap/actions/workflows/ci.yml)

## Install

```
pip install venvsnap
```

Requires Python 3.9 or newer.

## Usage

In a working venv:

```
venvsnap snapshot
```

This walks `pip list`, looks each package up on PyPI to find a wheel matching
the current platform, and writes the result to `venvsnap.lock` (TOML). Check
the lockfile in.

On another machine, in CI, or in a fresh clone:

```
venvsnap restore
```

This reads the lockfile, downloads any wheels that aren't already in
`~/.venvsnap/cache/`, creates `.venv` if needed, and installs everything with
`pip install --no-deps --no-index`. After the first run for a given lockfile,
no network is involved.

The cache is shared across projects. The first time `requests-2.31.0-py3-none-any.whl`
gets downloaded, every other project that pins the same wheel reuses the same file.

## Other commands

```
venvsnap verify        compare a venv against a lockfile, report drift
venvsnap cache info    show the cache path and size
venvsnap cache clean   delete every wheel from the cache
```

`--help` on any command lists its flags.

## Lockfile

`venvsnap.lock` is plain TOML. A two-package example:

```toml
version = 1
python_version = "3.11.7"
platform = "linux-x86_64"
created_at = "2026-04-25T12:34:56Z"

[[package]]
name = "requests"
version = "2.31.0"
sha256 = "58cd2187c01e70e6e26505bca751777aa9f2ee0b7f4300988b709f44e013003f"
wheel_filename = "requests-2.31.0-py3-none-any.whl"
wheel_url = "https://files.pythonhosted.org/packages/.../requests-2.31.0-py3-none-any.whl"
requires_python = ">=3.7"

[[package]]
name = "rich"
version = "13.7.0"
...
```

Diffs are readable: a dependency bump shows up as one `version`/`sha256`/`wheel_url`
change.

## Cache layout

```
~/.venvsnap/cache/wheels/<aa>/<sha256>/<filename>.whl
```

`<aa>` is the first two hex chars of the sha256, used as a bucket so directories
stay shallow on case-insensitive filesystems. Override with `--cache PATH` on
any command.

## How it compares

`pip install -r requirements.txt` re-resolves dependencies and consults PyPI on
every run. venvsnap skips the resolver. With a warm cache, restore is wheel
copies plus one `pip install` invocation.

`uv` is a faster pip with a real resolver. venvsnap doesn't replace either: use
pip or uv to build the env, then `venvsnap snapshot` to record it. They compose
fine.

`pip-tools` writes a pinned requirements file. Install still goes through the
index. venvsnap stores the wheels themselves.

## Limits

- Wheels only. If a package only ships an sdist, snapshot warns and skips it.
- PyPI only. Private indexes are not supported in 0.1.
- No resolver. venvsnap captures whatever is already installed; building the
  env is somebody else's job.

## Benchmark

`examples/benchmark.py` installs a small dependency set with `pip install -r`,
then runs `venvsnap restore` cold and warm, and prints the times. Numbers vary
with bandwidth and hardware, so run it locally.

```
python examples/benchmark.py
```

## Development

```
git clone https://github.com/VKSFY/venvsnap
cd venvsnap
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
```

`ruff check`, `ruff format --check`, `mypy src`, and `pytest` all run in CI on
push.

## License

MIT. See [LICENSE](LICENSE).
