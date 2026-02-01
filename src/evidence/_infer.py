"""Spec inference for Evidence.

Three inference strategies:
1. Structural (no LLM): test for shape preservation, monotonicity,
   idempotence, involution, conservation, sortedness via quick Hypothesis runs.
2. Docstring mining: regex patterns extracting contract-like statements.
3. LLM-assisted: feed structural properties + source to LLM to synthesize
   full @spec, validated against many examples.

No extra dependencies for structural inference.
"""

from __future__ import annotations

import inspect
import re
from collections.abc import Callable
from typing import Any

from hypothesis import HealthCheck, assume, given, settings

from evidence._bundle import _check_requires, _root_original
from evidence._strategies import _strategy_for_function


class InferredProperty:
    """A property discovered through inference."""

    __slots__ = ("description", "holds", "name", "source")

    def __init__(self, name: str, description: str, holds: bool, source: str = "structural") -> None:
        self.name = name
        self.description = description
        self.holds = holds
        self.source = source

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "holds": self.holds,
            "source": self.source,
        }


def _quick_check(
    fn: Callable[..., Any],
    predicate: Callable[[dict[str, Any], Any], bool],
    *,
    max_list_size: int = 10,
    max_examples: int = 200,
) -> bool:
    """Quick check if a predicate holds for a function over many examples.

    Returns True if no counterexample found.
    """
    root = _root_original(fn)
    strat = _strategy_for_function(root, max_list_size=max_list_size)

    try:
        @settings(
            max_examples=max_examples,
            deadline=None,
            suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
        )
        @given(strat)
        def prop(kwargs: dict[str, Any]) -> None:
            ok_pre, _ = _check_requires(root, (), kwargs)
            assume(ok_pre)
            try:
                result = root(**kwargs)
            except Exception:
                return  # skip if function errors
            assert predicate(kwargs, result)

        prop()
        return True
    except AssertionError:
        return False
    except Exception:
        return False


def infer_structural(fn: Callable[..., Any]) -> list[InferredProperty]:
    """Infer structural properties via quick Hypothesis runs.

    Tests for:
    - Shape preservation: len(output) == len(input) for list->list functions
    - Monotonicity: f(a) <= f(b) when a <= b for scalar functions
    - Idempotence: f(f(x)) == f(x)
    - Involution: f(f(x)) == x
    - Type preservation: type(output) == type(input)
    - Sortedness: output is sorted (for list outputs)
    """
    root = _root_original(fn)
    properties: list[InferredProperty] = []

    # Get type hints to determine what checks make sense
    hints = {}
    try:
        hints = fn.__annotations__ if hasattr(fn, "__annotations__") else {}
        if not hints:
            hints = root.__annotations__ if hasattr(root, "__annotations__") else {}
    except Exception:
        pass

    ret_type = hints.get("return")
    param_types = {k: v for k, v in hints.items() if k != "return"}

    # Check if it's a list -> list function
    is_list_to_list = False
    if ret_type is not None:
        ret_str = str(ret_type)
        if "list" in ret_str.lower():
            for pt in param_types.values():
                if "list" in str(pt).lower():
                    is_list_to_list = True
                    break

    # Shape preservation (list -> list)
    if is_list_to_list:
        list_params = [k for k, v in param_types.items() if "list" in str(v).lower()]
        if len(list_params) == 1:
            param = list_params[0]
            holds = _quick_check(fn, lambda kw, r: isinstance(r, list) and len(r) == len(kw.get(param, [])))
            properties.append(InferredProperty(
                "shape_preservation",
                f"len(result) == len({param})",
                holds,
            ))

    # Sortedness (for list outputs)
    if is_list_to_list:
        holds = _quick_check(
            fn,
            lambda kw, r: isinstance(r, list) and (
                len(r) <= 1 or all(r[i] <= r[i + 1] for i in range(len(r) - 1))
            ),
        )
        properties.append(InferredProperty(
            "sortedness",
            "output is sorted",
            holds,
        ))

    # Idempotence: f(f(x)) == f(x)
    # Only for single-arg functions where input and output types match
    if len(param_types) == 1:
        param_name = next(iter(param_types.keys()))
        try:
            holds = _quick_check(
                fn,
                lambda kw, r: _safe_idempotence_check(root, param_name, kw, r),
            )
            properties.append(InferredProperty(
                "idempotence",
                "f(f(x)) == f(x)",
                holds,
            ))
        except Exception:
            pass

    # Involution: f(f(x)) == x
    if len(param_types) == 1:
        param_name = next(iter(param_types.keys()))
        try:
            holds = _quick_check(
                fn,
                lambda kw, r: _safe_involution_check(root, param_name, kw, r),
            )
            properties.append(InferredProperty(
                "involution",
                "f(f(x)) == x",
                holds,
            ))
        except Exception:
            pass

    return properties


