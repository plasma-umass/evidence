from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any

from hypothesis import HealthCheck

from evidence._bundle import _bundle, _check_ensures, _check_requires, _root_original, _set_original
from evidence._util import _qualified_name


def requires(pred: Callable[..., bool]) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        _bundle(fn)["requires"].append(pred)

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            ok, err = _check_requires(fn, args, kwargs)
            if not ok:
                raise AssertionError(f"Precondition failed for {_qualified_name(_root_original(fn))}: {err}")
            return fn(*args, **kwargs)

        _set_original(wrapper, fn)
        return wrapper

    return deco


def ensures(pred: Callable[..., bool]) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        _bundle(fn)["ensures"].append(pred)

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            ok, err = _check_requires(fn, args, kwargs)
            if not ok:
                raise AssertionError(f"Precondition failed for {_qualified_name(_root_original(fn))}: {err}")
            result = fn(*args, **kwargs)
            ok2, err2 = _check_ensures(fn, args, kwargs, result)
            if not ok2:
                raise AssertionError(f"Postcondition failed for {_qualified_name(_root_original(fn))}: {err2}")
            return result

        _set_original(wrapper, fn)
        return wrapper

    return deco


def spec(fn: Callable[..., Any]) -> Callable[..., Any]:
    _bundle(fn)["is_spec"] = True
    return fn


def pure(
    fn: Callable[..., Any] | None = None,
    *,
    seed: int | None = None,
    eq: Callable[[Any, Any], bool] | None = None,
) -> Callable[..., Any]:
    """Assert function purity via static analysis and dynamic verification.

    Two modes:

    **Strict purity** (``@pure``):
        No IO, no non-determinism, no global mutation. Same inputs always
        produce the same output. Static analysis flags any use of random,
        datetime.now, print, etc.

    **Seed-deterministic purity** (``@pure(seed=42)``):
        The function may use randomness internally but is deterministic
        when seeds (random, numpy, torch) are fixed. Static analysis
        *permits* random/PRNG usage but still flags IO and global mutation.
        Dynamic check seeds all PRNGs before each invocation.

    Args:
        seed: If set, treat the function as seed-deterministic rather than
              strictly pure. PRNGs are seeded to this value before each call.
        eq:   Custom equality for comparing outputs across calls.
              Useful for approximate equality with numeric/ML outputs.
    """
    def _apply(f: Callable[..., Any]) -> Callable[..., Any]:
        _bundle(f)["pure"] = {"seed": seed, "eq": eq}
        return f

    if fn is not None:
        # Used as @pure without arguments
        return _apply(fn)
    # Used as @pure(seed=42) — return decorator
    return _apply


def against(
    spec_fn: Callable[..., Any],
    *,
    eq: Callable[[Any, Any], bool] | str | None = None,
    max_examples: int = 200,
    deadline_ms: int | None = None,
    suppress_health_checks: tuple[HealthCheck, ...] = (
        HealthCheck.too_slow,
        HealthCheck.filter_too_much,
    ),
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    # Resolve eq="approx" shorthand
    resolved_eq = eq
    if isinstance(eq, str):
        from evidence._numeric import resolve_eq
        resolved_eq = resolve_eq(eq)

    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        _bundle(fn)["against"] = {
            "spec": spec_fn,
            "eq": resolved_eq,
            "max_examples": max_examples,
            "deadline_ms": deadline_ms,
            "suppress_health_checks": suppress_health_checks,
        }
        return fn

    return deco
