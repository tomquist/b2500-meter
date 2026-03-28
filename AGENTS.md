# Agent notes

Resolved versions live in `Pipfile.lock`; install dev deps the same way CI does:

```bash
pipenv sync --dev
```

Before finishing Python changes, run (from repo root, with dev deps):

```bash
pipenv run black .
pipenv run python3 -m flake8 --select BLK **/*.py
pipenv run python3 -m pytest
```

CI runs the same `flake8 --select BLK` and `pytest` steps; `black .` keeps formatting aligned so BLK passes.

## Changelog

On every user-facing change, add a bullet under **`## Next`** in `CHANGELOG.md`. Skip when nothing users would notice changes (refactors, tests-only, etc.).

## Adding a powermeter

1. **Implementation** — Add `powermeter/<module>.py` with a class subclassing `Powermeter`; implement `get_powermeter_watts()` (and `wait_for_message()` only if the base default is wrong for your source).
2. **Exports** — Import and re-export the class from `powermeter/__init__.py`.
3. **Config** — In `config/config_loader.py`: import the class, define a `*_SECTION` string, add a `section.startswith(...)` branch in `create_powermeter()`, and a `create_*_powermeter()` factory that reads options from the section. `POWER_OFFSET` / `POWER_MULTIPLIER`, `THROTTLE_INTERVAL`, and `NETMASK` are handled globally for any section that returns a powermeter — no extra wiring unless you need something custom.
4. **Examples, docs & changelog** — Add a commented example to `config.ini.example`, a subsection under **Configuration** in `README.md`, and a bullet under **`## Next`** in `CHANGELOG.md`.
5. **Tests** — Add `powermeter/<module>_test.py` (or extend existing tests) and run the commands above before finishing.
