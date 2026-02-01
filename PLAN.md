# Evidence Roadmap

## High-Level Goal

Transform Evidence from a property-testing framework into a comprehensive correctness toolkit that can **test**, **measure**, **prove**, and **infer** specifications for Python functions — including numeric, data science, and ML workloads. All new capabilities are opt-in via CLI flags and optional dependencies.

## Features (in priority order)

### 1. Shrunk Counterexamples
Capture the minimal failing input directly from Hypothesis's shrinking pass instead of re-running a second search. Fixes a correctness and performance issue in `_engine.py`.

**Files**: `_engine.py`

### 2. `@pure` Decorator (static + dynamic)
Assert function purity via two layers:
- **Static**: AST analysis detecting transitive use of IO (`print`, `open`, `sys.stdout`), non-determinism (`random.*`, `time.time`, `datetime.now`), hash/address-dependent operations (`id`, `hash`, `repr`), and global mutation (`setattr`, `exec`). Recursively follows calls to user-defined functions in the same module.
- **Dynamic**: Call function twice with identical inputs, assert outputs match. Capture stdout/stderr to detect IO. Support `@pure(seed=42)` for ML functions that are deterministic given a seed.

**Files**: `_purity.py` (new), `_bundle.py`, `_decorators.py`, `_engine.py`, `__init__.py`

### 3. Coverage Reporting (`--coverage`)
Wrap test execution with `coverage.py` to measure line/branch coverage per function. Isolate to function's source lines via `inspect.getsourcelines`. Optional dep: `coverage>=7.0`.

**Files**: `_coverage.py` (new), `_engine.py`, `_cli.py`, `pyproject.toml`

### 4. Mutation Testing (`--mutate`)
Lightweight AST-based mutator (7 operators: flip comparisons, swap arithmetic, negate conditions, delete statements, change constants, swap boolean ops, remove return values). For each mutant, check if Evidence catches it. Report mutation score per function. No external deps (stdlib `ast` only).

**Files**: `_mutate.py` (new), `_engine.py`, `_cli.py`

### 5. CrossHair/Z3 Symbolic Verification (`--prove`)
Use the `hypothesis-crosshair` backend to attempt symbolic proof. Cleanest integration since Evidence already uses Hypothesis — just switch the backend. Results: "verified" (proven), "disproved" (symbolic counterexample), or "inconclusive". Optional deps: `hypothesis-crosshair`, `crosshair-tool`.

**Files**: `_symbolic.py` (new), `_engine.py`, `_cli.py`, `pyproject.toml`

### 6. LLM-Assisted Spec Mining (`--suggest`)
`SpecSuggester` protocol with `ClaudeSuggester` default implementation. Given function source + existing contracts + mutation score, suggests `@ensures` postconditions and full `@spec` reference implementations. All suggestions validated by running Evidence checks before presenting. Optional dep: `anthropic>=0.40`.

**Files**: `_suggest.py` (new), `_cli.py`, `__init__.py`, `pyproject.toml`

### 7. Spec Inference from Existing Code (`--infer`)
Three inference strategies:
- **Structural** (no LLM): test for shape preservation, monotonicity, idempotence, involution, conservation, sortedness via quick Hypothesis runs (~200 examples each)
- **Docstring mining**: regex patterns extracting contract-like statements from docstrings
- **LLM-assisted**: feed structural properties + source to LLM to synthesize full `@spec`, validated against 500+ examples

**Files**: `_infer.py` (new), `_suggest.py` (modify), `_cli.py` (modify)

### 8. Numeric, Data Science & ML Support
- **Strategy synthesis** for numpy arrays, pandas DataFrames/Series, PyTorch/JAX tensors (lazy imports, via `hypothesis.extra.numpy`/`hypothesis.extra.pandas` + torch/jax wrappers)
- **`eq="approx"`** shorthand in `@against` — auto-dispatches to `np.allclose`/`torch.allclose`/`math.isclose` based on return type
- **`@pure(seed=42)`** for seed-deterministic ML functions
- **Documented idioms** for shape contracts, dtype contracts, gradient checking
- **Example**: `examples/example_numeric.py` with numpy sorting, softmax, seeded random

**Files**: `_numeric.py` (new), `_strategies.py`, `_decorators.py`, `_engine.py`, `pyproject.toml`, `examples/example_numeric.py` (new)

## New CLI Flags

| Flag | Feature | Requires |
|------|---------|----------|
| `--coverage` | Line/branch coverage per function | `pip install evidence[coverage]` |
| `--mutate` | Mutation testing score | (no extra deps) |
| `--prove` | Z3 symbolic verification | `pip install evidence[prove]` |
| `--suggest` | LLM spec suggestions | `pip install evidence[suggest]` + `ANTHROPIC_API_KEY` |
| `--infer` | Structural spec inference | (no extra deps for structural; LLM part uses `--suggest`) |

## Optional Dependency Groups

```toml
[project.optional-dependencies]
coverage = ["coverage>=7.0"]
prove = ["hypothesis-crosshair>=0.0.18", "crosshair-tool>=0.0.77"]
suggest = ["anthropic>=0.40"]
numeric = ["numpy>=1.24", "pandas>=2.0"]
ml = ["torch>=2.0"]
all = ["coverage>=7.0", "hypothesis-crosshair>=0.0.18", "crosshair-tool>=0.0.77", "anthropic>=0.40", "numpy>=1.24", "pandas>=2.0"]
```

## New Files

| File | Feature |
|------|---------|
| `src/evidence/_purity.py` | 2 |
| `src/evidence/_coverage.py` | 3 |
| `src/evidence/_mutate.py` | 4 |
| `src/evidence/_symbolic.py` | 5 |
| `src/evidence/_suggest.py` | 6, 7 |
| `src/evidence/_infer.py` | 7 |
| `src/evidence/_numeric.py` | 8 |
| `examples/example_numeric.py` | 8 |

## Verification

```bash
cd examples && python -m evidence example_sort -v          # Feature 1: shrunk counterexamples
python -m evidence example_numeric -v                       # Feature 2: @pure
pip install -e ".[coverage]" && python -m evidence example_sort --coverage -v  # Feature 3
python -m evidence example_sort --mutate -v                 # Feature 4
pip install -e ".[prove]" && python -m evidence example_sort --prove -v        # Feature 5
pip install -e ".[suggest]" && python -m evidence example_sort --suggest       # Feature 6
python -m evidence example_sort --infer                     # Feature 7
pip install -e ".[numeric]" && python -m evidence example_numeric -v           # Feature 8
ruff check src/ examples/ && mypy src/evidence/             # Lint + types
```
