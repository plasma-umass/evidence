"""Tests for core decorators: @spec, @requires, @ensures, @against, @pure."""

from __future__ import annotations

import pytest

from evidence._bundle import _get_bundle, _root_original
from evidence._decorators import against, ensures, pure, requires, spec


# ---------------------------------------------------------------------------
# @spec
# ---------------------------------------------------------------------------

class TestSpec:
    def test_marks_is_spec(self):
        @spec
        def f(x: int) -> int:
            return x
        assert _get_bundle(f)["is_spec"] is True

    def test_returns_original_function(self):
        def f(x: int) -> int:
            return x
        result = spec(f)
        assert result is f


# ---------------------------------------------------------------------------
# @requires
# ---------------------------------------------------------------------------

class TestRequires:
    def test_passes_when_satisfied(self):
        @requires(lambda x: x > 0)
        def f(x: int) -> int:
            return x * 2
        assert f(x=5) == 10

    def test_raises_when_violated(self):
        @requires(lambda x: x > 0)
        def f(x: int) -> int:
            return x * 2
        with pytest.raises(AssertionError, match="Precondition failed"):
            f(x=-1)

    def test_stacking(self):
        @requires(lambda x: x > 0)
        @requires(lambda x: x < 100)
        def f(x: int) -> int:
            return x
        assert f(x=50) == 50
        with pytest.raises(AssertionError):
            f(x=-1)
        with pytest.raises(AssertionError):
            f(x=200)

    def test_bundle_accumulates(self):
        @requires(lambda x: x > 0)
        @requires(lambda x: x < 100)
        def f(x: int) -> int:
            return x
        b = _get_bundle(f)
        assert len(b["requires"]) == 2


# ---------------------------------------------------------------------------
# @ensures
# ---------------------------------------------------------------------------

class TestEnsures:
    def test_passes_when_satisfied(self):
        @ensures(lambda x, result: result > x)
        def f(x: int) -> int:
            return x + 1
        assert f(x=5) == 6

    def test_raises_when_violated(self):
        @ensures(lambda x, result: result > x)
        def f(x: int) -> int:
            return x - 1
        with pytest.raises(AssertionError, match="Postcondition failed"):
            f(x=5)

    def test_stacking(self):
        @ensures(lambda x, result: result > 0)
        @ensures(lambda x, result: isinstance(result, int))
        def f(x: int) -> int:
            return abs(x) + 1
        assert f(x=-5) == 6

    def test_also_checks_requires(self):
        @ensures(lambda x, result: result > 0)
        @requires(lambda x: x > 0)
        def f(x: int) -> int:
            return x
        with pytest.raises(AssertionError, match="Precondition failed"):
            f(x=-1)


# ---------------------------------------------------------------------------
# @against
# ---------------------------------------------------------------------------

class TestAgainst:
    def test_stores_spec_in_bundle(self):
        def my_spec(x: int) -> int:
            return x

        @against(my_spec)
        def f(x: int) -> int:
            return x
        b = _get_bundle(f)
        assert b["against"]["spec"] is my_spec
        assert b["against"]["max_examples"] == 200

    def test_custom_max_examples(self):
        def my_spec(x: int) -> int:
            return x

        @against(my_spec, max_examples=500)
        def f(x: int) -> int:
            return x
        assert _get_bundle(f)["against"]["max_examples"] == 500

    def test_eq_approx_resolves(self):
        def my_spec(x: float) -> float:
            return x

        @against(my_spec, eq="approx")
        def f(x: float) -> float:
            return x
        b = _get_bundle(f)
        eq = b["against"]["eq"]
        assert callable(eq)
        assert eq(1.0, 1.0 + 1e-9)

    def test_eq_callable(self):
        custom_eq = lambda a, b: abs(a - b) < 0.1

        def my_spec(x: float) -> float:
            return x

        @against(my_spec, eq=custom_eq)
        def f(x: float) -> float:
            return x
        assert _get_bundle(f)["against"]["eq"] is custom_eq


# ---------------------------------------------------------------------------
# @pure
# ---------------------------------------------------------------------------

class TestPure:
    def test_bare_decorator(self):
        @pure
        def f(x: int) -> int:
            return x * 2
        b = _get_bundle(f)
        assert b["pure"] is not None
        assert b["pure"]["seed"] is None

    def test_with_seed(self):
        @pure(seed=42)
        def f(x: int) -> int:
            return x
        b = _get_bundle(f)
        assert b["pure"]["seed"] == 42

    def test_with_eq(self):
        custom_eq = lambda a, b: a == b

        @pure(eq=custom_eq)
        def f(x: int) -> int:
            return x
        assert _get_bundle(f)["pure"]["eq"] is custom_eq

    def test_returns_original(self):
        def f(x: int) -> int:
            return x
        result = pure(f)
        assert result is f

    def test_seed_deterministic_returns_original(self):
        def f(x: int) -> int:
            return x
        result = pure(seed=42)(f)
        assert result is f


# ---------------------------------------------------------------------------
# Decorator ordering / chaining
# ---------------------------------------------------------------------------

class TestDecoratorChaining:
    def test_full_stack(self):
        @spec
        def ref(x: int) -> int:
            return x + 1

        @against(ref)
        @ensures(lambda x, result: result > x)
        @requires(lambda x: x >= 0)
        def f(x: int) -> int:
            return x + 1

        root = _root_original(f)
        b = _get_bundle(root)
        assert len(b["requires"]) == 1
        assert len(b["ensures"]) == 1
        assert b["against"]["spec"] is ref

    def test_pure_with_contracts(self):
        @pure
        @ensures(lambda x, result: result >= 0)
        @requires(lambda x: x >= 0)
        def f(x: int) -> int:
            return x
        b = _get_bundle(f)
        assert b["pure"] is not None
        assert len(b["requires"]) == 1
        assert len(b["ensures"]) == 1
