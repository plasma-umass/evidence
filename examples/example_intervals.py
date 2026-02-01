# example_intervals.py
from __future__ import annotations

from hypothesis import strategies as st

from evidence import against, ensures, register_strategy, requires, spec

Interval = tuple[int, int]

# Dense generation: bounded and always well-formed (lo <= hi)
register_strategy(
    Interval,
    st.tuples(st.integers(-10, 10), st.integers(-10, 10)).map(lambda t: (min(t[0], t[1]), max(t[0], t[1]))),
)


def is_well_formed(xs: list[Interval]) -> bool:
    return all(lo <= hi for (lo, hi) in xs)


def is_sorted_disjoint(xs: list[Interval]) -> bool:
    # Canonical: sorted by lo, non-overlapping, non-adjacent.
    for i in range(len(xs) - 1):
        (a0, a1) = xs[i]
        (b0, b1) = xs[i + 1]
        if not (a0 <= a1 and b0 <= b1):
            return False
        if not (a0 <= b0):
            return False
        if not (b0 > a1 + 1):
            return False
    return True


@spec
def normalize_spec(xs: list[Interval]) -> list[Interval]:
    # Spec: expand to points, then compress into maximal intervals.
    pts = set()
    for (lo, hi) in xs:
        for v in range(lo, hi + 1):
            pts.add(v)

    if not pts:
        return []

    s = sorted(pts)
    out: list[Interval] = []
    cur_lo = s[0]
    cur_hi = s[0]
    for v in s[1:]:
        if v == cur_hi + 1:
            cur_hi = v
        else:
            out.append((cur_lo, cur_hi))
            cur_lo = v
            cur_hi = v
    out.append((cur_lo, cur_hi))
    return out


@requires(lambda xs: is_well_formed(xs))
@requires(lambda xs: len(xs) <= 12)
@requires(lambda xs: all(-10 <= lo <= 10 and -10 <= hi <= 10 for (lo, hi) in xs))
@against(normalize_spec, max_examples=500)
@ensures(lambda xs, result: is_well_formed(result))
@ensures(lambda xs, result: is_sorted_disjoint(result))
def normalize(xs: list[Interval]) -> list[Interval]:
    """
    BUGGY normalize:
      merges overlapping intervals, but fails to merge *adjacent* intervals.
      (Uses lo <= cur_hi instead of lo <= cur_hi + 1.)
    """
    if not xs:
        return []

    ys = sorted(xs, key=lambda p: (p[0], p[1]))
    out: list[Interval] = []
    cur_lo, cur_hi = ys[0]

    for lo, hi in ys[1:]:
        # BUG: should be `lo <= cur_hi + 1`
        if lo <= cur_hi:
            if hi > cur_hi:
                cur_hi = hi
        else:
            out.append((cur_lo, cur_hi))
            cur_lo, cur_hi = lo, hi

    out.append((cur_lo, cur_hi))
    return out
