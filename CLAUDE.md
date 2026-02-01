# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is Evidence?

Evidence is a Python framework for specification-based property testing. It uses Hypothesis to automatically generate test cases and verify that function implementations satisfy their contracts (preconditions/postconditions) and match reference specifications.

## Running

```bash
# Install in development mode
pip install -e .

# Install with dev tools (ruff, mypy)
pip install -e ".[dev]"

# Run checks on a module (module must be importable)
evidence example_sort
python -m evidence example_sort
python -m evidence example_sort --out .evidence --max-list-size 20 --smoke-max-list-size 5

# CLI flags
python -m evidence example_sort -v          # verbose: show counterexample details and timing
python -m evidence example_sort -q          # quiet: only summary + exit code
python -m evidence example_sort --json      # JSON array to stdout (machine-friendly)
python -m evidence example_sort --no-color  # disable ANSI colors (also: NO_COLOR env)

# Linting and type checking
ruff check src/ examples/
mypy src/evidence/
```

## Public API

The public API is re-exported from `evidence/__init__.py`:

- `@spec` — marks a function as a reference specification
- `@against(spec_fn, *, max_examples=200, deadline_ms=None, suppress_health_checks=(...), eq=None)` — declares the decorated function should match `spec_fn` for all valid inputs
- `@requires(pred)` — adds a precondition; `pred` takes the same args as the function, returns bool; generated inputs violating it are filtered via `hypothesis.assume()`; stackable
- `@ensures(pred)` — adds a postcondition; `pred` takes the original args plus the return value, returns bool; stackable
- `register_strategy(type, strategy)` — register a Hypothesis strategy for a custom type
- `register_strategy_factory(type, factory)` — register a parameterized strategy factory for a custom type
- `check_module(module_name, *, out_dir=".evidence", max_list_size=20, smoke_max_list_size=5, on_result=None)` — programmatic entry point; returns `(list[ObligationResult], trust_dict)`
- `main(argv=None)` — CLI entry point

### Decorator ordering

Decorators are applied bottom-up. The typical stacking order is:

```python
@against(spec_fn)      # outermost: attach spec reference
@ensures(postcond)     # postcondition checks
@requires(precond)     # innermost contract: precondition checks
def my_func(...):
    ...
```

### Custom type strategies

Built-in types (`int`, `str`, `float`, `bool`, `list`, `dict`, `set`, `tuple`, unions, dataclasses) are handled automatically from type annotations. For custom types, register before `check_module()` runs:

```python
from hypothesis import strategies as st
from evidence import register_strategy

Interval = tuple[int, int]
register_strategy(
    Interval,
    st.tuples(st.integers(-10, 10), st.integers(-10, 10))
      .map(lambda t: (min(t), max(t))),
)
```

## Architecture

The project uses a standard Python src layout:

```
src/evidence/
├── __init__.py      # public API re-exports
├── __main__.py      # CLI entry point (calls main())
├── _util.py         # helpers: _ensure_dir, _now_iso, _qualified_name, _jsonable, _safe_call, type aliases
├── _bundle.py       # bundle metadata: _BUNDLE_ATTR, _ORIGINAL_ATTR, _root_original, _bundle, _set_original, _get_bundle, _check_requires, _check_ensures
├── _decorators.py   # @requires, @ensures, @spec, @against
├── _strategies.py   # strategy registry + synthesis: register_strategy, _strategy_for_type, _strategy_for_function, _find_satisfying_kwargs
├── _engine.py       # check_module, ObligationResult, _collect_functions, _find_counterexample
├── _cli.py          # main(), argument parsing, colored output, JSON/quiet/verbose modes
└── _term.py         # ANSI terminal helpers: supports_color, force_color, style, green, red, yellow, dim, bold
```

- **`_util.py`** — Shared utilities and type aliases (`EvidencePredicate`, `StrategyFactory`)
- **`_bundle.py`** — Metadata stored as function attributes (`_BUNDLE_ATTR`, `_ORIGINAL_ATTR`) to track decorator chains; precondition/postcondition checking
- **`_decorators.py`** — `@requires(pred)`, `@ensures(pred)`, `@spec`, `@against(spec_fn)` attach contracts and specifications to functions
- **`_strategies.py`** — `register_strategy()` and `register_strategy_factory()` for custom types; `_strategy_for_type` generates Hypothesis strategies from type hints (primitives, unions, tuples, lists, dicts, sets, dataclasses with depth limiting)
- **`_engine.py`** — `check_module`: two-phase approach per function (smoke test + equivalence test via counterexample search and randomized verification); `on_result` callback for live progress; `ObligationResult` dataclass with `duration_s` timing; outputs JSON reports
- **`_cli.py`** — `main()` with argparse; `-v`/`-q`/`--json`/`--no-color` flags; colored status output via `_term.py`; real-time per-obligation printing via `on_result` callback
- **`_term.py`** — Minimal ANSI helper; respects `NO_COLOR` env, `TERM=dumb`, and tty detection; `force_color()` for programmatic override

### How check_module works

For each decorated function, two phases run:

1. **Smoke test** — generate one input satisfying all `@requires`, run the function, check all `@ensures`. Catches obvious contract violations quickly.
2. **Spec equivalence** — if `@against(spec_fn)` is present, search for a counterexample where impl and spec disagree. Uses `hypothesis.find` for a deterministic probe, then a randomized `@given`-based search.

Each phase produces an `ObligationResult` with status `pass`/`fail`/`error`/`skip` and a `duration_s` field. The optional `on_result` callback fires after each result is appended.

### Output files

Two JSON files per module in the output directory:
- `{module}.obligations.json` — array of per-obligation results (status, details, duration_s)
- `{module}.trust.json` — summary with module name, timestamp, and function list

### CLI exit codes

- `0` — all obligations passed (or no decorated functions found)
- `1` — any obligation failed/errored, or module could not be imported

## Examples

`examples/` contains three modules with intentionally buggy implementations:

- **`example_sort.py`** — sort that fails on lists starting with 0; demonstrates `@spec`, `@against`, `@ensures`
- **`example_runs.py`** — run-length grouping that drops the final group; demonstrates multiple `@ensures`
- **`example_intervals.py`** — interval normalizer that fails on adjacent intervals; demonstrates `register_strategy`, `@requires` for custom types

## Key Patterns

- Functions under test must have type annotations (strategies are synthesized from type hints)
- Custom types need strategies registered via `register_strategy()` before `check_module()` runs
- The `@against` decorator accepts `max_examples`, `deadline_ms`, `suppress_health_checks`, and `eq` (custom equality function) parameters
- `@requires` predicates filter generated inputs via `hypothesis.assume()`
- Use `--json` for machine-readable output; use `on_result` callback for programmatic live progress
