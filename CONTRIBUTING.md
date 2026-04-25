# Contributing to venvsnap

Thanks for considering a contribution! venvsnap is intentionally small, so the
bar for new features is high — but bug reports, docs improvements, and tests
are always welcome.

## Setting up

```bash
git clone https://github.com/VKSFY/venvsnap
cd venvsnap
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Running checks

```bash
pytest                       # tests
ruff check .                 # lint
ruff format --check .        # formatting
mypy src                     # types
```

All four must pass before a PR is merged. CI runs them on every push.

## Scope

venvsnap exists to make one operation — recreating an existing venv — as fast
as possible. Anything that drifts toward "another package manager" is out of
scope. Open an issue before working on a large change so we can confirm fit.

## Reporting bugs

Please include:

- The output of `venvsnap --version`
- Your Python version and OS
- The exact command you ran
- The full output, ideally with `--workers 1` to make tracebacks legible
