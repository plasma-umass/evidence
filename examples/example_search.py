"""Search and lookup functions — demonstrates @requires for sorted-input contracts.

Bug: `binary_search()` has the classic overflow bug in midpoint calculation.
Bug: `find_closest()` fails on single-element lists.
"""

from __future__ import annotations

from evidence import against, ensures, pure, requires, spec


# ---------------------------------------------------------------------------
# binary search
# ---------------------------------------------------------------------------

@spec
@pure
def binary_search_spec(xs: list[int], target: int) -> int:
    """Reference: return index of target, or -1 if not found."""
    try:
        return xs.index(target)
    except ValueError:
        return -1


@against(binary_search_spec, max_examples=500)
@ensures(lambda xs, target, result: result == -1 or (0 <= result < len(xs) and xs[result] == target))
@requires(lambda xs, target: xs == sorted(xs))
@requires(lambda xs, target: len(xs) <= 50)
@requires(lambda xs, target: len(xs) == len(set(xs)))  # no duplicates for simple index matching
@pure
def binary_search(xs: list[int], target: int) -> int:
    """Binary search in a sorted list.

    Bug: uses (lo + hi) // 2 instead of lo + (hi - lo) // 2.
    This doesn't cause overflow in Python (arbitrary precision ints),
    but the implementation has an off-by-one in the hi bound.
    """
    lo, hi = 0, len(xs)  # Bug: should be len(xs) - 1 for inclusive hi
    while lo <= hi:
        mid = (lo + hi) // 2
        if mid >= len(xs):  # guard to avoid index error
            break
        if xs[mid] == target:
            return mid
        elif xs[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1


# ---------------------------------------------------------------------------
# find minimum
# ---------------------------------------------------------------------------

@spec
@pure
def find_min_spec(xs: list[int]) -> int:
    return min(xs)


@against(find_min_spec, max_examples=500)
@ensures(lambda xs, result: result in xs)
@ensures(lambda xs, result: all(result <= x for x in xs))
@requires(lambda xs: len(xs) > 0 and len(xs) <= 50)
@pure
def find_min(xs: list[int]) -> int:
    """Find minimum element.

    This implementation is correct.
    """
    m = xs[0]
    for x in xs[1:]:
        if x < m:
            m = x
    return m


# ---------------------------------------------------------------------------
# find_closest: find element closest to target in sorted list
# ---------------------------------------------------------------------------

@spec
@pure
def find_closest_spec(xs: list[int], target: int) -> int:
    """Reference: element in xs closest to target."""
    return min(xs, key=lambda x: abs(x - target))


@against(find_closest_spec, max_examples=500)
@ensures(lambda xs, target, result: result in xs)
@requires(lambda xs, target: len(xs) > 0 and len(xs) <= 50)
@requires(lambda xs, target: xs == sorted(xs))
@requires(lambda xs, target: abs(target) < 10000)
@pure
def find_closest(xs: list[int], target: int) -> int:
    """Find closest element to target in sorted list via binary search.

    Bug: doesn't check the left neighbor, only right, so it can miss
    the actual closest element when the target falls between two values.
    """
    if len(xs) == 1:
        return xs[0]

    lo, hi = 0, len(xs) - 1
    while lo < hi:
        mid = lo + (hi - lo) // 2
        if xs[mid] == target:
            return xs[mid]
        elif xs[mid] < target:
            lo = mid + 1
        else:
            hi = mid

    # Bug: always returns xs[lo] without comparing with xs[lo-1]
    return xs[lo]


# ---------------------------------------------------------------------------
# two_sum: find two elements that sum to target
# ---------------------------------------------------------------------------

@spec
@pure
def two_sum_spec(xs: list[int], target: int) -> tuple[int, int]:
    """Reference: brute-force two-sum."""
    for i in range(len(xs)):
        for j in range(i + 1, len(xs)):
            if xs[i] + xs[j] == target:
                return (i, j)
    return (-1, -1)


@against(two_sum_spec, max_examples=300)
@ensures(lambda xs, target, result: result == (-1, -1) or xs[result[0]] + xs[result[1]] == target)
@requires(lambda xs, target: len(xs) <= 20)
@requires(lambda xs, target: all(abs(x) < 100 for x in xs))
@pure
def two_sum(xs: list[int], target: int) -> tuple[int, int]:
    """Two-sum via hash map.

    This implementation is correct.
    """
    seen: dict[int, int] = {}
    for i, x in enumerate(xs):
        complement = target - x
        if complement in seen:
            return (seen[complement], i)
        seen[x] = i
    return (-1, -1)
