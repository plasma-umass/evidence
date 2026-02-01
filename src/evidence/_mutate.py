"""Lightweight AST-based mutation testing for Evidence.

Seven mutation operators:
1. Flip comparisons: ==/<=> !=, </<=> >=, >/<=> <=
2. Swap arithmetic: +/<=>-, */<=>/, //<=>%
3. Negate conditions: `if x` -> `if not x`
4. Delete statements: remove body statements (replace with `pass`)
5. Change constants: int +/- 1, flip bools, empty strings
6. Swap boolean ops: and/<=>or
7. Remove return values: `return x` -> `return None`

No external dependencies (stdlib ast only).
"""

from __future__ import annotations

import ast
import copy
import inspect
import textwrap
from collections.abc import Callable
from typing import Any


class Mutant:
    """Represents a single mutation applied to a function."""

    __slots__ = ("description", "lineno", "operator", "tree")

    def __init__(self, operator: str, description: str, lineno: int | None, tree: ast.Module) -> None:
        self.operator = operator
        self.description = description
        self.lineno = lineno
        self.tree = tree

    def __repr__(self) -> str:
        loc = f" (line {self.lineno})" if self.lineno is not None else ""
        return f"Mutant({self.operator}: {self.description}{loc})"


# ---------- Comparison operator flips ----------

_CMP_FLIPS: dict[type[ast.cmpop], type[ast.cmpop]] = {
    ast.Eq: ast.NotEq,
    ast.NotEq: ast.Eq,
    ast.Lt: ast.GtE,
    ast.GtE: ast.Lt,
    ast.Gt: ast.LtE,
    ast.LtE: ast.Gt,
    ast.Is: ast.IsNot,
    ast.IsNot: ast.Is,
    ast.In: ast.NotIn,
    ast.NotIn: ast.In,
}

# ---------- Arithmetic operator swaps ----------

_ARITH_SWAPS: dict[type[ast.operator], type[ast.operator]] = {
    ast.Add: ast.Sub,
    ast.Sub: ast.Add,
    ast.Mult: ast.Div,
    ast.Div: ast.Mult,
    ast.FloorDiv: ast.Mod,
    ast.Mod: ast.FloorDiv,
}

# ---------- Boolean operator swaps ----------

_BOOL_SWAPS: dict[type[ast.boolop], type[ast.boolop]] = {
    ast.And: ast.Or,
    ast.Or: ast.And,
}


def _get_source_and_tree(fn: Callable[..., Any]) -> tuple[str, ast.Module, int] | None:
    """Get dedented source, parsed AST, and starting line offset."""
    try:
        source = inspect.getsource(fn)
        _, start_line = inspect.getsourcelines(fn)
    except (OSError, TypeError):
        return None
    source = textwrap.dedent(source)
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    return source, tree, start_line


def generate_mutants(fn: Callable[..., Any], *, max_mutants: int = 50) -> list[Mutant]:
    """Generate mutant ASTs for a function.

    Returns at most max_mutants mutants to keep execution bounded.
    """
    result = _get_source_and_tree(fn)
    if result is None:
        return []
    _source, tree, _start = result
    mutants: list[Mutant] = []

    # Walk the AST and generate mutations
    for node in ast.walk(tree):
        if len(mutants) >= max_mutants:
            break

        # 1) Flip comparisons
        if isinstance(node, ast.Compare):
            for i, op in enumerate(node.ops):
                if type(op) in _CMP_FLIPS and len(mutants) < max_mutants:
                    new_tree = copy.deepcopy(tree)
                    _apply_cmp_flip(new_tree, node, i)
                    mutants.append(Mutant(
                        "flip_comparison",
                        f"{type(op).__name__} -> {_CMP_FLIPS[type(op)].__name__}",
                        getattr(node, "lineno", None),
                        new_tree,
                    ))

        # 2) Swap arithmetic
        if isinstance(node, ast.BinOp) and type(node.op) in _ARITH_SWAPS and len(mutants) < max_mutants:
                new_tree = copy.deepcopy(tree)
                _apply_arith_swap(new_tree, node)
                mutants.append(Mutant(
                    "swap_arithmetic",
                    f"{type(node.op).__name__} -> {_ARITH_SWAPS[type(node.op)].__name__}",
                    getattr(node, "lineno", None),
                    new_tree,
                ))

        # 3) Negate conditions
        if isinstance(node, ast.If) and len(mutants) < max_mutants:
                new_tree = copy.deepcopy(tree)
                _apply_negate_condition(new_tree, node)
                mutants.append(Mutant(
                    "negate_condition",
                    "if cond -> if not cond",
                    getattr(node, "lineno", None),
                    new_tree,
                ))

        # 4) Delete statements (replace with pass)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for i, stmt in enumerate(node.body):
                if len(mutants) >= max_mutants:
                    break
                if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    new_tree = copy.deepcopy(tree)
                    _apply_delete_stmt(new_tree, node, i)
                    mutants.append(Mutant(
                        "delete_statement",
                        f"delete statement at line {getattr(stmt, 'lineno', '?')}",
                        getattr(stmt, "lineno", None),
                        new_tree,
                    ))

        # 5) Change constants
        if isinstance(node, ast.Constant) and len(mutants) < max_mutants:
                new_val = _mutate_constant(node.value)
                if new_val is not None:
                    new_tree = copy.deepcopy(tree)
                    _apply_change_constant(new_tree, node, new_val)
                    mutants.append(Mutant(
                        "change_constant",
                        f"{node.value!r} -> {new_val!r}",
                        getattr(node, "lineno", None),
                        new_tree,
                    ))

        # 6) Swap boolean ops
        if isinstance(node, ast.BoolOp) and type(node.op) in _BOOL_SWAPS and len(mutants) < max_mutants:
                new_tree = copy.deepcopy(tree)
                _apply_bool_swap(new_tree, node)
                mutants.append(Mutant(
                    "swap_boolean",
                    f"{type(node.op).__name__} -> {_BOOL_SWAPS[type(node.op)].__name__}",
                    getattr(node, "lineno", None),
                    new_tree,
                ))

        # 7) Remove return values
        if isinstance(node, ast.Return) and node.value is not None and len(mutants) < max_mutants:
                new_tree = copy.deepcopy(tree)
                _apply_remove_return(new_tree, node)
                mutants.append(Mutant(
                    "remove_return",
                    "return x -> return None",
                    getattr(node, "lineno", None),
                    new_tree,
                ))

    return mutants


