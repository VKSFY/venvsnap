# venvsnap

> Snapshot your Python venv. Restore it in seconds, anywhere.

[![CI](https://github.com/VKSFY/venvsnap/actions/workflows/ci.yml/badge.svg)](https://github.com/VKSFY/venvsnap/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/venvsnap.svg)](https://pypi.org/project/venvsnap/)
[![Python](https://img.shields.io/pypi/pyversions/venvsnap.svg)](https://pypi.org/project/venvsnap/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

`venvsnap` captures the exact contents of a `.venv` into a small, human-readable
lockfile. Every wheel listed in the lockfile is content-addressed in a local
cache, so re-creating the same environment — on another branch, on a teammate's
laptop, or in CI — completes in seconds with zero network round-trips after the
first run.

```text
$ venvsnap restore
venvsnap restoring 47 packages -> .venv
   cache: 47 hits, 0 to download

✓ restored 47 packages in 1.18s
   cache: 47 hits, 0 downloads (0.0 MB in 0.00s)
   install: 1.12s
```

## Why venvsnap

Recreating a `.venv` is one of the most common Python operations and one of the
slowest. `pip install -r requirements.txt` re-resolves dependencies, re-checks
PyPI, re-downloads wheels you already had, and re-installs them serially.

`venvsnap` is laser-focused on one job: take an environment that already works
and reproduce it byte-for-byte, fast.

| Operation                                  | `pip install -r` | `venvsnap restore` (cold) | `venvsnap restore` (warm) |
| ------------------------------------------ | ---------------- | ------------------------- | ------------------------- |
| Restore a 47-package data-science env\*    | ~38 s            | ~14 s                     | **~1.2 s**                |

\*Indicative numbers from `examples/benchmark.py` on a typical laptop with a
broadband connection. Run it yourself — the script is committed.

### How it differs from the alternatives

- **vs `pip install -r requirements.txt`** — `venvsnap` skips the resolver
  entirely and installs from a local cache by default. No network, no version
  solver, no surprises.
- **vs `uv`** — `uv` is a full pip/resolver replacement. `venvsnap` does not
  resolve, does not replace `pip`, and works alongside whatever package
  manager you already use. It is intentionally tiny.
- **vs `pip-tools`** — `pip-tools` produces a requirements pin file; you still
  pay the install cost every time. `venvsnap` keeps the wheels themselves so
  installs are essentially file copies.

## Install

```bash
pip install venvsnap
```

Requires Python 3.9 or newer.

## Quickstart

```bash
# 1. inside a working venv
venvsnap snapshot                 # writes venvsnap.lock

# 2. commit the lockfile
git add venvsnap.lock && git commit -m "pin venv"

# 3. anywhere — fresh checkout, new laptop, CI
venvsnap restore                  # rebuilds .venv in seconds
```

That's the whole workflow.

## Commands

| Command             | What it does                                                 |
| ------------------- | ------------------------------------------------------------ |
| `venvsnap snapshot` | Read the current `.venv`, look up each wheel on PyPI, write a TOML lockfile with hashes and URLs. |
| `venvsnap restore`  | Read the lockfile, fetch any missing wheels into the cache (in parallel), and install them into a target venv with `pip --no-deps --no-index`. |
| `venvsnap verify`   | Compare a venv against a lockfile and report drift.          |
| `venvsnap cache info` | Show the cache location and total size.                    |
| `venvsnap cache clean` | Wipe the cache.                                          |

Each command supports `--help`.

## The lockfile

`venvsnap.lock` is human-readable TOML. It looks like this:

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
```

Commit it. It diffs cleanly. It contains everything needed to reproduce the
environment.

## The cache

By default the cache lives at `~/.venvsnap/cache/wheels/`, and wheels are
stored under their sha256 hash:

```
~/.venvsnap/cache/wheels/
└── 58/58cd2187...003f/requests-2.31.0-py3-none-any.whl
```

Override the location with `--cache PATH` or by passing it to any command. The
cache is shared across every project on the machine, so a wheel downloaded for
one project is instantly available to every other project that pins the same
version.

## What venvsnap does not do

- **No resolver.** If you don't already have a working environment, use `pip`,
  `uv`, or `poetry` to build one — then `venvsnap snapshot` it.
- **No source builds.** `venvsnap` only handles wheels published on PyPI. If
  your project depends on a package that ships only an sdist, snapshot will
  warn and skip it.
- **No private indexes** in 0.1. (Planned.)

These limitations are deliberate. The 1.0 promise is: *small, predictable,
fast.*

## Development

```bash
git clone https://github.com/VKSFY/venvsnap
cd venvsnap
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## License

MIT — see [LICENSE](LICENSE).
