"""Tests for Feature 8: Numeric/ML support."""

from __future__ import annotations

import math

import pytest

from evidence._numeric import approx_eq, resolve_eq


# ---------------------------------------------------------------------------
# approx_eq
# ---------------------------------------------------------------------------

class TestApproxEq:
    def test_exact_floats(self):
        assert approx_eq(1.0, 1.0) is True

    def test_close_floats(self):
        assert approx_eq(1.0, 1.0 + 1e-9) is True

    def test_different_floats(self):
        assert approx_eq(1.0, 2.0) is False

    def test_integers(self):
        assert approx_eq(1, 1) is True
        assert approx_eq(1, 2) is False

    def test_lists(self):
        assert approx_eq([1.0, 2.0], [1.0, 2.0]) is True
        assert approx_eq([1.0, 2.0], [1.0, 3.0]) is False

    def test_nested_lists(self):
        assert approx_eq([[1.0, 2.0]], [[1.0, 2.0]]) is True

    def test_different_length_lists(self):
        assert approx_eq([1.0], [1.0, 2.0]) is False

    def test_tuples(self):
        assert approx_eq((1.0, 2.0), (1.0, 2.0)) is True
        assert approx_eq((1.0,), (1.0, 2.0)) is False

    def test_strings_exact(self):
        assert approx_eq("abc", "abc") is True
        assert approx_eq("abc", "def") is False

    def test_none_values(self):
        assert approx_eq(None, None) is True


# ---------------------------------------------------------------------------
# Numpy support
# ---------------------------------------------------------------------------

class TestApproxEqNumpy:
    @pytest.fixture(autouse=True)
    def _skip_without_numpy(self):
        pytest.importorskip("numpy")

    def test_numpy_arrays_equal(self):
        import numpy as np
        a = np.array([1.0, 2.0, 3.0])
        b = np.array([1.0, 2.0, 3.0])
        assert approx_eq(a, b) is True

    def test_numpy_arrays_close(self):
        import numpy as np
        a = np.array([1.0, 2.0, 3.0])
        b = np.array([1.0, 2.0 + 1e-9, 3.0])
        assert approx_eq(a, b) is True

    def test_numpy_arrays_different(self):
        import numpy as np
        a = np.array([1.0, 2.0, 3.0])
        b = np.array([1.0, 5.0, 3.0])
        assert approx_eq(a, b) is False


# ---------------------------------------------------------------------------
# resolve_eq
# ---------------------------------------------------------------------------

class TestResolveEq:
    def test_none_returns_equality(self):
        eq = resolve_eq(None)
        assert eq(1, 1) is True
        assert eq(1, 2) is False

    def test_approx_string(self):
        eq = resolve_eq("approx")
        assert eq is approx_eq

    def test_callable_passthrough(self):
        custom = lambda a, b: a == b  # noqa: E731
        eq = resolve_eq(custom)
        assert eq is custom

    def test_invalid_raises(self):
        with pytest.raises(ValueError, match="Invalid eq"):
            resolve_eq("invalid_string")


# ---------------------------------------------------------------------------
# register_numeric_strategies
# ---------------------------------------------------------------------------

class TestRegisterNumericStrategies:
    def test_registers_without_error(self):
        from evidence._numeric import register_numeric_strategies
        # Should not raise even if optional deps are missing
        register_numeric_strategies()

    def test_numpy_strategy_registered(self):
        pytest.importorskip("numpy")
        import numpy as np
        from evidence._numeric import register_numeric_strategies
        from evidence._strategies import _STRATEGY_FACTORY_OVERRIDES

        register_numeric_strategies()
        assert np.ndarray in _STRATEGY_FACTORY_OVERRIDES
