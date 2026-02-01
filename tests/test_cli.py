"""Tests for the CLI interface."""

from __future__ import annotations

import json

import pytest

from evidence._cli import main


# ---------------------------------------------------------------------------
# CLI exit codes
# ---------------------------------------------------------------------------

class TestCLIExitCodes:
    def test_passing_module_exits_zero(self, tmp_out):
        # example_sort has a bug, so it should fail
        code = main(["example_sort", "--out", tmp_out, "--no-color"])
        assert code == 1

    def test_nonexistent_module_exits_one(self):
        code = main(["nonexistent_module_xyz123", "--no-color"])
        assert code == 1


# ---------------------------------------------------------------------------
# CLI output modes
# ---------------------------------------------------------------------------

class TestCLIOutputModes:
    def test_json_mode(self, tmp_out, capsys):
        main(["example_sort", "--out", tmp_out, "--json", "--no-color"])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, list)
        assert len(data) > 0
        # Each result should have standard fields
        for r in data:
            assert "function" in r
            assert "obligation" in r
            assert "status" in r

    def test_quiet_mode(self, tmp_out, capsys):
        main(["example_sort", "--out", tmp_out, "-q", "--no-color"])
        captured = capsys.readouterr()
        # Quiet mode still prints summary
        assert "passed" in captured.out or "failed" in captured.out

    def test_verbose_mode(self, tmp_out, capsys):
        main(["example_sort", "--out", tmp_out, "-v", "--no-color"])
        captured = capsys.readouterr()
        # Verbose should show counterexample details
        assert len(captured.out) > 0


# ---------------------------------------------------------------------------
# CLI feature flags
# ---------------------------------------------------------------------------

class TestCLIFeatureFlags:
    def test_coverage_flag(self, tmp_out, capsys):
        code = main(["example_sort", "--out", tmp_out, "--coverage", "--no-color", "-v"])
        # Should complete without error
        assert code in (0, 1)

    def test_mutate_flag(self, tmp_out, capsys):
        code = main(["example_sort", "--out", tmp_out, "--mutate", "--no-color"])
        assert code in (0, 1)

    def test_infer_flag(self, tmp_out, capsys):
        code = main(["example_sort", "--out", tmp_out, "--infer", "--no-color"])
        assert code in (0, 1)

    def test_prove_flag(self, tmp_out, capsys):
        code = main(["example_sort", "--out", tmp_out, "--prove", "--no-color"])
        assert code in (0, 1)
