"""Tests for Feature 4: Mutation testing."""

from __future__ import annotations

import ast

from evidence._mutate import (
    Mutant,
    _mutate_constant,
    compile_mutant,
    generate_mutants,
    run_mutation_testing,
)


# ---------------------------------------------------------------------------
# _mutate_constant
# ---------------------------------------------------------------------------

class TestMutateConstant:
    def test_bool_flip(self):
        assert _mutate_constant(True) is False
        assert _mutate_constant(False) is True

    def test_int_increment(self):
        assert _mutate_constant(0) == 1
        assert _mutate_constant(5) == 6
        assert _mutate_constant(-1) == 0

    def test_float_increment(self):
        assert _mutate_constant(1.0) == 2.0
        assert _mutate_constant(0.0) == 1.0

    def test_string_to_empty(self):
        assert _mutate_constant("hello") == ""

    def test_empty_string_returns_none(self):
        assert _mutate_constant("") is None

    def test_none_returns_none(self):
        assert _mutate_constant(None) is None


# ---------------------------------------------------------------------------
# generate_mutants
# ---------------------------------------------------------------------------

class TestGenerateMutants:
    def test_generates_mutants(self):
        def f(x: int) -> int:
            if x > 0:
                return x + 1
            return x - 1

        mutants = generate_mutants(f)
        assert len(mutants) > 0
        assert all(isinstance(m, Mutant) for m in mutants)

    def test_flip_comparison(self):
        def f(x: int) -> bool:
            return x > 0

        mutants = generate_mutants(f)
        cmp_mutants = [m for m in mutants if m.operator == "flip_comparison"]
        assert len(cmp_mutants) > 0

    def test_swap_arithmetic(self):
        def f(x: int, y: int) -> int:
            return x + y

        mutants = generate_mutants(f)
        arith_mutants = [m for m in mutants if m.operator == "swap_arithmetic"]
        assert len(arith_mutants) > 0

    def test_negate_condition(self):
        def f(x: int) -> int:
            if x > 0:
                return 1
            return 0

        mutants = generate_mutants(f)
        neg_mutants = [m for m in mutants if m.operator == "negate_condition"]
        assert len(neg_mutants) > 0

    def test_delete_statement(self):
        def f(x: int) -> int:
            y = x + 1
            return y

        mutants = generate_mutants(f)
        del_mutants = [m for m in mutants if m.operator == "delete_statement"]
        assert len(del_mutants) > 0

    def test_change_constant(self):
        def f(x: int) -> int:
            return x + 1

        mutants = generate_mutants(f)
        const_mutants = [m for m in mutants if m.operator == "change_constant"]
        assert len(const_mutants) > 0

    def test_swap_boolean(self):
        def f(x: bool, y: bool) -> bool:
            return x and y

        mutants = generate_mutants(f)
        bool_mutants = [m for m in mutants if m.operator == "swap_boolean"]
        assert len(bool_mutants) > 0

    def test_remove_return(self):
        def f(x: int) -> int:
            return x + 1

        mutants = generate_mutants(f)
        ret_mutants = [m for m in mutants if m.operator == "remove_return"]
        assert len(ret_mutants) > 0

    def test_max_mutants_limit(self):
        def f(x: int) -> int:
            if x > 0:
                y = x + 1
                z = y * 2
                return z - 1
            elif x == 0:
                return 0
            else:
                return x * -1

        mutants = generate_mutants(f, max_mutants=3)
        assert len(mutants) <= 3

    def test_empty_for_builtin(self):
        # Built-in functions have no inspectable source
        mutants = generate_mutants(len)
        assert mutants == []


# ---------------------------------------------------------------------------
# compile_mutant
# ---------------------------------------------------------------------------

class TestCompileMutant:
    def test_compiles_valid_mutant(self):
        def f(x: int) -> int:
            return x + 1

        mutants = generate_mutants(f)
        assert len(mutants) > 0
        compiled = compile_mutant(mutants[0], f)
        assert compiled is not None
        assert callable(compiled)

    def test_mutated_function_differs(self):
        def f(x: int) -> int:
            return x + 1

        mutants = generate_mutants(f)
        arith = [m for m in mutants if m.operator == "swap_arithmetic"]
        if arith:
            compiled = compile_mutant(arith[0], f)
            assert compiled is not None
            # x + 1 should become x - 1
            assert compiled(5) != f(5)


# ---------------------------------------------------------------------------
# Mutant repr
# ---------------------------------------------------------------------------

class TestMutantRepr:
    def test_repr_with_lineno(self):
        tree = ast.parse("x = 1")
        m = Mutant("flip_comparison", "Eq -> NotEq", 5, tree)
        r = repr(m)
        assert "flip_comparison" in r
        assert "line 5" in r

    def test_repr_without_lineno(self):
        tree = ast.parse("x = 1")
        m = Mutant("swap_arithmetic", "Add -> Sub", None, tree)
        r = repr(m)
        assert "swap_arithmetic" in r
        assert "line" not in r


# ---------------------------------------------------------------------------
# run_mutation_testing
# ---------------------------------------------------------------------------

class TestRunMutationTesting:
    def test_basic_mutation_testing(self):
        def f(x: int) -> int:
            return x + 1

        # Checker that always catches mutations
        result = run_mutation_testing(f, lambda mf: mf(5) != 6, max_mutants=5)
        assert "total_mutants" in result
        assert "killed" in result
        assert "survived" in result
        assert "mutation_score" in result

    def test_no_mutants_for_builtin(self):
        result = run_mutation_testing(len, lambda mf: True)
        assert result["total_mutants"] == 0
        assert result["mutation_score"] is None
