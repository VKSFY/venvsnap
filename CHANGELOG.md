# Changelog

All notable changes to venvsnap are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
adheres to [Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-04-25

Initial public release.

### Added
- `venvsnap snapshot` to capture the current venv into a TOML lockfile.
- `venvsnap restore` to rebuild a venv from a lockfile, using a content-
  addressed local cache at `~/.venvsnap/cache/`.
- `venvsnap verify` to detect drift between a venv and its lockfile.
- `venvsnap cache info` and `venvsnap cache clean` for cache management.
- Parallel PyPI lookups during snapshot and parallel wheel downloads during
  restore.
- Test suite covering the lockfile, cache, PyPI client, and CLI.
