"""Tests for Feature 6: LLM-assisted spec mining."""

from __future__ import annotations

import json

import pytest

from evidence._suggest import (
    Suggestion,
    _build_prompt,
    _parse_suggestions,
    validate_suggestion,
)


# ---------------------------------------------------------------------------
# Suggestion
# ---------------------------------------------------------------------------

class TestSuggestion:
    def test_fields(self):
        s = Suggestion("ensures", "lambda x, result: result > 0", "positive output", 0.9)
        assert s.kind == "ensures"
        assert s.code == "lambda x, result: result > 0"
        assert s.description == "positive output"
        assert s.confidence == 0.9

    def test_to_dict(self):
        s = Suggestion("spec", "def spec(x): return x", "identity", 0.5)
        d = s.to_dict()
        assert d["kind"] == "spec"
        assert d["code"] == "def spec(x): return x"
        assert d["confidence"] == 0.5

    def test_repr(self):
        s = Suggestion("ensures", "code", "desc", 0.8)
        r = repr(s)
        assert "ensures" in r
        assert "desc" in r
        assert "0.8" in r


# ---------------------------------------------------------------------------
# _build_prompt
# ---------------------------------------------------------------------------

class TestBuildPrompt:
    def test_includes_source(self):
        prompt = _build_prompt("def f(x):\n    return x")
        assert "def f(x):" in prompt
        assert "return x" in prompt

    def test_includes_existing_contracts(self):
        prompt = _build_prompt("def f(x): pass", existing_contracts={"requires": 2})
        assert "requires" in prompt
        assert "2" in prompt

    def test_includes_mutation_score(self):
        prompt = _build_prompt("def f(x): pass", mutation_score=75.0)
        assert "75.0%" in prompt
        assert "mutation" in prompt.lower()


# ---------------------------------------------------------------------------
# _parse_suggestions
# ---------------------------------------------------------------------------

class TestParseSuggestions:
    def test_valid_json_array(self):
        text = json.dumps([
            {"kind": "ensures", "code": "lambda x, result: result > 0", "description": "positive", "confidence": 0.9},
        ])
        suggestions = _parse_suggestions(text)
        assert len(suggestions) == 1
        assert suggestions[0].kind == "ensures"
        assert suggestions[0].confidence == 0.9

    def test_markdown_code_block(self):
        text = "```json\n" + json.dumps([
            {"kind": "ensures", "code": "lambda x: True", "description": "trivial"},
        ]) + "\n```"
        suggestions = _parse_suggestions(text)
        assert len(suggestions) == 1

    def test_json_embedded_in_text(self):
        text = 'Here are my suggestions: [{"kind": "ensures", "code": "lambda x: True", "description": "test"}] end'
        suggestions = _parse_suggestions(text)
        assert len(suggestions) == 1

    def test_invalid_json(self):
        suggestions = _parse_suggestions("this is not json at all")
        assert suggestions == []

    def test_non_list_json(self):
        suggestions = _parse_suggestions('{"key": "value"}')
        assert suggestions == []

    def test_missing_required_fields(self):
        text = json.dumps([{"description": "no kind or code"}])
        suggestions = _parse_suggestions(text)
        assert suggestions == []

    def test_default_confidence(self):
        text = json.dumps([{"kind": "ensures", "code": "lambda x: True", "description": "test"}])
        suggestions = _parse_suggestions(text)
        assert len(suggestions) == 1
        assert suggestions[0].confidence == 0.0


# ---------------------------------------------------------------------------
# validate_suggestion
# ---------------------------------------------------------------------------

class TestValidateSuggestion:
    def test_valid_ensures_suggestion(self):
        from evidence._decorators import requires

        @requires(lambda x: x >= 0)
        def f(x: int) -> int:
            return x * 2

        s = Suggestion("ensures", "lambda x, result: result >= 0", "non-negative output")
        result = validate_suggestion(s, f)
        assert result is True

    def test_invalid_ensures_suggestion(self):
        def f(x: int) -> int:
            return x * 2

        # This will fail to compile as a predicate (bad syntax)
        s = Suggestion("ensures", "not a valid lambda!!!", "broken")
        result = validate_suggestion(s, f)
        assert result is False

    def test_valid_spec_suggestion(self):
        def f(x: int) -> int:
            return x + x

        s = Suggestion("spec", "def spec_fn(x: int) -> int:\n    return x * 2", "double")
        result = validate_suggestion(s, f)
        assert result is True
