from __future__ import annotations

import dataclasses
import os
import time
from collections.abc import Callable
from typing import Any

from hypothesis import strategies as st

EvidencePredicate = Callable[..., bool]
StrategyFactory = Callable[..., st.SearchStrategy[Any]]


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _qualified_name(fn: Callable[..., Any]) -> str:
    return f"{fn.__module__}.{getattr(fn, '__qualname__', getattr(fn, '__name__', str(fn)))}"


def _jsonable(obj: Any) -> Any:
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, (list, tuple)):
        return [_jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {"__dataclass__": obj.__class__.__name__, **_jsonable(dataclasses.asdict(obj))}
    return repr(obj)


def _safe_call(pred: EvidencePredicate, *args: Any, **kwargs: Any) -> tuple[bool, str | None]:
    try:
        return bool(pred(*args, **kwargs)), None
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
