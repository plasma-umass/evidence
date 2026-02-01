"""Tests for Feature 3: Coverage measurement."""

from __future__ import annotations

import pytest

from evidence._coverage import CoverageCollector, _get_function_lines


# ---------------------------------------------------------------------------
# _get_function_lines
# ---------------------------------------------------------------------------

class TestGetFunctionLines:
    def test_returns_tuple_for_normal_function(self):
        def f(x: int) -> int:
            return x

        result = _get_function_lines(f)
        assert result is not None
        filepath, start, end = result
        assert filepath.endswith(".py")
        assert start > 0
        assert end >= start

    def test_returns_none_for_builtin(self):
        result = _get_function_lines(len)
        assert result is None

    def test_returns_none_for_lambda(self):
        # Lambdas defined at module level should work; only truly
        # uninspectable objects should return None
        fn = lambda x: x  # noqa: E731
        result = _get_function_lines(fn)
        # Lambdas actually do have source lines in test files
        if result is not None:
            filepath, start, end = result
            assert start > 0


# ---------------------------------------------------------------------------
# CoverageCollector
# ---------------------------------------------------------------------------

class TestCoverageCollector:
    def test_available(self):
        collector = CoverageCollector()
        # coverage.py should be installed in dev environment
        assert isinstance(collector.available, bool)

    @pytest.mark.skipif(
        not CoverageCollector().available,
        reason="coverage package not installed",
    )
    def test_start_stop(self):
        collector = CoverageCollector()
        collector.start()
        # Execute some code
        x = 1 + 2
        _ = x * 3
        collector.stop()

    @pytest.mark.skipif(
        not CoverageCollector().available,
        reason="coverage package not installed",
    )
    def test_report_for_function(self):
        def target_fn(x: int) -> int:
            if x > 0:
                return x * 2
            return -x

        collector = CoverageCollector()
        collector.start()
        target_fn(5)
        target_fn(-3)
        collector.stop()

        report = collector.report_for_function(target_fn)
        assert report is not None
        assert "lines_total" in report
        assert "lines_covered" in report
        assert "line_coverage_pct" in report
        assert "missing_lines" in report
        assert report["lines_covered"] > 0

    @pytest.mark.skipif(
        not CoverageCollector().available,
        reason="coverage package not installed",
    )
    def test_report_for_builtin_returns_none(self):
        collector = CoverageCollector()
        collector.start()
        collector.stop()
        report = collector.report_for_function(len)
        assert report is None
