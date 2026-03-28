# Agent notes

Before finishing Python changes, run (from repo root, with dev deps):

```bash
pipenv run black .
pipenv run python3 -m flake8 --select BLK **/*.py
pipenv run python3 -m pytest
```

CI runs the same `flake8 --select BLK` and `pytest` steps; `black .` keeps formatting aligned so BLK passes.
