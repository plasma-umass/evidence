"""Static and dynamic purity analysis for Evidence.

Static analysis uses AST inspection to detect impure operations:
- IO: print, open, sys.stdout, sys.stderr, input
- Non-determinism: random.*, time.time, datetime.now
- Hash/address-dependent: id, hash, repr (on mutable objects)
- Global mutation: setattr, exec, eval, globals()

Dynamic analysis calls the function twice with identical inputs
and asserts outputs match. Captures stdout/stderr to detect IO.
"""

from __future__ import annotations

import ast
import inspect
import io
import sys
import textwrap
from collections.abc import Callable
from typing import Any

# Functions / attributes considered impure (static analysis)
_IO_NAMES: frozenset[str] = frozenset({
    "print", "open", "input",
})

_IO_ATTRS: frozenset[str] = frozenset({
    "sys.stdout", "sys.stderr", "sys.stdin",
    "stdout.write", "stderr.write",
})

_NONDETERMINISM_NAMES: frozenset[str] = frozenset({
    "random", "time.time", "datetime.now", "uuid4", "uuid1",
})

_NONDETERMINISM_MODULES: frozenset[str] = frozenset({
    "random",
})

_HASH_ADDR_NAMES: frozenset[str] = frozenset({
    "id", "hash",
})

_GLOBAL_MUTATION_NAMES: frozenset[str] = frozenset({
    "setattr", "delattr", "exec", "eval", "globals",
    "__import__",
})


class ImpurityWarning:
    """A single detected impurity in static analysis."""

    __slots__ = ("category", "description", "lineno")

    def __init__(self, category: str, description: str, lineno: int | None = None) -> None:
        self.category = category
        self.description = description
        self.lineno = lineno

    def __repr__(self) -> str:
        loc = f" (line {self.lineno})" if self.lineno is not None else ""
        return f"ImpurityWarning({self.category}: {self.description}{loc})"


def _get_called_name(node: ast.expr) -> str | None:
    """Extract a dotted name from a Call node's func attribute."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _get_called_name(node.value)
        if prefix is not None:
            return f"{prefix}.{node.attr}"
        return node.attr
    return None


def static_purity_check(
    fn: Callable[..., Any],
    *,
    seed_deterministic: bool = False,
) -> list[ImpurityWarning]:
    """Analyze function source via AST for impure operations.

    Args:
        fn: The function to analyze.
        seed_deterministic: If True, non-determinism warnings (random, time,
            etc.) are suppressed since the function is expected to use PRNGs
            but be deterministic given a fixed seed. IO and global mutation
            warnings are still reported.

    Returns a list of ImpurityWarning objects. Empty list means no
    impurities detected (not a guarantee of purity).
    """
    try:
        source = inspect.getsource(fn)
    except (OSError, TypeError):
        return [ImpurityWarning("unknown", "could not retrieve source")]

    source = textwrap.dedent(source)
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return [ImpurityWarning("unknown", "could not parse source")]

    warnings: list[ImpurityWarning] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = _get_called_name(node.func)
            if name is None:
                continue

            # Check IO
            if name in _IO_NAMES:
                warnings.append(ImpurityWarning("io", f"call to {name}", getattr(node, "lineno", None)))
            # Check IO attribute access (e.g., sys.stdout.write)
            for attr in _IO_ATTRS:
                if name.endswith(attr):
                    warnings.append(ImpurityWarning("io", f"call to {name}", getattr(node, "lineno", None)))
                    break

            # Check non-determinism (skip if seed-deterministic mode)
            if not seed_deterministic:
                if name in _NONDETERMINISM_NAMES:
                    warnings.append(
                        ImpurityWarning("nondeterminism", f"call to {name}", getattr(node, "lineno", None))
                    )
                parts = name.split(".")
                if parts[0] in _NONDETERMINISM_MODULES:
                    warnings.append(
                        ImpurityWarning("nondeterminism", f"call to {name}", getattr(node, "lineno", None))
                    )

            # Check hash/address-dependent
            if name in _HASH_ADDR_NAMES:
                warnings.append(ImpurityWarning("hash_addr", f"call to {name}", getattr(node, "lineno", None)))

            # Check global mutation
            if name in _GLOBAL_MUTATION_NAMES:
                warnings.append(
                    ImpurityWarning("global_mutation", f"call to {name}", getattr(node, "lineno", None))
                )

        # Also flag global/nonlocal keywords
        elif isinstance(node, ast.Global):
            warnings.append(
                ImpurityWarning(
                    "global_mutation",
                    f"global statement: {', '.join(node.names)}",
                    getattr(node, "lineno", None),
                )
            )
        elif isinstance(node, ast.Nonlocal):
            warnings.append(
                ImpurityWarning(
                    "global_mutation",
                    f"nonlocal statement: {', '.join(node.names)}",
                    getattr(node, "lineno", None),
                )
            )

    return warnings


def dynamic_purity_check(
    fn: Callable[..., Any],
    kwargs: dict[str, Any],
    *,
    eq: Callable[[Any, Any], bool] | None = None,
    seed: int | None = None,
) -> tuple[bool, str]:
    """Call fn twice with identical inputs; assert outputs match and no stdout/stderr.

    If seed is provided, sets random.seed(seed) + numpy/torch seeds before each call.

    Returns (is_pure, error_message). error_message is empty if pure.
    """
    import copy

    if eq is None:
        eq = lambda a, b: a == b  # noqa: E731

    def _set_seeds(s: int) -> None:
        import random
        random.seed(s)
        try:
            import numpy as np
            np.random.seed(s)  # type: ignore[attr-defined]
        except ImportError:
            pass
        try:
            import torch  # type: ignore[import-not-found]
            torch.manual_seed(s)
        except ImportError:
            pass

    kwargs1 = copy.deepcopy(kwargs)
    kwargs2 = copy.deepcopy(kwargs)

    # First call
    if seed is not None:
        _set_seeds(seed)
    old_stdout, old_stderr = sys.stdout, sys.stderr
    capture1_out = io.StringIO()
    capture1_err = io.StringIO()
    try:
        sys.stdout = capture1_out
        sys.stderr = capture1_err
        result1 = fn(**kwargs1)
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
    stdout1 = capture1_out.getvalue()
    stderr1 = capture1_err.getvalue()

    # Second call
    if seed is not None:
        _set_seeds(seed)
    capture2_out = io.StringIO()
    capture2_err = io.StringIO()
    try:
        sys.stdout = capture2_out
        sys.stderr = capture2_err
        result2 = fn(**kwargs2)
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
    stdout2 = capture2_out.getvalue()
    stderr2 = capture2_err.getvalue()

    errors: list[str] = []

    if not eq(result1, result2):
        errors.append(f"results differ: {result1!r} vs {result2!r}")

    if stdout1 or stdout2:
        errors.append("function produced stdout output")

    if stderr1 or stderr2:
        errors.append("function produced stderr output")

    if errors:
        return False, "; ".join(errors)
    return True, ""
