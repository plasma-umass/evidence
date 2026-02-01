"""Math functions — demonstrates @requires preconditions and multiple @ensures.

Bug: `gcd()` fails when both arguments are zero.
Bug: `fibonacci()` is off-by-one for index 0.
"""

from __future__ import annotations

from evidence import against, ensures, pure, requires, spec


# ---------------------------------------------------------------------------
# greatest common divisor
# ---------------------------------------------------------------------------

@spec
@pure
def gcd_spec(a: int, b: int) -> int:
    """Reference GCD via Euclidean algorithm."""
    a, b = abs(a), abs(b)
    while b:
        a, b = b, a % b
    return a


@against(gcd_spec, max_examples=500)
@ensures(lambda a, b, result: result >= 0)
@ensures(lambda a, b, result: (a == 0 and b == 0) or result > 0 or (a == 0 and b == 0))
@requires(lambda a, b: abs(a) < 10000 and abs(b) < 10000)
@pure
def gcd(a: int, b: int) -> int:
    """Compute GCD.

    Bug: doesn't handle the case where a == 0 properly (returns b without abs).
    """
    if a == 0:
        return b  # Bug: should be abs(b)
    if b == 0:
        return abs(a)
    a, b = abs(a), abs(b)
    while b:
        a, b = b, a % b
    return a


# ---------------------------------------------------------------------------
# fibonacci
# ---------------------------------------------------------------------------

@spec
@pure
def fib_spec(n: int) -> int:
    """Reference Fibonacci."""
    if n <= 0:
        return 0
    if n == 1:
        return 1
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b


@against(fib_spec, max_examples=300)
@ensures(lambda n, result: result >= 0)
@requires(lambda n: 0 <= n <= 30)
@pure
def fib(n: int) -> int:
    """Compute nth Fibonacci number.

    Bug: off-by-one — iterates one too few times.
    """
    if n <= 0:
        return 0
    if n == 1:
        return 1
    a, b = 0, 1
    for _ in range(2, n):  # Bug: should be range(2, n + 1)
        a, b = b, a + b
    return b


# ---------------------------------------------------------------------------
# integer square root
# ---------------------------------------------------------------------------

@spec
@pure
def isqrt_spec(n: int) -> int:
    """Reference: largest integer k such that k*k <= n."""
    if n < 0:
        return 0
    k = 0
    while (k + 1) * (k + 1) <= n:
        k += 1
    return k


@against(isqrt_spec, max_examples=500)
@ensures(lambda n, result: result * result <= n)
@ensures(lambda n, result: (result + 1) * (result + 1) > n)
@requires(lambda n: 0 <= n <= 100000)
@pure
def isqrt(n: int) -> int:
    """Integer square root via Newton's method.

    This implementation is actually correct.
    """
    if n < 0:
        return 0
    if n == 0:
        return 0
    x = n
    while True:
        x1 = (x + n // x) // 2
        if x1 >= x:
            return x
        x = x1


# ---------------------------------------------------------------------------
# power (modular exponentiation)
# ---------------------------------------------------------------------------

@spec
@requires(lambda base, exp, mod: exp >= 0 and mod > 1 and abs(base) < 1000)
@requires(lambda base, exp, mod: exp <= 20)
@pure
def mod_pow_spec(base: int, exp: int, mod: int) -> int:
    return pow(base, exp, mod)


@against(mod_pow_spec, max_examples=500)
@ensures(lambda base, exp, mod, result: 0 <= result < mod)
@requires(lambda base, exp, mod: exp >= 0 and mod > 1 and abs(base) < 1000)
@requires(lambda base, exp, mod: exp <= 20)
@pure
def mod_pow(base: int, exp: int, mod: int) -> int:
    """Fast modular exponentiation.

    This implementation is correct.
    """
    result = 1
    base = base % mod
    while exp > 0:
        if exp % 2 == 1:
            result = (result * base) % mod
        exp = exp >> 1
        base = (base * base) % mod
    return result
