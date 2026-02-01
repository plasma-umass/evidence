"""Tests for Feature 7: Spec inference."""

from __future__ import annotations

from evidence._infer import (
    InferredProperty,
    _quick_check,
    infer_all,
    infer_from_docstring,
    infer_structural,
)


# ---------------------------------------------------------------------------
# InferredProperty
# ---------------------------------------------------------------------------

class TestInferredProperty:
    def test_to_dict(self):
        p = InferredProperty("idempotence", "f(f(x)) == f(x)", True, "structural")
        d = p.to_dict()
        assert d["name"] == "idempotence"
        assert d["holds"] is True
        assert d["source"] == "structural"


# ---------------------------------------------------------------------------
# _quick_check
# ---------------------------------------------------------------------------

class TestQuickCheck:
    def test_holds_for_pure_function(self):
        def f(x: int) -> int:
            return x * 2

        result = _quick_check(f, lambda kw, r: isinstance(r, int))
        assert result is True

    def test_fails_for_false_property(self):
        def f(x: int) -> int:
            return x * 2

        result = _quick_check(f, lambda kw, r: r < 0)  # not always true
        assert result is False


# ---------------------------------------------------------------------------
# infer_structural
# ---------------------------------------------------------------------------

class TestInferStructural:
    def test_list_to_list_shape_preservation(self):
        def sort_fn(xs: list[int]) -> list[int]:
            return sorted(xs)

        props = infer_structural(sort_fn)
        names = [p.name for p in props]
        assert "shape_preservation" in names
        shape_prop = next(p for p in props if p.name == "shape_preservation")
        assert shape_prop.holds is True

    def test_list_to_list_sortedness(self):
        def sort_fn(xs: list[int]) -> list[int]:
            return sorted(xs)

        props = infer_structural(sort_fn)
        names = [p.name for p in props]
        assert "sortedness" in names
        sort_prop = next(p for p in props if p.name == "sortedness")
        assert sort_prop.holds is True

    def test_idempotence(self):
        def f(x: int) -> int:
            return abs(x)

        props = infer_structural(f)
        names = [p.name for p in props]
        assert "idempotence" in names
        idem = next(p for p in props if p.name == "idempotence")
        assert idem.holds is True

    def test_involution(self):
        def negate(x: int) -> int:
            return -x

        props = infer_structural(negate)
        names = [p.name for p in props]
        assert "involution" in names
        inv = next(p for p in props if p.name == "involution")
        assert inv.holds is True

    def test_non_idempotent(self):
        def f(x: int) -> int:
            return x + 1

        props = infer_structural(f)
        idem_props = [p for p in props if p.name == "idempotence"]
        if idem_props:
            assert idem_props[0].holds is False


# ---------------------------------------------------------------------------
# infer_from_docstring
# ---------------------------------------------------------------------------

class TestInferFromDocstring:
    def test_sorted_docstring(self):
        def f(xs: list[int]) -> list[int]:
            """Returns a sorted list."""
            return sorted(xs)

        props = infer_from_docstring(f)
        names = [p.name for p in props]
        assert "sortedness" in names

    def test_same_length_docstring(self):
        def f(xs: list[int]) -> list[int]:
            """Returns a list of the same length as the input."""
            return xs[:]

        props = infer_from_docstring(f)
        names = [p.name for p in props]
        assert "shape_preservation" in names

    def test_no_docstring(self):
        def f(x: int) -> int:
            return x

        props = infer_from_docstring(f)
        assert props == []

    def test_idempotent_docstring(self):
        def f(x: int) -> int:
            """This function is idempotent."""
            return abs(x)

        props = infer_from_docstring(f)
        names = [p.name for p in props]
        assert "idempotence" in names

    def test_pure_docstring(self):
        def f(x: int) -> int:
            """A pure function with no side effects."""
            return x

        props = infer_from_docstring(f)
        names = [p.name for p in props]
        assert "purity" in names


# ---------------------------------------------------------------------------
# infer_all
# ---------------------------------------------------------------------------

class TestInferAll:
    def test_combines_strategies(self):
        def sort_fn(xs: list[int]) -> list[int]:
            """Returns a sorted list of the same length."""
            return sorted(xs)

        props = infer_all(sort_fn, include_llm=False)
        sources = {p.source for p in props}
        assert "structural" in sources
        assert "docstring" in sources

    def test_without_llm(self):
        def f(x: int) -> int:
            return x * 2

        props = infer_all(f, include_llm=False)
        # Should not crash, and all properties should be from structural/docstring
        for p in props:
            assert p.source in ("structural", "docstring")
