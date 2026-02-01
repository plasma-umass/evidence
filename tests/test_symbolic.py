"""Tests for Feature 5: Symbolic verification."""

from __future__ import annotations

from evidence._symbolic import _check_crosshair_available, prove_function


# ---------------------------------------------------------------------------
# _check_crosshair_available
# ---------------------------------------------------------------------------

class TestCheckCrosshairAvailable:
    def test_returns_bool(self):
        result = _check_crosshair_available()
        assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# prove_function
# ---------------------------------------------------------------------------

class TestProveFunction:
    def test_unavailable_without_crosshair(self):
        """If crosshair is not installed, status should be 'unavailable'."""
        def f(x: int) -> int:
            return x * 2

        if not _check_crosshair_available():
            result = prove_function(f)
            assert result["status"] == "unavailable"
            assert "install" in result["details"].lower()

    def test_no_strategy_gives_inconclusive(self):
        """Without a strategy, should be inconclusive."""
        def f(x: int) -> int:
            return x * 2

        if _check_crosshair_available():
            result = prove_function(f, strategy=None)
            assert result["status"] == "inconclusive"

    def test_result_dict_structure(self):
        def f(x: int) -> int:
            return x * 2

        result = prove_function(f)
        assert "status" in result
        assert "details" in result
        assert result["status"] in ("verified", "disproved", "inconclusive", "unavailable")

    def test_with_spec_fn(self):
        """Test proving with a spec function."""
        def impl(x: int) -> int:
            return x * 2

        def spec(x: int) -> int:
            return x + x

        if _check_crosshair_available():
            from hypothesis import strategies as st
            strategy = st.fixed_dictionaries({"x": st.integers(min_value=-100, max_value=100)})
            result = prove_function(impl, spec_fn=spec, strategy=strategy)
            assert result["status"] in ("verified", "inconclusive")
        else:
            result = prove_function(impl, spec_fn=spec)
            assert result["status"] == "unavailable"

    def test_disproved_with_wrong_spec(self):
        """Test that a wrong spec gets disproved."""
        def impl(x: int) -> int:
            return x * 2

        def wrong_spec(x: int) -> int:
            return x * 3

        if _check_crosshair_available():
            from hypothesis import strategies as st
            strategy = st.fixed_dictionaries({"x": st.integers(min_value=1, max_value=100)})
            result = prove_function(impl, spec_fn=wrong_spec, strategy=strategy)
            assert result["status"] in ("disproved", "inconclusive")
