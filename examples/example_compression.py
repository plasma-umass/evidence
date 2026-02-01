"""Compression/encoding — demonstrates round-trip properties and @pure.

Bug: `base64_encode`/`base64_decode` pair fails on bytes with padding.
"""

from __future__ import annotations

from evidence import against, ensures, pure, requires, spec


# ---------------------------------------------------------------------------
# Caesar cipher (encode + decode should round-trip)
# ---------------------------------------------------------------------------

@pure
@ensures(lambda text, shift, result: len(result) == len(text))
@requires(lambda text, shift: 0 <= shift < 26)
@requires(lambda text, shift: all(c.isalpha() and c.islower() for c in text))
@requires(lambda text, shift: len(text) <= 100)
def caesar_encode(text: str, shift: int) -> str:
    """Encode with Caesar cipher.

    This implementation is correct.
    """
    result = []
    for c in text:
        shifted = chr((ord(c) - ord("a") + shift) % 26 + ord("a"))
        result.append(shifted)
    return "".join(result)


@pure
@ensures(lambda text, shift, result: len(result) == len(text))
@requires(lambda text, shift: 0 <= shift < 26)
@requires(lambda text, shift: all(c.isalpha() and c.islower() for c in text))
@requires(lambda text, shift: len(text) <= 100)
def caesar_decode(text: str, shift: int) -> str:
    """Decode Caesar cipher.

    This implementation is correct.
    """
    result = []
    for c in text:
        shifted = chr((ord(c) - ord("a") - shift) % 26 + ord("a"))
        result.append(shifted)
    return "".join(result)


# ---------------------------------------------------------------------------
# round-trip test via @spec/@against
# ---------------------------------------------------------------------------

@spec
def roundtrip_caesar_spec(text: str, shift: int) -> str:
    """Encoding then decoding should return the original."""
    return text


@ensures(lambda text, shift, result: result == text)
@requires(lambda text, shift: 0 <= shift < 26)
@requires(lambda text, shift: all(c.isalpha() and c.islower() for c in text))
@requires(lambda text, shift: len(text) <= 100)
@pure
def roundtrip_caesar(text: str, shift: int) -> str:
    """Encode then decode — should be identity.

    This implementation is correct.
    """
    return caesar_decode(caesar_encode(text, shift), shift)


# ---------------------------------------------------------------------------
# simple checksum
# ---------------------------------------------------------------------------

@spec
@pure
def checksum_spec(data: list[int]) -> int:
    """Reference: sum mod 256."""
    return sum(data) % 256


@against(checksum_spec, max_examples=500)
@ensures(lambda data, result: 0 <= result < 256)
@requires(lambda data: all(0 <= x < 256 for x in data))
@requires(lambda data: len(data) <= 100)
@pure
def checksum(data: list[int]) -> int:
    """Compute a simple checksum.

    Bug: uses XOR instead of sum, producing different results.
    """
    result = 0
    for b in data:
        result ^= b  # Bug: should be result = (result + b) % 256
    return result % 256


# ---------------------------------------------------------------------------
# zigzag encoding (signed -> unsigned for varints)
# ---------------------------------------------------------------------------

@spec
@pure
def zigzag_encode_spec(n: int) -> int:
    """Reference zigzag encoding: 0->0, -1->1, 1->2, -2->3, 2->4, ..."""
    if n >= 0:
        return 2 * n
    return -2 * n - 1


@spec
@pure
def zigzag_decode_spec(n: int) -> int:
    """Reference zigzag decoding."""
    if n % 2 == 0:
        return n // 2
    return -(n + 1) // 2


@ensures(lambda n, result: result >= 0)
@requires(lambda n: abs(n) < 10000)
@pure
def zigzag_encode(n: int) -> int:
    """Zigzag-encode a signed integer.

    This implementation is correct.
    """
    if n >= 0:
        return 2 * n
    return -2 * n - 1


@ensures(lambda n, result: zigzag_encode(result) == n)
@requires(lambda n: 0 <= n < 20000)
@pure
def zigzag_decode(n: int) -> int:
    """Zigzag-decode back to signed.

    This implementation is correct.
    """
    if n % 2 == 0:
        return n // 2
    return -(n + 1) // 2
