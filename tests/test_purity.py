"""Tests for Feature 2: @pure decorator — static + dynamic purity analysis."""

from __future__ import annotations

import random

import pytest

from evidence._purity import ImpurityWarning, dynamic_purity_check, static_purity_check


# ---------------------------------------------------------------------------
# Static purity analysis
# ---------------------------------------------------------------------------

class TestStaticPurityCheck:
    def test_pure_function_no_warnings(self):
        def f(x: int) -> int:
            return x * 2 + 1
        assert static_purity_check(f) == []

    def test_detects_print(self):
        def f(x: int) -> int:
            print(x)
            return x
        warnings = static_purity_check(f)
        assert any(w.category == "io" for w in warnings)

    def test_detects_open(self):
        def f(x: str) -> str:
            open(x)
            return x
        warnings = static_purity_check(f)
        assert any(w.category == "io" and "open" in w.description for w in warnings)

    def test_detects_input(self):
        def f() -> str:
            return input("prompt")
        warnings = static_purity_check(f)
        assert any(w.category == "io" and "input" in w.description for w in warnings)

    def test_detects_random(self):
        def f(x: int) -> int:
            return x + random.randint(0, 10)
        warnings = static_purity_check(f)
        assert any(w.category == "nondeterminism" for w in warnings)

    def test_detects_hash(self):
        def f(x: list) -> int:
            return id(x)
        warnings = static_purity_check(f)
        assert any(w.category == "hash_addr" for w in warnings)

    def test_detects_setattr(self):
        def f(obj, name, val):
            setattr(obj, name, val)
        warnings = static_purity_check(f)
        assert any(w.category == "global_mutation" for w in warnings)

    def test_detects_exec(self):
        def f(code: str) -> None:
            exec(code)
        warnings = static_purity_check(f)
        assert any(w.category == "global_mutation" and "exec" in w.description for w in warnings)

    def test_detects_global_statement(self):
        def f() -> None:
            global counter
            counter = 1
        warnings = static_purity_check(f)
        assert any(w.category == "global_mutation" and "global" in w.description for w in warnings)

    def test_seed_deterministic_skips_random(self):
        def f(x: int) -> int:
            return x + random.randint(0, 10)
        warnings = static_purity_check(f, seed_deterministic=True)
        assert not any(w.category == "nondeterminism" for w in warnings)

    def test_seed_deterministic_still_flags_io(self):
        def f(x: int) -> int:
            print(x)
            return x + random.randint(0, 10)
        warnings = static_purity_check(f, seed_deterministic=True)
        assert any(w.category == "io" for w in warnings)
        assert not any(w.category == "nondeterminism" for w in warnings)

    def test_warnings_have_line_numbers(self):
        def f(x: int) -> int:
            print(x)
            return x
        warnings = static_purity_check(f)
        assert len(warnings) > 0
        assert all(w.lineno is not None for w in warnings)


# ---------------------------------------------------------------------------
# Dynamic purity analysis
# ---------------------------------------------------------------------------

class TestDynamicPurityCheck:
    def test_pure_function(self):
        def f(x: int) -> int:
            return x * 2
        is_pure, err = dynamic_purity_check(f, {"x": 5})
        assert is_pure
        assert err == ""

    def test_nondeterministic_function(self):
        def f(x: int) -> int:
            return x + random.randint(0, 1000)
        is_pure, err = dynamic_purity_check(f, {"x": 5})
        assert not is_pure
        assert "results differ" in err

    def test_detects_stdout(self):
        def f(x: int) -> int:
            print(x)
            return x
        is_pure, err = dynamic_purity_check(f, {"x": 5})
        assert not is_pure
        assert "stdout" in err

    def test_detects_stderr(self):
        import sys

        def f(x: int) -> int:
            print(x, file=sys.stderr)
            return x
        is_pure, err = dynamic_purity_check(f, {"x": 5})
        assert not is_pure
        assert "stderr" in err

    def test_seed_deterministic(self):
        def f(x: int) -> int:
            return x + random.randint(0, 1000)
        is_pure, err = dynamic_purity_check(f, {"x": 5}, seed=42)
        assert is_pure
        assert err == ""

    def test_custom_eq(self):
        def f(x: float) -> float:
            return x + 0.0  # floating-point identity
        is_pure, err = dynamic_purity_check(f, {"x": 1.0}, eq=lambda a, b: abs(a - b) < 1e-6)
        assert is_pure

    def test_deep_copies_inputs(self):
        """Verify that mutation of inputs doesn't cause false failures."""
        def f(xs: list) -> list:
            xs.append(1)
            return xs
        # Even though f mutates its input, it should be called with independent copies
        is_pure, err = dynamic_purity_check(f, {"xs": [1, 2, 3]})
        assert is_pure


class TestImpurityWarning:
    def test_repr_with_lineno(self):
        w = ImpurityWarning("io", "call to print", lineno=42)
        assert "io" in repr(w)
        assert "print" in repr(w)
        assert "42" in repr(w)

    def test_repr_without_lineno(self):
        w = ImpurityWarning("io", "call to print")
        assert "io" in repr(w)
        assert "line" not in repr(w)
