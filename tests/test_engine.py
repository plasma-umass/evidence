"""Tests for the check_module engine and ObligationResult."""

from __future__ import annotations

import json
import os
import sys
import types

import pytest

from evidence._engine import ObligationResult, _collect_functions, check_module


# ---------------------------------------------------------------------------
# ObligationResult
# ---------------------------------------------------------------------------

class TestObligationResult:
    def test_to_json(self):
        r = ObligationResult("my_fn", "smoke", "pass", {"key": "val"}, duration_s=1.2345)
        j = r.to_json()
        assert j["function"] == "my_fn"
        assert j["obligation"] == "smoke"
        assert j["status"] == "pass"
        assert j["details"] == {"key": "val"}
        assert j["duration_s"] == 1.234  # rounded to 3 decimals

    def test_default_duration(self):
        r = ObligationResult("f", "o", "pass", {})
        assert r.duration_s == 0.0


# ---------------------------------------------------------------------------
# _collect_functions
# ---------------------------------------------------------------------------

class TestCollectFunctions:
    def test_finds_decorated_functions(self):
        from evidence._bundle import _bundle
        mod = types.ModuleType("dummy_mod")
        def f(x: int) -> int:
            return x
        _bundle(f)  # attach bundle metadata
        mod.f = f
        mod.not_decorated = lambda x: x
        fns = _collect_functions(mod)
        assert any(fn is f for fn in fns)

    def test_ignores_non_callables(self):
        mod = types.ModuleType("dummy_mod")
        mod.x = 42
        mod.y = "hello"
        fns = _collect_functions(mod)
        assert fns == []


# ---------------------------------------------------------------------------
# check_module (integration)
# ---------------------------------------------------------------------------

class TestCheckModule:
    def test_example_sort(self, tmp_out):
        results, trust = check_module("example_sort", out_dir=tmp_out)
        assert len(results) > 0
        assert trust["module"] == "example_sort"
        # The buggy sort should produce at least one failure
        statuses = [r.status for r in results]
        assert "fail" in statuses

    def test_example_runs(self, tmp_out):
        results, trust = check_module("example_runs", out_dir=tmp_out)
        assert len(results) > 0
        statuses = [r.status for r in results]
        assert "fail" in statuses

    def test_example_intervals(self, tmp_out):
        results, trust = check_module("example_intervals", out_dir=tmp_out)
        assert len(results) > 0

    def test_writes_json_files(self, tmp_out):
        results, trust = check_module("example_sort", out_dir=tmp_out)
        obligations_path = os.path.join(tmp_out, "example_sort.obligations.json")
        trust_path = os.path.join(tmp_out, "example_sort.trust.json")
        assert os.path.exists(obligations_path)
        assert os.path.exists(trust_path)

        with open(obligations_path) as f:
            data = json.load(f)
        assert isinstance(data, list)
        assert len(data) == len(results)

    def test_on_result_callback(self, tmp_out):
        collected = []
        results, _ = check_module("example_sort", out_dir=tmp_out, on_result=collected.append)
        assert len(collected) == len(results)

    def test_shrunk_counterexample_present(self, tmp_out):
        """Feature 1: Shrunk counterexamples should appear in failure details."""
        results, _ = check_module("example_sort", out_dir=tmp_out)
        failures = [r for r in results if r.status == "fail" and r.obligation == "equiv_to_spec"]
        for f in failures:
            ce = f.details.get("counterexample")
            if ce is not None:
                assert "kwargs" in ce
                # Shrunk CE should have small-ish input
                assert isinstance(ce["kwargs"], dict)

    def test_smoke_test_pass(self, tmp_out):
        results, _ = check_module("example_sort", out_dir=tmp_out)
        smoke_results = [r for r in results if r.obligation == "contracts_smoke"]
        assert len(smoke_results) > 0


# ---------------------------------------------------------------------------
# check_module with optional features
# ---------------------------------------------------------------------------

class TestCheckModuleFeatures:
    def test_coverage_flag(self, tmp_out):
        """Feature 3: Coverage collection."""
        results, _ = check_module("example_sort", out_dir=tmp_out, coverage=True)
        cov_results = [r for r in results if r.obligation == "coverage"]
        # Coverage should be available (coverage.py is a dev dep)
        if cov_results:
            for cr in cov_results:
                assert "lines_total" in cr.details
                assert "line_coverage_pct" in cr.details

    def test_mutate_flag(self, tmp_out):
        """Feature 4: Mutation testing."""
        results, _ = check_module("example_sort", out_dir=tmp_out, mutate=True)
        mut_results = [r for r in results if r.obligation == "mutation_score"]
        assert len(mut_results) > 0
        for mr in mut_results:
            assert "total_mutants" in mr.details
            assert "killed" in mr.details
            assert "mutation_score" in mr.details

    def test_infer_flag(self, tmp_out):
        """Feature 7: Spec inference."""
        results, _ = check_module("example_sort", out_dir=tmp_out, infer=True)
        infer_results = [r for r in results if r.obligation == "inferred_properties"]
        assert len(infer_results) > 0
        for ir in infer_results:
            assert "properties_found" in ir.details
            assert "holding" in ir.details

    def test_prove_flag_graceful(self, tmp_out):
        """Feature 5: Symbolic verification (may be unavailable)."""
        results, _ = check_module("example_sort", out_dir=tmp_out, prove=True)
        proof_results = [r for r in results if r.obligation == "symbolic_proof"]
        # Should produce results even if crosshair not installed
        assert len(proof_results) > 0
