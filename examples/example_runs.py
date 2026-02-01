# example_runs.py
from __future__ import annotations

from evidence import against, ensures, spec


def flatten(xss: list[list[int]]) -> list[int]:
    return [x for xs in xss for x in xs]


def all_nonempty(xss: list[list[int]]) -> bool:
    return all(len(xs) > 0 for xs in xss)


def all_constant_runs(xss: list[list[int]]) -> bool:
    # Each inner list should contain the same value repeated.
    return all(all(x == xs[0] for x in xs) for xs in xss if xs)


def adjacent_runs_distinct(xss: list[list[int]]) -> bool:
    # Adjacent groups must have different representative values.
    reps = [xs[0] for xs in xss if xs]
    return all(reps[i] != reps[i + 1] for i in range(len(reps) - 1))


@spec
def group_runs_spec(xs: list[int]) -> list[list[int]]:
    """
    Slow, obviously-correct reference implementation.
    """
    if not xs:
        return []
    out: list[list[int]] = []
    cur = [xs[0]]
    for x in xs[1:]:
        if x == cur[0]:
            cur.append(x)
        else:
            out.append(cur)
            cur = [x]
    out.append(cur)
    return out


@against(group_runs_spec, max_examples=500)
@ensures(lambda xs, result: flatten(result) == xs)
@ensures(lambda xs, result: all_nonempty(result))
@ensures(lambda xs, result: all_constant_runs(result))
@ensures(lambda xs, result: adjacent_runs_distinct(result))
def group_runs(xs: list[int]) -> list[list[int]]:
    """
    BUGGY implementation: forgets to append the final run.
    Subtle because it "works" for many inputs in ad-hoc testing if you never check the tail.
    """
    if not xs:
        return []

    out: list[list[int]] = []
    cur = [xs[0]]
    for x in xs[1:]:
        if x == cur[0]:
            cur.append(x)
        else:
            out.append(cur)
            cur = [x]

    # BUG: missing `out.append(cur)` here.
    return out
