from __future__ import annotations

import argparse
import importlib
import json
import sys
import time

from evidence._engine import ObligationResult, check_module
from evidence._term import bold, dim, force_color, green, red, style, yellow


def _status_label(status: str) -> str:
    if status == "pass":
        return green("PASS")
    if status == "fail":
        return style("FAIL", 31, 1)  # red bold
    if status == "error":
        return red("ERROR")
    if status == "skip":
        return yellow("SKIP")
    return status.upper()


def _print_result_line(r: ObligationResult, *, verbose: bool = False) -> None:
    label = _status_label(r.status)
    # Pad the raw status to 5 chars, then colorize — avoids ANSI codes breaking alignment
    raw = r.status.upper()
    pad = " " * (5 - len(raw))
    timing = "  " + dim(f"({r.duration_s:.1f}s)") if r.duration_s >= 0.05 else ""
    print(f"  {pad}{label}  {r.obligation:<22}  {bold(r.function)}{timing}")

    if verbose and r.status == "fail":
        ce = r.details.get("counterexample")
        if ce and isinstance(ce, dict):
            if "kwargs" in ce:
                print(f"         kwargs: {json.dumps(ce['kwargs'], default=str)}")
            if "impl_result" in ce:
                print(f"         impl:   {json.dumps(ce['impl_result'], default=str)}")
            if "spec_result" in ce:
                print(f"         spec:   {json.dumps(ce['spec_result'], default=str)}")
            if "note" in ce:
                print(f"         note:   {ce['note']}")
            if "error" in ce:
                print(f"         error:  {ce['error']}")
        # Show purity warnings
        if "warnings" in r.details:
            for w in r.details["warnings"]:
                print(f"         warning: {w}")
        # Show standalone error
        if "error" in r.details and not ce:
            print(f"         error:  {r.details['error']}")

    if verbose and r.obligation == "inferred_properties":
        for p in r.details.get("holding", []):
            print(f"         {green('HOLDS')}  {p['name']}: {p['description']}  ({dim(p.get('source', ''))})")
        for p in r.details.get("not_holding", []):
            print(f"         {red('FAILS')}  {p['name']}: {p['description']}")

    if verbose and r.obligation == "spec_suggestions":
        for s in r.details.get("suggestions", []):
            valid_marker = green("valid") if s.get("validated") else red("unverified")
            print(f"         [{s.get('kind', '?')}] {s.get('description', '')}  ({valid_marker})")
            print(f"           {s.get('code', '')}")

    if verbose and r.obligation == "mutation_score":
        d = r.details
        score = d.get("mutation_score")
        print(f"         score:    {score}%" if score is not None else "         score:    N/A")
        print(f"         killed:   {d.get('killed', 0)}/{d.get('total_mutants', 0)}")
        surv = d.get("survivors", [])
        for s in surv:
            print(f"         survived: {s['operator']}: {s['description']}")

    if verbose and r.obligation == "coverage":
        d = r.details
        print(f"         lines:    {d.get('lines_covered', '?')}/{d.get('lines_total', '?')}"
              f" ({d.get('line_coverage_pct', '?')}%)")
        print(f"         branches: {d.get('branches_covered', '?')}/{d.get('branches_total', '?')}"
              f" ({d.get('branch_coverage_pct', '?')}%)")
        missing = d.get("missing_lines", [])
        if missing:
            print(f"         missing:  {missing}")


def _print_summary(results: list[ObligationResult], total_s: float, out_dir: str) -> None:
    passed = sum(1 for r in results if r.status == "pass")
    failed = sum(1 for r in results if r.status in ("fail", "error"))
    skipped = sum(1 for r in results if r.status == "skip")

    parts: list[str] = []
    if passed:
        parts.append(green(f"{passed} passed"))
    if failed:
        parts.append(red(f"{failed} failed"))
    if skipped:
        parts.append(dim(f"{skipped} skipped"))

    summary = ", ".join(parts) if parts else "no obligations"
    timing = dim(f"({total_s:.1f}s total)")
    location = dim(f"JSON reports in {out_dir}/")
    print(f"\n{summary}  {timing}  {location}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="evidence", description="Run evidence checks on a module.")
    p.add_argument("module", help="Python module to import (e.g. mypkg.mymodule)")
    p.add_argument("--out", default=".evidence", help="Output directory for JSON reports")
    p.add_argument("--max-list-size", type=int, default=20, help="Max size for generated lists/collections")
    p.add_argument("--smoke-max-list-size", type=int, default=5, help="Max size for smoke-test generation")
    p.add_argument("-v", "--verbose", action="store_true", help="Show counterexample details and timing")
    p.add_argument("-q", "--quiet", action="store_true", help="Only print summary and exit code")
    p.add_argument("--json", action="store_true", help="Output results as JSON array to stdout")
    p.add_argument("--no-color", action="store_true", help="Disable ANSI colors")
    p.add_argument("--coverage", action="store_true", help="Measure line/branch coverage per function")
    p.add_argument("--mutate", action="store_true", help="Run mutation testing and report mutation score")
    p.add_argument("--prove", action="store_true", help="Attempt symbolic verification via CrossHair/Z3")
    p.add_argument("--suggest", action="store_true", help="Use LLM to suggest postconditions and specs")
    p.add_argument("--infer", action="store_true", help="Infer structural properties from function behavior")
    args = p.parse_args(argv)

    if args.no_color:
        force_color(False)

    # --json implies quiet for human text
    json_mode = args.json

    def on_result(r: ObligationResult) -> None:
        if not json_mode and not args.quiet:
            _print_result_line(r, verbose=args.verbose)

    try:
        importlib.import_module(args.module)
    except ImportError as e:
        print(f"error: could not import module '{args.module}': {e}", file=sys.stderr)
        return 1

    t_start = time.monotonic()
    results, _trust = check_module(
        args.module,
        out_dir=args.out,
        max_list_size=args.max_list_size,
        smoke_max_list_size=args.smoke_max_list_size,
        on_result=on_result,
        coverage=args.coverage,
        mutate=args.mutate,
        prove=args.prove,
        suggest=args.suggest,
        infer=args.infer,
    )
    total_s = time.monotonic() - t_start

    if not results:
        if json_mode:
            print("[]")
        else:
            msg = f"warning: no @requires/@ensures/@against decorated functions found in '{args.module}'"
            print(msg, file=sys.stderr)
        return 0

    if json_mode:
        print(json.dumps([r.to_json() for r in results], indent=2, default=str))
        return 1 if any(r.status in ("fail", "error") for r in results) else 0

    if not args.quiet:
        pass  # lines already printed via on_result

    _print_summary(results, total_s, args.out)

    if any(r.status in ("fail", "error") for r in results):
        return 1
    return 0