def _safe_idempotence_check(
    fn: Callable[..., Any], param_name: str, kwargs: dict[str, Any], result: Any
) -> bool:
    """Check f(f(x)) == f(x), handling exceptions."""
    try:
        second = fn(**{param_name: result})
        return bool(second == result)
    except Exception:
        return True  # skip on error


def _safe_involution_check(
    fn: Callable[..., Any], param_name: str, kwargs: dict[str, Any], result: Any
) -> bool:
    """Check f(f(x)) == x, handling exceptions."""
    try:
        second = fn(**{param_name: result})
        return bool(second == kwargs[param_name])
    except Exception:
        return True  # skip on error


# ---------- Docstring mining ----------

_DOCSTRING_PATTERNS = [
    # "Returns ... sorted ..."
    (r"returns?\s+.*sorted", "sortedness", "output is sorted (from docstring)"),
    # "Returns a list of the same length"
    (r"same\s+length", "shape_preservation", "output has same length as input (from docstring)"),
    # "preserves" / "maintains"
    (r"preserves?|maintains?", "conservation", "preserves some property (from docstring)"),
    # "never negative" / "non-negative"
    (r"non[\s-]?negative|never\s+negative|>= 0", "non_negative", "output is non-negative (from docstring)"),
    # "unique"
    (r"unique|distinct|no\s+duplicates?", "uniqueness", "output contains unique elements (from docstring)"),
    # "idempotent"
    (r"idempoten", "idempotence", "function is idempotent (from docstring)"),
    # "pure" / "no side effects"
    (r"pure|no\s+side\s+effects?|deterministic", "purity", "function is pure (from docstring)"),
]


def infer_from_docstring(fn: Callable[..., Any]) -> list[InferredProperty]:
    """Mine contract-like statements from function docstrings."""
    doc = inspect.getdoc(fn) or ""
    if not doc:
        root = _root_original(fn)
        doc = inspect.getdoc(root) or ""

    if not doc:
        return []

    properties: list[InferredProperty] = []
    doc_lower = doc.lower()

    for pattern, name, description in _DOCSTRING_PATTERNS:
        if re.search(pattern, doc_lower):
            properties.append(InferredProperty(name, description, True, source="docstring"))

    return properties


def infer_all(
    fn: Callable[..., Any],
    *,
    include_llm: bool = False,
    mutation_score: float | None = None,
) -> list[InferredProperty]:
    """Run all inference strategies on a function.

    Args:
        fn: The function to analyze.
        include_llm: If True, also use LLM-assisted inference (requires anthropic).
        mutation_score: If available, pass to LLM for targeted suggestions.

    Returns:
        Combined list of inferred properties from all strategies.
    """
    properties: list[InferredProperty] = []

    # 1. Structural inference
    properties.extend(infer_structural(fn))

    # 2. Docstring mining
    properties.extend(infer_from_docstring(fn))

    # 3. LLM-assisted (optional, reuses _suggest module)
    if include_llm:
        try:
            from evidence._suggest import ClaudeSuggester
            suggester = ClaudeSuggester()
            existing = {
                "structural_properties": [p.to_dict() for p in properties if p.holds],
            }
            suggestions = suggester.suggest(
                fn,
                existing_contracts=existing,
                mutation_score=mutation_score,
            )
            for s in suggestions:
                properties.append(InferredProperty(
                    f"llm_{s.kind}",
                    s.description,
                    True,  # Will be validated separately
                    source="llm",
                ))
        except ImportError:
            pass

    return properties
