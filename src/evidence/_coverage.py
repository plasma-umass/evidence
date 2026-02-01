"""Coverage measurement for Evidence function checks.

Wraps test execution with coverage.py to measure line/branch coverage
per function. Isolates coverage to the function's source lines via
inspect.getsourcelines.

Requires: pip install evidence[coverage]  (coverage>=7.0)
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any


def _get_function_lines(fn: Callable[..., Any]) -> tuple[str, int, int] | None:
    """Get the source file and line range for a function.

    Returns (filepath, start_line, end_line) or None if unavailable.
    """
    try:
        source_lines, start_line = inspect.getsourcelines(fn)
        filepath = inspect.getfile(fn)
        end_line = start_line + len(source_lines) - 1
        return filepath, start_line, end_line
    except (OSError, TypeError):
        return None


class CoverageCollector:
    """Collects coverage data during Evidence test execution.

    Usage:
        collector = CoverageCollector()
        collector.start()
        # ... run tests ...
        collector.stop()
        report = collector.report_for_function(fn)
    """

    def __init__(self) -> None:
        try:
            import coverage as cov_mod
            self._cov: Any = cov_mod.Coverage(branch=True)
            self._available = True
        except ImportError:
            self._cov = None
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    def start(self) -> None:
        if self._cov is not None:
            self._cov.start()

    def stop(self) -> None:
        if self._cov is not None:
            self._cov.stop()

    def report_for_function(self, fn: Callable[..., Any]) -> dict[str, Any] | None:
        """Generate coverage report for a specific function.

        Returns a dict with:
            - file: source file path
            - start_line / end_line: function location
            - lines_total: total executable lines in function
            - lines_covered: lines executed
            - line_coverage_pct: percentage
            - branches_total: total branches
            - branches_covered: branches taken
            - branch_coverage_pct: percentage
            - missing_lines: list of uncovered line numbers

        Returns None if coverage data unavailable.
        """
        if self._cov is None:
            return None

        loc = _get_function_lines(fn)
        if loc is None:
            return None

        filepath, start_line, end_line = loc

        try:
            analysis = self._cov.analysis2(filepath)
        except Exception:
            return None

        # analysis2 returns: (filename, executable, excluded, missing, formatted_missing)
        executable_lines: list[int] = list(analysis[1])
        missing_lines: list[int] = list(analysis[3])

        # Filter to function's line range
        fn_executable = [ln for ln in executable_lines if start_line <= ln <= end_line]
        fn_missing = [ln for ln in missing_lines if start_line <= ln <= end_line]
        fn_covered = [ln for ln in fn_executable if ln not in set(fn_missing)]

        lines_total = len(fn_executable)
        lines_covered = len(fn_covered)
        line_pct = (lines_covered / lines_total * 100) if lines_total > 0 else 100.0

        # Branch coverage via arc analysis
        branches_total = 0
        branches_covered = 0
        try:
            branch_data = self._cov._analyze(filepath)
            if hasattr(branch_data, 'arc_possibilities') and hasattr(branch_data, 'arcs_executed'):
                all_arcs: list[tuple[int, int]] = list(branch_data.arc_possibilities())
                exec_arcs: list[tuple[int, int]] = list(branch_data.arcs_executed())
                fn_arcs = [(a, b) for a, b in all_arcs if start_line <= a <= end_line]
                fn_exec_arcs = [(a, b) for a, b in exec_arcs if start_line <= a <= end_line]
                branches_total = len(fn_arcs)
                branches_covered = len(fn_exec_arcs)
        except Exception:
            pass

        branch_pct = (branches_covered / branches_total * 100) if branches_total > 0 else 100.0

        return {
            "file": filepath,
            "start_line": start_line,
            "end_line": end_line,
            "lines_total": lines_total,
            "lines_covered": lines_covered,
            "line_coverage_pct": round(line_pct, 1),
            "branches_total": branches_total,
            "branches_covered": branches_covered,
            "branch_coverage_pct": round(branch_pct, 1),
            "missing_lines": fn_missing,
        }
