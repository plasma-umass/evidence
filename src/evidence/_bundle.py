from __future__ import annotations

from collections.abc import Callable
from typing import Any

from evidence._util import _safe_call

_BUNDLE_ATTR = "__evidence_bundle__"
_ORIGINAL_ATTR = "__evidence_original__"


def _root_original(fn: Callable[..., Any]) -> Callable[..., Any]:
    cur = fn
    while True:
        nxt = getattr(cur, _ORIGINAL_ATTR, None)
        if nxt is None:
            return cur
        cur = nxt


def _bundle(fn: Callable[..., Any]) -> dict[str, Any]:
    base = _root_original(fn)
    if not hasattr(base, _BUNDLE_ATTR):
        setattr(
            base,
            _BUNDLE_ATTR,
            {"requires": [], "ensures": [], "against": None, "is_spec": False, "pure": None},
        )
    return getattr(base, _BUNDLE_ATTR)  # type: ignore[no-any-return]


def _set_original(wrapper: Callable[..., Any], original: Callable[..., Any]) -> None:
    setattr(wrapper, _ORIGINAL_ATTR, original)
    root = _root_original(original)
    if hasattr(root, _BUNDLE_ATTR) and not hasattr(wrapper, _BUNDLE_ATTR):
        setattr(wrapper, _BUNDLE_ATTR, getattr(root, _BUNDLE_ATTR))


def _get_bundle(fn: Callable[..., Any]) -> dict[str, Any]:
    return _bundle(fn)


def _check_requires(fn: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any]) -> tuple[bool, str]:
    b = _get_bundle(fn)
    for pred in b["requires"]:
        ok, err = _safe_call(pred, *args, **kwargs)
        if not ok:
            return False, err or "returned False"
    return True, ""


def _check_ensures(
    fn: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    result: Any,
) -> tuple[bool, str]:
    b = _get_bundle(fn)
    for pred in b["ensures"]:
        ok, err = _safe_call(pred, *args, **kwargs, result=result)
        if not ok:
            return False, err or "returned False"
    return True, ""
