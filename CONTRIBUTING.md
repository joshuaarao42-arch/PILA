# Contributing to PILA

Thanks for helping improve PILA! Bug reports, new algorithms, tests and docs are all welcome.

## Development setup

```bash
git clone <your-fork-url> PILA && cd PILA
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python -m pytest                                       # should be all green
python main.py
```

Linux needs Tkinter (`sudo apt install python3-tk`). On a headless machine use `SDL_VIDEODRIVER=dummy` for tests and `xvfb-run` for GUI checks.

## Project layout

See *Architecture* in the README. Rules of thumb: keep the engine, algorithms, database and analytics free of GUI imports; the UI only calls into them.

## Adding a scheduling algorithm

1. Create `pila/algorithms/<name>.py` with a subclass of `SchedulingAlgorithm` defining `key`, `name`, `description` and `sort_key` (and `time_slice` / `preemptive = True` if it preempts).
2. Register it in `pila/algorithms/__init__.py`.
3. Add its colour to `ALGO_COLORS` in `pila/theme.py`.
4. Add tests with a hand-computed schedule in `tests/test_algorithms.py`; the invariant tests in `test_engine_invariants.py` pick it up automatically.

## Coding standards

- Python 3.9+, type hints on public functions, `from __future__ import annotations`.
- PEP 8, 4-space indent, lines ≤ 120 chars; docstrings on modules, classes and public functions.
- Raise the project errors in `pila/errors.py` (`ConfigError`, `SimulationError`, `DatabaseError`) for user-facing failures; the UI shows them in dialogs.
- Validate input at the boundary (`SimulationConfig.validate`, CSV import). Use parameterised SQL only.
- No new dependency without a strong reason; avoid duplicating logic between the engine and the UI.
- Statistics must stay mathematically consistent: any change to metrics needs a hand-computed test.

## Tests

- Every bug fix gets a regression test; every feature gets tests.
- Algorithm and statistics code must be covered by deterministic, hand-checkable cases.
- Run `python -m pytest` before pushing; CI runs it on Python 3.10 and 3.12.

## Pull requests

1. Fork and create a branch: `git checkout -b feature/short-description`.
2. Keep commits focused with clear messages (`Add SRTF algorithm`, `Fix Gantt label overlap`).
3. Update the README/docs if behaviour changes; add screenshots for UI changes.
4. Open a PR describing *what* and *why*, how you tested it, and linking any issue.
5. Be responsive to review; PRs are merged once tests pass and a maintainer approves.

## Reporting bugs

Open an issue with your OS, Python version, steps to reproduce, the seed and configuration used, and any traceback.

By contributing you agree your work is released under the project's license.
