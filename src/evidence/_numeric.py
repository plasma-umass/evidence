"""Numeric, data science, and ML support for Evidence.

Provides:
- Strategy synthesis for numpy arrays, pandas DataFrames/Series, PyTorch tensors
- eq="approx" shorthand for approximate equality
- Auto-dispatch to np.allclose / torch.allclose / math.isclose based on return type

All imports are lazy to avoid hard dependencies.

Requires: pip install evidence[numeric]  (numpy, pandas)
          pip install evidence[ml]  (torch)
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any


def approx_eq(a: Any, b: Any, *, rtol: float = 1e-5, atol: float = 1e-8) -> bool:
    """Approximate equality that auto-dispatches based on type.

    Handles:
    - numpy arrays: np.allclose
    - torch tensors: torch.allclose
    - pandas Series/DataFrames: element-wise approx comparison
    - Python floats: math.isclose
    - Iterables: recursive element-wise comparison
    - Exact types: ==
    """
    # numpy array
    try:
        import numpy as np
        if isinstance(a, np.ndarray) or isinstance(b, np.ndarray):
            return bool(np.allclose(a, b, rtol=rtol, atol=atol, equal_nan=True))
    except ImportError:
        pass

    # torch tensor
    try:
        import torch  # type: ignore[import-not-found]
        if isinstance(a, torch.Tensor) or isinstance(b, torch.Tensor):
            if not isinstance(a, torch.Tensor):
                a = torch.tensor(a)
            if not isinstance(b, torch.Tensor):
                b = torch.tensor(b)
            return bool(torch.allclose(a, b, rtol=rtol, atol=atol))
    except ImportError:
        pass

    # pandas
    try:
        import pandas as pd  # type: ignore[import-untyped]
        if isinstance(a, (pd.Series, pd.DataFrame)):
            if isinstance(a, pd.DataFrame):
                try:
                    import numpy as np
                    return bool(np.allclose(a.values, b.values, rtol=rtol, atol=atol, equal_nan=True))
                except Exception:
                    return bool(a.equals(b))
            else:
                try:
                    import numpy as np
                    return bool(np.allclose(a.values, b.values, rtol=rtol, atol=atol, equal_nan=True))
                except Exception:
                    return bool(a.equals(b))
    except ImportError:
        pass

    # Python float
    if isinstance(a, float) and isinstance(b, float):
        return math.isclose(a, b, rel_tol=rtol, abs_tol=atol)

    # Iterables (list, tuple)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        if len(a) != len(b):
            return False
        return all(approx_eq(ai, bi, rtol=rtol, atol=atol) for ai, bi in zip(a, b, strict=True))

    # Fallback to exact equality
    return bool(a == b)


def register_numeric_strategies() -> None:
    """Register Hypothesis strategies for numpy, pandas, and torch types.

    Safe to call even if these packages aren't installed — skips silently.
    """
    from evidence._strategies import register_strategy_factory

    # numpy arrays
    try:
        import numpy as np
        from hypothesis.extra.numpy import arrays

        def numpy_array_factory(*, max_list_size: int = 20, depth: int = 0) -> Any:
            from hypothesis import strategies as st
            return arrays(
                dtype=st.sampled_from([np.float64, np.float32, np.int64, np.int32]),
                shape=st.tuples(
                    st.integers(min_value=0, max_value=max_list_size),
                ),
                elements=st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
            )

        register_strategy_factory(np.ndarray, numpy_array_factory)
    except ImportError:
        pass

    # pandas Series
    try:
        import pandas as pd
        from hypothesis.extra.pandas import series

        def pandas_series_factory(*, max_list_size: int = 20, depth: int = 0) -> Any:
            from hypothesis import strategies as st
            return series(
                dtype=float,
                elements=st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
            )

        register_strategy_factory(pd.Series, pandas_series_factory)
    except ImportError:
        pass

    # pandas DataFrame
    try:
        import pandas as pd
        from hypothesis.extra.pandas import column, data_frames

        def pandas_df_factory(*, max_list_size: int = 20, depth: int = 0) -> Any:
            from hypothesis import strategies as st
            return data_frames(
                columns=[
                    column("a", dtype=float, elements=st.floats(-1e6, 1e6, allow_nan=False, allow_infinity=False)),
                    column("b", dtype=float, elements=st.floats(-1e6, 1e6, allow_nan=False, allow_infinity=False)),
                ],
            )

        register_strategy_factory(pd.DataFrame, pandas_df_factory)
    except ImportError:
        pass

    # torch Tensor
    try:
        import torch

        def torch_tensor_factory(*, max_list_size: int = 20, depth: int = 0) -> Any:
            from hypothesis import strategies as st
            return st.lists(
                st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
                min_size=1,
                max_size=max_list_size,
            ).map(lambda xs: torch.tensor(xs, dtype=torch.float32))

        register_strategy_factory(torch.Tensor, torch_tensor_factory)
    except ImportError:
        pass


def resolve_eq(eq: str | Callable[[Any, Any], bool] | None) -> Callable[[Any, Any], bool]:
    """Resolve an eq parameter, supporting the 'approx' shorthand.

    Args:
        eq: Either None (use ==), "approx" (use approx_eq), or a callable.

    Returns:
        A callable equality function.
    """
    if eq is None:
        return lambda a, b: a == b
    if eq == "approx":
        return approx_eq
    if callable(eq):
        return eq
    raise ValueError(f"Invalid eq parameter: {eq!r}. Expected None, 'approx', or a callable.")
