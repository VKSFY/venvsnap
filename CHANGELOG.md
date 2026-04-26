# Changelog

## 0.1.0 (2026-04-25)

First release.

- `snapshot`: walk a venv with `pip list`, look every package up on PyPI,
  pick a wheel for the current platform, write versions and sha256 hashes
  to `venvsnap.lock`. PyPI lookups run in parallel.
- `restore`: read a lockfile, fetch missing wheels into the cache (in
  parallel), create the venv if needed, install everything via
  `pip install --no-deps --no-index`.
- `verify`: report missing/extra/version-mismatched packages between a
  venv and a lockfile.
- `cache info`, `cache clean`: inspect or wipe the local wheel cache,
  which lives under `~/.venvsnap/cache/` by default.
