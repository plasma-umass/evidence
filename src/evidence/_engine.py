from __future__ import annotations

import dataclasses
import importlib
import json
import os
import time
from collections.abc import Callable
from typing import Any

from hypothesis import assume, find, given, settings
from hypothesis.errors import FailedHealthCheck, NoSuchExample

from evidence._bundle import _BUNDLE_ATTR, _check_ensures, _check_requires, _get_bundle, _root_original
from evidence._purity import dynamic_purity_check, static_purity_check
from evidence._strategies import _find_satisfying_kwargs, _strategy_for_function
from evidence._util import _ensure_dir, _jsonable, _now_iso, _qualified_name


@dataclasses.dataclass
class ObligationResult:
    function: str
    obligation: str
    status: str  # "pass" | "fail" | "error" | "skip"
    details: dict[str, Any]
    duration_s: float = 0.0

    def to_json(self) -> dict[str, Any]:
        return {
            "function": self.function,
            "obligation": self.obligation,
            "status": self.status,
            "details": self.details,
            "duration_s": round(self.duration_s, 3),
        }


def _collect_functions(module: Any) -> list[Callable[..., Any]]:
    fns: list[Callable[..., Any]] = []
    for _name, obj in vars(module).items():
        if callable(obj) and hasattr(_root_original(obj), _BUNDLE_ATTR):
            fns.append(obj)
    return fns


def _find_counterexample(
    impl_root: Callable[..., Any],
    spec_fn: Callable[..., Any],
    eq: Callable[[Any, Any], bool],
    *,
    max_list_size: int,
) -> dict[str, Any] | None:
    strat_kwargs = _strategy_for_function(impl_root, max_list_size=max_list_size)

    def fails(kwargs: dict[str, Any]) -> bool:
        ok_pre, _ = _check_requires(impl_root, (), kwargs)
        if not ok_pre:
            return False
        try:
            impl_r = impl_root(**kwargs)
            ok_post, _ = _check_ensures(impl_root, (), kwargs, impl_r)
            if not ok_post:
                return True
            spec_r = spec_fn(**kwargs)
            return not eq(impl_r, spec_r)
        except Exception:
            return True

    try:
        kwargs = find(strat_kwargs, fails)
    except NoSuchExample:
        return None

    try:
        impl_r = impl_root(**kwargs)
        ok_post, post_err = _check_ensures(impl_root, (), kwargs, impl_r)
        if not ok_post:
            return {
                "kwargs": _jsonable(kwargs),
                "impl_result": _jsonable(impl_r),
                "spec_result": None,
                "note": f"ensures failed: {post_err}",
            }
        spec_r = spec_fn(**kwargs)
        return {
            "kwargs": _jsonable(kwargs),
            "impl_result": _jsonable(impl_r),
            "spec_result": _jsonable(spec_r),
        }
    except Exception as e:
        return {"kwargs": _jsonable(kwargs), "error": f"{type(e).__name__}: {e}"}


