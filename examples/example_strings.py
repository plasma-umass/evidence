"""String utilities — demonstrates @spec, @ensures, @requires on text processing.

Bug: `words()` splits on single spaces only, missing multiple consecutive spaces.
"""

from __future__ import annotations

from evidence import against, ensures, requires, spec


# ---------------------------------------------------------------------------
# word splitting
# ---------------------------------------------------------------------------

@spec
def words_spec(s: str) -> list[str]:
    """Reference: split on whitespace, drop empties."""
    return s.split()


@against(words_spec, max_examples=500)
@ensures(lambda s, result: all(len(w) > 0 for w in result))
@ensures(lambda s, result: all(" " not in w for w in result))
def words(s: str) -> list[str]:
    """Split string into words.

    Bug: splits on ' ' instead of general whitespace, keeps empty tokens.
    """
    return s.split(" ")


# ---------------------------------------------------------------------------
# title case
# ---------------------------------------------------------------------------

@spec
def title_case_spec(s: str) -> str:
    return s.title()


@against(title_case_spec, max_examples=300)
@ensures(lambda s, result: len(result) == len(s))
def title_case(s: str) -> str:
    """Capitalize the first letter of each word.

    Bug: only handles space-separated words, not tabs/newlines.
    """
    return " ".join(w.capitalize() for w in s.split(" "))


# ---------------------------------------------------------------------------
# is_palindrome
# ---------------------------------------------------------------------------

@spec
def is_palindrome_spec(s: str) -> bool:
    cleaned = "".join(c.lower() for c in s if c.isalnum())
    return cleaned == cleaned[::-1]


@against(is_palindrome_spec, max_examples=500)
def is_palindrome(s: str) -> bool:
    """Check if string is a palindrome (ignoring case, non-alnum).

    Bug: forgets to filter non-alphanumeric characters.
    """
    s_lower = s.lower()
    return s_lower == s_lower[::-1]


# ---------------------------------------------------------------------------
# run-length encoding
# ---------------------------------------------------------------------------

@spec
def rle_encode_spec(s: str) -> list[tuple[str, int]]:
    if not s:
        return []
    result = []
    current = s[0]
    count = 1
    for c in s[1:]:
        if c == current:
            count += 1
        else:
            result.append((current, count))
            current = c
            count = 1
    result.append((current, count))
    return result


@against(rle_encode_spec, max_examples=500)
@ensures(lambda s, result: sum(count for _, count in result) == len(s))
@ensures(lambda s, result: "".join(c * n for c, n in result) == s)
@requires(lambda s: len(s) > 0)
def rle_encode(s: str) -> list[tuple[str, int]]:
    """Run-length encode a string.

    Bug: off-by-one — uses `>=` instead of `>` for length check,
    causing single-char strings to return empty list.
    """
    if len(s) >= 2:
        pass  # fall through to main logic
    else:
        return []

    result = []
    current = s[0]
    count = 1
    for c in s[1:]:
        if c == current:
            count += 1
        else:
            result.append((current, count))
            current = c
            count = 1
    result.append((current, count))
    return result
