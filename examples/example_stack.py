"""Stack data structure — demonstrates dataclass strategies and invariant checking.

Bug: `push_many()` reverses the order of pushed elements.
"""

from __future__ import annotations

import dataclasses

from evidence import against, ensures, requires, spec


# ---------------------------------------------------------------------------
# Stack as a list wrapper
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class Stack:
    items: list[int] = dataclasses.field(default_factory=list)

    def push(self, x: int) -> None:
        self.items.append(x)

    def pop(self) -> int:
        return self.items.pop()

    def peek(self) -> int:
        return self.items[-1]

    def is_empty(self) -> bool:
        return len(self.items) == 0

    def size(self) -> int:
        return len(self.items)


# ---------------------------------------------------------------------------
# push_many: push a list of elements onto the stack
# ---------------------------------------------------------------------------

@spec
def push_many_spec(xs: list[int]) -> list[int]:
    """Reference: after pushing all of xs, stack contains xs in order."""
    return list(xs)


@against(push_many_spec, max_examples=500)
@ensures(lambda xs, result: len(result) == len(xs))
@ensures(lambda xs, result: all(a == b for a, b in zip(result, xs, strict=True)))
def push_many(xs: list[int]) -> list[int]:
    """Push elements onto a stack and return the stack contents.

    Bug: iterates in reverse, so elements are pushed in wrong order.
    """
    s = Stack()
    for x in reversed(xs):  # Bug: should not reverse
        s.push(x)
    return s.items


# ---------------------------------------------------------------------------
# balanced parentheses checker
# ---------------------------------------------------------------------------

@spec
def is_balanced_spec(s: str) -> bool:
    """Reference balanced-paren checker."""
    depth = 0
    for c in s:
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        if depth < 0:
            return False
    return depth == 0


@against(is_balanced_spec, max_examples=500)
@requires(lambda s: all(c in "()" for c in s))
@requires(lambda s: len(s) <= 20)
def is_balanced(s: str) -> bool:
    """Check if parentheses are balanced using a stack.

    This implementation is correct.
    """
    stack: list[str] = []
    for c in s:
        if c == "(":
            stack.append(c)
        elif c == ")":
            if not stack:
                return False
            stack.pop()
    return len(stack) == 0


# ---------------------------------------------------------------------------
# reverse_list using a stack
# ---------------------------------------------------------------------------

@spec
def reverse_spec(xs: list[int]) -> list[int]:
    return xs[::-1]


@against(reverse_spec, max_examples=500)
@ensures(lambda xs, result: len(result) == len(xs))
@ensures(lambda xs, result: sorted(result) == sorted(xs))
def reverse_list(xs: list[int]) -> list[int]:
    """Reverse a list using a stack.

    This implementation is correct.
    """
    s = Stack()
    for x in xs:
        s.push(x)
    result = []
    while not s.is_empty():
        result.append(s.pop())
    return result