def check_module(
    module_name: str,
    *,
    out_dir: str = ".evidence",
    max_list_size: int = 20,
    smoke_max_list_size: int = 5,
    on_result: Callable[[ObligationResult], None] | None = None,
    coverage: bool = False,
    mutate: bool = False,
    prove: bool = False,
    suggest: bool = False,
    infer: bool = False,
) -> tuple[list[ObligationResult], dict[str, Any]]:
    _ensure_dir(out_dir)

    # Coverage collector (optional)
    cov_collector = None
    if coverage:
        from evidence._coverage import CoverageCollector
        cov_collector = CoverageCollector()
        if not cov_collector.available:
            import sys
            print("warning: coverage package not installed; install with: pip install evidence[coverage]",
                  file=sys.stderr)
            cov_collector = None
        else:
            cov_collector.start()

    module = importlib.import_module(module_name)
    funcs = _collect_functions(module)

    results: list[ObligationResult] = []
    trust: dict[str, Any] = {"module": module_name, "timestamp": _now_iso(), "functions": []}

    def _emit(result: ObligationResult) -> None:
        results.append(result)
        if on_result is not None:
            on_result(result)

    for fn in funcs:
        root = _root_original(fn)
        b = _get_bundle(root)
        qn = _qualified_name(root)

        # 1) Smoke: satisfiable requires + ensures on one satisfying input
        t0 = time.monotonic()
        try:
            smoke_strat = _strategy_for_function(root, max_list_size=smoke_max_list_size)
            example_kwargs = _find_satisfying_kwargs(root, smoke_strat)
            r = root(**example_kwargs)
            ok_post, post_err = _check_ensures(root, (), example_kwargs, r)
            if not ok_post:
                _emit(
                    ObligationResult(
                        qn,
                        "ensures_holds_on_smoke",
                        "fail",
                        {"example": _jsonable(example_kwargs), "result": _jsonable(r), "error": post_err},
                        duration_s=time.monotonic() - t0,
                    )
                )
            else:
                _emit(
                    ObligationResult(
                        qn,
                        "contracts_smoke",
                        "pass",
                        {
                            "example": _jsonable(example_kwargs),
                            "requires": len(b["requires"]),
                            "ensures": len(b["ensures"]),
                        },
                        duration_s=time.monotonic() - t0,
                    )
                )
        except NoSuchExample:
            _emit(ObligationResult(
                qn, "requires_satisfiable", "fail",
                {"error": "No satisfying input found"},
                duration_s=time.monotonic() - t0,
            ))
            trust["functions"].append({"function": qn})
            continue
        except Exception as e:
            _emit(ObligationResult(
                qn, "contracts_smoke", "error",
                {"error": f"{type(e).__name__}: {e}"},
                duration_s=time.monotonic() - t0,
            ))

        # 2) Purity check (if @pure is present)
        if b["pure"] is not None:
            pure_cfg = b["pure"]
            is_seed_det = pure_cfg.get("seed") is not None
            pure_eq = pure_cfg.get("eq")
            mode_label = "seed-deterministic" if is_seed_det else "strict"

            tp = time.monotonic()
            # Static analysis (skip nondeterminism warnings for seed-deterministic)
            static_warnings = static_purity_check(root, seed_deterministic=is_seed_det)
            if static_warnings:
                _emit(ObligationResult(
                    qn, "pure_static", "fail",
                    {"mode": mode_label, "warnings": [repr(w) for w in static_warnings]},
                    duration_s=time.monotonic() - tp,
                ))
            else:
                _emit(ObligationResult(
                    qn, "pure_static", "pass",
                    {"mode": mode_label, "message": "no impure operations detected"},
                    duration_s=time.monotonic() - tp,
                ))

            # Dynamic analysis: call twice with identical inputs, assert outputs match
            tp2 = time.monotonic()
            try:
                smoke_strat2 = _strategy_for_function(root, max_list_size=smoke_max_list_size)
                dyn_kwargs = _find_satisfying_kwargs(root, smoke_strat2)
                is_pure, pure_err = dynamic_purity_check(
                    root, dyn_kwargs,
                    seed=pure_cfg.get("seed"),
                    eq=pure_eq,
                )
                if is_pure:
                    _emit(ObligationResult(
                        qn, "pure_dynamic", "pass",
                        {"mode": mode_label, "example": _jsonable(dyn_kwargs)},
                        duration_s=time.monotonic() - tp2,
                    ))
                else:
                    _emit(ObligationResult(
                        qn, "pure_dynamic", "fail",
                        {"mode": mode_label, "example": _jsonable(dyn_kwargs), "error": pure_err},
                        duration_s=time.monotonic() - tp2,
                    ))
            except Exception as e:
                _emit(ObligationResult(
                    qn, "pure_dynamic", "error",
                    {"mode": mode_label, "error": f"{type(e).__name__}: {e}"},
                    duration_s=time.monotonic() - tp2,
                ))

        # 3) Spec equivalence
        t1 = time.monotonic()
        if b["against"] is not None and b["against"]["spec"] is not None:
            spec_fn = b["against"]["spec"]
            eq = b["against"]["eq"] or (lambda a, b2: a == b2)
            max_examples = int(b["against"]["max_examples"])
            deadline_ms = b["against"]["deadline_ms"]
            suppress_hc = b["against"]["suppress_health_checks"]

            # ---- deterministic probe first ----
            ce = _find_counterexample(root, spec_fn, eq, max_list_size=max_list_size)
            if ce is not None:
                _emit(
                    ObligationResult(
                        qn,
                        "equiv_to_spec",
                        "fail",
                        {
                            "spec": _qualified_name(spec_fn),
                            "error": "counterexample found by find()",
                            "counterexample": ce,
                        },
                        duration_s=time.monotonic() - t1,
                    )
                )
                trust["functions"].append({"function": qn})
                continue

            # ---- if no CE found by find(), do randomized search for confidence ----
            strat_kwargs = _strategy_for_function(root, max_list_size=max_list_size)

            # Mutable container to capture the shrunk counterexample from Hypothesis
            shrunk_ce: list[dict[str, Any] | None] = [None]

            def run_equiv(
                _root: Callable[..., Any] = root,
                _spec_fn: Callable[..., Any] = spec_fn,
                _eq: Callable[[Any, Any], bool] = eq,
                _max_examples: int = max_examples,
                _deadline_ms: int | None = deadline_ms,
                _suppress_hc: tuple[Any, ...] = suppress_hc,
                _strat_kwargs: Any = strat_kwargs,
                _shrunk_ce: list[dict[str, Any] | None] = shrunk_ce,
            ) -> None:
                @settings(
                    max_examples=_max_examples,
                    deadline=_deadline_ms,
                    suppress_health_check=list(_suppress_hc),
                    derandomize=False,
                )
                @given(_strat_kwargs)
                def prop(kwargs: dict[str, Any]) -> None:
                    ok_pre, _ = _check_requires(_root, (), kwargs)
                    assume(ok_pre)

                    impl_r = _root(**kwargs)
                    ok_post, post_err = _check_ensures(_root, (), kwargs, impl_r)
                    if not ok_post:
                        # Capture shrunk counterexample before raising
                        _shrunk_ce[0] = {
                            "kwargs": _jsonable(kwargs),
                            "impl_result": _jsonable(impl_r),
                            "spec_result": None,
                            "note": f"ensures failed: {post_err}",
                        }
                        raise AssertionError(f"ensures failed: {post_err}")

                    spec_r = _spec_fn(**kwargs)
                    if not _eq(impl_r, spec_r):
                        # Capture shrunk counterexample before raising
                        _shrunk_ce[0] = {
                            "kwargs": _jsonable(kwargs),
                            "impl_result": _jsonable(impl_r),
                            "spec_result": _jsonable(spec_r),
                        }
                        raise AssertionError("impl != spec")

                prop()

            try:
                run_equiv()
                _emit(
                    ObligationResult(
                        qn,
                        "equiv_to_spec",
                        "pass",
                        {
                            "spec": _qualified_name(spec_fn),
                            "max_examples": max_examples,
                            "requires": len(b["requires"]),
                            "ensures": len(b["ensures"]),
                        },
                        duration_s=time.monotonic() - t1,
                    )
                )
            except FailedHealthCheck as e:
                _emit(
                    ObligationResult(
                        qn,
                        "equiv_to_spec",
                        "fail",
                        {"spec": _qualified_name(spec_fn), "error": f"FailedHealthCheck: {e}"},
                        duration_s=time.monotonic() - t1,
                    )
                )
            except AssertionError as e:
                _emit(
                    ObligationResult(
                        qn,
                        "equiv_to_spec",
                        "fail",
                        {"spec": _qualified_name(spec_fn), "error": str(e), "counterexample": shrunk_ce[0]},
                        duration_s=time.monotonic() - t1,
                    )
                )
            except Exception as e:
                _emit(
                    ObligationResult(
                        qn,
                        "equiv_to_spec",
                        "error",
                        {"spec": _qualified_name(spec_fn), "error": f"{type(e).__name__}: {e}"},
                        duration_s=time.monotonic() - t1,
                    )
                )
        else:
            _emit(ObligationResult(
                qn, "equiv_to_spec", "skip",
                {"reason": "no @against(spec) attached"},
                duration_s=0.0,
            ))

        trust["functions"].append({"function": qn})

    # Stop coverage collection and emit per-function coverage results
    if cov_collector is not None:
        cov_collector.stop()
        for fn in funcs:
            root = _root_original(fn)
            qn = _qualified_name(root)
            report = cov_collector.report_for_function(root)
            if report is not None:
                _emit(ObligationResult(
                    qn, "coverage", "pass",
                    report,
                    duration_s=0.0,
                ))

    # Mutation testing (optional)
    if mutate:
        from evidence._mutate import compile_mutant, generate_mutants

        for fn in funcs:
            root = _root_original(fn)
            b = _get_bundle(root)
            qn = _qualified_name(root)

            # Skip spec functions
            if b.get("is_spec"):
                continue

            tm = time.monotonic()
            spec_cfg = b.get("against")
            spec_fn = spec_cfg["spec"] if spec_cfg else None
            eq_fn = (spec_cfg.get("eq") or (lambda a, b2: a == b2)) if spec_cfg else None

            mutant_list = generate_mutants(root, max_mutants=50)
            killed = 0
            survived = 0
            errors = 0
            survivors: list[dict[str, Any]] = []

            for m in mutant_list:
                mutated = compile_mutant(m, root)
                if mutated is None:
                    errors += 1
                    continue
                try:
                    caught = False
                    # Check postconditions
                    strat = _strategy_for_function(root, max_list_size=smoke_max_list_size)
                    try:
                        ex_kw = _find_satisfying_kwargs(root, strat)
                        mr = mutated(**ex_kw)
                        ok_post, _ = _check_ensures(root, (), ex_kw, mr)
                        if not ok_post:
                            caught = True
                        elif spec_fn is not None and eq_fn is not None:
                            sr = spec_fn(**ex_kw)
                            if not eq_fn(mr, sr):
                                caught = True
                    except Exception:
                        caught = True

                    if caught:
                        killed += 1
                    else:
                        survived += 1
                        survivors.append({
                            "operator": m.operator,
                            "description": m.description,
                            "lineno": m.lineno,
                        })
                except Exception:
                    errors += 1

            total_testable = killed + survived
            score = (killed / total_testable * 100) if total_testable > 0 else None
            status = "pass" if (score is not None and score >= 80) else "fail" if score is not None else "skip"
            _emit(ObligationResult(
                qn, "mutation_score", status,
                {
                    "total_mutants": len(mutant_list),
                    "killed": killed,
                    "survived": survived,
                    "errors": errors,
                    "mutation_score": round(score, 1) if score is not None else None,
                    "survivors": survivors[:5],  # limit detail output
                },
                duration_s=time.monotonic() - tm,
            ))

    # Symbolic verification (optional)
    if prove:
        from evidence._symbolic import prove_function

        for fn in funcs:
            root = _root_original(fn)
            b = _get_bundle(root)
            qn = _qualified_name(root)

            if b.get("is_spec"):
                continue

            tp = time.monotonic()
            spec_cfg = b.get("against")
            s_fn = spec_cfg["spec"] if spec_cfg else None
            s_eq = (spec_cfg.get("eq") or (lambda a, b2: a == b2)) if spec_cfg else None
            strat = _strategy_for_function(root, max_list_size=max_list_size)

            result = prove_function(
                root,
                spec_fn=s_fn,
                eq=s_eq,
                check_requires=_check_requires,
                check_ensures=_check_ensures,
                strategy=strat,
            )
            status_map = {"verified": "pass", "disproved": "fail", "inconclusive": "skip", "unavailable": "skip"}
            _emit(ObligationResult(
                qn, "symbolic_proof", status_map.get(result["status"], "skip"),
                result,
                duration_s=time.monotonic() - tp,
            ))

    # Spec inference (optional)
    if infer:
        from evidence._infer import infer_all

        for fn in funcs:
            root = _root_original(fn)
            b = _get_bundle(root)
            qn = _qualified_name(root)

            if b.get("is_spec"):
                continue

            ti = time.monotonic()
            # Get mutation score if available
            mut_score = None
            for r in results:
                if r.function == qn and r.obligation == "mutation_score":
                    mut_score = r.details.get("mutation_score")

            props = infer_all(fn, include_llm=suggest, mutation_score=mut_score)
            holding = [p.to_dict() for p in props if p.holds]
            not_holding = [p.to_dict() for p in props if not p.holds]

            _emit(ObligationResult(
                qn, "inferred_properties", "pass" if holding else "skip",
                {
                    "properties_found": len(holding),
                    "properties_rejected": len(not_holding),
                    "holding": holding,
                    "not_holding": not_holding,
                },
                duration_s=time.monotonic() - ti,
            ))

    # LLM-assisted spec mining (optional)
    if suggest:
        from evidence._suggest import ClaudeSuggester, validate_suggestion

        try:
            suggester = ClaudeSuggester()
            for fn in funcs:
                root = _root_original(fn)
                b = _get_bundle(root)
                qn = _qualified_name(root)

                if b.get("is_spec"):
                    continue

                ts = time.monotonic()
                existing = {
                    "requires": len(b["requires"]),
                    "ensures": len(b["ensures"]),
                    "has_spec": b["against"] is not None,
                }

                # Get mutation score if available from results
                mut_score = None
                for r in results:
                    if r.function == qn and r.obligation == "mutation_score":
                        mut_score = r.details.get("mutation_score")

                suggestions = suggester.suggest(
                    root,
                    existing_contracts=existing,
                    mutation_score=mut_score,
                )

                # Validate each suggestion
                validated = []
                for s in suggestions:
                    valid = validate_suggestion(s, fn)
                    validated.append({**s.to_dict(), "validated": valid})

                _emit(ObligationResult(
                    qn, "spec_suggestions", "pass" if validated else "skip",
                    {"suggestions": validated},
                    duration_s=time.monotonic() - ts,
                ))
        except ImportError:
            import sys
            print("warning: anthropic package not installed; install with: pip install evidence[suggest]",
                  file=sys.stderr)

    obligations_path = os.path.join(out_dir, f"{module_name}.obligations.json")
    trust_path = os.path.join(out_dir, f"{module_name}.trust.json")

    with open(obligations_path, "w", encoding="utf-8") as f:
        json.dump([r.to_json() for r in results], f, indent=2)

    with open(trust_path, "w", encoding="utf-8") as f:
        json.dump(trust, f, indent=2)

    return results, trust
