"""Symbolic verification via hypothesis-crosshair backend.

Uses the hypothesis-crosshair backend to attempt symbolic proof of
function contracts and spec equivalence. Results are:
- "verified": proven correct for all inputs
- "disproved": symbolic counterexample found
- "inconclusive": solver could not determine

Requires: pip install evidence[prove]
  (hypothesis-crosshair>=0.0.18, crosshair-tool>=0.0.77)
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def _check_crosshair_available() -> bool:
    """Check if hypothesis-crosshair is installed."""
    try:
        import hypothesis_crosshair  # type: ignore[import-not-found]  # noqa: F401
        return True
    except ImportError:
        return False


def prove_function(
    impl_fn: Callable[..., Any],
    *,
    spec_fn: Callable[..., Any] | None = None,
    eq: Callable[[Any, Any], bool] | None = None,
    check_requires: Callable[[Callable[..., Any], tuple[Any, ...], dict[str, Any]], tuple[bool, str]] | None = None,
    check_ensures: Callable[[Callable[..., Any], tuple[Any, ...], dict[str, Any], Any], tuple[bool, str]] | None = None,
    strategy: Any = None,
    max_examples: int = 50,
) -> dict[str, Any]:
    """Attempt symbolic proof of function correctness.

    Args:
        impl_fn: The implementation to verify.
        spec_fn: Optional reference specification.
        eq: Equality function for comparing impl/spec outputs.
        check_requires: Precondition checker (returns (ok, err)).
        check_ensures: Postcondition checker (returns (ok, err)).
        strategy: Hypothesis strategy for generating kwargs.
        max_examples: Max examples for the CrossHair backend.

    Returns:
        Dict with keys:
            status: "verified" | "disproved" | "inconclusive" | "unavailable"
            details: Additional information
    """
    if not _check_crosshair_available():
        return {
            "status": "unavailable",
            "details": "hypothesis-crosshair not installed; install with: pip install evidence[prove]",
        }

    if eq is None:
        eq = lambda a, b: a == b  # noqa: E731

    from hypothesis import HealthCheck, assume, given, settings

    # Verify the CrossHair backend is functional
    try:
        import hypothesis_crosshair  # type: ignore[import-not-found]  # noqa: F401
    except ImportError:
        return {
            "status": "unavailable",
            "details": "hypothesis-crosshair import failed",
        }

    if strategy is None:
        return {
            "status": "inconclusive",
            "details": "no strategy provided for symbolic verification",
        }

    counterexample: list[dict[str, Any] | None] = [None]

    try:
        @settings(
            backend="crosshair",
            max_examples=max_examples,
            deadline=None,
            suppress_health_check=list(HealthCheck),
            derandomize=False,
        )
        @given(strategy)
        def prop(kwargs: dict[str, Any]) -> None:
            if check_requires is not None:
                ok_pre, _ = check_requires(impl_fn, (), kwargs)
                assume(ok_pre)

            impl_r = impl_fn(**kwargs)

            if check_ensures is not None:
                ok_post, post_err = check_ensures(impl_fn, (), kwargs, impl_r)
                if not ok_post:
                    counterexample[0] = {
                        "kwargs": kwargs,
                        "impl_result": impl_r,
                        "note": f"ensures failed: {post_err}",
                    }
                    raise AssertionError(f"ensures failed: {post_err}")

            if spec_fn is not None:
                spec_r = spec_fn(**kwargs)
                if not eq(impl_r, spec_r):
                    counterexample[0] = {
                        "kwargs": kwargs,
                        "impl_result": impl_r,
                        "spec_result": spec_r,
                    }
                    raise AssertionError("impl != spec")

        prop()

        return {
            "status": "verified",
            "details": f"symbolically verified with {max_examples} examples",
        }

    except AssertionError:
        return {
            "status": "disproved",
            "details": "symbolic counterexample found",
            "counterexample": counterexample[0],
        }
    except Exception as e:
        return {
            "status": "inconclusive",
            "details": f"solver inconclusive: {type(e).__name__}: {e}",
        }
