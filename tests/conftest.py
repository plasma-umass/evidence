"""Shared fixtures for Evidence tests."""

from __future__ import annotations

import os
import sys
import tempfile

import pytest


@pytest.fixture
def tmp_out(tmp_path):
    """Temporary output directory for JSON reports."""
    return str(tmp_path / ".evidence")


@pytest.fixture(autouse=True)
def _add_examples_to_path():
    """Ensure examples/ is importable."""
    examples_dir = os.path.join(os.path.dirname(__file__), "..", "examples")
    examples_dir = os.path.abspath(examples_dir)
    if examples_dir not in sys.path:
        sys.path.insert(0, examples_dir)
    yield
    if examples_dir in sys.path:
        sys.path.remove(examples_dir)
