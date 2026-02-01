"""Example: numeric functions with Evidence.

Demonstrates:
- numpy array strategies (auto-registered)
- eq="approx" for floating-point comparisons
- @pure and @pure(seed=42) for purity checking
- Shape and dtype contracts
"""

from __future__ import annotations

import numpy as np

from evidence import against, ensures, pure, requires, spec
from evidence._numeric import register_numeric_strategies

# Register strategies for numpy/pandas/torch types
register_numeric_strategies()


# ---------- Sorting ----------

@spec
def sort_spec(xs: list[float]) -> list[float]:
    """Reference: sort a list of floats."""
    return sorted(xs)


@pure
@against(sort_spec, eq="approx", max_examples=500)
@ensures(lambda xs, result: len(result) == len(xs))
def sort_floats(xs: list[float]) -> list[float]:
    """Sort a list of floats — intentionally correct."""
    return sorted(xs)


# ---------- Softmax ----------

def _softmax_spec(xs: list[float]) -> list[float]:
    """Reference softmax: numerically stable."""
    if not xs:
        return []
    m = max(xs)
    exps = [np.exp(x - m) for x in xs]
    total = sum(exps)
    return [float(e / total) for e in exps]


@pure
@against(_softmax_spec, eq="approx", max_examples=300)
@requires(lambda xs: len(xs) > 0)
@requires(lambda xs: all(-100 <= x <= 100 for x in xs))
@ensures(lambda xs, result: len(result) == len(xs))
@ensures(lambda xs, result: all(r >= 0 for r in result))
@ensures(lambda xs, result: abs(sum(result) - 1.0) < 1e-6)
def softmax(xs: list[float]) -> list[float]:
    """Softmax with a subtle bug: missing numeric stability shift."""
    # BUG: doesn't subtract max — will overflow for large inputs
    exps = [np.exp(x) for x in xs]
    total = sum(exps)
    return [float(e / total) for e in exps]
