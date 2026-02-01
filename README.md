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
| `eq` | `None` | Custom equality: a callable `(a, b) -> bool`, or `"approx"` for floating-point tolerance |

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

### `@pure` / `@pure(seed=N, eq=fn)`

Marks a function as pure (no side effects, deterministic). Evidence runs both
static AST analysis (detecting I/O, global mutation, nondeterminism) and
dynamic verification (calling the function twice with identical inputs and
comparing outputs).

```python
@pure
def double(x: int) -> int:
    return x * 2

@pure(seed=42)  # seed-deterministic: seeds PRNGs before each call
def sample(x: int) -> int:
    import random
    return x + random.randint(0, 10)
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
| `--coverage` | Measure line/branch coverage per function (requires `pip install evidence[coverage]`) |
| `--mutate` | Run mutation testing and report mutation score |
| `--prove` | Attempt symbolic verification via CrossHair/Z3 (requires `pip install evidence[prove]`) |
| `--suggest` | Use an LLM to suggest postconditions and specs (requires `pip install evidence[suggest]`) |
| `--infer` | Infer structural properties from function behavior |

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

## Advanced features

### Coverage reporting (`--coverage`)

Measures line and branch coverage per function during test execution using
[coverage.py](https://coverage.readthedocs.io/).

```bash
python -m evidence example_sort --coverage -v
```

### Mutation testing (`--mutate`)

Generates AST-level mutants of each function (7 operators: flip comparisons,
swap arithmetic, negate conditions, delete statements, change constants, swap
boolean ops, remove return values) and checks whether Evidence's contracts and
specs catch them. Reports a mutation score.

```bash
python -m evidence example_sort --mutate -v
```

### Symbolic verification (`--prove`)

Attempts to symbolically prove function correctness using the
[CrossHair](https://github.com/pschanely/CrossHair) solver backend via
`hypothesis-crosshair`. Results are `verified`, `disproved`, or `inconclusive`.

```bash
pip install evidence[prove]
python -m evidence example_sort --prove -v
```

### Spec inference (`--infer`)

Automatically infers structural properties of functions via quick Hypothesis
runs and docstring mining. Checks for shape preservation, sortedness,
idempotence, involution, and more.

```bash
python -m evidence example_sort --infer -v
```

### LLM-assisted spec mining (`--suggest`)

Uses the Anthropic API to suggest postconditions and reference specifications,
then validates them. Requires `ANTHROPIC_API_KEY` in the environment.

```bash
pip install evidence[suggest]
python -m evidence example_sort --suggest -v
```

### Numeric/ML support (`eq="approx"`)

For floating-point and numeric code, use `eq="approx"` with `@against` for
approximate equality. Auto-dispatches to `np.allclose`, `torch.allclose`, or
`math.isclose` based on return type.

```python
from evidence import against, spec
from evidence._numeric import register_numeric_strategies

register_numeric_strategies()  # registers numpy/pandas/torch strategies

@spec
def softmax_spec(xs: list[float]) -> list[float]:
    ...

@against(softmax_spec, eq="approx")
def softmax(xs: list[float]) -> list[float]:
    ...
```

### Optional dependency groups

```bash
pip install evidence[coverage]   # coverage.py
pip install evidence[prove]      # hypothesis-crosshair, crosshair-tool
pip install evidence[suggest]    # anthropic
pip install evidence[numeric]    # numpy, pandas
pip install evidence[ml]         # torch
pip install evidence[all]        # everything
```

## How it works

For each decorated function, Evidence runs two phases:

1. **Smoke test** -- generate a single input satisfying all `@requires`
   preconditions, run the function, and check all `@ensures` postconditions.
   This catches obvious contract violations quickly.

2. **Spec equivalence** -- if `@against(spec_fn)` is present, search for a
   counterexample where the implementation and spec disagree. This uses
   `hypothesis.find` for a deterministic probe, then falls back to a randomized
   `@given`-based search for higher confidence. When a counterexample is found,
   Hypothesis shrinks it to a minimal failing input.

Optional phases (enabled via CLI flags) add purity checking, coverage
measurement, mutation testing, symbolic verification, property inference, and
LLM-assisted spec mining.

## Examples

The `examples/` directory contains 10 modules with intentionally buggy
implementations that Evidence catches:

| Module | Domain | Bugs | Features demonstrated |
|--------|--------|------|----------------------|
| `example_sort` | Sorting | Fails on lists starting with `0` | `@spec`, `@against`, `@ensures` |
| `example_runs` | Run-length grouping | Drops the final group | Multiple `@ensures` |
| `example_intervals` | Interval merging | Fails on adjacent intervals | `register_strategy`, `@requires` for custom types |
| `example_numeric` | Numeric/ML | Softmax overflow on large inputs | `@pure`, `eq="approx"`, numeric strategies |
| `example_strings` | Text processing | Whitespace splitting, palindrome filter, RLE off-by-one | `@spec`, `@against`, `@ensures` |
| `example_math` | Number theory | GCD sign bug, Fibonacci off-by-one | `@pure`, `@requires`, `@ensures` |
| `example_sets` | Collections | `unique()` loses order, `intersect()` leaks duplicates | `@spec`, multiple postconditions |
| `example_stack` | Data structures | `push_many()` reverses order | Dataclass usage, `@ensures` |
| `example_search` | Search algorithms | Binary search off-by-one, closest-element misses neighbor | `@pure`, sorted-input `@requires` |
| `example_compression` | Encoding | Checksum uses XOR instead of sum | `@pure`, round-trip properties |

Run any of them:

```bash
cd examples
python -m evidence example_sort -v
python -m evidence example_math -v --mutate --infer
python -m evidence example_compression -v --coverage
```
