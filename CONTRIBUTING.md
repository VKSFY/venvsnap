# Contributing

Bug reports, docs fixes, and tests are welcome. For larger features, open an
issue first so we can check whether it fits the scope (snapshot and restore,
not a new package manager).

## Setup

```
git clone https://github.com/VKSFY/venvsnap
cd venvsnap
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Checks

```
pytest
ruff check .
ruff format --check .
mypy src
```

CI runs all four on push.

## Bug reports

Include the output of `venvsnap --version`, your Python version, your OS, and
the exact command. `--workers 1` makes tracebacks easier to read.
