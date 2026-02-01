# example_sort.py
from __future__ import annotations

from collections import Counter

from evidence import against, ensures, spec


def is_sorted(xs: list[int]) -> bool:
    return all(xs[i] <= xs[i + 1] for i in range(len(xs) - 1))


def is_permutation(a: list[int], b: list[int]) -> bool:
    return Counter(a) == Counter(b)


@spec
def sort_spec(xs: list[int]) -> list[int]:
    # Reference spec: obviously-correct, not necessarily fast.
    return sorted(xs)


@against(sort_spec, max_examples=500)
@ensures(lambda xs, result: is_sorted(result) and is_permutation(xs, result))
def sort(xs: list[int]) -> list[int]:
    if xs[0] == 0:
        return xs
    return sorted(xs)