def _apply_cmp_flip(tree: ast.Module, target: ast.Compare, idx: int) -> None:
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and _same_loc(node, target):
            node.ops[idx] = _CMP_FLIPS[type(node.ops[idx])]()
            return


def _apply_arith_swap(tree: ast.Module, target: ast.BinOp) -> None:
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and _same_loc(node, target):
            node.op = _ARITH_SWAPS[type(node.op)]()
            return


def _apply_negate_condition(tree: ast.Module, target: ast.If) -> None:
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and _same_loc(node, target):
            node.test = ast.UnaryOp(op=ast.Not(), operand=node.test)
            ast.fix_missing_locations(tree)
            return


def _apply_delete_stmt(tree: ast.Module, target_fn: ast.FunctionDef | ast.AsyncFunctionDef, idx: int) -> None:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _same_loc(node, target_fn):
            node.body[idx] = ast.Pass()
            ast.fix_missing_locations(tree)
            return


def _apply_change_constant(tree: ast.Module, target: ast.Constant, new_val: Any) -> None:
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and _same_loc(node, target) and node.value == target.value:
            node.value = new_val
            return


def _apply_bool_swap(tree: ast.Module, target: ast.BoolOp) -> None:
    for node in ast.walk(tree):
        if isinstance(node, ast.BoolOp) and _same_loc(node, target):
            node.op = _BOOL_SWAPS[type(node.op)]()
            return


def _apply_remove_return(tree: ast.Module, target: ast.Return) -> None:
    for node in ast.walk(tree):
        if isinstance(node, ast.Return) and _same_loc(node, target):
            node.value = ast.Constant(value=None)
            ast.fix_missing_locations(tree)
            return


def _same_loc(a: ast.AST, b: ast.AST) -> bool:
    return (
        getattr(a, "lineno", None) == getattr(b, "lineno", None)
        and getattr(a, "col_offset", None) == getattr(b, "col_offset", None)
    )


def _mutate_constant(val: Any) -> Any:
    if isinstance(val, bool):
        return not val
    if isinstance(val, int):
        return val + 1
    if isinstance(val, float):
        return val + 1.0
    if isinstance(val, str) and val:
        return ""
    return None


def compile_mutant(mutant: Mutant, fn: Callable[..., Any]) -> Callable[..., Any] | None:
    """Compile a mutant AST back into a callable function.

    Returns None if compilation fails.
    """
    ast.fix_missing_locations(mutant.tree)
    try:
        code = compile(mutant.tree, f"<mutant:{mutant.operator}>", "exec")
    except (SyntaxError, TypeError):
        return None

    # Execute in a namespace with the function's globals
    ns: dict[str, Any] = dict(fn.__globals__) if hasattr(fn, "__globals__") else {}
    try:
        exec(code, ns)
    except Exception:
        return None

    fn_name = fn.__name__
    mutated_fn = ns.get(fn_name)
    if mutated_fn is None or not callable(mutated_fn):
        return None

    return mutated_fn  # type: ignore[no-any-return]


def run_mutation_testing(
    fn: Callable[..., Any],
    checker: Callable[[Callable[..., Any]], bool],
    *,
    max_mutants: int = 50,
) -> dict[str, Any]:
    """Run mutation testing on a function.

    Args:
        fn: The function to mutate.
        checker: A callable that takes a (possibly mutated) function and returns
                 True if Evidence catches the mutation (test fails), False if the
                 mutation survives (test passes).
        max_mutants: Maximum number of mutants to generate.

    Returns:
        Dict with mutation score details.
    """
    mutants = generate_mutants(fn, max_mutants=max_mutants)
    if not mutants:
        return {
            "total_mutants": 0,
            "killed": 0,
            "survived": 0,
            "errors": 0,
            "mutation_score": None,
            "survivors": [],
        }

    killed = 0
    survived = 0
    errors = 0
    survivors: list[dict[str, Any]] = []

    for mutant in mutants:
        mutated_fn = compile_mutant(mutant, fn)
        if mutated_fn is None:
            errors += 1
            continue
        try:
            caught = checker(mutated_fn)
            if caught:
                killed += 1
            else:
                survived += 1
                survivors.append({
                    "operator": mutant.operator,
                    "description": mutant.description,
                    "lineno": mutant.lineno,
                })
        except Exception:
            errors += 1

    total_testable = killed + survived
    score = (killed / total_testable * 100) if total_testable > 0 else None

    return {
        "total_mutants": len(mutants),
        "killed": killed,
        "survived": survived,
        "errors": errors,
        "mutation_score": round(score, 1) if score is not None else None,
        "survivors": survivors,
    }
