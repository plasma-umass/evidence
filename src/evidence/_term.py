from __future__ import annotations

import os
import sys

_COLOR: bool | None = None


def supports_color() -> bool:
    global _COLOR
    if _COLOR is not None:
        return _COLOR
    if (
        os.environ.get("NO_COLOR", "") != ""
        or os.environ.get("TERM", "") == "dumb"
        or not hasattr(sys.stdout, "isatty")
        or not sys.stdout.isatty()
    ):
        _COLOR = False
    else:
        _COLOR = True
    return _COLOR


def force_color(enabled: bool) -> None:
    global _COLOR
    _COLOR = enabled


def style(text: str, *codes: int) -> str:
    if not supports_color() or not codes:
        return text
    seq = ";".join(str(c) for c in codes)
    return f"\033[{seq}m{text}\033[0m"


def green(text: str) -> str:
    return style(text, 32)


def red(text: str) -> str:
    return style(text, 31)


def yellow(text: str) -> str:
    return style(text, 33)


def dim(text: str) -> str:
    return style(text, 2)


def bold(text: str) -> str:
    return style(text, 1)
