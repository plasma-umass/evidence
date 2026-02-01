from __future__ import annotations

import dataclasses
import inspect
from collections.abc import Callable
from dataclasses import is_dataclass
from typing import Any, Union, get_args, get_origin, get_type_hints

from hypothesis import find
from hypothesis import strategies as st

from evidence._bundle import _check_requires, _root_original
from evidence._util import StrategyFactory

_STRATEGY_OVERRIDES: dict[Any, st.SearchStrategy[Any]] = {}
_STRATEGY_FACTORY_OVERRIDES: dict[Any, StrategyFactory] = {}


def register_strategy(tp: Any, strat: st.SearchStrategy[Any]) -> None:
    _STRATEGY_OVERRIDES[tp] = strat


def register_strategy_factory(tp: Any, factory: StrategyFactory) -> None:
    _STRATEGY_FACTORY_OVERRIDES[tp] = factory


def _try_override(tp: Any, *, max_list_size: int, depth: int) -> st.SearchStrategy[Any] | None:
    if tp in _STRATEGY_OVERRIDES:
        return _STRATEGY_OVERRIDES[tp]
    if tp in _STRATEGY_FACTORY_OVERRIDES:
        return _STRATEGY_FACTORY_OVERRIDES[tp](max_list_size=max_list_size, depth=depth)

    origin = get_origin(tp)
    if origin in _STRATEGY_OVERRIDES:
        return _STRATEGY_OVERRIDES[origin]
    if origin in _STRATEGY_FACTORY_OVERRIDES:
        return _STRATEGY_FACTORY_OVERRIDES[origin](max_list_size=max_list_size, depth=depth)

    return None


def _strategy_for_type(tp: Any, *, max_list_size: int = 20, depth: int = 0) -> st.SearchStrategy[Any]:
    if depth > 5:
        return st.none()

    ov = _try_override(tp, max_list_size=max_list_size, depth=depth)
    if ov is not None:
        return ov

    origin = get_origin(tp)
    args = get_args(tp)

    if tp is Any:
        return st.one_of(st.none(), st.booleans(), st.integers(), st.floats(allow_nan=False), st.text())
    if tp is int:
        return st.integers()
    if tp is float:
        return st.floats(allow_nan=False, allow_infinity=False)
    if tp is bool:
        return st.booleans()
    if tp is str:
        return st.text()
    if tp is bytes:
        return st.binary()

    if origin is Union and len(args) == 2 and type(None) in args:
        other = args[0] if args[1] is type(None) else args[1]
        return st.one_of(st.none(), _strategy_for_type(other, max_list_size=max_list_size, depth=depth + 1))

    if origin is Union:
        return st.one_of(*[_strategy_for_type(a, max_list_size=max_list_size, depth=depth + 1) for a in args])

    if origin is tuple:
        if len(args) == 2 and args[1] is Ellipsis:
            return st.lists(
                _strategy_for_type(args[0], max_list_size=max_list_size, depth=depth + 1),
                max_size=max_list_size,
            ).map(tuple)
        return st.tuples(*[_strategy_for_type(a, max_list_size=max_list_size, depth=depth + 1) for a in args])

    if origin is list:
        (elem,) = args if args else (Any,)
        return st.lists(_strategy_for_type(elem, max_list_size=max_list_size, depth=depth + 1), max_size=max_list_size)

    if origin is dict:
        k, v = args if args else (Any, Any)
        return st.dictionaries(
            _strategy_for_type(k, max_list_size=max_list_size, depth=depth + 1),
            _strategy_for_type(v, max_list_size=max_list_size, depth=depth + 1),
            max_size=max_list_size,
        )

    if origin is set:
        (elem,) = args if args else (Any,)
        return st.sets(_strategy_for_type(elem, max_list_size=max_list_size, depth=depth + 1), max_size=max_list_size)

    if isinstance(tp, type) and is_dataclass(tp):
        field_strats = {
            f.name: _strategy_for_type(f.type, max_list_size=max_list_size, depth=depth + 1)
            for f in dataclasses.fields(tp)
        }
        return st.builds(tp, **field_strats)

    return st.just(None)


def _strategy_for_function(fn: Callable[..., Any], *, max_list_size: int = 20) -> st.SearchStrategy[dict[str, Any]]:
    sig = inspect.signature(fn)
    hints = get_type_hints(fn)

    kwargs_strats: dict[str, st.SearchStrategy[Any]] = {}
    for name, param in sig.parameters.items():
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            continue
        tp = hints.get(name, Any)
        s = _strategy_for_type(tp, max_list_size=max_list_size)
        if param.default is not inspect._empty:
            kwargs_strats[name] = st.one_of(st.just(param.default), s)
        else:
            kwargs_strats[name] = s

    return st.fixed_dictionaries(kwargs_strats)


def _find_satisfying_kwargs(
    fn: Callable[..., Any], strat_kwargs: st.SearchStrategy[dict[str, Any]]
) -> dict[str, Any]:
    root = _root_original(fn)

    def ok(kwargs: dict[str, Any]) -> bool:
        ok_pre, _ = _check_requires(root, (), kwargs)
        return ok_pre

    return find(strat_kwargs, ok)
