# Evidence

Specification-based property testing for Python.

Evidence uses [Hypothesis](https://hypothesis.readthedocs.io/) to automatically
generate test cases and verify that your function implementations satisfy their
contracts (preconditions and postconditions) and match reference specifications.

## Installation

Requires Python 3.10+.

```bash
pip install -e .

# With dev tools (ruff, mypy)
pip install -e ".[dev]"
```

## Quick start

Write a reference specification with `@spec`, then annotate your implementation
with `@against` and optional `@requires`/`@ensures` contracts:

```python
from evidence import against, ensures, spec

@spec
def sort_spec(xs: list[int]) -> list[int]:
    return sorted(xs)

@against(sort_spec, max_examples=500)
@ensures(lambda xs, result: len(result) == len(xs))
def sort(xs: list[int]) -> list[int]:
    ...  # your implementation
```

Run the checker:

```bash
evidence example_sort
# or
python -m evidence example_sort
```

Evidence will generate random inputs, check that preconditions are satisfiable,
postconditions hold, and the implementation agrees with the spec. It reports any
counterexamples it finds.

## Decorators

### `@spec`

Marks a function as a reference specification. Spec functions are not tested
themselves -- they serve as the ground truth for `@against`.

```python
@spec
def my_spec(x: int, y: int) -> int:
    ...
```

### `@against(spec_fn, *, max_examples=200, deadline_ms=None, suppress_health_checks=(...), eq=None)`

Declares that the decorated function should produce the same output as
`spec_fn` for all valid inputs. Evidence will search for a counterexample where
the two disagree.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `spec_fn` | (required) | The `@spec`-decorated reference function |
| `max_examples` | `200` | Number of Hypothesis examples for the randomized pass |
| `deadline_ms` | `None` | Per-example time limit in milliseconds |
| `suppress_health_checks` | `(too_slow, filter_too_much)` | Hypothesis health checks to suppress |
| `eq` | `None` | Custom equality function `(impl_result, spec_result) -> bool` |

### `@requires(pred)`

Adds a precondition. `pred` receives the same arguments as the decorated
function and returns a bool. Generated inputs that violate the precondition are
filtered out (via `hypothesis.assume`). Multiple `@requires` can be stacked.

```python
@requires(lambda xs: len(xs) > 0)
@requires(lambda xs: all(x >= 0 for x in xs))
def my_func(xs: list[int]) -> int:
    ...
```

### `@ensures(pred)`

Adds a postcondition. `pred` receives the original arguments followed by the
return value, and returns a bool. Multiple `@ensures` can be stacked.

```python
@ensures(lambda xs, result: len(result) == len(xs))
@ensures(lambda xs, result: all(x in xs for x in result))
def my_func(xs: list[int]) -> list[int]:
    ...
```

## Custom type strategies

Evidence synthesizes Hypothesis strategies from type annotations. Built-in
types (`int`, `str`, `float`, `bool`, `list`, `dict`, `set`, `tuple`, unions,
and dataclasses) are handled automatically.

For custom types, register a strategy before calling `check_module`:

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

You can also register a factory function with `register_strategy_factory` for
types that need parameterized strategies.

## CLI usage

```
evidence <module> [options]
```

The module must be importable (i.e., on `sys.path`). Running from the directory
containing the module or using `pip install -e .` is the easiest way.

### Options

| Flag | Description |
|------|-------------|
| `--out DIR` | Output directory for JSON reports (default: `.evidence`) |
| `--max-list-size N` | Max size for generated lists/collections (default: `20`) |
| `--smoke-max-list-size N` | Max size for smoke-test generation (default: `5`) |
| `-v`, `--verbose` | Show counterexample details (kwargs, impl vs spec output) and per-obligation timing |
| `-q`, `--quiet` | Suppress per-obligation lines; only print the summary and set the exit code |
| `--json` | Print results as a JSON array to stdout; suppresses human-readable output |
| `--no-color` | Disable ANSI colors (also respected via the `NO_COLOR` environment variable) |

### Exit codes

- `0` -- all obligations passed (or no decorated functions found)
- `1` -- one or more obligations failed or errored, or the module could not be imported

### Default output

```
  PASS  contracts_smoke         example_sort.sort_spec
  SKIP  equiv_to_spec           example_sort.sort_spec
 ERROR  contracts_smoke         example_sort.sort
  FAIL  equiv_to_spec           example_sort.sort

1 passed, 2 failed, 1 skipped  (0.4s total)  JSON reports in .evidence/
```

### Verbose mode (`-v`)

Failures include inline counterexample details:

```
  FAIL  equiv_to_spec           example_sort.sort  (1.2s)
         kwargs: {"xs": [0, 3, 1]}
         impl:   [0, 3, 1]
         spec:   [0, 1, 3]
```

### Quiet mode (`-q`)

Only the summary line is printed. Useful in CI pipelines where you only care
about the exit code.

### JSON mode (`--json`)

Prints a JSON array of result objects to stdout, suitable for machine
consumption or piping into other tools:

```json
[
  {
    "function": "example_sort.sort",
    "obligation": "equiv_to_spec",
    "status": "fail",
    "details": { ... },
    "duration_s": 0.042
  }
]
```

## JSON reports

Each run writes two files to the output directory (default `.evidence/`):

- **`<module>.obligations.json`** -- array of per-obligation results with
  status (`pass`, `fail`, `error`, `skip`), details, and timing.
- **`<module>.trust.json`** -- summary with module name, timestamp, and the
  list of functions that were checked.

## How it works

For each decorated function, Evidence runs two phases:

1. **Smoke test** -- generate a single input satisfying all `@requires`
   preconditions, run the function, and check all `@ensures` postconditions.
   This catches obvious contract violations quickly.

2. **Spec equivalence** -- if `@against(spec_fn)` is present, search for a
   counterexample where the implementation and spec disagree. This uses
   `hypothesis.find` for a deterministic probe, then falls back to a randomized
   `@given`-based search for higher confidence.

## Examples

The `examples/` directory contains three modules with intentionally buggy
implementations:

- **`example_sort.py`** -- a sort that fails on lists starting with `0`
- **`example_runs.py`** -- a run-length grouping that drops the final group
- **`example_intervals.py`** -- an interval normalizer that fails to merge
  adjacent (non-overlapping) intervals; also demonstrates `register_strategy`
  and `@requires` for custom types

Run any of them to see Evidence catch the bugs:

```bash
cd examples
python -m evidence example_sort -v
python -m evidence example_runs -v
python -m evidence example_intervals -v
```
