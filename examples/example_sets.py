"""Set operations — demonstrates contracts on collection-returning functions.

Bug: `unique()` doesn't preserve input order.
Bug: `intersection()` fails on duplicate elements in inputs.
"""

from __future__ import annotations

from evidence import against, ensures, requires, spec


# ---------------------------------------------------------------------------
# unique elements (order-preserving dedup)
# ---------------------------------------------------------------------------

@spec
def unique_spec(xs: list[int]) -> list[int]:
    """Reference: unique elements preserving first-occurrence order."""
    seen: set[int] = set()
    result: list[int] = []
    for x in xs:
        if x not in seen:
            seen.add(x)
            result.append(x)
    return result


@against(unique_spec, max_examples=500)
@ensures(lambda xs, result: len(result) == len(set(result)))
@ensures(lambda xs, result: set(result) == set(xs))
@ensures(lambda xs, result: len(result) <= len(xs))
def unique(xs: list[int]) -> list[int]:
    """Remove duplicates from a list.

    Bug: uses set conversion, which doesn't preserve order.
    """
    return list(set(xs))


# ---------------------------------------------------------------------------
# list intersection
# ---------------------------------------------------------------------------

@spec
def intersect_spec(xs: list[int], ys: list[int]) -> list[int]:
    """Reference: elements in both lists, preserving order from xs, no dupes."""
    seen = set(ys)
    result: list[int] = []
    added: set[int] = set()
    for x in xs:
        if x in seen and x not in added:
            result.append(x)
            added.add(x)
    return result


@against(intersect_spec, max_examples=500)
@ensures(lambda xs, ys, result: all(x in xs and x in ys for x in result))
@ensures(lambda xs, ys, result: len(result) == len(set(result)))
def intersect(xs: list[int], ys: list[int]) -> list[int]:
    """Intersection of two lists, preserving order from xs.

    Bug: doesn't track already-added elements, so duplicates in xs leak through.
    """
    seen = set(ys)
    result: list[int] = []
    for x in xs:
        if x in seen:
            result.append(x)
    return result


# ---------------------------------------------------------------------------
# symmetric difference
# ---------------------------------------------------------------------------

@spec
def symmetric_diff_spec(xs: list[int], ys: list[int]) -> list[int]:
    """Elements in either list but not both."""
    sx, sy = set(xs), set(ys)
    return sorted(sx ^ sy)


@against(symmetric_diff_spec, max_examples=500)
@ensures(lambda xs, ys, result: result == sorted(result))
@ensures(lambda xs, ys, result: len(result) == len(set(result)))
def symmetric_diff(xs: list[int], ys: list[int]) -> list[int]:
    """Symmetric difference of two lists.

    This implementation is correct.
    """
    sx, sy = set(xs), set(ys)
    return sorted(sx ^ sy)


# ---------------------------------------------------------------------------
# is_subset
# ---------------------------------------------------------------------------

@spec
def is_subset_spec(xs: list[int], ys: list[int]) -> bool:
    return set(xs).issubset(set(ys))


@against(is_subset_spec, max_examples=500)
def is_subset(xs: list[int], ys: list[int]) -> bool:
    """Check if all elements of xs appear in ys.

    This implementation is correct.
    """
    return all(x in ys for x in xs)
